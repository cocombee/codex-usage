"""Never confuse a stale mapped image or duplicate app with the installed build."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import startup_health
import install_once as worker


class LaunchIdentityTests(unittest.TestCase):
    def test_stale_same_path_inode_is_not_the_installed_build(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Path(directory).resolve()/'ChatGPT.app'
            paths=[app/'Contents/MacOS/ChatGPT',app/'Contents/Frameworks/Codex Framework.framework/Versions/Current/Codex Framework']
            for path in paths:path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
            output='p123\n'+''.join(f'i{path.stat().st_ino}\nn{path}\n' for path in paths)
            result=Mock(returncode=0,stdout=output)
            with patch.object(startup_health.subprocess,'run',return_value=result):
                self.assertTrue(startup_health.mapped_build_matches(123,app))
                result.stdout=output.replace('i'+str(paths[0].stat().st_ino),'i1')
                self.assertFalse(startup_health.mapped_build_matches(123,app))

    def test_already_reopened_verified_candidate_gets_no_second_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            receipt={'state':'candidate_verified','candidate_sha256':'new','preinstall_sha256':'working','candidate_entitlements':{},'preinstall_entitlements':{},'candidate_fingerprint':'new-fp','preinstall_fingerprint':'working-fp','version':'fixture'}
            state={'phase':'old','clock':0,'installed':'working'}
            def pids():return [10] if state['phase']=='old' else [20] if state['phase']=='new' else []
            def instances():return [{'pid':pid,'executable':worker.EXECUTABLE} for pid in pids()]
            def kill(pid,sig):state['phase']='closed'
            def install(rollback=False):state.update(phase='new',installed='new')
            def clock():state['clock']+=2;return state['clock']
            def sha(path):return state['installed'] if path==worker.APP/worker.ASAR else 'working' if path==worker.NEW/worker.ASAR else worker.BASELINE
            with patch.object(worker,'REPORT',root/'status.json'),patch.object(worker,'RECEIPT',root/'receipt.json'),patch.object(worker,'GATE',root/'gate.json'),patch.object(worker,'COMMAND',root/'command'),patch.object(worker,'running_app',pids),patch.object(worker,'codex_instances',instances),patch.object(worker,'mapped_build_matches',return_value=True),patch.object(worker,'verify_builds'),patch.object(worker,'guard'),patch.object(worker,'verify_signing'),patch.object(worker,'CrashMonitor'),patch.object(worker,'sha',sha),patch.object(worker,'install',install),patch.object(worker,'app_version',return_value='fixture'),patch.object(worker,'ancestry',return_value=[{'pid':999,'executable':'/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal'}]),patch.object(worker.os,'kill',kill),patch.object(worker.subprocess,'run') as launch,patch.object(worker.time,'monotonic',clock),patch.object(worker.time,'sleep'):
                worker.RECEIPT.write_text(json.dumps(receipt));worker.run('fixture',10,auto_authorize=True)
                launch.assert_not_called()
                report=json.loads(worker.REPORT.read_text())
                self.assertEqual(report['attached_existing_verified_pid'],20)
                self.assertEqual(report['launch_count'],0)
                self.assertEqual(report['state'],'process_healthy_ui_pending')


unittest.main(verbosity=2)
