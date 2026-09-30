"""New shutdown reserve boundaries only; README_FIELD_ARCHIVE_FINALIZATION_V1.md."""
import json,sys,time,types,hashlib
from pathlib import Path
import field_dependencies_v2 as pins
from field_archive_budget_v2 import validate,digest,encode_control

def run(root,a):
    pins.configure_output(root,a['target_output_max_bytes'])
    installed=Path(a['installed_release']);sys.path.insert(0,str(installed))
    from release_tools.runtime_lock import RuntimeLock
    derivation=json.loads((root/'ARCHIVE_FINALIZATION_DERIVATION_V1.json').read_text())
    base=root.parent/'field-archive-budget-v1/archive_budget_v1/app/sessions.py'
    assert pins.sha(base)==derivation['base_source_sha256'] and pins.sha(root/'archive_finalization_v1/app/sessions.py')==derivation['derivative_sha256']
    assert pins.sha(root/'field_archive_budget_v2.py')==derivation['helper_sha256']
    package=types.ModuleType('app');package.__path__=[str(root/'archive_finalization_v1/app'),str(installed/'app')];sys.modules['app']=package
    from app.sessions import EpochArchive,encoded
    limits=json.loads((installed/'config/artifact_limits.json').read_text())
    budget=validate(json.loads((root/'ARCHIVE_BUDGET_V2.json').read_text()))
    policy=dict(archive_budget=budget,artifact_limits=limits,quota_mib=512,free_floor_mib=5120,record_bytes=65536)
    cases=[]
    def save(name,**kw):
        value=dict(case=name,**kw);pins.exclusive(root/(name+'.json'),value);cases.append(value)
    def reject(name,fn):
        try:fn()
        except (ValueError,RuntimeError) as exc:save(name,rejected=True,error=type(exc).__name__+': '+str(exc))
        else:raise AssertionError('Missing rejection: '+name)
    for i,change in enumerate([dict(initial_control_bytes=32769),dict(runtime_control_bytes=True),dict(detail_file_bytes=262145),dict(auxiliary_bytes=1048575),dict(control_file_bytes=32768)]):
        bad=dict(budget,**change);pins.exclusive(root/f'invalid-{i}.json',bad)
        reject(f'reserve-{i}',lambda bad=bad:EpochArchive(root/f'must-not-publish-{i}',{},False,policy=dict(policy,archive_budget=bad)))
    reject('initial-over-reserve',lambda:EpochArchive(root/'must-not-publish-initial',{'padding':'x'*50000},False,policy=policy))
    assert not list(root.glob('must-not-publish*'))
    owner=RuntimeLock(root/'data','archive_finalization_fixtures');token=(root/'data/runtime.lock').read_bytes()
    def drained(x):
        end=time.monotonic()+10
        while x.queue.unfinished_tasks:
            if time.monotonic()>end:raise TimeoutError('Small fixture drain')
            time.sleep(.002)
    def check(x,name,expect_error=False):
        meta=json.loads((x.path/'epoch.json').read_text())
        assert meta['state']==('PARTIAL' if expect_error else 'CLOSED') and meta['closed'] and meta['worker_alive'] is False
        assert not x.thread.is_alive() and meta['queue_items']==meta['queue_bytes']==0
        assert meta['accepted_items']==meta['completed_items']==1
        assert (x.path/'epoch.json').stat().st_size<=65536 and not list(x.path.glob('.*.tmp'))
        sizes={q.name:q.stat().st_size for q in x.path.iterdir() if q.is_file()}
        assert sizes.get('failure.txt',0)<=262144 and sizes.get('checkpoint-detail.json',0)<=262144
        auxiliary=sum(sizes.get(n,0) for n in ['windows.jsonl','resources.jsonl','transforms.jsonl'])
        assert auxiliary==meta['auxiliary_bytes']<=1048576
        assert auxiliary+sizes.get('failure.txt',0)+2*sizes.get('checkpoint-detail.json',0)<=2097152
        assert not any('sqlite' in k for k in sizes)
        return dict(epoch=x.path.name,initial_bytes=len(encode_control(x._initial_control,32768)),final_bytes=sizes['epoch.json'],sizes=sizes,meta_sha256=pins.sha(x.path/'epoch.json'),accepted=1,completed=1,worker_closed=True,state=meta['state'])
    def create(i,padding):
        x=EpochArchive(root/'epochs'/format(i,'032x'),{'synthetic_no_capture':True,'padding':padding},False,policy=policy)
        assert x.offer('events',encoded(dict(kind='synthetic_finalization',index=i)));drained(x);assert x.error is None
        return x
    try:
        normal=create(1,'')
        try:normal.close();base_bytes=len(encode_control(normal._initial_control,32768));save('normal-reserved-close',**check(normal,'normal'))
        finally:
            if normal.thread.is_alive():normal.close()
        padding='x'*(32760-base_bytes)
        reason=('late synthetic failure \n quote=" unicode=é; '*2100)
        (root/'INPUT_failure.txt').write_bytes(reason.encode('utf-8'))
        failed=create(2,padding)
        try:
            failed.fail(reason,0);failed.close();meta=json.loads((failed.path/'epoch.json').read_text())
            assert (failed.path/'failure.txt').read_bytes()==reason.encode('utf-8')
            assert meta['failure_detail']['retained'] and meta['failure_detail']['sha256']==hashlib.sha256(reason.encode()).hexdigest()
            assert len(meta['archive_error'].encode())<1200 and not meta['diagnostic_retention_failed']
            assert 32752<=len(encode_control(failed._initial_control,32768))<=32768
            save('near-full-late-failure',**check(failed,'failure',True),raw_failure_sha256=pins.sha(failed.path/'failure.txt'))
        finally:
            if failed.thread.is_alive():failed.close()
        overflow=create(3,padding)
        try:
            overflow.metadata['late_detail']='y'*50000
            overflow.close();meta=json.loads((overflow.path/'epoch.json').read_text());detail=json.loads((overflow.path/'checkpoint-detail.json').read_text())
            assert detail['late_detail']=='y'*50000 and meta['control_metadata_overflow'] and meta['late_metadata_detail']['retained']
            assert meta['late_metadata_detail']['sha256']==pins.sha(overflow.path/'checkpoint-detail.json')
            assert 'late_detail' not in meta and meta['archive_error']=='ARCHIVE_CONTROL_RUNTIME_LIMIT'
            save('late-metadata-overflow',**check(overflow,'overflow',True),detail_sha256=pins.sha(overflow.path/'checkpoint-detail.json'))
        finally:
            if overflow.thread.is_alive():overflow.close()
        # An out-of-contract diagnostic cannot be presented as fully retained. The harness keeps the entire input privately.
        oversized='z'*262145;(root/'INPUT_oversized_failure.txt').write_bytes(oversized.encode())
        oversized_archive=create(4,padding)
        try:
            oversized_archive.fail(oversized,0)
            try:oversized_archive.close()
            except RuntimeError as exc:close_error=str(exc)
            else:raise AssertionError('Oversized diagnostic close must fail')
            meta=json.loads((oversized_archive.path/'epoch.json').read_text())
            assert meta['diagnostic_retention_failed'] and not meta['failure_detail']['retained'] and not (oversized_archive.path/'failure.txt').exists()
            assert meta['failure_detail']['bytes']==262145 and meta['failure_detail']['sha256']==pins.sha(root/'INPUT_oversized_failure.txt')
            save('diagnostic-retention-overflow',**check(oversized_archive,'diagnostic',True),close_error=close_error,full_fixture_retained=True)
        finally:
            if oversized_archive.thread.is_alive():oversized_archive.close()
        assert (root/'data/runtime.lock').read_bytes()==token
    finally:owner.close()
    assert not (root/'data/runtime.lock').exists() and 'sounddevice' not in sys.modules and 'sherpa_onnx' not in sys.modules
    pins.exclusive(root/'LEASE_CLOSED.json',dict(released=True,token=owner.token))
    return dict(status='PASS_NATIVE_RESERVED_ARCHIVE_FINALIZATION_ONLY',cases=cases,budget=budget,budget_sha256=digest(budget),capture=False,models=False,GUI=False,audio_generated=False,installed_integration=False,ownership_closed=True,full_maximum_files_exercised=False)
