"""Pending recovery retention and explicit acceptance, on disposable bundles only."""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import mod
import startup_health


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for key in ['APP', 'NEW', 'SAFE']:
            self.stack.enter_context(patch.object(mod, key, root / key))
        self.stack.enter_context(patch.object(mod, 'RECEIPT', root / 'receipt.json'))
        for bundle, payload in [(mod.APP, b'pending candidate'), (mod.NEW, b'last verified mod')]:
            archive = bundle / mod.ASAR
            archive.parent.mkdir(parents=True)
            archive.write_bytes(payload)
        self.receipt = {
            'version': mod.VERSION, 'state': 'installed_pending_live_check',
            'candidate_sha256': mod.sha(mod.APP / mod.ASAR),
            'preinstall_sha256': mod.sha(mod.NEW / mod.ASAR),
            'candidate_fingerprint': 'candidate-fingerprint',
            'preinstall_fingerprint': 'verified-fingerprint',
            'candidate_entitlements': {}, 'preinstall_entitlements': {},
            'preinstall_signing_kind': 'local',
        }
        mod.save_receipt(self.receipt)

    def signing_fixtures(self):
        self.stack.enter_context(patch.object(mod.integrity, 'guard'))
        self.stack.enter_context(patch.object(mod.signing, 'verify'))
        self.stack.enter_context(patch.object(mod.signing, 'verify_source'))
        self.stack.enter_context(patch.object(mod, 'codex_instances', return_value=[{
            'pid': 123, 'executable': str(mod.APP / 'Contents/MacOS/ChatGPT')}]))
        return self.stack.enter_context(patch.object(startup_health, 'mapped_build_matches', return_value=True))

    def test_pending_source_is_identified_without_recording_acceptance(self):
        before = mod.RECEIPT.read_bytes()
        self.assertEqual(mod.build_source_fingerprint(self.receipt, self.receipt['candidate_sha256']), 'candidate-fingerprint')
        self.assertEqual((mod.NEW / mod.ASAR).read_bytes(), b'last verified mod')
        self.assertEqual(mod.RECEIPT.read_bytes(), before)

    def test_interrupted_exchange_cannot_reuse_the_retained_slot(self):
        self.receipt['state'] = 'candidate_verified'
        mod.save_receipt(self.receipt)
        with patch.object(mod, 'copy_app') as copy, patch.object(mod.shutil, 'rmtree') as remove:
            with self.assertRaisesRegex(ValueError, 'transaction state'):
                mod.build(replace_candidate=True)
            copy.assert_not_called()
            remove.assert_not_called()

    def test_process_health_or_one_confirmation_cannot_accept(self):
        before = mod.RECEIPT.read_bytes()
        for flags in [(False, False), (True, False), (False, True)]:
            with self.subTest(flags=flags), self.assertRaisesRegex(ValueError, 'both'):
                mod.accept_installation(*flags)
        self.assertEqual(mod.RECEIPT.read_bytes(), before)

    def test_changed_candidate_cannot_be_accepted(self):
        (mod.APP / mod.ASAR).write_bytes(b'different candidate')
        with self.assertRaisesRegex(ValueError, 'changed'):
            mod.accept_installation(True, True)
        self.assertEqual(json.loads(mod.RECEIPT.read_text())['state'], 'installed_pending_live_check')

    def test_stale_running_image_cannot_be_accepted(self):
        self.signing_fixtures().return_value = False
        with self.assertRaisesRegex(ValueError, 'only running'):
            mod.accept_installation(True, True)
        self.assertEqual(json.loads(mod.RECEIPT.read_text())['state'], 'installed_pending_live_check')

    def test_failed_integrity_check_does_not_record_acceptance(self):
        self.signing_fixtures()
        with patch.object(mod.integrity, 'guard', side_effect=ValueError('changed fingerprint')):
            with self.assertRaisesRegex(ValueError, 'fingerprint'):
                mod.accept_installation(True, True)
        self.assertEqual(json.loads(mod.RECEIPT.read_text())['state'], 'installed_pending_live_check')

    def test_explicit_acceptance_unlocks_exact_source_and_keeps_backup(self):
        self.signing_fixtures()
        mod.accept_installation(True, True)
        receipt = json.loads(mod.RECEIPT.read_text())
        self.assertEqual(receipt['state'], 'installed_accepted')
        self.assertEqual(receipt['acceptance']['method'], 'explicit_user_attestation')
        self.assertEqual(receipt['acceptance']['candidate_fingerprint'], 'candidate-fingerprint')
        self.assertEqual(mod.build_source_fingerprint(receipt, receipt['candidate_sha256']), 'candidate-fingerprint')
        self.assertEqual((mod.NEW / mod.ASAR).read_bytes(), b'last verified mod')
        with self.assertRaisesRegex(ValueError, 'transaction state'):
            mod.build_source_fingerprint(receipt, 'another-candidate')

    def test_recovered_previous_app_can_be_built_again(self):
        self.receipt['state'] = 'recovered_previous_mod'
        self.assertEqual(mod.build_source_fingerprint(self.receipt, self.receipt['preinstall_sha256']), 'verified-fingerprint')


unittest.main(verbosity=2)
