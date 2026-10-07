"""Real copying/exchanges of disposable bundles; no installed app or native signing."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import plistlib
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import mod
import startup_health
import install_once as worker


class ProtectedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(mod, 'ROOT', root))
        for name in ['APP', 'NEW', 'SAFE', 'PROTECTED']:
            self.stack.enter_context(patch.object(mod, name, root / name / 'ChatGPT.app'))
        self.stack.enter_context(patch.object(mod, 'RECEIPT', root / 'receipt.json'))
        self.stack.enter_context(patch.object(mod, 'PROTECTED_RECEIPT', root / 'recovery.json'))
        for bundle, payload in [(mod.APP, b'pending'), (mod.NEW, b'working'), (mod.SAFE, b'baseline')]:
            (bundle / mod.ASAR).parent.mkdir(parents=True)
            (bundle / mod.ASAR).write_bytes(payload)
            (bundle / mod.PLIST).write_bytes(plistlib.dumps({'ElectronAsarIntegrity': {'Resources/app.asar': {'hash': 'fixture'}}}))
        self.stack.enter_context(patch.object(mod, 'BASELINE', mod.sha(mod.SAFE / mod.ASAR)))
        receipt = {'version': mod.VERSION, 'state': 'installed_pending_live_check',
                   'candidate_sha256': mod.sha(mod.APP / mod.ASAR), 'preinstall_sha256': mod.sha(mod.NEW / mod.ASAR),
                   'candidate_fingerprint': mod.sha(mod.APP / mod.ASAR), 'preinstall_fingerprint': mod.sha(mod.NEW / mod.ASAR),
                   'candidate_entitlements': {}, 'preinstall_entitlements': {}, 'preinstall_signing_kind': 'local'}
        mod.save_receipt(receipt)
        self.stack.enter_context(patch.object(mod.integrity, 'guard', side_effect=self.guard))
        self.stack.enter_context(patch.object(mod.signing, 'verify_source', return_value={}))
        self.stack.enter_context(patch.object(mod.signing, 'verify', return_value={}))
        self.stack.enter_context(patch.object(mod.signing, 'metadata', return_value={'adhoc': True}))
        self.stack.enter_context(patch.object(mod.signing, 'sign', return_value={}))
        self.stack.enter_context(patch.object(mod, 'running_app', return_value=[]))
        self.stack.enter_context(patch.object(mod, 'app_version', return_value=mod.VERSION))
        for target, name in [(mod, 'syntax_check'), (mod, 'verify_unrelated'),
                             (mod.integrity, 'verify_entries'), (mod.integrity, 'patch_digest')]:
            self.stack.enter_context(patch.object(target, name))
        self.stack.enter_context(patch.object(mod, 'patch_sources', return_value={}))
        archive = Mock()
        archive.write.side_effect = self.write_archive
        self.stack.enter_context(patch.object(mod, 'Archive', return_value=archive))
        self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.next_payload = b'next'

    def guard(self, app, expected=None):
        fingerprint = mod.sha(app / mod.ASAR)
        if expected is not None and fingerprint != expected:
            raise ValueError('Fixture fingerprint mismatch')
        return {'fingerprint': fingerprint, 'fuses': 'unchanged-fixture'}

    def write_archive(self, destination, replacements):
        destination.write_bytes(self.next_payload)
        return 'fixture-header'

    def test_pending_build_preserves_verified_predecessor_before_reusing_new(self):
        mod.build(replace_candidate=True)
        receipt = json.loads(mod.RECEIPT.read_text())
        recovery = json.loads(mod.PROTECTED_RECEIPT.read_text())
        self.assertEqual((mod.PROTECTED / mod.ASAR).read_bytes(), b'working')
        self.assertEqual((mod.NEW / mod.ASAR).read_bytes(), b'next')
        self.assertEqual((mod.APP / mod.ASAR).read_bytes(), b'pending')
        self.assertEqual(receipt['recovery'], recovery)
        self.assertEqual(receipt['state'], 'candidate_verified')
        self.assertNotIn('acceptance', receipt)

    def test_repeated_pending_updates_recover_original_and_can_build_afterward(self):
        mod.build(replace_candidate=True)
        protected_identity = (mod.PROTECTED / mod.ASAR).stat().st_ino
        mod.install()
        self.next_payload = b'newer'
        mod.build(replace_candidate=True)
        mod.install()
        mod.install(rollback=True)
        self.assertEqual((mod.APP / mod.ASAR).read_bytes(), b'working')
        self.assertEqual((mod.PROTECTED / mod.ASAR).read_bytes(), b'working')
        self.assertEqual((mod.PROTECTED / mod.ASAR).stat().st_ino, protected_identity)
        self.assertEqual((mod.NEW / mod.ASAR).read_bytes(), b'next')
        receipt = json.loads(mod.RECEIPT.read_text())
        self.assertTrue(receipt['restored_from_protected'])
        self.assertEqual(receipt['state'], 'recovered_previous_mod')
        self.next_payload = b'after-recovery'
        mod.build(replace_candidate=True)
        self.assertEqual((mod.NEW / mod.ASAR).read_bytes(), b'after-recovery')
        self.assertNotIn('recovery', json.loads(mod.RECEIPT.read_text()))

    def test_rebuilding_ready_candidate_preserves_protected_rollback_policy(self):
        mod.build(replace_candidate=True)
        expected = json.loads(mod.RECEIPT.read_text())['recovery']
        self.next_payload = b'revised-before-install'
        mod.build(replace_candidate=True)
        self.assertEqual(json.loads(mod.RECEIPT.read_text())['recovery'], expected)

    def test_new_accepted_lineage_uses_newer_predecessor_and_keeps_older_copy(self):
        self.next_payload = b'C'
        mod.build(replace_candidate=True)
        mod.install()
        with patch.object(mod, 'codex_instances', return_value=[{'pid':123,'executable':str(mod.APP/'Contents/MacOS/ChatGPT')}]), \
                patch.object(startup_health, 'mapped_build_matches', return_value=True):
            mod.accept_installation(True, True)
        self.next_payload = b'D'
        mod.build(replace_candidate=True)
        mod.install()
        self.assertNotIn('recovery', json.loads(mod.RECEIPT.read_text()))
        self.next_payload = b'E'
        mod.build(replace_candidate=True)
        recovery = json.loads(mod.RECEIPT.read_text())['recovery']
        protected_c, provenance = mod.recovery_paths(recovery)
        self.assertNotEqual(protected_c, mod.PROTECTED)
        self.assertEqual((protected_c / mod.ASAR).read_bytes(), b'C')
        self.assertEqual(json.loads(provenance.read_text()), recovery)
        self.assertEqual((mod.PROTECTED / mod.ASAR).read_bytes(), b'working')
        mod.install()
        mod.install(rollback=True)
        self.assertEqual((mod.APP / mod.ASAR).read_bytes(), b'C')
        self.assertEqual((protected_c / mod.ASAR).read_bytes(), b'C')
        self.assertEqual((mod.PROTECTED / mod.ASAR).read_bytes(), b'working')

    def test_unknown_protected_copy_blocks_before_new_is_deleted(self):
        mod.PROTECTED.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'unrecorded'):
            mod.build(replace_candidate=True)
        self.assertEqual((mod.NEW / mod.ASAR).read_bytes(), b'working')
        self.assertEqual(json.loads(mod.RECEIPT.read_text())['state'], 'installed_pending_live_check')

    def test_changed_protected_archive_blocks_next_pending_update(self):
        mod.build(replace_candidate=True)
        mod.install()
        (mod.PROTECTED / mod.ASAR).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'archive changed'):
            mod.build(replace_candidate=True)
        self.assertEqual((mod.NEW / mod.ASAR).read_bytes(), b'pending')

    def test_failed_post_restore_check_reverses_exchange_and_preserves_original(self):
        mod.build(replace_candidate=True)
        mod.install()
        def fail_restored(app, expected=None):
            if app == mod.APP and (app / mod.ASAR).read_bytes() == b'working':
                raise ValueError('simulated recovery validation failure')
            return self.guard(app, expected)
        with patch.object(mod.integrity, 'guard', side_effect=fail_restored):
            with self.assertRaisesRegex(ValueError, 'simulated'):
                mod.install(rollback=True)
        self.assertEqual((mod.APP / mod.ASAR).read_bytes(), b'next')
        self.assertEqual((mod.PROTECTED / mod.ASAR).read_bytes(), b'working')
        self.assertEqual(json.loads(mod.RECEIPT.read_text())['state'], 'installed_pending_live_check')

    def test_worker_failed_startup_restores_and_launches_protected_predecessor_once(self):
        mod.build(replace_candidate=True)
        state = {'phase':'old', 'clock':0, 'candidate_checks':0, 'opens':0}
        def pids():
            if state['phase'] == 'old':return [10]
            if state['phase'] == 'candidate':
                state['candidate_checks'] += 1
                return [20] if state['candidate_checks'] == 1 else []
            return [30] if state['phase'] == 'recovered' else []
        def clock():
            state['clock'] += 2
            return state['clock']
        def stop(pid, sig):state['phase'] = 'closed'
        original_run = subprocess.run
        def command(argv, **kwargs):
            if argv[0] == '/usr/bin/open':
                state['opens'] += 1
                state['phase'] = 'recovered' if (mod.APP / mod.ASAR).read_bytes() == b'working' else 'candidate'
                return subprocess.CompletedProcess(argv, 0)
            return original_run(argv, **kwargs)
        with ExitStack() as stack:
            for name in ['APP', 'NEW', 'SAFE', 'RECEIPT', 'BASELINE']:
                stack.enter_context(patch.object(worker, name, getattr(mod, name)))
            for name in ['REPORT', 'GATE', 'COMMAND']:
                stack.enter_context(patch.object(worker, name, mod.ROOT / (name + '.json')))
            stack.enter_context(patch.object(worker, 'EXECUTABLE', str(mod.APP / 'Contents/MacOS/ChatGPT')))
            for name in ['verify_builds', 'verify_signing', 'verify_source', 'CrashMonitor']:
                stack.enter_context(patch.object(worker, name))
            for name, value in [('running_app',pids), ('install',mod.install), ('guard',self.guard), ('sha',mod.sha)]:
                stack.enter_context(patch.object(worker, name, value))
            stack.enter_context(patch.object(worker, 'ancestry', return_value=[{'pid':999,'executable':'/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal'}]))
            stack.enter_context(patch.object(worker, 'codex_instances', side_effect=lambda:[{'pid':pid,'executable':worker.EXECUTABLE} for pid in pids()]))
            stack.enter_context(patch.object(worker.os, 'kill', side_effect=stop))
            stack.enter_context(patch.object(worker.subprocess, 'run', side_effect=command))
            stack.enter_context(patch.object(worker.time, 'monotonic', side_effect=clock))
            stack.enter_context(patch.object(worker.time, 'sleep'))
            with self.assertRaisesRegex(ValueError, 'did not remain running'):
                worker.run('protected-fixture', 10, auto_authorize=True)
            report = json.loads(worker.REPORT.read_text())
        self.assertEqual(report['state'], 'recovered_relaunched_previous_mod')
        self.assertEqual(state['opens'], 2)
        self.assertEqual((mod.APP / mod.ASAR).read_bytes(), b'working')
        self.assertEqual((mod.PROTECTED / mod.ASAR).read_bytes(), b'working')


unittest.main(verbosity=2)
