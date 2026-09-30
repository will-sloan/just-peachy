"""Changed candidate/launcher boundary; README_FIELD_CHILD_DEADLINE_V1.md."""
import copy
from pathlib import Path
import subprocess
import sys
import time
import field_dependencies_v2 as pins
import field_child_deadline_v1 as deadlines
import field_overlay_deployment_v1 as adapter
import field_overlay_transaction_v1 as transactions

def run(root,a):
    pins.configure_output(root,a['target_output_max_bytes']);base=Path(a['installed_release'])
    sys.path[:0]=[str(base),str(base/'vendor'),str(base/'native')]
    from release_tools import release as rt
    data=root/'data';candidate=root/'deployment'
    (candidate/'transactions').mkdir(parents=True);(candidate/'staged').mkdir()
    pins.exclusive(data/'DATA_SCHEMA.json',dict(schema_version=1))
    config={n:pins.sha(data/n) for n in ['DATA_SCHEMA.json','live_config.json','n2_runtime.json']}
    row=dict(source=a['overlay_source'],source_sha256=a['overlay_source_sha256'],descriptor=a['overlay_descriptor'],descriptor_sha256=a['overlay_descriptor_sha256'])
    common=dict(schema='just-peachy.overlay-deployment.v1',release=str(base),manifest_sha256=a['release_manifest_sha256'],candidate_root=str(candidate),data_root=str(data),config_sha256=config,
                base_binding=dict(path=a['compact_binding'],sha256=a['compact_binding_sha256']))
    base_doc={**common,'version':'b01-offline-20260930-v12','overlay':None}
    overlay_doc={**common,'version':'b01-offline-20260930-v12+archive-budget-v2','overlay':row}
    cases=[]
    def inventory():return {q.relative_to(candidate).as_posix():pins.sha(q) for q in candidate.rglob('*') if q.is_file()}
    for label in ['overlay-source-sha','overlay-source-origin','overlay-descriptor-sha','extra-overlay-field','wrong-compact-binding','config-binding','overlay-version']:
        d=copy.deepcopy(overlay_doc)
        if label=='overlay-source-sha':d['overlay']['source_sha256']='0'*64
        elif label=='overlay-source-origin':d['overlay']['source']=str(base/'native/field_entry_v5.py')
        elif label=='overlay-descriptor-sha':d['overlay']['descriptor_sha256']='0'*64
        elif label=='extra-overlay-field':d['overlay']['capture_enabled']=True
        elif label=='wrong-compact-binding':d['base_binding']['path']=str(base/'config/field_contract.json')
        elif label=='config-binding':d['config_sha256']['n2_runtime.json']='0'*64
        elif label=='overlay-version':d['version']='unreviewed-overlay'
        path=root/(label+'.deployment.json');pins.exclusive(path,d);before=inventory()
        try:transactions.activate(candidate,data,path,pins.sha(path),None,rt)
        except ValueError as e:receipt=dict(case=label,rejected=True,error=str(e),candidate_unchanged=inventory()==before)
        else:raise AssertionError('Invalid adapter deployment accepted')
        assert receipt['candidate_unchanged'] and not (data/'runtime.lock').exists()
        pins.exclusive(root/(label+'-REJECTION.json'),receipt);cases.append(receipt)
    paths=[]
    for name,d in [('base',base_doc),('overlay',overlay_doc)]:
        path=root/(name+'.deployment.json');pins.exclusive(path,d);paths.append(path)
    first,first_sha=transactions.activate(candidate,data,paths[0],pins.sha(paths[0]),None,rt)
    selected,selected_sha=transactions.activate(candidate,data,paths[1],pins.sha(paths[1]),first_sha,rt)
    launches=[]
    def launch(case,expected=None,*,requested_state=None,requested_config=None,command='overlay-controller',barriers=False):
        state,state_sha=transactions.inspect(candidate);before=inventory()
        spec=dict(case=case,command=command,run_admission_sha256=pins.sha(root/'ADMISSION.json'),deadline=deadlines.create(a),
                  candidate_root=str(candidate),data_root=str(data),state_sha256=requested_state or state_sha,config_sha256=requested_config or config,test_barriers=barriers)
        path=root/(case+'-launch.json');pins.exclusive(path,spec);blocked=[]
        with (root/(case+'.log')).open('xb') as log:
            proc=deadlines.spawn([sys.executable,'-B',str(root/'field_overlay_launcher_v2.py'),'--launch',str(path)],spec['deadline'],a,stdout=log,stderr=subprocess.STDOUT)
            started=time.monotonic()
            try:
                for phase in ['before-entry','controller-active','after-entry'] if barriers else []:
                    event_path=root/(case+'-'+phase+'.json')
                    while not event_path.exists():
                        if proc.poll() is not None:raise RuntimeError('Launcher ended before '+phase)
                        if deadlines.remaining(spec['deadline'])<=0:raise deadlines.DeadlineExpired('Absolute launcher phase deadline')
                        time.sleep(.01)
                    event=pins.read(event_path);owner=pins.read(data/'runtime.lock')
                    assert event['owner']['pid']==proc.pid==owner['pid'] and event['lease_token']==owner['token']
                    try:transactions.rollback(candidate,data,state_sha,rt)
                    except RuntimeError as e:
                        assert 'owns' in str(e) and before==inventory()
                        blocked.append(dict(phase=phase,pid=proc.pid,lease_token=event['lease_token'],error=str(e),candidate_unchanged=True))
                    else:raise AssertionError('Update acquired running overlay data')
                    pins.exclusive(root/(case+'-'+phase+'-continue.json'),dict(continue_phase=phase,owner_pid=proc.pid))
                termination=deadlines.supervise(proc,spec['deadline'],a);code=proc.returncode
                pins.exclusive(root/(case+'-DEADLINE.json'),termination)
            finally:
                if proc.poll() is None:
                    termination=deadlines.supervise(proc,spec['deadline'],a,abort=True)
                    pins.exclusive(root/(case+'-FORCED_CLOSE.json'),termination)
        result=pins.read(root/(case+'-RESULT.json'))
        if expected:assert code==1 and not result['entered'] and expected in result['error'],result
        else:
            assert code==0 and result['status']=='PASS_GUARDED_RETAINED_OVERLAY_ONLY',result
            assert result['borrowers']==result['borrowers_closed']==1 and result['lease_continuous'] and result['threads_closed']
            assert result['dependency_check']['entries']==7890 and result['dependency_check']['archive_budget_sha256']=='d2cc2038e868f93dde009a9403feb259879bba4e8c0a05e760d1e14d087f86f8'
        assert before==inventory() and not (data/'runtime.lock').exists()
        assert (root/(case+'.log')).stat().st_size<128*1024
        receipt=dict(case=case,exit_code=code,expected_rejection=expected,result_sha256=pins.sha(root/(case+'-RESULT.json')),state_sha256=state_sha,blocked_updates=blocked)
        pins.exclusive(root/(case+'-COLLECTED.json'),receipt);launches.append(receipt)
    launch('stale-overlay-state','candidate state changed',requested_state='0'*64)
    launch('overlay-config-conflict','configuration differs',requested_config={**config,'n2_runtime.json':'0'*64})
    launch('capture-command','Only no-capture',command='gui')
    launch('guarded-overlay',barriers=True)
    final,final_sha=transactions.rollback(candidate,data,selected_sha,rt)
    assert final['current']==first['current'] and final['previous']==selected['current']
    launch('rollback-overlay-refused','no archive overlay; no fallback')
    assert transactions.inspect(candidate)==(final,final_sha)
    assert len(list((candidate/'transactions').glob('*.json')))==3 and not list((candidate/'staged').iterdir())
    for n,h in config.items():assert pins.sha(data/n)==h
    assert not list(root.glob('*FORCED_CLOSE.json')) and not (data/'source_receipts').exists() and not (data/'sessions').exists()
    assert not list(data.rglob('*.wav')) and not list(data.rglob('epoch.json'))
    assert {q.relative_to(base).as_posix():pins.sha(q) for q in base.rglob('*') if q.is_file()}==a['installed_files']
    pins.exclusive(root/'ADAPTER_CASES.json',dict(rejections=cases,launches=launches,first=first,selected=selected,final=final,final_state_sha256=final_sha,config_sha256=config))
    return dict(status='PASS_COMPACT_OVERLAY_TRANSACTION_AND_GUARDED_ENTRY_ONLY',prepublication_rejections=len(cases),launch_rejections=4,
                new_controller_entries=1,blocked_updates=3,committed_records=3,final_state_sha256=final_sha,models=False,capture=False,GUI=False,
                audio=False,engine=False,epoch_created=False,baseline_activated=False,base_unchanged=True,catalogue_copied=False,release_copied=False,
                exact_configs=True,ownership_closed=True,entry_closed=True)
