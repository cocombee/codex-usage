#!/usr/bin/env python3
"""One-command, bounded installation from macOS Terminal."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
import install_once as worker
import mod

LOG = mod.ROOT / 'local-setup.log'


def require_supported_platform():
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('This inspected build supports Apple Silicon macOS only.')
    if sys.version_info < (3,9):
        raise ValueError('Python 3.9 or newer is required.')


def stop_build_group(process, grace=5):
    """Reap the leader and stop surviving descendants in its original group."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + grace
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        pass
    # Give descendants the remainder of the grace period even if the leader
    # exited immediately. A leader's exit does not prove the group is empty.
    time.sleep(max(0, deadline - time.monotonic()))
    # The leader may already have exited while a copy/signing child survived.
    # Group cleanup must not depend on the leader's wait() result.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def run_bounded(argv, *, timeout, output):
    """Timeout stops the complete build process group before any app quit."""
    process = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        code = process.wait(timeout=timeout)
    except BaseException as error:
        stop_build_group(process)
        if isinstance(error,subprocess.TimeoutExpired):
            raise ValueError('Build timed out. Codex was not closed or replaced; see ' + str(LOG))
        raise
    if code:
        raise ValueError('Build verification failed. Codex was not closed or replaced; see ' + str(LOG))


def preflight():
    require_supported_platform()
    if not mod.APP.is_dir() or mod.APP.is_symlink():
        raise ValueError('Install the supported Codex app at /Applications/ChatGPT.app first.')
    if mod.app_version(mod.APP) != mod.VERSION:
        raise ValueError('Unsupported Codex version. Required: ' + mod.VERSION + '. App unchanged; wait for a reviewed version update.')
    node = shutil.which('node')
    if not node:
        raise ValueError('Install Node.js 20 or newer, then rerun this command. App unchanged.')
    version = subprocess.run([node,'--version'],check=True,capture_output=True,text=True,timeout=15).stdout.strip()
    if int(version.lstrip('v').split('.')[0]) < 20:
        raise ValueError('Node.js 20 or newer is required. App unchanged.')
    if not shutil.which('codesign'):
        raise ValueError('macOS codesign is unavailable. App unchanged.')
    if not os.access(mod.APP.parent,os.W_OK) or not os.access(mod.ROOT,os.W_OK):
        raise ValueError('The app folder and checkout must be writable. No sudo or security changes are performed.')
    if mod.ROOT.stat().st_dev != mod.APP.parent.stat().st_dev:
        raise ValueError('Keep this checkout on the same disk as /Applications for atomic installation. App unchanged.')
    known = {mod.BASELINE}
    receipt = json.loads(mod.RECEIPT.read_text()) if mod.RECEIPT.exists() else None
    if receipt:
        if receipt.get('version') == mod.VERSION:
            known.update([receipt.get('candidate_sha256'),receipt.get('preinstall_sha256')])
            if receipt.get('recovery'):known.add(receipt['recovery']['sha256'])
    installed_hash = mod.sha(mod.APP/mod.ASAR)
    if installed_hash not in known:
        raise ValueError('Unrecognized app archive. Refusing to overwrite another modification; app unchanged.')
    mod.build_source_fingerprint(receipt, installed_hash)
    size = int(subprocess.run(['/usr/bin/du','-sk',str(mod.APP)],check=True,capture_output=True,text=True,timeout=30).stdout.split()[0])*1024
    copies = 1 + int(not mod.SAFE.exists())
    if receipt and (receipt['state'] == 'installed_pending_live_check' or receipt.get('recovery')):
        # Reserve a fresh copy for protected rollback as well as initial retention.
        copies += 1 + int(not receipt.get('recovery'))
    if shutil.disk_usage(mod.ROOT).free < size*copies + 128*1024*1024:
        raise ValueError('Not enough free space for the candidate and protected backup. App unchanged.')
    pids = mod.codex_instances()
    if len(pids)>1:
        raise ValueError('More than one Codex process is running; close duplicate instances first.')


def install():
    require_supported_platform()
    # Never close an app that owns this command. Normal Terminal is independent.
    chain = worker.ancestry()
    pids = mod.running_app()
    if any(row['pid'] in pids for row in chain) or not any(row['executable'].endswith('/Terminal.app/Contents/MacOS/Terminal') for row in chain):
        raise ValueError('Run this command in macOS Terminal, outside Codex, so installation can finish while Codex reopens.')
    with worker.exclusive_install():
        print('1/3 Checking compatibility and backup space…',flush=True)
        preflight()
        print('2/3 Building, signing and verifying. Codex stays open during this step…',flush=True)
        with LOG.open('w') as log:
            run_bounded([sys.executable,'-B',str(mod.ROOT/'scripts/mod.py'),'build','--replace-candidate'],timeout=900,output=log)
        pids = mod.running_app()
        if len(pids)>1:
            raise ValueError('Codex process changed during preparation; app unchanged.')
        print('3/3 Installing and reopening Codex automatically. Please do not open another copy during this step…',flush=True)
        labels = {'installed':'App replaced; checking normal startup…',
                  'recovered_previous_mod':'Startup failed; previous app restored.',
                  'recovered_relaunched_previous_mod':'Previous app reopened. Failed candidate will not be retried.'}
        worker.run(str(uuid.uuid4()),pids[0] if pids else 0,auto_authorize=True,
                   progress=lambda state: print(labels[state],flush=True) if state in labels else None,already_locked=True)
        print('Updated and reopened. Confirm the usage row renders, then normally quit/reopen Codex once.',flush=True)
        print('After both checks pass, you may record your acceptance with:\n' + mod.ACCEPT_COMMAND,flush=True)


def main():
    def interrupted(signum,frame):
        raise KeyboardInterrupt('Interrupted; checking the installation boundary.')
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--check',action='store_true',help='Check compatibility without building, quitting or installing')
    actions.add_argument('--accept',action='store_true',help='Record your verification of the exact installed candidate; never builds or launches')
    parser.add_argument('--confirm-rendered-ui',action='store_true',help='Attest that you verified the installed usage row renders correctly')
    parser.add_argument('--confirm-quit-reopen',action='store_true',help='Attest that you normally quit and reopened that installed candidate')
    args = parser.parse_args()
    try:
        require_supported_platform()
        for signum in (signal.SIGTERM,signal.SIGHUP):
            signal.signal(signum,interrupted)
        if not args.accept and (args.confirm_rendered_ui or args.confirm_quit_reopen):
            raise ValueError('Acceptance confirmations require --accept.')
        if args.accept:
            with worker.exclusive_install():
                mod.accept_installation(args.confirm_rendered_ui, args.confirm_quit_reopen)
        elif args.check:
            preflight()
            print('Compatibility checks passed. Run without --check in macOS Terminal to install.')
        else:
            install()
    except (Exception, KeyboardInterrupt) as error:
        # Closing Terminal is discouraged; state remains in the durable receipt.
        print('Stopped: ' + (str(error) or 'Interrupted. Check the local installation report before retrying.'),file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
