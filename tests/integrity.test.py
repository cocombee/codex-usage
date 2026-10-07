#!/usr/bin/env python3
"""Synthetic local binary/archive fixtures only; never launch or touch real data."""
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import integrity as sync


class DynamicSynchronizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='codex-usage-integrity-')
        self.addCleanup(self.temp.cleanup)
        self.root_patch = patch.object(sync, 'ROOT', Path(self.temp.name))
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.app = sync.ROOT / 'New Build' / 'ChatGPT.app'
        self.app.mkdir(parents=True)
        self.make_archive(b'first mod payload')
        self.make_binary()

    def make_archive(self, data):
        archive = self.app / 'Contents/Resources/app.asar'
        archive.parent.mkdir(parents=True, exist_ok=True)
        block = 4
        tree = {'files': {'main.js': {'size': len(data), 'offset': '0', 'integrity': {
            'algorithm': 'SHA256', 'hash': hashlib.sha256(data).hexdigest(), 'blockSize': block,
            'blocks': [hashlib.sha256(data[i:i + block]).hexdigest() for i in range(0, len(data), block)]}}}}
        raw = json.dumps(tree, separators=(',', ':')).encode()
        payload = (4 + len(raw) + 3) // 4 * 4
        archive.write_bytes(struct.pack('<IIII', 4, payload + 4, payload, len(raw))
                            + raw + b'\0' * (payload - 4 - len(raw)) + data)
        self.info = {'CFBundleShortVersionString': 'synthetic-unit-test', 'ElectronAsarIntegrity': {
            'Resources/app.asar': {'algorithm': 'SHA256', 'hash': hashlib.sha256(raw).hexdigest()}}}
        self.write_info()

    def write_info(self):
        (self.app / 'Contents/Info.plist').write_bytes(plistlib.dumps(self.info))

    def make_binary(self, enabled=1, wire=b'010011001'):
        framework = self.app / sync.FRAMEWORK / 'Versions/Fixture'
        framework.mkdir(parents=True, exist_ok=True)
        current = framework.parent / 'Current'
        if not current.exists():
            current.symlink_to('Fixture')
        self.binary = framework / 'Codex Framework'
        segment = struct.pack('<II16sQQQQiiII', 0x19, 152, b'__DATA_CONST', 0, 4096, 0, 1024, 3, 1, 1, 0)
        section = struct.pack('<16s16sQQIIIIIIII', b'__asar_integrity', b'__DATA_CONST', 256, 66, 256, 0, 0, 0, 0, 0, 0, 0)
        signature = struct.pack('<IIII', 0x1d, 16, 960, 64)
        data = bytearray(1024)
        data[:32] = struct.pack('<IiiIIIII', 0xfeedfacf, 0x100000c, 0, 6, 2, 168, 0, 0)
        data[32:200] = segment + section + signature
        data[256:322] = sync.SENTINEL + bytes([enabled, 1]) + bytes(32)
        fuse = sync.FUSE_SENTINEL + bytes([1, len(wire)]) + wire
        data[384:384 + len(fuse)] = fuse
        self.binary.write_bytes(data)

    def test_dynamic_digest_for_two_different_current_dictionaries(self):
        first = sync.patch_digest(self.app)
        self.assertTrue(first['after']['native_matches_dictionary'])
        first_digest = first['after']['dictionary_digest']
        self.make_archive(b'second different newer mod payload')
        second = sync.patch_digest(self.app)
        self.assertTrue(second['after']['native_matches_dictionary'])
        self.assertNotEqual(first_digest, second['after']['dictionary_digest'])

    def test_only_32_byte_native_slot_changes_no_archive_or_fuse_changes(self):
        binary_before = self.binary.read_bytes()
        archive = self.app / 'Contents/Resources/app.asar'
        archive_before = archive.read_bytes()
        state = sync.inspect(self.app)
        sync.patch_digest(self.app)
        binary_after = self.binary.read_bytes()
        offset = state['native_slot']['digest_offset']
        self.assertEqual(binary_before[:offset], binary_after[:offset])
        self.assertEqual(binary_before[offset + 32:], binary_after[offset + 32:])
        self.assertEqual(archive_before, archive.read_bytes())
        self.assertEqual(sync.inspect(self.app)['fuses'], state['fuses'])

    def test_idempotent_sync_makes_no_second_write(self):
        sync.patch_digest(self.app)
        before = self.binary.stat().st_mtime_ns
        self.assertEqual(sync.patch_digest(self.app)['status'], 'already_synchronized')
        self.assertEqual(self.binary.stat().st_mtime_ns, before)

    def test_guard_rejects_native_mismatch_before_codesign(self):
        with patch.object(sync.subprocess, 'run') as sign:
            with self.assertRaisesRegex(ValueError, 'Enabled native ASAR slot rejects'):
                sync.guard(self.app)
            sign.assert_not_called()

    def test_guard_accepts_synced_signature_verified_candidate(self):
        sync.patch_digest(self.app)
        result = subprocess.CompletedProcess([], 0, '', '')
        with patch.object(sync.subprocess, 'run', return_value=result) as sign:
            self.assertTrue(sync.guard(self.app)['deep_strict_signature_valid'])
            self.assertEqual(sign.call_args[0][0][1:4], ['--verify', '--deep', '--strict'])

    def test_guard_rejects_invalid_signature(self):
        sync.patch_digest(self.app)
        result = subprocess.CompletedProcess([], 1, '', 'synthetic invalid signature')
        with patch.object(sync.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(ValueError, 'signature verification failed'):
                sync.guard(self.app)

    def test_guard_rejects_stale_receipt_before_codesign(self):
        sync.patch_digest(self.app)
        old = sync.inspect(self.app)['fingerprint']
        self.make_archive(b'new builder overwrite')
        sync.patch_digest(self.app)
        with patch.object(sync.subprocess, 'run') as sign:
            with self.assertRaisesRegex(ValueError, 'changed since its verified receipt'):
                sync.guard(self.app, old)
            sign.assert_not_called()

    def test_dictionary_hash_must_match_actual_current_archive_header(self):
        self.info['ElectronAsarIntegrity']['Resources/app.asar']['hash'] = 'a' * 64
        self.write_info()
        with self.assertRaisesRegex(ValueError, 'Dictionary/header mismatch'):
            sync.inspect(self.app)

    def test_unsafe_dictionary_path_rejected(self):
        entry = self.info['ElectronAsarIntegrity'].pop('Resources/app.asar')
        self.info['ElectronAsarIntegrity']['Resources/../app.asar'] = entry
        self.write_info()
        with self.assertRaisesRegex(ValueError, 'Unsafe integrity dictionary path'):
            sync.inspect(self.app)

    def test_disabled_native_validation_rejected_without_patch(self):
        self.make_binary(enabled=0)
        before = self.binary.read_bytes()
        with self.assertRaisesRegex(ValueError, 'must stay enabled'):
            sync.patch_digest(self.app)
        self.assertEqual(before, self.binary.read_bytes())

    def test_disabled_integrity_fuse_rejected_without_patch(self):
        self.make_binary(wire=b'010000001')
        before = self.binary.read_bytes()
        with self.assertRaisesRegex(ValueError, 'fuses must stay enabled'):
            sync.patch_digest(self.app)
        self.assertEqual(before, self.binary.read_bytes())

    def test_full_and_block_entry_hashes_detect_payload_tampering(self):
        path = self.app / 'Contents/Resources/app.asar'
        self.assertEqual(len(sync.verify_entries(path, ['main.js'])), 1)
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'full hash mismatch'):
            sync.verify_entries(path, ['main.js'])

    def test_sync_refuses_installed_or_external_bundle_before_inspection(self):
        with patch.object(sync, 'inspect') as inspect:
            with self.assertRaisesRegex(ValueError, 'Only canonical staged bundles'):
                sync.patch_digest('/Applications/ChatGPT.app')
            inspect.assert_not_called()

    def test_guard_detects_bundle_change_during_signature_verification(self):
        sync.patch_digest(self.app)
        def change(*args, **kwargs):
            self.make_archive(b'concurrent replacement')
            sync.patch_digest(self.app)
            return subprocess.CompletedProcess([], 0, '', '')
        with patch.object(sync.subprocess, 'run', side_effect=change):
            with self.assertRaisesRegex(ValueError, 'changed while verifying signature'):
                sync.guard(self.app)


if __name__ == '__main__':
    unittest.main(verbosity=2)
