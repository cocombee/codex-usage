#!/usr/bin/env python3
"""Narrow local-signing policy, with no credentials or vendor impersonation."""
import copy
import plistlib
from pathlib import Path
import re
import struct
import subprocess
import tempfile

LIBRARY_LOADING_KEY = 'com.apple.security.cs.disable-library-validation'

RESTRICTED_VENDOR_KEYS = frozenset({
    'com.apple.application-identifier',
    'com.apple.developer.aps-environment',
    'com.apple.developer.team-identifier',
    'com.apple.security.application-groups',
    'keychain-access-groups',
})


def local_entitlements(original, *, allow_library_loading=False, verified_executable_host=False):
    """Preserve supported caps; the app-only loading exception is explicit opt-in.

    The caller must separately prove that the target is an authorized Mach-O
    executable loading this framework. Frameworks and unrelated helpers cannot
    receive this new capability merely because they are nested in the app.
    """
    if type(allow_library_loading) is not bool or type(verified_executable_host) is not bool:
        raise ValueError('Library-loading policy requires literal boolean opt-in')
    if allow_library_loading and not verified_executable_host:
        raise ValueError('Library-loading exception requires a verified executable host')
    result = copy.deepcopy(original)
    for key in RESTRICTED_VENDOR_KEYS:
        result.pop(key, None)
    if allow_library_loading:
        result[LIBRARY_LOADING_KEY] = True
    assert_local_entitlements(result)
    return result


def assert_local_entitlements(value):
    prohibited = set(value) & RESTRICTED_VENDOR_KEYS
    prohibited.update(key for key in value if key.startswith('com.apple.developer.') or key == 'application-identifier')
    if prohibited:
        raise ValueError('Ad-hoc signature cannot claim vendor entitlements: ' + ', '.join(sorted(prohibited)))
    return True


def require(condition, message):
    if not condition:
        raise ValueError(message)

def verified_loader(executable, framework):
    executable, framework = Path(executable), Path(framework).resolve(strict=True)
    data = executable.read_bytes()
    require(len(data) >= 32, 'Truncated executable host')
    header = struct.unpack_from('<IiiIIIII', data)
    require(header[0] == 0xfeedfacf and header[1] == 0x100000c and header[3] == 2,
            'Loading exception is only for a thin arm64 MH_EXECUTE host')
    end, position = 32 + header[5], 32
    require(end <= len(data), 'Host load commands truncated')
    dependencies = []
    for _ in range(header[4]):
        require(position + 8 <= end, 'Truncated host command')
        command, size = struct.unpack_from('<II', data, position)
        require(size >= 8 and size % 8 == 0 and position + size <= end, 'Invalid host command')
        if command in (0xc, 0x80000018, 0x8000001f, 0x20, 0x80000023):
            require(size >= 24, 'Truncated dylib command')
            offset = struct.unpack_from('<I', data, position + 8)[0]
            require(24 <= offset < size, 'Invalid dylib name')
            dependencies.append(data[position + offset:position + size].split(b'\0', 1)[0].decode())
        position += size
    require(position == end, 'Host command count inconsistent')
    paths = []
    for name in dependencies:
        if name.startswith('@executable_path/'):
            target = executable.parent / name[len('@executable_path/'):]
            if target.resolve(strict=True) == framework:
                paths.append({'route': 'LC_LOAD_DYLIB', 'literal': name})
    if b'_dlopen\0' in data and b'ChromeMain\0' in data:
        for match in re.findall(rb'[ -~]{4,}', data):
            if match.startswith(b'../') and match.endswith(b'Codex Framework'):
                literal = match.decode()
                if (executable.parent / literal).resolve(strict=True) == framework:
                    paths.append({'route': 'dlopen/ChromeMain', 'literal': literal})
    require(paths, 'Executable is not a verified loader of the exact bundled framework')
    return {'executable': str(executable), 'framework': str(framework), 'macho_filetype': 'MH_EXECUTE',
            'framework_loading_proof': paths}


FRAMEWORK = Path('Contents/Frameworks/Codex Framework.framework')


def targets(app):
    app = Path(app).resolve(strict=True)
    framework = app / FRAMEWORK
    helpers = sorted((framework / 'Versions/Current/Helpers').glob('*.app'))
    require(len(helpers) == 8, 'Pinned helper set changed; inspect before signing')
    return helpers + [framework, app]


def executable(bundle):
    info = plistlib.loads((bundle / 'Contents/Info.plist').read_bytes())
    result = (bundle / 'Contents/MacOS' / info['CFBundleExecutable']).resolve(strict=True)
    require(result.is_relative_to(bundle.resolve()), 'Executable escaped its host bundle')
    return result


def metadata(target):
    result = subprocess.run(['/usr/bin/codesign', '-d', '--entitlements', ':-', str(target)],
                            capture_output=True, check=True,timeout=30)
    entitlements = plistlib.loads(result.stdout) if result.stdout else {}
    result = subprocess.run(['/usr/bin/codesign', '-dv', '--verbose=4', str(target)],
                            capture_output=True, text=True, check=True,timeout=30)
    flags = re.search(r'flags=(0x[0-9a-f]+)', result.stderr)
    team = re.search(r'TeamIdentifier=(.*)', result.stderr)
    require(flags and team, 'Unrecognized signing metadata')
    return {'entitlements': entitlements, 'flags': int(flags.group(1), 16),
            'team': team.group(1), 'adhoc': 'Signature=adhoc' in result.stderr}


def verify(app, expected=None):
    app = Path(app).resolve(strict=True)
    framework_binary = (app / FRAMEWORK / 'Versions/Current/Codex Framework').resolve(strict=True)
    observed = {}
    for target in targets(app):
        key = str(target.relative_to(app)) if target != app else '.'
        row = metadata(target)
        require(row['adhoc'] and row['team'] == 'not set', 'Expected local/ad-hoc signing identity: ' + key)
        require(row['flags'] & 0x10000, 'Hardened Runtime missing: ' + key)
        assert_local_entitlements(row['entitlements'])
        if row['entitlements'].get(LIBRARY_LOADING_KEY):
            require(target.suffix == '.app', 'Library-loading exception is restricted to executable hosts')
            verified_loader(executable(target), framework_binary)
        elif target.suffix == '.app':
            try:
                verified_loader(executable(target), framework_binary)
            except ValueError:
                pass
            else:
                raise ValueError('Verified local framework loader lacks its scoped loading exception: ' + key)
        observed[key] = row['entitlements']
    require(expected is None or observed == expected, 'Expected entitlements changed')
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)],
                   check=True, capture_output=True,timeout=120)
    return observed


def verify_source(app, expected=None, kind='local'):
    """Accept a valid original vendor bundle or our verified local bundle.

    Vendor identity/entitlements are checked on the source only. Candidate
    signing always uses the scoped local policy and never copies vendor claims.
    """
    if kind == 'local':
        return verify(app, expected)
    require(kind == 'vendor', 'Unknown source signing policy')
    app = Path(app).resolve(strict=True)
    observed, teams = {}, set()
    for target in targets(app):
        key = str(target.relative_to(app)) if target != app else '.'
        row = metadata(target)
        require(not row['adhoc'] and row['team'] not in ('not set',''), 'Expected vendor identity: ' + key)
        require(row['flags'] & 0x10000, 'Hardened Runtime missing: ' + key)
        teams.add(row['team'])
        observed[key] = row['entitlements']
    require(len(teams) == 1, 'Source launcher/framework signing teams differ')
    require(expected is None or observed == expected, 'Source entitlements changed')
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',
                    '-R=anchor apple generic and identifier "com.openai.codex"',str(app)],
                   check=True,capture_output=True,timeout=120)
    return observed


def sign(app):
    # The copy comes from the already repaired working app, preserving all
    # supported capabilities. Only verified Codex Framework hosts get the
    # existing user-approved library-loading exception.
    app = Path(app).resolve(strict=True)
    framework_binary = (app / FRAMEWORK / 'Versions/Current/Codex Framework').resolve(strict=True)
    expected = {}
    with tempfile.TemporaryDirectory(prefix='codex-usage-signing-') as directory:
        for index, target in enumerate(targets(app)):
            before = metadata(target)
            allow = False
            if target.suffix == '.app':
                try:
                    verified_loader(executable(target), framework_binary)
                except ValueError:
                    require(not before['entitlements'].get(LIBRARY_LOADING_KEY), 'Unexpected loading exception host')
                else:
                    allow = True
            safe = local_entitlements(before['entitlements'], allow_library_loading=allow,
                                      verified_executable_host=allow)
            key = str(target.relative_to(app)) if target != app else '.'
            expected[key] = safe
            entitlements = Path(directory) / f'{index}.plist'
            entitlements.write_bytes(plistlib.dumps(safe))
            subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', '--options', 'runtime',
                            '--timestamp=none', '--preserve-metadata=identifier', '--entitlements',
                            str(entitlements), str(target)], check=True, capture_output=True,timeout=120)
    return verify(app, expected)
