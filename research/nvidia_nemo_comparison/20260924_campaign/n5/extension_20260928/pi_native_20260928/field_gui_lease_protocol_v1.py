"""Real installed launcher/lease boundary. README_FIELD_GUI_LEASE_V1.md."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import field_dependencies_v2 as pins
import field_candidate_transaction_v1 as transactions


def run(root, a):
    sys.dont_write_bytecode = True
    pins.configure_output(root,a['target_output_max_bytes'])
    installed = Path(a['installed_release'])
    rollback_release = Path(a['rollback_release'])
    sys.path.insert(0,str(installed))
    from release_tools import release as rt
    from release_tools.runtime_lock import RuntimeLock
    deployment = root/'deployment'
    (deployment/'transactions').mkdir(parents=True)
    (deployment/'staged').mkdir()
    data = root/'data'
    data.mkdir()
    rt.write_json(data/'DATA_SCHEMA.json',dict(schema_version=1))
    shutil.copyfile(root/'LIVE_CONFIG_BACKUP.json',data/'live_config.json')
    (data/'private-preservation-canary').write_bytes(b'PRIVATE_SYNTHETIC_CANARY\n')
    config = {'DATA_SCHEMA.json':pins.sha(data/'DATA_SCHEMA.json'),
              'live_config.json':a['live_config_sha256'],'n2_runtime.json':a['runtime_config_sha256']}
    descriptors = []
    for candidate in (rollback_release,installed):
        m = pins.read(candidate/'RELEASE_MANIFEST.json')
        d = dict(schema='just-peachy.retained-deployment.v1',version=m['version'],release=str(candidate),
                 resolved_release=str(candidate.resolve()),manifest_sha256=pins.sha(candidate/'RELEASE_MANIFEST.json'),
                 contract_sha256=pins.sha(candidate/'config/field_contract.json'),dependencies=a['retained_lock'],
                 dependencies_sha256=a['retained_lock_sha256'],candidate_root=str(deployment),data_root=str(data))
        path = root/(m['version']+'.deployment.json')
        pins.exclusive(path,d)
        descriptors.append(path)
    first,first_sha = transactions.activate(deployment,data,descriptors[0],pins.sha(descriptors[0]),None,rt)
    state,state_sha = transactions.activate(deployment,data,descriptors[1],pins.sha(descriptors[1]),first_sha,rt)
    outcomes = []
    def launch(case, command, expected=None, *, requested_state=None, altered_config=None, barriers=False):
        current,current_sha = transactions.inspect(deployment)
        before = {p.relative_to(deployment).as_posix():pins.sha(p) for p in deployment.rglob('*') if p.is_file()}
        d = pins.read(current['current']['descriptor'])
        spec = dict(case=case,command=command,run_admission_sha256=pins.sha(root/'ADMISSION.json'),
                    expires_unix=time.time()+90,candidate_root=str(deployment),data_root=str(data),
                    state_sha256=requested_state or current_sha,config_sha256=altered_config or config,
                    entry_sha256=pins.sha(Path(d['release'])/'native/field_entry_v5.py'),test_barriers=barriers,
                    release_manifest_sha256=pins.sha(Path(d['release'])/'RELEASE_MANIFEST.json'),
                    autonomous_quiet_authorized=True,authority_sha256=a['authority_sha256'],capture_allowed=False)
        spec_path = root/(case+'-launch.json')
        pins.exclusive(spec_path,spec)
        command_line = [sys.executable,'-B',str(root/'field_guarded_gui_launcher_v1.py'),'--launch',str(spec_path)]
        blocked = []
        with (root/(case+'.log')).open('xb') as log:
            proc = subprocess.Popen(command_line,stdout=log,stderr=subprocess.STDOUT)
            began = time.monotonic()
            try:
                for phase in ('before-entry','gui-active','after-entry') if barriers else ():
                    receipt = root/(case+'-'+phase+'.json')
                    while not receipt.exists():
                        if proc.poll() is not None:
                            raise RuntimeError('Launcher closed before '+phase)
                        if time.monotonic()-began > 45:
                            raise TimeoutError('Launcher entry barrier deadline')
                        time.sleep(.01)
                    event = pins.read(receipt)
                    assert event['owner']['pid'] == proc.pid
                    owner = pins.read(data/'runtime.lock')
                    assert owner['pid'] == proc.pid and owner['token'] == event['lease_token']
                    try:
                        transactions.rollback(deployment,data,current_sha,rt)
                    except RuntimeError as exc:
                        assert 'owns' in str(exc)
                        assert before == {p.relative_to(deployment).as_posix():pins.sha(p) for p in deployment.rglob('*') if p.is_file()}
                        blocked.append(dict(phase=phase,pid=proc.pid,lease_token=event['lease_token'],error=str(exc),state_unchanged=True))
                    else:
                        raise AssertionError('Updater acquired live launcher data')
                    pins.exclusive(root/(case+'-'+phase+'-continue.json'),dict(continue_phase=phase,owner_pid=proc.pid))
                code = proc.wait(timeout=60)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
                    pins.exclusive(root/(case+'-FORCED_CLOSE.json'),dict(pid=proc.pid,returncode=proc.returncode))
        result = pins.read(root/(case+'-RESULT.json'))
        if expected:
            assert code == 1 and not result['entered'] and expected in result['error'],result
        else:
            assert code == 0 and result['status']=='PASS_GUARDED_INSTALLED_GUI_IDLE_ONLY',result
            assert result['lease_continuous'] and result['lease_released'] and result['threads_closed']
            assert result['entry_output']['status']=='INSTALLED_GUI_IDLE_CLOSED'
            assert result['borrowers']==result['borrowers_closed']==1
        assert before == {p.relative_to(deployment).as_posix():pins.sha(p) for p in deployment.rglob('*') if p.is_file()}
        assert (root/(case+'.log')).stat().st_size < 128*1024
        receipt = dict(case=case,command=command,exit_code=code,result_sha256=pins.sha(root/(case+'-RESULT.json')),
                       state_sha256=current_sha,expected_rejection=expected,blocked_updates=blocked)
        pins.exclusive(root/(case+'-COLLECTED.json'),receipt)
        outcomes.append(receipt)
        return result
    shutil.copyfile(root/'N2_RUNTIME_BACKUP.json',data/'n2_runtime.json')
    assert pins.sha(data/'n2_runtime.json')==config['n2_runtime.json']
    launch('v7-gui-idle','gui',barriers=True)
    final,final_sha=transactions.inspect(deployment)
    assert final_sha==state_sha
    for name,expected in config.items():assert pins.sha(data/name)==expected
    assert (data/'private-preservation-canary').read_bytes()==b'PRIVATE_SYNTHETIC_CANARY\n'
    assert not (data/'runtime.lock').exists()
    assert (data/'.runtime.guard').read_bytes()==b''
    assert not (data/'source_receipts').exists()
    assert not list(data.rglob('*.wav'))
    assert not list(root.glob('*FORCED_CLOSE.json'))
    pins.exclusive(root/'LAUNCHER_CASES.json',dict(outcomes=outcomes,first=first,activated=state,final=final,
                   final_state_sha256=final_sha,configuration_sha256=config))
    return dict(status='PASS_GUARDED_INSTALLED_GUI_IDLE_LIFETIME_ONLY',
                cases=1,new_launches=1,real_entry_calls=1,blocked_updates=3,
                final_state_sha256=final_sha,configuration_sha256=config,models_loaded=False,capture_opened=False,
                GUI_opened=True,GUI_mapped_480x800=True,physical_touch=False,baseline_activated=False,
                assets_copied=False,release_copied=False,data_canary_unchanged=True,new_capture_samples=0)
