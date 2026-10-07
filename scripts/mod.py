#!/usr/bin/env python3
"""Version-pinned Codex renderer patch. Does not alter settings or credentials."""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import tempfile
import integrity
import signing

ROOT = Path(__file__).resolve().parents[1]
APP = Path('/Applications/ChatGPT.app')
VERSION = '26.930.61225'
BASELINE = '88b8cce6f627771bf341f5a6bb464ad220749b0d442d44f618d7741c2de7318b'
PRIMARY = 'webview/assets/app-primary-1a9a7a89414a.js'
SHARED = 'webview/assets/app-shared-122c56612a72.js'
TURN = 'webview/assets/local-conversation-turn-1432d9d2675d.js'
INITIAL = 'webview/assets/app-initial-69cd8dbddec5.js'
ASAR = Path('Contents/Resources/app.asar')
PLIST = Path('Contents/Info.plist')
SAFE = ROOT / 'Safe Build' / 'ChatGPT.app'
NEW = ROOT / 'New Build' / 'ChatGPT.app'
PROTECTED = ROOT / 'Protected Recovery' / 'ChatGPT.app'
PROTECTED_RECEIPT = ROOT / 'local-recovery.json'
RECEIPT = ROOT / 'local-build.json'
ACCEPT_COMMAND = 'python3 scripts/setup.py --accept --confirm-rendered-ui --confirm-quit-reopen'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda: file.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save_receipt(receipt):
    save_json(RECEIPT, receipt)


def save_json(path, receipt):
    temporary = path.with_suffix('.json.pending')
    with temporary.open('w') as file:
        file.write(json.dumps(receipt, indent=2) + '\n')
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, path)


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        with self.path.open('rb') as file:
            prefix, header_size, payload_size, json_size = struct.unpack('<IIII', file.read(16))
            if prefix != 4 or payload_size + 4 != header_size or json_size > payload_size - 4:
                raise ValueError('Unsupported ASAR header')
            self.header_bytes = file.read(json_size)
        self.tree = json.loads(self.header_bytes)
        self.base = 8 + header_size

    def node(self, path):
        node = self.tree
        for part in path.split('/'):
            node = node['files'][part]
        return node

    def read(self, path):
        node = self.node(path)
        if 'offset' not in node:
            raise ValueError('Target is not a packed regular file: ' + path)
        with self.path.open('rb') as file:
            file.seek(self.base + int(node['offset']))
            data = file.read(node['size'])
        if len(data) != node['size']:
            raise ValueError('Truncated ASAR entry: ' + path)
        expected = node.get('integrity', {}).get('hash')
        if expected and hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('ASAR entry integrity mismatch: ' + path)
        return data

    @staticmethod
    def entries(tree, prefix=''):
        for name, node in tree.get('files', {}).items():
            path = prefix + name
            if 'files' in node:
                yield from Archive.entries(node, path + '/')
            else:
                yield path, node

    def write(self, destination, replacements):
        tree = copy.deepcopy(self.tree)
        for path in replacements:
            parts = path.split('/')
            node = tree
            for part in parts[:-1]:
                node = node.setdefault('files', {}).setdefault(part, {'files': {}})
            node['files'].setdefault(parts[-1], {})
        packed = [(path, node) for path, node in self.entries(tree) if 'offset' in node or path in replacements]
        packed.sort(key=lambda entry: int(entry[1].get('offset', '999999999999')))
        offset = 0
        for path, node in packed:
            if path in replacements:
                data = replacements[path]
                block_size = node.get('integrity', {}).get('blockSize', 4194304)
                node['size'] = len(data)
                node['integrity'] = {
                    'algorithm': 'SHA256', 'hash': hashlib.sha256(data).hexdigest(), 'blockSize': block_size,
                    'blocks': [hashlib.sha256(data[i:i + block_size]).hexdigest() for i in range(0, len(data), block_size)]}
            node['offset'] = str(offset)
            offset += node['size']
        header = json.dumps(tree, separators=(',', ':'), ensure_ascii=False).encode()
        padding = b'\0' * ((-len(header)) % 4)
        header_size = 8 + len(header) + len(padding)
        temporary = Path(str(destination) + '.candidate')
        try:
            with temporary.open('wb') as output, self.path.open('rb') as source:
                output.write(struct.pack('<IIII', 4, header_size, header_size - 4, len(header)))
                output.write(header + padding)
                for path, node in packed:
                    if path in replacements:
                        output.write(replacements[path])
                    else:
                        original = self.node(path)
                        source.seek(self.base + int(original['offset']))
                        remaining = original['size']
                        while remaining:
                            chunk = source.read(min(remaining, 1048576))
                            if not chunk:
                                raise ValueError('Unexpected end of original archive')
                            output.write(chunk)
                            remaining -= len(chunk)
                output.flush(); os.fsync(output.fileno())
            candidate = Archive(temporary)
            for path, data in replacements.items():
                if candidate.read(path) != data:
                    raise ValueError('Patched ASAR entry readback failed')
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return hashlib.sha256(header).hexdigest()


def unique_replace(source, anchor, replacement, label):
    count = source.count(anchor)
    if count != 1:
        raise ValueError(f'{label}: expected one source anchor, found {count}; refusing this version')
    return source.replace(anchor, replacement, 1)


def patch_sources(archive):
    shared = archive.read(SHARED).decode()
    primary = archive.read(PRIMARY).decode()
    anchor = 'Oe=(0,UR.jsxs)(pR.Item,{children:[se,De]})'
    primary = unique_replace(primary, anchor,
        'Oe=(0,UR.jsxs)(pR.Item,{"data-cu-native-goal":true,children:[se,De]})',
        'native Goal width reference marker')
    # Read-only notification observer runs before normal reduction. Observer
    # failure cannot interrupt message handling; notification params aren't logged.
    anchor = 'onNotification(e,t,n=null,r,i=Date.now()){'
    shared = unique_replace(shared, anchor, anchor +
        'try{__cuObserve(this.hostId,e,t)}catch{}', 'notification observer')
    shared = 'import{observeMetric as __cuObserve}from"./codex-usage-speed.mjs";\n' + shared
    anchor = 'className:Lr(`flex w-full flex-col gap-2`,Ne&&`relative`),onPaste:Ri?Dl:void 0'
    primary = unique_replace(primary, anchor,
        '"data-cu-composer-stack":true,' + anchor, 'composer stack scope')
    anchor = '(0,gZ.jsx)(zt,{initial:!1,children:Jl&&c==null?'
    primary = unique_replace(primary, anchor,
        'jt!==`cloud`&&!Je?(0,gZ.jsx)(__cuHost,'
        '{conversationId:Ye,hostId:st.hostId,rateLimit:en}):null,' + anchor,
        'usage above intact native Goal and composer controls')
    host = '''
let __cuBar;
function __cuHost({conversationId,hostId,rateLimit,selectedModel}){
  __cuBar??=__cuCreateBar(Hf(),X());
  const placementRef=Hf().useRef(null);
  __cuLayout(Hf(),placementRef);
  const usage=Y(Nf,conversationId);
  const core=gFe(rateLimit).filter(entry=>entry.limitName==null);
  return X().jsx(`div`,{ref:placementRef,"data-cu-placement":true,children:X().jsx(__cuBar,{conversationId,hostId,usage,entries:core})});
}
'''
    primary = ('import{useNativeLayout as __cuLayout}from"./codex-usage-native-layout.mjs";\n'
               'import{createBar as __cuCreateBar}from"./codex-usage-bar.mjs";\n'
               'import{weeklyWindow as __cuWeekly}from"./codex-usage-metrics.mjs";\n' + primary + host)
    turn = archive.read(TURN).decode()
    start = turn.index('function Ho(e){')
    end = turn.index('var Uo,Wo,Go,Ko,qo,Jo;', start)
    turn = unique_replace(turn, turn[start:end], '''function Ho(e){
      return __cuFixed(e,{React:__cuLoadReact(),jsx:Go,DOM:Wo,anchor:Zn,
        useSelector:U,diffAtom:Kt,cwdAtom:Pt,extraAtom:Ln,summarize:diff=>ro(Or(diff)),
        Diff:Yi,Motion:H,Presence:x,Todo:ta,Layout:ao,fade:qo,layout:Jo,delay:Ko});
    }
    ''', 'native fixed-content composition')
    turn = ('import{cfn as __cuLoadReact}from"./app-shared-122c56612a72.js";\n'
            'import{renderNativeFixed as __cuFixed}from"./codex-usage-native-fixed.mjs";\n' + turn)
    initial = archive.read(INITIAL).decode()
    anchor = '(Rs.div,{"aria-hidden":u,className:f,inert:p,initial:m,animate:h,exit:g,transition:_,children:b})'
    initial = unique_replace(initial, anchor, anchor.replace('{"aria-hidden":u', '{"data-cu-native-utility":true,"aria-hidden":u'), 'native utility flow marker')
    # New UI modules contain only our original source, never redistributed app code.
    modules = {}
    for name in ['bar', 'metrics', 'speed', 'diff-slot', 'native-fixed', 'native-layout', 'responsive']:
        source = (ROOT / 'src' / (name + '.mjs')).read_text()
        source = source.replace("'./metrics.mjs'", "'./codex-usage-metrics.mjs'")
        source = source.replace("'./speed.mjs'", "'./codex-usage-speed.mjs'")
        source = source.replace("'./diff-slot.mjs'", "'./codex-usage-diff-slot.mjs'")
        source = source.replace("'./responsive.mjs'", "'./codex-usage-responsive.mjs'")
        modules['webview/assets/codex-usage-' + name + '.mjs'] = source.encode()
    return {SHARED: shared.encode(), PRIMARY: primary.encode(), TURN: turn.encode(), INITIAL: initial.encode(), **modules}


def app_version(app):
    return plistlib.loads((app / PLIST).read_bytes())['CFBundleShortVersionString']


def copy_app(source, target):
    if target.exists():
        raise ValueError('Build slot already exists: ' + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['/usr/bin/ditto', str(source), str(target)], check=True,timeout=300)


def verify_unrelated(original, candidate, changed):
    old_entries = dict(original.entries(original.tree))
    new_entries = dict(candidate.entries(candidate.tree))
    if set(old_entries) - set(new_entries):
        raise ValueError('Candidate removed original archive entries')
    for path, node in old_entries.items():
        if path in changed:
            continue
        other = new_entries[path]
        left = {key: value for key, value in node.items() if key != 'offset'}
        right = {key: value for key, value in other.items() if key != 'offset'}
        if left != right:
            raise ValueError('Unrelated archive metadata changed: ' + path)
        if 'offset' in node and original.read(path) != candidate.read(path):
            raise ValueError('Unrelated archive data changed: ' + path)


def syntax_check(replacements):
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js is required to validate the patched modules')
    with tempfile.TemporaryDirectory(prefix='codex-usage-syntax-') as directory:
        for name, data in replacements.items():
            target = Path(directory) / (Path(name).stem + '.mjs')
            target.write_bytes(data)
            subprocess.run([node, '--check', str(target)], check=True, capture_output=True,timeout=30)


def build_source_fingerprint(receipt, installed_hash):
    """Identify the installed source without treating process health as acceptance."""
    if receipt is None:
        return None
    state = receipt.get('state')
    if state == 'recovered_previous_mod' and receipt.get('restored_from_protected'):
        recovery = receipt['recovery']
        if installed_hash != recovery['sha256']:
            raise ValueError('Installed app does not match the protected recovery receipt.')
        return recovery['fingerprint']
    source = {'candidate_verified': 'preinstall', 'recovered_previous_mod': 'preinstall',
              'installed_accepted': 'candidate', 'installed_pending_live_check': 'candidate'}.get(state)
    if source is None or receipt.get('version') != VERSION:
        raise ValueError('Build receipt requires review before reusing the recovery slot.')
    if installed_hash != receipt[source + '_sha256']:
        raise ValueError('Installed app does not match the recorded transaction state; preserve the recovery slot and review.')
    return receipt[source + '_fingerprint']


def verify_recovery_bundle(app, recovery):
    if recovery.get('version') != VERSION or recovery.get('provenance') != 'retained_preinstall':
        raise ValueError('Unrecognized protected recovery provenance; preserve it and review.')
    if sha(app / ASAR) != recovery['sha256']:
        raise ValueError('Protected recovery archive changed; refusing replacement.')
    integrity.guard(app, recovery['fingerprint'])
    signing.verify_source(app, recovery['entitlements'], recovery['signing_kind'])


def recovery_paths(recovery):
    slot = recovery.get('slot', 'primary')
    if slot == 'primary':
        return PROTECTED, PROTECTED_RECEIPT
    fingerprint = recovery['fingerprint']
    if slot != 'versioned' or len(fingerprint) != 64 or any(char not in '0123456789abcdef' for char in fingerprint):
        raise ValueError('Unknown protected recovery slot; preserve it and review.')
    directory = PROTECTED.parent / 'Verified Builds' / fingerprint
    return directory / 'ChatGPT.app', directory / 'local-recovery.json'


def checked_recovery(recovery):
    app, record = recovery_paths(recovery)
    if not app.exists() or not record.exists():
        raise ValueError('Incomplete or unrecorded Protected Recovery; preserve it and review.')
    if json.loads(record.read_text()) != recovery:
        raise ValueError('Protected recovery provenance differs from the build receipt.')
    verify_recovery_bundle(app, recovery)
    return app


def same_recovery_source(left, right):
    return all(left.get(key) == right.get(key) for key in
               ('version', 'provenance', 'sha256', 'fingerprint', 'entitlements', 'signing_kind'))


def preserve_recovery(receipt):
    """Keep the original verified predecessor through any number of pending updates."""
    if receipt.get('recovery') is not None:
        recovery = receipt['recovery']
        checked_recovery(recovery)
        return recovery
    recovery = {
        'version': VERSION, 'provenance': 'retained_preinstall',
        'source_candidate_sha256': receipt['candidate_sha256'],
        'sha256': receipt['preinstall_sha256'], 'fingerprint': receipt['preinstall_fingerprint'],
        'entitlements': receipt['preinstall_entitlements'],
        'signing_kind': receipt.get('preinstall_signing_kind', 'local'),
    }
    if PROTECTED.exists() or PROTECTED_RECEIPT.exists():
        if not PROTECTED.exists() or not PROTECTED_RECEIPT.exists():
            raise ValueError('Incomplete or unrecorded Protected Recovery; preserve it and review.')
        previous = json.loads(PROTECTED_RECEIPT.read_text())
        if recovery_paths(previous)[0] != PROTECTED:
            raise ValueError('Unexpected primary recovery provenance; preserve it and review.')
        checked_recovery(previous)
        if same_recovery_source(previous, recovery):
            return previous
        # A later accepted build starts a new recovery lineage. Keep the older
        # verified copy and retain this lineage in its own immutable slot.
        recovery['slot'] = 'versioned'
    target, record = recovery_paths(recovery)
    if target.exists() or record.exists():
        if not target.exists() or not record.exists():
            raise ValueError('Incomplete or unrecorded Protected Recovery; preserve it and review.')
        existing = json.loads(record.read_text())
        if not same_recovery_source(existing, recovery) or recovery_paths(existing)[0] != target:
            raise ValueError('Existing protected slot belongs to another recovery source.')
        checked_recovery(existing)
        return existing
    verify_recovery_bundle(NEW, recovery)
    copy_app(NEW, target)
    verify_recovery_bundle(target, recovery)
    save_json(record, recovery)
    return recovery


def accept_installation(confirm_rendered_ui=False, confirm_quit_reopen=False):
    """Record explicit user evidence; process health never implies acceptance."""
    if confirm_rendered_ui is not True or confirm_quit_reopen is not True:
        raise ValueError('Acceptance requires both your rendered-UI and normal quit/reopen confirmations. Run only after verifying both: ' + ACCEPT_COMMAND)
    receipt = json.loads(RECEIPT.read_text())
    if receipt.get('state') != 'installed_pending_live_check' or receipt.get('version') != VERSION:
        raise ValueError('No pending installed candidate is available for acceptance.')
    if sha(APP / ASAR) != receipt['candidate_sha256'] or sha(NEW / ASAR) != receipt['preinstall_sha256']:
        raise ValueError('Installed candidate or retained recovery app changed; acceptance refused.')
    integrity.guard(APP, receipt['candidate_fingerprint'])
    signing.verify(APP, receipt['candidate_entitlements'])
    integrity.guard(NEW, receipt['preinstall_fingerprint'])
    signing.verify_source(NEW, receipt['preinstall_entitlements'], receipt.get('preinstall_signing_kind', 'local'))
    if receipt.get('recovery'):
        checked_recovery(receipt['recovery'])
    from startup_health import mapped_build_matches
    instances = codex_instances()
    expected = str(APP / 'Contents/MacOS/ChatGPT')
    if len(instances) != 1 or instances[0]['executable'] != expected or not mapped_build_matches(instances[0]['pid'], APP):
        raise ValueError('The exact installed candidate must be the only running Codex app before acceptance.')
    receipt['state'] = 'installed_accepted'
    receipt['acceptance'] = {
        'method': 'explicit_user_attestation',
        'rendered_ui': True, 'normal_quit_reopen': True,
        'candidate_sha256': receipt['candidate_sha256'],
        'candidate_fingerprint': receipt['candidate_fingerprint'],
        'confirmed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    save_receipt(receipt)
    print('Your UI and normal quit/reopen acceptance is recorded for the verified installed candidate.')


def build(replace_candidate=False):
    installed_hash = sha(APP / ASAR)
    previous = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else None
    expected_source = build_source_fingerprint(previous, installed_hash)
    known_hashes = {BASELINE}
    if previous and previous.get('version') == VERSION:
        known_hashes.update([previous['candidate_sha256'],previous.get('preinstall_sha256')])
        if previous.get('recovery'):known_hashes.add(previous['recovery']['sha256'])
    if app_version(APP) != VERSION or installed_hash not in known_hashes:
        raise ValueError('Installed app differs from the inspected baseline; review before patching')
    working = integrity.guard(APP, expected_source)
    source_kind = 'vendor' if installed_hash == BASELINE and not signing.metadata(APP)['adhoc'] else 'local'
    working_entitlements = signing.verify_source(APP, kind=source_kind)
    keep_recovery = previous and (previous['state'] == 'installed_pending_live_check' or
                                 previous['state'] == 'candidate_verified' and previous.get('recovery'))
    recovery = preserve_recovery(previous) if keep_recovery else None
    if not SAFE.exists():
        if installed_hash != BASELINE:
            raise ValueError('Exact original Safe Build is required before updating a mod')
        copy_app(APP, SAFE)
    if sha(SAFE / ASAR) != BASELINE:
        raise ValueError('Safe Build differs from this inspected baseline; preserve it and review')
    original = Archive(SAFE / ASAR)
    replacements = patch_sources(original)
    syntax_check(replacements)
    if NEW.exists():
        if not replace_candidate:
            raise ValueError('New Build already exists; use --replace-candidate after reviewing changes')
        receipt = json.loads(RECEIPT.read_text())
        retained = 'preinstall' if receipt['state'] in ('installed_accepted', 'installed_pending_live_check') or receipt.get('restored_from_protected') else 'candidate'
        if sha(NEW / ASAR) != receipt[retained + '_sha256']:
            raise ValueError('Existing candidate has unrecorded changes; refusing replacement')
        shutil.rmtree(NEW)
    copy_app(APP, NEW)
    integrity.guard(NEW, working['fingerprint'])
    signing.verify_source(NEW, working_entitlements, source_kind)
    header_hash = Archive(SAFE / ASAR).write(NEW / ASAR, replacements)
    info = plistlib.loads((NEW / PLIST).read_bytes())
    info['ElectronAsarIntegrity']['Resources/app.asar']['hash'] = header_hash
    (NEW / PLIST).write_bytes(plistlib.dumps(info))
    verify_unrelated(Archive(SAFE / ASAR), Archive(NEW / ASAR), set(replacements))
    integrity.verify_entries(NEW / ASAR, list(replacements))
    integrity.patch_digest(NEW)
    # Repaired working bundle supplies the approved local signing policy.
    # Changed leaves/helpers, framework seal, then main app; no deep re-signing.
    candidate_entitlements = signing.sign(NEW)
    verified = integrity.guard(NEW)
    if verified['fuses'] != working['fuses']:
        raise ValueError('Candidate changed the enabled Electron fuses')
    receipt = {'version': VERSION, 'baseline_sha256': BASELINE, 'candidate_sha256': sha(NEW / ASAR),
               'preinstall_sha256': installed_hash,
               'preinstall_signing_kind': source_kind,
               'preinstall_entitlements': working_entitlements, 'candidate_entitlements': candidate_entitlements,
               'preinstall_fingerprint': working['fingerprint'], 'candidate_fingerprint': verified['fingerprint'],
               'header_sha256': header_hash, 'changed_entries': list(replacements),
               'state': 'candidate_verified', 'vendor_signature_replaced': True}
    if recovery is not None:receipt['recovery'] = recovery
    save_receipt(receipt)
    print(json.dumps(receipt, indent=2))


def running_app():
    result = subprocess.run(['/bin/ps', '-axo', 'pid=,comm='], check=True, capture_output=True, text=True,timeout=15)
    expected = str(APP / 'Contents/MacOS/ChatGPT')
    return [int(line.strip().split(None, 1)[0]) for line in result.stdout.splitlines()
            if len(line.strip().split(None, 1)) == 2 and line.strip().split(None, 1)[1] == expected]


def codex_instances():
    """Recognize other Codex app copies without reading arguments or UI."""
    result = subprocess.run(['/bin/ps','-axo','pid=,comm='],check=True,capture_output=True,text=True,timeout=15)
    instances=[]
    for line in result.stdout.splitlines():
        parts=line.strip().split(None,1)
        if len(parts)!=2 or not parts[1].endswith(('/Contents/MacOS/ChatGPT','/Contents/MacOS/Codex')):continue
        executable=Path(parts[1]);bundle=executable.parents[2]
        try:info=plistlib.loads((bundle/PLIST).read_bytes())
        except (OSError,ValueError):continue
        if info.get('CFBundleIdentifier')=='com.openai.codex':instances.append({'pid':int(parts[0]),'executable':str(executable)})
    return instances


def exchange_apps():
    exchange_paths(APP, NEW)


def exchange_paths(left, right):
    import ctypes
    libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    exchange = libc.renameatx_np
    exchange.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    exchange.restype = ctypes.c_int
    if exchange(-2, os.fsencode(left), -2, os.fsencode(right), 2) != 0:
        raise OSError(ctypes.get_errno(), 'Atomic app exchange failed; installation unchanged')


def restore_protected(receipt):
    """Restore a verified copy; the protected original is never exchanged or removed."""
    recovery = receipt['recovery']
    source = checked_recovery(recovery)
    # Unique staging on the checkout filesystem never reuses an interrupted copy.
    with tempfile.TemporaryDirectory(prefix='.codex-usage-recovery-', dir=ROOT) as directory:
        replacement = Path(directory) / 'ChatGPT.app'
        copy_app(source, replacement)
        verify_recovery_bundle(replacement, recovery)
        if running_app():
            raise ValueError('Codex reopened while preparing recovery; protected original retained, exchange refused.')
        exchange_paths(APP, replacement)
        try:
            verify_recovery_bundle(APP, recovery)
            receipt['state'] = 'recovered_previous_mod'
            receipt['restored_from_protected'] = True
            save_receipt(receipt)
        except BaseException:
            exchange_paths(APP, replacement)
            raise
    print(receipt['state'])


def install(rollback=False):
    if running_app():
        raise ValueError('Codex is running. Installation requires a verified quit/relaunch boundary.')
    receipt = json.loads(RECEIPT.read_text())
    if rollback and receipt.get('recovery'):
        if sha(APP / ASAR) != receipt['candidate_sha256'] or sha(NEW / ASAR) != receipt['preinstall_sha256'] or sha(SAFE / ASAR) != BASELINE:
            raise ValueError('Builds changed; refusing protected recovery over unrecorded changes')
        restore_protected(receipt)
        return
    if receipt.get('recovery'):
        checked_recovery(receipt['recovery'])
    current = receipt['candidate_sha256'] if rollback else receipt['preinstall_sha256']
    replacement = receipt['preinstall_sha256'] if rollback else receipt['candidate_sha256']
    target_fingerprint = receipt['preinstall_fingerprint'] if rollback else receipt['candidate_fingerprint']
    if sha(APP / ASAR) != current or sha(NEW / ASAR) != replacement or sha(SAFE / ASAR) != BASELINE:
        raise ValueError('Builds changed; refusing to overwrite unrecorded changes')
    kind = receipt.get('preinstall_signing_kind','local') if rollback else 'local'
    signing.verify_source(NEW, receipt['preinstall_entitlements'] if rollback else receipt['candidate_entitlements'], kind)
    integrity.guard(NEW, target_fingerprint)
    if not rollback:
        integrity.guard(APP, receipt['preinstall_fingerprint'])
        signing.verify_source(APP, receipt['preinstall_entitlements'], receipt.get('preinstall_signing_kind','local'))
    exchange_apps()
    try:
        if sha(APP / ASAR) != replacement:
            raise ValueError('Installed archive readback failed')
        integrity.guard(APP, target_fingerprint)
        signing.verify_source(APP, receipt['preinstall_entitlements'] if rollback else receipt['candidate_entitlements'], kind)
        receipt['state'] = 'recovered_previous_mod' if rollback else 'installed_pending_live_check'
        save_receipt(receipt)
    except Exception:
        exchange_apps()
        raise
    # New Build retains the complete verified previous mod until acceptance.
    # Recovery swaps that exact bundle back; the protected Safe Build is untouched.
    print(receipt['state'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'install', 'rollback'])
    parser.add_argument('--replace-candidate', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'build':
            build(args.replace_candidate)
        else:
            install(args.action == 'rollback')
    except Exception as error:
        raise SystemExit(str(error))
