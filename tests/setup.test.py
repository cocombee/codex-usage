"""First-install guards, concurrent-install lock, and real timeout cleanup."""
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, Mock
from contextlib import ExitStack
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import setup
import signing
import install_once as worker


class SetupTests(unittest.TestCase):
    def test_unsupported_platform_stops_before_app_or_build_access(self):
        with patch.object(setup.platform,'system',return_value='Linux'),patch.object(setup.mod,'app_version') as version:
            with self.assertRaisesRegex(ValueError,'Apple Silicon'):setup.preflight()
            version.assert_not_called()

    def test_duplicate_install_cannot_acquire_lock(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(worker,'REPORT',Path(directory)/'status.json'):
            with worker.exclusive_install():
                with self.assertRaisesRegex(ValueError,'Another Codex Usage'): 
                    with worker.exclusive_install():pass
            with worker.exclusive_install():pass

    def test_build_timeout_reaps_child_without_touching_app(self):
        with tempfile.TemporaryFile(mode='w+') as output:
            started=time.monotonic()
            with self.assertRaisesRegex(ValueError,'Codex was not closed'):
                setup.run_bounded([sys.executable,'-c','import os,time;print(os.getpid(),flush=True);time.sleep(30)'],timeout=.2,output=output)
            self.assertLess(time.monotonic()-started,6)
            output.seek(0);pid=int(output.read().strip())
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)

    def test_timeout_kills_surviving_child_after_leader_exits(self):
        child = 'import os,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print("child",os.getpid(),flush=True);time.sleep(30)'
        leader = ('import os,subprocess,sys,time;print("leader",os.getpid(),flush=True);'
                  'subprocess.Popen([sys.executable,"-c",' + repr(child) + ']);time.sleep(30)')
        with tempfile.TemporaryFile(mode='w+') as output:
            try:
                with self.assertRaisesRegex(ValueError,'Codex was not closed'):
                    setup.run_bounded([sys.executable,'-c',leader],timeout=.5,output=output)
                output.seek(0)
                pids = {name:int(pid) for name,pid in (line.split() for line in output.read().splitlines())}
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:os.kill(pids['child'],0)
                    except ProcessLookupError:break
                    time.sleep(.05)
                else:self.fail('Build descendant survived timeout cleanup')
                with self.assertRaises(ProcessLookupError):os.kill(pids['leader'],0)
            finally:
                output.seek(0)
                rows = dict(line.split() for line in output.read().splitlines())
                if 'leader' in rows:
                    try:os.killpg(int(rows['leader']),signal.SIGKILL)
                    except ProcessLookupError:pass

    def test_windows_entrypoints_refuse_before_posix_imports_or_signals(self):
        script = str(Path(setup.__file__).resolve())
        for arguments in [[],['--check'],['--accept','--confirm-rendered-ui','--confirm-quit-reopen']]:
            with self.subTest(arguments=arguments):
                source = '''import builtins,platform,runpy,signal,sys
platform.system=lambda:'Windows'
platform.machine=lambda:'AMD64'
original_import=builtins.__import__
def guarded_import(name,*args,**kwargs):
    if name=='fcntl':raise AssertionError('Unsupported OS imported fcntl')
    return original_import(name,*args,**kwargs)
builtins.__import__=guarded_import
if hasattr(signal,'SIGHUP'):del signal.SIGHUP
sys.path.insert(0,SCRIPT.rsplit('/',1)[0])
sys.argv=[SCRIPT]+ARGUMENTS
runpy.run_path(SCRIPT,run_name='__main__')
'''.replace('SCRIPT',repr(script)).replace('ARGUMENTS',repr(arguments))
                result = subprocess.run([sys.executable,'-B','-c',source],capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,1)
                self.assertEqual(result.stderr.strip(),'Stopped: This inspected build supports Apple Silicon macOS only.')

    def test_pending_update_reserves_protection_and_rollback_copy_space(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            app = root / 'ChatGPT.app'; app.mkdir()
            receipt = root / 'receipt.json'
            receipt.write_text(json.dumps({'version':setup.mod.VERSION,'state':'installed_pending_live_check',
                                          'candidate_sha256':'pending','preinstall_sha256':'working','candidate_fingerprint':'pending-fp'}))
            for key,value in [('APP',app),('ROOT',root),('SAFE',root/'missing-safe'),
                              ('PROTECTED',root/'missing-protected'),('RECEIPT',receipt)]:
                stack.enter_context(patch.object(setup.mod,key,value))
            stack.enter_context(patch.object(setup.mod,'app_version',return_value=setup.mod.VERSION))
            stack.enter_context(patch.object(setup.mod,'sha',return_value='pending'))
            stack.enter_context(patch.object(setup.mod,'codex_instances',return_value=[]))
            stack.enter_context(patch.object(setup.shutil,'which',return_value='/fixture/tool'))
            stack.enter_context(patch.object(setup.subprocess,'run',side_effect=lambda argv,**kw:Mock(stdout='v20.0.0' if '--version' in argv else '1024 fixture')))
            size = 1024*1024
            space = stack.enter_context(patch.object(setup.shutil,'disk_usage',return_value=Mock(free=3*size+128*1024*1024)))
            with self.assertRaisesRegex(ValueError,'Not enough free space'):setup.preflight()
            space.return_value.free = 4*size+128*1024*1024
            setup.preflight()

    def test_vendor_source_keeps_vendor_claims_only_before_local_signing(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Path(directory).resolve()/'ChatGPT.app';app.mkdir();framework=app/'Framework';framework.mkdir()
            row={'entitlements':{'com.apple.developer.team-identifier':'synthetic'},'adhoc':False,'team':'synthetic','flags':0x10000}
            with patch.object(signing,'targets',return_value=[framework,app]),patch.object(signing,'metadata',return_value=row),patch.object(signing.subprocess,'run') as check:
                observed=signing.verify_source(app,kind='vendor')
                self.assertIn('com.apple.developer.team-identifier',observed['.'])
                self.assertIn('anchor apple generic',check.call_args.args[0][-2])
            self.assertNotIn('com.apple.developer.team-identifier',signing.local_entitlements(row['entitlements']))

    def test_vendor_team_mismatch_rejected_before_candidate_signing(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Path(directory).resolve()/'ChatGPT.app';app.mkdir();helper=app/'Helper';helper.mkdir()
            rows=[{'entitlements':{},'adhoc':False,'team':team,'flags':0x10000} for team in ['one','two']]
            with patch.object(signing,'targets',return_value=[helper,app]),patch.object(signing,'metadata',side_effect=rows),patch.object(signing.subprocess,'run') as check:
                with self.assertRaisesRegex(ValueError,'teams differ'):signing.verify_source(app,kind='vendor')
                check.assert_not_called()


unittest.main(verbosity=2)
