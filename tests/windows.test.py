"""Synthetic PE fixtures plus Windows locking/deployment failure tests."""
import json
import os
from contextlib import ExitStack, contextmanager, nullcontext
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import windows_integrity as native
import windows_setup as setup


def executable(digest='a' * 64):
    """Small original fixture, not extracted vendor executable bytes."""
    data = bytearray(0x810)
    data[:2] = b'MZ'; struct.pack_into('<I', data, 60, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, 0x8664, 1)
    struct.pack_into('<H', data, 0x94, 240)
    optional = 0x98
    struct.pack_into('<H', data, optional, 0x20b)
    struct.pack_into('<I', data, optional + 108, 16)
    struct.pack_into('<II', data, optional + 128, 0x1000, 0x600)
    struct.pack_into('<II', data, optional + 144, 0x800, 16)
    at = optional + 240
    data[at:at + 8] = b'.rsrc\0\0\0'
    struct.pack_into('<IIII', data, at + 8, 0x600, 0x1000, 0x600, 0x200)
    # type -> name -> language -> resource data
    for relative, name, child in [(0, 0x80000100, 0x80000020), (0x20, 0x80000130, 0x80000040), (0x40, 1033, 0x60)]:
        struct.pack_into('<HH', data, 0x200 + relative + 12, 1 if relative < 0x40 else 0, 1 if relative == 0x40 else 0)
        struct.pack_into('<II', data, 0x200 + relative + 16, name, child)
    for relative, text in [(0x100, 'INTEGRITY'), (0x130, 'ELECTRONASAR')]:
        raw = text.encode('utf-16le'); struct.pack_into('<H', data, 0x200 + relative, len(text))
        data[0x202 + relative:0x202 + relative + len(raw)] = raw
    payload = json.dumps([{'file': 'resources\\app.asar', 'alg': 'SHA256', 'value': digest}], separators=(',', ':')).encode()
    struct.pack_into('<IIII', data, 0x260, 0x1200, len(payload), 0, 0)
    data[0x400:0x400 + len(payload)] = payload
    struct.pack_into('<IHH', data, 0x800, 16, 0x200, 2)
    return bytes(data)


class IntegrityTests(unittest.TestCase):
    def test_hash_update_preserves_code_and_removes_stale_signature(self):
        before = executable(); info = native.inspect_launcher(before)
        after = native.rewrite_launcher(before, 'a' * 64, 'b' * 64)
        self.assertEqual(native.inspect_launcher(after)['sha256'], 'b' * 64)
        self.assertEqual(native.inspect_launcher(after)['certificate'], (0, 0))
        self.assertEqual(len(after), 0x800)
        permitted = set(range(info['digest_offset'], info['digest_offset'] + 64)) | set(range(info['security_offset'], info['security_offset'] + 8))
        self.assertTrue(all(before[i] == after[i] or i in permitted for i in range(len(after))))

    def test_wrong_original_digest_and_certificate_overlay_rejected(self):
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            native.rewrite_launcher(executable(), 'c' * 64, 'b' * 64)
        with self.assertRaisesRegex(ValueError, 'certificate layout'):
            native.rewrite_launcher(executable() + b'overlay', 'a' * 64, 'b' * 64)

    def test_resource_cycle_and_out_of_bounds_rva_rejected(self):
        data = bytearray(executable()); struct.pack_into('<I', data, 0x214, 0x80000000)
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            native.inspect_launcher(data)
        data = bytearray(executable()); struct.pack_into('<I', data, 0x260, 0xFFFFFF00)
        with self.assertRaisesRegex(ValueError, 'RVA'):
            native.inspect_launcher(data)

    def test_truncated_pe_never_accepted(self):
        for length in [0, 63, 128, 260, 511, 1024]:
            with self.subTest(length=length), self.assertRaises(ValueError):
                native.inspect_launcher(executable()[:length])

    def test_integrity_fuses_must_stay_enabled_and_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'runtime.dll'
            p.write_bytes(b'padding' + native.FUSE_SENTINEL + b'\x01\x09010011001')
            self.assertEqual(native.inspect_fuses(p)['wire'], '010011001')
            p.write_bytes(native.FUSE_SENTINEL + b'\x01\x09010001001')
            with self.assertRaisesRegex(ValueError, 'must remain enabled'): native.inspect_fuses(p)
            p.write_bytes(native.FUSE_SENTINEL * 2)
            with self.assertRaisesRegex(ValueError, 'ambiguous'): native.inspect_fuses(p)


class DeploymentTests(unittest.TestCase):
    @contextmanager
    def installer_fixture(self, legacy=False):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as mocks:
            base = Path(directory).resolve()
            root, checkout = base / 'install', base / 'checkout'
            local = checkout / '.local-windows'
            build = local / 'builds' / 'new'
            (build / 'app').mkdir(parents=True)
            (root / 'builds' / 'old').mkdir(parents=True)
            scripts = root / 'scripts' if legacy else root / 'builds' / 'old' / 'scripts'
            scripts.mkdir()
            (scripts / 'windows_setup.py').write_text('print("old")\n')
            (checkout / 'scripts').mkdir(parents=True)
            for name in setup.SCRIPT_NAMES:
                (checkout / 'scripts' / name).write_text('print("new")\n')
            pointer = {'current': 'old', 'previous': None}
            setup.atomic_json(root / 'current.json', pointer)
            launcher = root / 'windows_setup.py'
            if not legacy:
                launcher.write_text(setup.DISPATCHER)
            shortcut = base / 'mod.lnk'; shortcut.write_text('old shortcut')

            def stage_shortcut(*args):
                temporary = base / 'mod.pending.lnk'
                temporary.write_text('new shortcut')
                return {'Path': str(shortcut), 'Temporary': str(temporary)}

            for name, value in [('ROOT', checkout), ('LOCAL', local)]:
                mocks.enter_context(patch.object(setup, name, value))
            mocks.enter_context(patch.object(setup, 'platform_guard'))
            mocks.enter_context(patch.object(setup, 'default_install_root', return_value=root))
            mocks.enter_context(patch.object(setup, 'exclusive', side_effect=lambda _: nullcontext()))
            mocks.enter_context(patch.object(setup, 'verify_build', return_value={'files': {}}))
            mocks.enter_context(patch.object(setup, 'powershell', side_effect=stage_shortcut))
            yield root, build, scripts, shortcut, pointer

    def selected_launcher_output(self, root):
        # Fixture launchers only print their identity; no desktop app is run.
        launcher = root / 'windows_setup.py'
        if not launcher.exists():
            launcher = root / 'scripts/windows_setup.py'
        return subprocess.check_output([sys.executable, '-B', str(launcher)], text=True).strip()

    def test_interrupted_launcher_copy_preserves_previous_modules_and_dispatch(self):
        original_copy = setup.shutil.copy2
        for legacy in (False, True):
            with self.subTest(legacy=legacy), self.installer_fixture(legacy) as (root, build, scripts, shortcut, pointer):
                original = (scripts / 'windows_setup.py').read_bytes()

                def interrupted_copy(source, destination):
                    if Path(source).name == 'windows_integrity.py':
                        Path(destination).write_text('def truncated(')
                        raise OSError('interrupted launcher copy')
                    return original_copy(source, destination)

                with patch.object(setup.shutil, 'copy2', side_effect=interrupted_copy):
                    with self.assertRaisesRegex(OSError, 'interrupted launcher copy'):
                        setup.install(build)
                self.assertEqual(setup.read_json(root / 'current.json'), pointer)
                self.assertEqual((scripts / 'windows_setup.py').read_bytes(), original)
                self.assertEqual(shortcut.read_text(), 'old shortcut')
                self.assertEqual(self.selected_launcher_output(root), 'old')

    def test_failed_dispatcher_replacement_preserves_old_launcher(self):
        original_replace = setup.os.replace
        with self.installer_fixture() as (root, build, scripts, shortcut, pointer):
            original = (root / 'windows_setup.py').read_bytes()

            def fail_dispatcher(source, destination):
                if Path(destination) == root / 'windows_setup.py':
                    raise OSError('dispatcher replacement denied')
                return original_replace(source, destination)

            with patch.object(setup.os, 'replace', side_effect=fail_dispatcher):
                with self.assertRaisesRegex(OSError, 'dispatcher replacement denied'):
                    setup.install(build)
            self.assertEqual((root / 'windows_setup.py').read_bytes(), original)
            self.assertEqual(setup.read_json(root / 'current.json'), pointer)
            self.assertEqual(self.selected_launcher_output(root), 'old')
            self.assertFalse(list(root.glob('windows_setup.py.pending-*')))

    def test_failed_shortcut_replacement_keeps_previous_launcher_and_pointer(self):
        original_replace = setup.os.replace
        with self.installer_fixture(legacy=True) as (root, build, scripts, shortcut, pointer):
            def fail_shortcut(source, destination):
                if Path(destination) == shortcut:
                    raise OSError('shortcut replacement denied')
                return original_replace(source, destination)

            with patch.object(setup.os, 'replace', side_effect=fail_shortcut):
                with self.assertRaisesRegex(OSError, 'shortcut replacement denied'):
                    setup.install(build)
            self.assertEqual(shortcut.read_text(), 'old shortcut')
            self.assertEqual(setup.read_json(root / 'current.json'), pointer)
            self.assertEqual(self.selected_launcher_output(root), 'old')

    def test_committed_install_and_rollback_select_matching_launcher_modules(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), self.installer_fixture(legacy) as (root, build, scripts, shortcut, pointer):
                setup.install(build)
                selected = setup.read_json(root / 'current.json')
                self.assertEqual((selected['current'], selected['previous']), ('new', 'old'))
                self.assertEqual(self.selected_launcher_output(root), 'new')
                self.assertEqual(setup.inventory(root / 'builds/new/scripts'), setup.inventory(setup.ROOT / 'scripts'))
                setup.select_previous(root, selected, 'test rollback')
                self.assertEqual(self.selected_launcher_output(root), 'old')

    def test_failed_pointer_commit_keeps_new_shortcut_on_previous_launcher(self):
        original_replace = setup.os.replace
        for legacy in (False, True):
            with self.subTest(legacy=legacy), self.installer_fixture(legacy) as (root, build, scripts, shortcut, pointer):
                def fail_pointer(source, destination):
                    if Path(destination) == root / 'current.json':
                        raise OSError('pointer commit interrupted')
                    return original_replace(source, destination)

                with patch.object(setup.os, 'replace', side_effect=fail_pointer):
                    with self.assertRaisesRegex(OSError, 'pointer commit interrupted'):
                        setup.install(build)
                self.assertEqual(shortcut.read_text(), 'new shortcut')
                self.assertEqual(setup.read_json(root / 'current.json'), pointer)
                self.assertEqual(self.selected_launcher_output(root), 'old')

    def test_unsupported_package_stops_before_source_file_access(self):
        with patch.object(setup, 'platform_guard'), patch.object(setup, 'powershell', return_value={'Version': '99.1.0', 'Architecture': 'x64'}), patch.object(setup, 'sha') as hashing:
            with self.assertRaisesRegex(ValueError, 'Uninspected'): setup.discover()
            hashing.assert_not_called()

    def test_process_query_handles_one_or_many_processes(self):
        for raw, expected in [(None, []), ({'ProcessId': 7}, [{'ProcessId': 7}]), ([{'ProcessId': 7}], [{'ProcessId': 7}])]:
            with patch.object(setup, 'powershell', return_value=raw): self.assertEqual(setup.app_processes(), expected)

    def test_escaped_build_pointer_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for value in ['..', '../outside', '/absolute', 'C:\\elsewhere', 'a/b']:
                with self.subTest(value=value), self.assertRaises(ValueError): setup.current_build(root, value)

    def test_failed_replacement_keeps_previous_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'install'; root.mkdir()
            build = Path(directory) / 'source'; (build / 'app').mkdir(parents=True)
            original = {'current': 'old', 'previous': None}
            setup.atomic_json(root / 'current.json', original)
            from contextlib import nullcontext
            with patch.object(setup, 'platform_guard'), patch.object(setup, 'inside', side_effect=lambda path, root: Path(path).resolve()), patch.object(setup, 'verify_build', return_value={'files': {}}), patch.object(setup, 'default_install_root', return_value=root), patch.object(setup, 'validate_install_root', return_value=root), patch.object(setup, 'exclusive', return_value=nullcontext()), patch.object(setup.shutil, 'copytree', side_effect=OSError('interrupted copy')):
                with self.assertRaisesRegex(OSError, 'interrupted copy'): setup.install(build)
            self.assertEqual(setup.read_json(root / 'current.json'), original)

    def test_rollback_verifies_previous_before_switching(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); original = {'current': 'new', 'previous': 'old'}
            setup.atomic_json(root / 'current.json', original)
            with patch.object(setup, 'verify_build', side_effect=ValueError('corrupt previous')):
                with self.assertRaisesRegex(ValueError, 'corrupt'): setup.select_previous(root, original, 'test')
            self.assertEqual(setup.read_json(root / 'current.json'), original)
            with patch.object(setup, 'verify_build'): setup.select_previous(root, original, 'test')
            self.assertEqual(setup.read_json(root / 'current.json')['current'], 'old')

    def test_first_launch_failure_does_not_relaunch_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            setup.select_previous(root, {'current': 'new', 'previous': None}, 'startup failure')
            self.assertEqual(setup.read_json(root / 'current.json')['state'], 'launch-failed')

    def test_acceptance_requires_all_observations(self):
        with self.assertRaisesRegex(ValueError, 'explicit'): setup.accept({'rendered_ui': True, 'quit_reopen': False})

    def test_os_launch_failure_records_failure_without_relaunch(self):
        from contextlib import nullcontext
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            setup.atomic_json(root / 'current.json', {'current': 'new', 'previous': None})
            with patch.object(setup, 'platform_guard'), patch.object(setup, 'default_install_root', return_value=root), patch.object(setup, 'validate_install_root', return_value=root), patch.object(setup, 'verify_build'), patch.object(setup, 'app_processes', return_value=[]), patch.object(setup, 'exclusive', return_value=nullcontext()), patch.object(setup.subprocess, 'Popen', side_effect=OSError('launch denied')) as launch:
                with self.assertRaisesRegex(OSError, 'launch denied'): setup.launch()
                launch.assert_called_once()
            self.assertEqual(setup.read_json(root / 'current.json')['state'], 'launch-failed')

    def test_interrupted_health_check_preserves_live_process_and_records_attention(self):
        from contextlib import nullcontext
        from unittest.mock import Mock
        process = Mock(pid=42); process.poll.return_value = None
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            setup.atomic_json(root / 'current.json', {'current': 'new', 'previous': 'old'})
            with patch.object(setup, 'platform_guard'), patch.object(setup, 'default_install_root', return_value=root), patch.object(setup, 'validate_install_root', return_value=root), patch.object(setup, 'verify_build'), patch.object(setup, 'app_processes', return_value=[]), patch.object(setup, 'exclusive', return_value=nullcontext()), patch.object(setup.subprocess, 'Popen', return_value=process), patch.object(setup.time, 'monotonic', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt): setup.launch()
            pointer = setup.read_json(root / 'current.json')
            self.assertEqual((pointer['current'], pointer['state']), ('new', 'needs-attention'))
            process.terminate.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows byte-range locking')
    def test_duplicate_lock_rejected_and_crashed_owner_releases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with setup.exclusive(root):
                with self.assertRaisesRegex(ValueError, 'Another'):
                    with setup.exclusive(root): pass
            code = 'import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import windows_setup as w\nwith w.exclusive(Path(sys.argv[2])):\n print("locked",flush=True);time.sleep(30)'
            p = subprocess.Popen([sys.executable, '-B', '-c', code, str(Path(setup.__file__).parent), directory], stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(p.stdout.readline().strip(), 'locked')
                with self.assertRaisesRegex(ValueError, 'Another'):
                    with setup.exclusive(root): pass
            finally:
                p.kill(); p.wait(timeout=5); p.stdout.close()
            with setup.exclusive(root): pass


if __name__ == '__main__':
    unittest.main()
