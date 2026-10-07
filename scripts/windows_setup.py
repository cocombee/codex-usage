#!/usr/bin/env python3
"""Build/install a separate local Windows mod. The Store package is read-only."""
import argparse
from contextlib import contextmanager
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
from integrity import require, verify_entries, changed_entries
from mod import Archive, ROOT, sha, verify_unrelated
import windows_integrity as native
import windows_patch as patch

LOCAL = ROOT / '.local-windows'
POWERSHELL = str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def powershell(script, *arguments, timeout=120):
    # Invoke cmdlets directly; never relax script execution policy. Arguments
    # cross the process boundary as JSON data, never interpolated source.
    environment = os.environ.copy()
    # A parent PowerShell 7 session can otherwise direct Windows PowerShell 5.1
    # to incompatible modules. Let the child initialize its own standard paths.
    environment = {key: value for key, value in environment.items() if key.lower() != 'psmodulepath'}
    environment['PSModulePath'] = str(Path(POWERSHELL).parent / 'Modules')
    environment['CODEX_USAGE_COMMAND_ARGS'] = json.dumps(list(map(str, arguments)))
    preamble = "$ErrorActionPreference = 'Stop'; [Console]::OutputEncoding = [Text.UTF8Encoding]::new(); $taskArguments = ConvertFrom-Json -InputObject $env:CODEX_USAGE_COMMAND_ARGS;\n"
    result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-Command', preamble + script.replace('$args', '$taskArguments')],
                            capture_output=True, text=True, encoding='utf-8', errors='replace', env=environment,
                            timeout=timeout, creationflags=CREATE_NO_WINDOW)
    require(result.returncode == 0, 'Windows command failed: ' + result.stderr.strip())
    return json.loads(result.stdout) if result.stdout.strip() else None


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def platform_guard():
    require(platform.system() == 'Windows' and platform.machine().lower() in ('amd64', 'x86_64'),
            'This Windows adapter supports x64 Windows only.')
    require(sys.version_info >= (3, 10), 'Python 3.10+ is required for the Windows installer.')


def normal_path(value):
    return os.path.normcase(str(Path(value).resolve()))


def inside(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    require(path != root and path.is_relative_to(root), 'Path escaped the managed installation directory')
    return path


def reject_reparse(path):
    path = Path(path)
    if path.exists() or path.is_symlink():
        require(not path.is_symlink() and not getattr(path.lstat(), 'st_file_attributes', 0) & 0x400,
                'Reparse points are unsupported: ' + str(path))


@contextmanager
def exclusive(root):
    """OS lock is released on process death; stale lock files are harmless."""
    import msvcrt
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'install.lock').open('a+b')
    try:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            raise ValueError('Another Codex Usage operation is running.') from error
        try:
            yield
        finally:
            lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        lock.close()


def discover():
    platform_guard()
    result = powershell('''
$p = @(Get-AppxPackage -Name OpenAI.Codex)
if ($p.Count -ne 1) { throw 'Expected exactly one current-user OpenAI.Codex installation.' }
$p[0] | Select-Object Name,@{n='Version';e={$_.Version.ToString()}},@{n='Architecture';e={$_.Architecture.ToString()}},InstallLocation,PackageFamilyName,@{n='SignatureKind';e={$_.SignatureKind.ToString()}},@{n='Status';e={$_.Status.ToString()}} | ConvertTo-Json -Compress
''')
    require(result['Version'] == patch.VERSION and result['Architecture'].lower() == 'x64',
            'Uninspected Windows package: ' + result['Version'] + '/' + result['Architecture'])
    require(result['SignatureKind'] == 'Store' and result['Status'] == 'Ok', 'Source package is not a healthy Store installation')
    package = Path(result['InstallLocation']).resolve(strict=True)
    windows_apps = (Path(os.environ['ProgramFiles']) / 'WindowsApps').resolve()
    require(package.is_relative_to(windows_apps), 'Source is not the registered WindowsApps package')
    app = package / 'app'
    for name, expected in patch.PINNED.items():
        require(sha(app / name) == expected, 'Uninspected or altered source: ' + name)
    signatures = powershell('''
@($args | ForEach-Object {
  $s = Get-AuthenticodeSignature -LiteralPath $_
  [pscustomobject]@{Path=$_;Status=$s.Status.ToString();Subject=$s.SignerCertificate.Subject}
}) | ConvertTo-Json -Compress
''', app / 'ChatGPT.exe', app / 'chrome.dll')
    require(len(signatures) == 2 and all(s['Status'] == 'Valid' and 'OpenAI OpCo' in s['Subject'] for s in signatures),
            'Source OpenAI Authenticode signatures did not verify')
    archive = Archive(app / 'resources/app.asar')
    require(json.loads(archive.read('package.json'))['version'] == patch.APP_VERSION, 'Unexpected renderer version')
    # Validate all exact anchors before any large copy or change.
    replacements = patch.patch_sources(archive)
    state = native.verify_pair(app)
    return result, app, replacements, state


def inventory(root):
    reject_reparse(root)
    root = Path(root).resolve(strict=True)
    result = {}
    for base, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(base) / name
            # Directory junctions must not escape our managed copy either.
            reject_reparse(path)
        for name in files:
            path = Path(base) / name
            result[path.relative_to(root).as_posix()] = sha(path)
    return result


def verify_build(build):
    build = Path(build).resolve(strict=True)
    receipt = read_json(build / 'receipt.json')
    require(receipt['schema'] == 1 and receipt['package_version'] == patch.VERSION, 'Unsupported build receipt')
    app = build / 'app'
    require(inventory(app) == receipt['files'], 'Installed files differ from the verified build')
    require(native.verify_pair(app) == receipt['integrity'], 'Installed native integrity changed')
    require(native.inspect_launcher((app / 'ChatGPT.exe').read_bytes())['certificate'] == (0, 0),
            'Modified launcher must not retain an invalid vendor signature')
    return receipt


def build():
    package, source, replacements, original_integrity = discover()
    LOCAL.mkdir(exist_ok=True)
    with exclusive(LOCAL):
        builds = LOCAL / 'builds'; builds.mkdir(exist_ok=True)
        destination = builds / (patch.VERSION + '-' + uuid.uuid4().hex[:12])
        destination.mkdir()
        atomic_json(destination / 'status.json', {'state': 'building', 'started_at': now()})
        try:
            original_files = inventory(source)
            size = sum(p.stat().st_size for p in source.rglob('*') if p.is_file())
            require(shutil.disk_usage(builds).free >= size + 2 * (source / 'resources/app.asar').stat().st_size + 256 * 1024**2,
                    'Not enough free disk space to stage and validate this build')
            print('Copying the verified Windows app into a separate local build...', flush=True)
            app = destination / 'app'
            shutil.copytree(source, app)
            require(inventory(app) == original_files, 'Source changed during copy')
            for name, expected in patch.PINNED.items():
                require(sha(app / name) == expected, 'Copied source pin mismatch: ' + name)
            archive = Archive(app / 'resources/app.asar')
            before_hash = original_integrity['header_sha256']
            new_hash = archive.write(app / 'resources/app.asar', replacements)
            (app / 'ChatGPT.exe').write_bytes(native.rewrite_launcher((app / 'ChatGPT.exe').read_bytes(), before_hash, new_hash))
            candidate = Archive(app / 'resources/app.asar')
            verify_unrelated(Archive(source / 'resources/app.asar'), candidate, replacements)
            require(changed_entries(source / 'resources/app.asar', app / 'resources/app.asar') == sorted(replacements),
                    'Unexpected archive changes')
            verify_entries(app / 'resources/app.asar', list(replacements))
            files = inventory(app)
            changed = sorted(name for name in set(files) | set(original_files) if files.get(name) != original_files.get(name))
            require(changed == ['ChatGPT.exe', 'resources/app.asar'], 'Unexpected files changed in copied app')
            signatures = powershell('''
@($args | ForEach-Object { $s=Get-AuthenticodeSignature -LiteralPath $_; [pscustomobject]@{Status=$s.Status.ToString()} }) | ConvertTo-Json -Compress
''', app / 'ChatGPT.exe', app / 'chrome.dll')
            require([s['Status'] for s in signatures] == ['NotSigned', 'Valid'], 'Unexpected candidate signature state')
            receipt = {'schema': 1, 'created_at': now(), 'package_version': patch.VERSION,
                       'app_version': patch.APP_VERSION, 'architecture': 'x64', 'distribution': 'local-unpackaged-copy',
                       'source_package': package['PackageFamilyName'], 'source_pins': patch.PINNED,
                       'files': files, 'integrity': native.verify_pair(app), 'changed_entries': sorted(replacements),
                       'acceptance': {'rendered_ui': False, 'live_metrics': False, 'diff_interaction': False, 'quit_reopen': False}}
            require(receipt['integrity']['fuses'] == original_integrity['fuses'], 'Fuse configuration changed')
            atomic_json(destination / 'receipt.json', receipt)
            verify_build(destination)
            atomic_json(destination / 'status.json', {'state': 'verified', 'completed_at': now()})
            atomic_json(LOCAL / 'latest.json', {'build': str(destination)})
            return destination
        except BaseException as error:
            atomic_json(destination / 'status.json', {'state': 'failed', 'error': str(error), 'at': now()})
            # Keep the failed slot for diagnosis; it can never be selected for launch.
            raise


def default_install_root():
    # The source MSIX explicitly excludes LocalAppData/OpenAI from filesystem
    # virtualization. This path stays stable when run from inside or outside it.
    return Path(os.environ['LOCALAPPDATA']) / 'OpenAI/CodexUsage'


def validate_install_root(root):
    reject_reparse(root)
    root = Path(root).resolve()
    require(normal_path(root) == normal_path(default_install_root()), 'Only the per-user CodexUsage installation directory is supported')
    reject_reparse(root / 'builds')
    reject_reparse(root / 'scripts')
    return root


def current_build(root, entry):
    require(isinstance(entry, str) and Path(entry).name == entry and entry not in ('.', '..'), 'Invalid build pointer')
    reject_reparse(root / 'builds')
    reject_reparse(root / 'builds' / entry)
    path = inside(root / 'builds' / entry, root / 'builds')
    require(path.parent == (root / 'builds').resolve(), 'Build pointer escaped its slot')
    return path


def install(build_path):
    platform_guard()
    build_path = inside(build_path, LOCAL / 'builds')
    receipt = verify_build(build_path)
    root = validate_install_root(default_install_root())
    with exclusive(root):
        root.joinpath('builds').mkdir(exist_ok=True)
        target = root / 'builds' / build_path.name
        require(not target.exists(), 'This build is already installed; use --launch')
        require(shutil.disk_usage(root).free > sum((build_path / 'app' / p).stat().st_size for p in receipt['files']) + 256 * 1024**2,
                'Not enough free disk space for installation')
        pointer_path = root / 'current.json'
        old = read_json(pointer_path) if pointer_path.exists() else None
        if old:
            verify_build(current_build(root, old['current']))
        # An interrupted copy is never referenced by current.json.
        shutil.copytree(build_path, target)
        verify_build(target)
        scripts = root / 'scripts'; scripts.mkdir(exist_ok=True)
        for name in ['windows_setup.py', 'windows_integrity.py', 'windows_patch.py', 'integrity.py', 'mod.py', 'signing.py']:
            shutil.copy2(ROOT / 'scripts' / name, scripts / name)
        shortcut = powershell('''
$folder = Join-Path ([Environment]::GetFolderPath('Programs')) 'Codex Usage'
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$path = Join-Path $folder 'Codex Usage (local mod).lnk'
$link = (New-Object -ComObject WScript.Shell).CreateShortcut($path)
$link.TargetPath = $args[0]
$link.Arguments = $args[1]
$link.WorkingDirectory = $args[2]
$link.Description = 'Locally modified Codex Usage; close the Store app before opening.'
$link.Save()
$path | ConvertTo-Json -Compress
''', sys.executable, subprocess.list2cmdline(['-B', str(scripts / 'windows_setup.py'), '--launch']), root)
        atomic_json(pointer_path, {'current': target.name, 'previous': old['current'] if old else None,
                                   'installed_at': now(), 'state': 'installed-awaiting-launch'})
        return {'installation': str(root), 'shortcut': shortcut, 'build': target.name}


def app_processes():
    result = powershell('''
@(Get-CimInstance Win32_Process -Filter "Name = 'ChatGPT.exe'" | Select-Object ProcessId,ParentProcessId,ExecutablePath) | ConvertTo-Json -Compress
''')
    return result if isinstance(result, list) else [result] if result else []


def select_previous(root, pointer, reason):
    previous = pointer.get('previous')
    if previous:
        verify_build(current_build(root, previous))
        atomic_json(root / 'current.json', {'current': previous, 'previous': None, 'state': 'rolled-back', 'reason': reason, 'at': now()})
    else:
        atomic_json(root / 'current.json', {**pointer, 'state': 'launch-failed', 'reason': reason, 'at': now()})


def launch():
    platform_guard()
    root = validate_install_root(default_install_root())
    with exclusive(root):
        pointer = read_json(root / 'current.json')
        require(pointer.get('state') != 'launch-failed', 'This build failed startup. Use the original Store app or install a repaired build.')
        build_path = current_build(root, pointer['current'])
        verify_build(build_path)
        require(not app_processes(), 'Close all ChatGPT/Codex desktop windows normally, then open Codex Usage again. No app was stopped.')
        exe = build_path / 'app/ChatGPT.exe'
        environment = os.environ.copy()
        # Use the normal host profile without copying credentials or history.
        # Explicit test overrides must never leak into the normal launcher.
        environment.pop('CODEX_ELECTRON_USER_DATA_PATH', None)
        environment.pop('CODEX_ELECTRON_AGENT_RUN_ID', None)
        atomic_json(root / 'current.json', {**pointer, 'state': 'starting', 'at': now()})
        process = None
        try:
            process = subprocess.Popen([str(exe)], cwd=exe.parent, env=environment,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                require(process.poll() is None, 'Candidate exited during startup: ' + str(process.returncode))
                time.sleep(.5)
            observed = app_processes()
            require(any(p['ProcessId'] == process.pid and p['ExecutablePath'] and normal_path(p['ExecutablePath']) == normal_path(exe) for p in observed),
                    'Exact installed launcher process was not found')
            count = pointer.get('healthy_launches', 0) + 1
            atomic_json(root / 'current.json', {**pointer, 'state': 'process-healthy', 'pid': process.pid,
                                               'healthy_launches': count, 'at': now()})
            print('Codex Usage opened. Process health passed; rendered UI and live metrics still need acceptance.')
        except BaseException as error:
            if process is not None and process.poll() is None:
                # Do not start another app or swap files under a live process.
                atomic_json(root / 'current.json', {**pointer, 'state': 'needs-attention', 'reason': str(error), 'pid': process.pid})
            else:
                select_previous(root, pointer, str(error))
            raise


def rollback():
    root = validate_install_root(default_install_root())
    with exclusive(root):
        require(not app_processes(), 'Close Codex normally before selecting a previous build.')
        pointer = read_json(root / 'current.json')
        require(pointer.get('previous'), 'No previous local mod exists. The original Store app is still available.')
        select_previous(root, pointer, 'Requested rollback')


def accept(confirmations):
    require(all(confirmations.values()), 'Acceptance requires explicit rendered UI, live metrics, diff action and normal quit/reopen confirmations.')
    root = validate_install_root(default_install_root())
    with exclusive(root):
        pointer = read_json(root / 'current.json')
        build_path = current_build(root, pointer['current'])
        require(pointer.get('healthy_launches', 0) >= 2, 'Two normal healthy launches are required before acceptance.')
        receipt = verify_build(build_path)
        exe = build_path / 'app/ChatGPT.exe'
        require(any(p['ExecutablePath'] and normal_path(p['ExecutablePath']) == normal_path(exe) for p in app_processes()),
                'The exact installed build must be running for acceptance.')
        receipt['acceptance'] = {**confirmations, 'at': now()}
        atomic_json(build_path / 'receipt.json', receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--check', action='store_true')
    actions.add_argument('--build', action='store_true')
    actions.add_argument('--install', metavar='VERIFIED_BUILD')
    actions.add_argument('--launch', action='store_true')
    actions.add_argument('--rollback', action='store_true')
    actions.add_argument('--accept', action='store_true')
    for flag in ['rendered-ui', 'live-metrics', 'diff-interaction', 'quit-reopen']:
        parser.add_argument('--confirm-' + flag, action='store_true')
    args = parser.parse_args()
    try:
        platform_guard()
        confirmations = {key: getattr(args, 'confirm_' + key) for key in ['rendered_ui', 'live_metrics', 'diff_interaction', 'quit_reopen']}
        require(args.accept or not any(confirmations.values()), 'Confirmations require --accept')
        if args.check:
            package, _, replacements, state = discover()
            print(json.dumps({'package_version': package['Version'], 'architecture': package['Architecture'],
                              'patch_entries': len(replacements), 'integrity': state}, indent=2))
        elif args.build:
            print('Verified build: ' + str(build()))
        elif args.install:
            print(json.dumps(install(Path(args.install)), indent=2))
        elif args.launch:
            launch()
        elif args.rollback:
            rollback()
        else:
            accept(confirmations)
    except (Exception, KeyboardInterrupt) as error:
        print('Stopped: ' + (str(error) or 'Interrupted; no Store files were modified.'), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
