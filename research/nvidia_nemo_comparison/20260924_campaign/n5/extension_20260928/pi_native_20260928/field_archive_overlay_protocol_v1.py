"""Changed installed archive policy boundary only; README_FIELD_ARCHIVE_OVERLAY_V1.md."""
import copy
import json
from pathlib import Path
import sys
import threading

def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)

def run(root,a):
    import field_archive_overlay_v1 as overlay
    sha=overlay.sha;descriptor=root/'OVERLAY_MANIFEST.json';expected=a['overlay_descriptor_sha256']
    doc=json.loads(descriptor.read_text());binding=overlay.verify(descriptor,expected)
    selected=binding['base'];sys.path[:0]=[str(selected),str(selected/'vendor'),str(selected/'native')]
    from release_tools.runtime_lock import RuntimeLock
    from app import paths
    data=root/'data';preserved={p.name:sha(p) for p in data.iterdir() if p.is_file()}
    owner=RuntimeLock(data,'archive_overlay_construction');raw=(data/'runtime.lock').read_bytes()
    original=paths.RuntimeLock;borrowed=dict(opened=0,closed=0)
    class Borrow:
        def __init__(self,path,purpose):
            if Path(path).resolve()!=data.resolve() or purpose!='application' or borrowed['opened']:raise RuntimeError('Invalid lease borrower')
            assert (data/'runtime.lock').read_bytes()==raw
            self.token=owner.token;self.closed=False;borrowed['opened']+=1
        def close(self):
            if not self.closed:self.closed=True;borrowed['closed']+=1
    paths.RuntimeLock=Borrow
    controller=None;archive=None;cases=[]
    def reject(name,fn):
        try:fn()
        except (ValueError,RuntimeError,FileNotFoundError) as e:row=dict(case=name,rejected=True,error=type(e).__name__+': '+str(e))
        else:raise AssertionError('Expected rejection: '+name)
        save(root/(name+'.json'),row);cases.append(row)
    try:
        for label in ['missing-budget','changed-budget-hash','missing-field','wrong-type','reserve-conflict','unreviewed-budget','contract-conflict','wrong-entry','wrong-session-origin','changed-module-hash','stale-descriptor']:
            fixture=root/'fixtures'/label;(fixture/'config').mkdir(parents=True)
            d=copy.deepcopy(doc);budget=copy.deepcopy(binding['budget']);contract=copy.deepcopy(binding['contract'])
            if label=='missing-field':budget.pop('detail_reserve_bytes')
            if label=='wrong-type':budget['metadata_input_bytes']=True
            if label=='reserve-conflict':budget['runtime_control_bytes']=65536
            if label=='unreviewed-budget':budget['metadata_input_bytes']=8*1024**2
            if label=='contract-conflict':contract['session_reservation_bytes']=32*1024**2
            if label=='wrong-entry':d['entry']=str(selected/'native/field_entry_v4.py')
            if label=='wrong-session-origin':d['modules']['app.sessions']['path']=str(selected/'app/sessions.py')
            if label=='changed-module-hash':d['modules']['app.sessions']['sha256']='0'*64
            if label!='missing-budget':
                save(fixture/'config/archive_budget.json',budget)
                d['budget_sha256']=sha(fixture/'config/archive_budget.json')
                contract['archive_budget']['sha256']=d['budget_sha256']
            if label=='changed-budget-hash':d['budget_sha256']='0'*64
            save(fixture/'config/field_contract.json',contract);d['contract_sha256']=sha(fixture/'config/field_contract.json')
            save(fixture/'OVERLAY_MANIFEST.json',d)
            bound='0'*64 if label=='stale-descriptor' else sha(fixture/'OVERLAY_MANIFEST.json')
            reject(label,lambda:overlay.create_controller(fixture/'OVERLAY_MANIFEST.json',bound,fixture/'must-not-publish'))
            assert not (fixture/'must-not-publish').exists() and borrowed['opened']==0
        health=overlay.health(descriptor,expected);save(root/'OVERLAY_HEALTH.json',health)
        controller=overlay.create_controller(descriptor,expected,data)
        assert controller.state=='IDLE' and controller.engine is None and controller.models.asr_loads==controller.models.speaker_loads==0
        store=controller.session_store
        assert store.archive_budget==store.policy['archive_budget']==binding['budget'] and store.contract==binding['contract']
        assert (data/'runtime.lock').read_bytes()==raw and borrowed==dict(opened=1,closed=0)
        from app import sessions
        origins=dict(sessions=str(Path(sessions.__file__).resolve()),controller=str(Path(sys.modules['app.controller'].__file__).resolve()),
                     pipeline=str(Path(sys.modules['app.pipeline'].__file__).resolve()),paths=str(Path(paths.__file__).resolve()),
                     store_parent=str(Path(sys.modules['field_archive_v3'].__file__).resolve()),budget=str(Path(sys.modules['field_archive_budget_v2'].__file__).resolve()))
        assert origins['sessions']==doc['modules']['app.sessions']['path'] and origins['budget']==doc['modules']['field_archive_budget_v2']['path']
        assert all(origins[k]==str(selected/'app'/f'{k}.py') for k in ['controller','pipeline','paths'])
        assert origins['store_parent']==str(selected/'native/field_archive_v3.py')
        original_budget=copy.deepcopy(store.policy['archive_budget']);store.policy['archive_budget']['metadata_input_bytes']=8*1024**2
        try:reject('store-policy-conflict',controller._artifact_limits_for_epoch)
        finally:store.policy['archive_budget']=original_budget
        limits=controller._artifact_limits_for_epoch();assert limits==store.policy['artifact_limits']
        reject('capture-unavailable',controller.start_live)
        reject('pipeline-start-unavailable',controller._start_session)
        reject('import-unavailable',lambda:store.import_archive('unqualified.zip'))
        reject('export-unavailable',lambda:store.export('none',root/'unqualified.zip'))
        identifier=store.new(audio=False,consent=False,title='Archive overlay propagation fixture; no audio')
        archive=store.begin(identifier,dict(synthetic_no_capture=True,overlay_descriptor_sha256=expected))
        assert archive.archive_budget==binding['budget'] and archive.artifact_limits==limits
        receipt=store.ended(identifier,archive);meta=json.loads((archive.path/'epoch.json').read_text())
        assert meta['state']=='CLOSED' and not meta['worker_alive'] and not meta['archive_error']
        assert meta['accepted_items']==meta['completed_items']==0 and meta['queue_items']==meta['queue_bytes']==0
        assert meta['archive_budget']==binding['budget'] and meta['archive_budget_sha256']==overlay.BUDGET_SHA
        assert not list(archive.path.glob('*.sqlite')) and not list(archive.path.glob('*.wav')) and not list(archive.path.glob('*.f32le'))
        assert not (data/'source_receipts').exists() and not (data/'sessions').exists()
        assert controller.models.asr_loads==controller.models.speaker_loads==0 and controller.engine is None
        result=dict(status='PASS_INSTALLED_RETAINED_ARCHIVE_OVERLAY_ONLY',rejections=cases,descriptor_sha256=expected,
                    budget_sha256=overlay.BUDGET_SHA,health=health,store_policy=store.policy,module_origins=origins,
                    archive_path=str(archive.path),archive_metadata_sha256=sha(archive.path/'epoch.json'),archive_receipt=receipt,
                    policy_before_epoch=True,engine_constructed=False,models=0,capture=False,GUI=False,audio=False,
                    lease_token=owner.token,base_release=str(selected),base_manifest_sha256=overlay.BASE_MANIFEST,
                    package_copied=False,catalogue_copied=False,pointer_activated=False)
    finally:
        if archive is not None and archive.thread.is_alive():archive.close()
        if controller is not None:
            if not controller.closed:controller.close()
            controller.commands.join();controller.worker.join(10)
            assert controller.closed and not controller.worker.is_alive()
        assert (data/'runtime.lock').read_bytes()==raw
        paths.RuntimeLock=original;owner.close()
        save(root/'OWNERSHIP_CLOSURE.json',dict(borrowed=borrowed,outer_released=True,controller_closed=bool(controller and controller.closed),
            worker_joined=bool(controller and not controller.worker.is_alive()),pending_commands=controller.commands.unfinished_tasks if controller else None))
    assert borrowed==dict(opened=1,closed=1) and not (data/'runtime.lock').exists()
    for name,h in preserved.items():assert sha(data/name)==h
    assert {p.relative_to(selected).as_posix():sha(p) for p in selected.rglob('*') if p.is_file()}==a['installed_files']
    assert not any(t.name in ('proto-session-archive','proto-controller','bounded-event-journal') for t in threading.enumerate())
    result.update(ownership_closed=True,base_unchanged=True,private_configs_unchanged=True)
    return result
