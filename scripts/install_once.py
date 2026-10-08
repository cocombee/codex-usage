#!/usr/bin/env python3
"""Finite install/relaunch worker, launched by independent macOS Terminal."""
import argparse
from contextlib import contextmanager
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from integrity import guard
from signing import verify as verify_signing, verify_source
from startup_health import CrashMonitor, mapped_build_matches
from mod import APP, ASAR, PLIST, NEW, SAFE, BASELINE, ROOT, RECEIPT, Archive, sha, app_version, install, running_app
from mod import codex_instances

REPORT = ROOT / 'local-install-status.json'
GATE = ROOT / 'local-install-authorized.json'
COMMAND = ROOT / 'local-install.command'
EXECUTABLE = str(APP / 'Contents/MacOS/ChatGPT')


@contextmanager
def exclusive_install():
    if sys.platform != 'darwin':
        raise ValueError('This inspected build supports Apple Silicon macOS only.')
    import fcntl
    with (REPORT.parent / 'local-install.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another Codex Usage installation is running; wait for it to finish.')
        try:
            yield
        finally:
            fcntl.flock(lock,fcntl.LOCK_UN)


def verify_previous(app,receipt):
    if receipt.get('preinstall_signing_kind','local') == 'local':
        return verify_signing(app,receipt['preinstall_entitlements'])
    return verify_source(app,receipt['preinstall_entitlements'],'vendor')


def atomic_json(path, value):
    pending = path.with_suffix(path.suffix + '.pending')
    with pending.open('w') as file:
        file.write(json.dumps(value, indent=2) + '\n')
        file.flush()
        os.fsync(file.fileno())
    os.replace(pending, path)


def ancestry():
    result = []
    pid = os.getpid()
    for _ in range(32):
        process = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'pid=,ppid=,comm='], check=True, capture_output=True, text=True,timeout=15)
        parts = process.stdout.strip().split(None, 2)
        if len(parts) != 3:
            raise ValueError('Cannot prove installer ancestry')
        current, parent = int(parts[0]), int(parts[1])
        result.append({'pid': current, 'parent': parent, 'executable': parts[2]})
        if current == 1 or parent == 0:
            break
        pid = parent
    return result


def verify_builds(receipt, installed_hash):
    if sha(APP / ASAR) != installed_hash:
        raise ValueError('Installed app changed since preparation')
    if sha(SAFE / ASAR) != BASELINE or sha(NEW / ASAR) != receipt['candidate_sha256']:
        raise ValueError('Safe or candidate build changed since preparation')
    if app_version(APP) != receipt['version'] or app_version(NEW) != receipt['version']:
        raise ValueError('App version changed since preparation')
    candidate = Archive(NEW / ASAR)
    digest = hashlib.sha256(candidate.header_bytes).hexdigest()
    info = plistlib.loads((NEW / PLIST).read_bytes())
    if digest != receipt['header_sha256'] or info['ElectronAsarIntegrity']['Resources/app.asar']['hash'] != digest:
        raise ValueError('Candidate Electron integrity mismatch')
    for path in receipt['changed_entries']:
        candidate.read(path)
    verify_signing(NEW, receipt['candidate_entitlements'])
    verify_previous(APP,receipt)
    guard(NEW, receipt['candidate_fingerprint'])
    guard(APP, receipt['preinstall_fingerprint'])


def run(nonce, expected_pid, *, auto_authorize=False, progress=None, already_locked=False):
    if already_locked:
        return _run(nonce,expected_pid,auto_authorize,progress)
    with exclusive_install():
        return _run(nonce,expected_pid,auto_authorize,progress)


def _run(nonce, expected_pid, auto_authorize=False, progress=None):
    status = {'operation': 'install', 'nonce': nonce, 'worker_pid': os.getpid(),
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'safe_build': str(SAFE), 'candidate_build': str(NEW), 'installed_app': str(APP),
              'old_main_pid': expected_pid, 'launch_count': 0, 'live_ui_verified': False}
    def record(state, **values):
        status.update(values)
        status['state'] = state
        status['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        atomic_json(REPORT, status)
        if progress: progress(state)
    stopped = False
    launch_attempted = False
    recovery_attempted = False
    def launch(recovery=False):
        nonlocal launch_attempted, recovery_attempted
        if launch_attempted and not recovery:
            raise ValueError('Refusing a second candidate relaunch attempt')
        if recovery and recovery_attempted:
            raise ValueError('Refusing a second recovery relaunch')
        recovery_attempted = recovery_attempted or recovery
        launch_attempted = True
        existing=codex_instances()
        if existing:
            if len(existing)==1 and existing[0]['executable']==EXECUTABLE and mapped_build_matches(existing[0]['pid'],APP):
                status['attached_existing_verified_pid']=existing[0]['pid']
                return existing[0]['pid']
            raise ValueError('Another or stale Codex instance is already open. Quit that copy; refusing a duplicate launch.')
        status['launch_count'] += 1
        subprocess.run(['/usr/bin/open','-a',str(APP)], check=True, capture_output=True,timeout=30)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            pids = running_app()
            if len(pids) == 1 and pids[0] != expected_pid:
                return pids[0]
            if len(pids) > 1:
                raise ValueError('More than one main app process after relaunch')
            time.sleep(.5)
        raise ValueError('Installed app did not relaunch within 90 seconds')
    try:
        receipt = json.loads(RECEIPT.read_text())
        preinstall_hash = receipt.get('preinstall_sha256', BASELINE)
        if receipt['state'] != 'candidate_verified':
            raise ValueError('Candidate receipt is not ready for first installation')
        chain = ancestry()
        if expected_pid in [item['pid'] for item in chain]:
            raise ValueError('Installer is still owned by Codex')
        if not any(item['executable'].endswith('/Terminal.app/Contents/MacOS/Terminal') for item in chain):
            raise ValueError('Installer was not launched by independent Terminal')
        if running_app() != ([expected_pid] if expected_pid else []):
            raise ValueError('Expected exactly one inspected main app PID')
        if [row['pid'] for row in codex_instances()] != ([expected_pid] if expected_pid else []):
            raise ValueError('Another Codex copy is running. Quit other copies before installing.')
        verify_builds(receipt, preinstall_hash)
        crashes = CrashMonitor(APP)
        record('prepared', ancestry=chain, candidate_sha256=receipt['candidate_sha256'], baseline_sha256=BASELINE, preinstall_sha256=preinstall_hash)
        # A short bounded gate lets the calling agent read back independence and
        # preparation before allowing the user-authorized shutdown.
        deadline = time.monotonic() + 120
        while not auto_authorize and time.monotonic() < deadline:
            if GATE.exists():
                gate = json.loads(GATE.read_text())
                if gate.get('nonce') == nonce and gate.get('candidate_sha256') == receipt['candidate_sha256']:
                    break
            time.sleep(.25)
        else:
            if not auto_authorize: raise ValueError('Authorization gate timed out; app untouched')
        if running_app() != ([expected_pid] if expected_pid else []):
            raise ValueError('Main app PID changed before shutdown')
        verify_builds(receipt, preinstall_hash)
        record('closing_writer')
        # Process lifecycle for bundle replacement; no UI scripting or inspection.
        if expected_pid: os.kill(expected_pid, signal.SIGTERM)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and running_app():
            time.sleep(.25)
        if running_app():
            raise ValueError('App writer did not stop; app unchanged')
        stopped = True
        if codex_instances():raise ValueError('Codex was reopened during preparation; app unchanged. Let the installer finish reopening it.')
        record('writer_stopped')
        install()
        if sha(APP / ASAR) != receipt['candidate_sha256']:
            raise ValueError('Installed candidate readback failed')
        guard(APP, receipt['candidate_fingerprint'])
        verify_signing(APP, receipt['candidate_entitlements'])
        record('installed')
        new_pid = launch()
        record('relaunched', new_main_pid=new_pid)
        # Some startup paths replace the initial process. Allow a single healthy
        # main process to settle without issuing another launch command.
        deadline = time.monotonic() + 30
        stable_since = None
        last_sample=None
        while time.monotonic() < deadline:
            crashes.check()
            pids = running_app()
            mapped = len(pids)==1 and mapped_build_matches(pids[0],APP)
            sample={'pids':pids,'mapped_installed_build':mapped}
            if sample!=last_sample:
                status.setdefault('startup_trace',[]).append(sample)
                last_sample=sample
                record('checking_startup')
            if len(pids) == 1 and pids[0] != expected_pid and mapped:
                if pids[0] != new_pid:
                    new_pid = pids[0]
                    stable_since = None
                stable_since = stable_since or time.monotonic()
                if time.monotonic() - stable_since >= 10:
                    break
            else:
                stable_since = None
            time.sleep(.5)
        else:
            raise ValueError('Relaunched app did not remain running')
        guard(APP, receipt['candidate_fingerprint'])
        verify_signing(APP, receipt['candidate_entitlements'])
        crashes.check()
        if sha(SAFE / ASAR) != BASELINE:
            raise ValueError('Protected backup changed')
        record('process_healthy_ui_pending', new_main_pid=new_pid, installed_sha256=sha(APP / ASAR), installed_version=app_version(APP),
               acceptance_pending=['Rendered native UI', 'Normal user quit and reopen of installed app', 'Live usage values', 'Native diff click and tooltip', 'User visual acceptance'])
    except (Exception, KeyboardInterrupt) as error:
        record('failed', error=str(error))
        # A failed candidate startup gets one transactional recovery to the
        # retained verified mod, never repeated launches of the failed candidate.
        if stopped:
            try:
                receipt = json.loads(RECEIPT.read_text())
                restored = False
                if sha(APP / ASAR) == receipt['candidate_sha256'] and sha(NEW / ASAR) == receipt['preinstall_sha256']:
                    pids = running_app()
                    if len(pids) > 1 or expected_pid in pids:
                        raise ValueError('Cannot prove a safe recovery process boundary')
                    if pids:
                        os.kill(pids[0], signal.SIGTERM)
                        deadline = time.monotonic() + 30
                        while running_app() and time.monotonic() < deadline:
                            time.sleep(.25)
                    if running_app():
                        raise ValueError('Failed candidate still running; recovery deferred')
                    install(rollback=True)
                    restored = True
                    record('recovered_previous_mod', installed_sha256=sha(APP / ASAR))
                if restored and receipt.get('recovery'):
                    recovery = receipt['recovery']
                    guard(APP, recovery['fingerprint'])
                    verify_source(APP, recovery['entitlements'], recovery['signing_kind'])
                else:
                    guard(APP, receipt['preinstall_fingerprint'])
                    verify_previous(APP,receipt)
                if not running_app():
                    new_pid = launch(recovery=True)
                    record('recovered_relaunched_previous_mod', new_main_pid=new_pid)
            except Exception as recovery_error:
                record('failed_recovery', recovery_error=str(recovery_error))
        raise
    finally:
        if GATE.exists():
            try:
                if json.loads(GATE.read_text()).get('nonce') == nonce:
                    GATE.unlink()
            except Exception:
                pass
        COMMAND.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nonce', required=True)
    parser.add_argument('--expected-pid', required=True, type=int)
    parser.add_argument('--show-progress',action='store_true')
    args = parser.parse_args()
    labels={'prepared':'Verified and ready. Codex will reopen automatically; please leave Terminal open.',
            'closing_writer':'Closing Codex for replacement…','installed':'Installed. Opening the exact updated app…',
            'checking_startup':'Checking the running executable and framework…',
            'process_healthy_ui_pending':'Updated app is running. Confirm the usage row renders.',
            'recovered_previous_mod':'Startup check failed; previous app restored.',
            'recovered_relaunched_previous_mod':'Previous app reopened; the failed candidate will not be retried.'}
    progress=lambda state:print(labels[state],flush=True) if state in labels else None
    run(args.nonce,args.expected_pid,progress=progress if args.show_progress else None)
