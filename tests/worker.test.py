"""Inject a failed startup; prove recovery restores the working mod, once."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import install_once as worker

with tempfile.TemporaryDirectory(prefix='codex-usage-worker-test-') as directory:
    root=Path(directory)
    for key,name in [('REPORT','status.json'),('GATE','gate.json'),('COMMAND','launch.command'),('RECEIPT','receipt.json')]:
        setattr(worker,key,root/name)
    receipt={'state':'candidate_verified','candidate_sha256':'new','preinstall_sha256':'working',
             'candidate_entitlements':{},'preinstall_entitlements':{},'candidate_fingerprint':'new-fp','preinstall_fingerprint':'working-fp','version':'fixture'}
    worker.RECEIPT.write_text(json.dumps(receipt))
    worker.GATE.write_text(json.dumps({'nonce':'test','candidate_sha256':'new'}))
    state={'phase':'old','installed':'working','candidate_launch_checks':0,'opens':0,'clock':0}
    def pids():
        if state['phase']=='old':return [10]
        if state['phase']=='candidate':
            state['candidate_launch_checks']+=1
            return [20] if state['candidate_launch_checks']==1 else []
        return [30] if state['phase']=='recovered-running' else []
    def kill(pid,sig):state['phase']='stopped'
    def install(rollback=False):state['installed']='working' if rollback else 'new'
    def run(argv,**kwargs):
        if argv[0]=='/usr/bin/open':
            state['opens']+=1
            state['phase']='candidate' if state['installed']=='new' else 'recovered-running'
    def sha(path):
        if path==worker.APP/worker.ASAR:return state['installed']
        if path==worker.NEW/worker.ASAR:return 'working' if state['installed']=='new' else 'new'
        return worker.BASELINE
    def clock():state['clock']+=2;return state['clock']
    chain=[{'pid':999,'executable':'/System/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal'}]
    with patch.object(worker,'running_app',pids),patch.object(worker,'verify_builds'),patch.object(worker,'CrashMonitor'),patch.object(worker,'codex_instances',side_effect=lambda:[{'pid':pid,'executable':worker.EXECUTABLE} for pid in ([] if state.get('phase')=='stopped' or not state.get('opens') and state.get('phase')!='old' else pids())]),patch.object(worker,'mapped_build_matches',return_value=True),patch.object(worker,'guard'),patch.object(worker,'verify_signing'),patch.object(worker,'sha',sha),patch.object(worker,'install',install),patch.object(worker,'ancestry',return_value=chain),patch.object(worker.os,'kill',kill),patch.object(worker.subprocess,'run',run),patch.object(worker.time,'monotonic',clock),patch.object(worker.time,'sleep'):
        try:worker.run('test',10);raise AssertionError('Expected failed startup')
        except ValueError as error:assert 'did not remain running' in str(error)
    report=json.loads(worker.REPORT.read_text())
    assert state['installed']=='working' and state['opens']==2
    assert report['state']=='recovered_relaunched_previous_mod'
    assert report['launch_count']==2 and report['new_main_pid']==30
    assert not worker.GATE.exists()
print('Failed candidate startup recovered to the verified mod with one recovery launch')

# Initially closed apps install without a PID-0 signal; stuck quits never exchange.
for scenario in ['initially-closed','stuck-quit']:
    with tempfile.TemporaryDirectory(prefix='codex-usage-worker-boundary-') as directory:
        root=Path(directory)
        for key,name in [('REPORT','status.json'),('GATE','gate.json'),('COMMAND','launch.command'),('RECEIPT','receipt.json')]:setattr(worker,key,root/name)
        worker.RECEIPT.write_text(json.dumps(receipt))
        state={'installed':'working','opens':0,'clock':0,'exchanges':0,'kills':[]}
        def pids():return [10] if scenario=='stuck-quit' else ([20] if state['opens'] else [])
        def kill(pid,sig):state['kills'].append(pid)
        def install(rollback=False):state.update(installed='working' if rollback else 'new',exchanges=state['exchanges']+1)
        def run(argv,**kwargs):
            if argv[0]=='/usr/bin/open':state['opens']+=1
        def sha(path):
            if path==worker.APP/worker.ASAR:return state['installed']
            if path==worker.NEW/worker.ASAR:return 'working' if state['installed']=='new' else 'new'
            return worker.BASELINE
        def clock():state['clock']+=2;return state['clock']
        with patch.object(worker,'running_app',pids),patch.object(worker,'verify_builds'),patch.object(worker,'CrashMonitor'),patch.object(worker,'codex_instances',side_effect=lambda:[{'pid':pid,'executable':worker.EXECUTABLE} for pid in ([10] if scenario=='stuck-quit' else ([20] if state['opens'] else []))]),patch.object(worker,'mapped_build_matches',return_value=True),patch.object(worker,'guard'),patch.object(worker,'verify_signing'),patch.object(worker,'sha',sha),patch.object(worker,'install',install),patch.object(worker,'app_version',return_value='fixture'),patch.object(worker,'ancestry',return_value=chain),patch.object(worker.os,'kill',kill),patch.object(worker.subprocess,'run',run),patch.object(worker.time,'monotonic',clock),patch.object(worker.time,'sleep'):
            if scenario=='stuck-quit':
                try:worker.run('boundary',10,auto_authorize=True);raise AssertionError('Expected quit refusal')
                except ValueError as error:assert 'did not stop' in str(error)
                assert state['exchanges']==0 and state['opens']==0
            else:
                worker.run('boundary',0,auto_authorize=True)
                assert state['kills']==[] and state['exchanges']==1 and state['opens']==1
                assert json.loads(worker.REPORT.read_text())['state']=='process_healthy_ui_pending'
print('Initially closed app installed once; stuck quit refused before replacement')
