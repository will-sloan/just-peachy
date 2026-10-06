"""Focused Saved ownership closure fixtures; README_SAVED_SOURCE_CLOSURE.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import types
import uuid

HERE = Path(__file__).resolve().parent
Q = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE = Q/'audit-preparation/stabilization-package-41186a7a33004f1f8656e7be91e54e12/package'


def main():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    times = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(), *(ctypes.byref(item) for item in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    root = Q/'audit-preparation'/('saved-source-closure-check-'+uuid.uuid4().hex)
    root.mkdir(); started = time.monotonic(); written = 0
    def put(name, value):
        nonlocal written
        raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, allow_nan=False).encode()
        if written+len(raw)>2*1024**2 or time.monotonic()-started>600:
            raise RuntimeError('Finite 2MiB/600s host scope')
        for drive, floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw): raise OSError('Original host free floor')
        with (root/name).open('xb') as stream:
            if stream.write(raw)!=len(raw): raise OSError('Short host write')
            stream.flush(); os.fsync(stream.fileno())
        written += len(raw)
        if (root/name).read_bytes()!=raw: raise OSError('Independent readback mismatch')
    owner = dict(schema='just-peachy.host-registered-owner.v1', cpu=14, affinity_mask=16384,
        pid=os.getpid(), creation_filetime=times[0].value,
        create_time=(times[0].value-116444736000000000)/10000000)
    put('REGISTERED_OWNER.json', owner)
    put('HOST_SCOPE.json', dict(issued_unix=time.time(), expires_unix=time.time()+600,
        maximum_bytes=2*1024**2, native_actions=False))
    sources = {name:(HERE/name).read_bytes() for name in
        ('launcher.py','check_saved_source_closure.py','README_SAVED_SOURCE_CLOSURE.md')}
    old = (BASE/'launcher.py').read_bytes()
    if hashlib.sha256(old).hexdigest()!='adbaef0aa81a02ccba2e0ae43d5f1c3f3476cf9f1804c58b6e2e4f73b65d0de8':
        raise ValueError('Exact immutable build25 launcher baseline required')
    for name, raw in dict(sources, original_build25_launcher=old).items():
        for suffix in ('.backup','.restore'): put(name+suffix, raw)
    pins = {name:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in sources.items()}
    put('SOURCE_CLOSED.json', dict(files=pins, independent_restores=True, closed_unix=time.time(), native_action=False))
    def methods(raw):
        tree=ast.parse(raw)
        cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Manager')
        return {node.name:node for node in cls.body if isinstance(node,ast.FunctionDef)}
    before, after = methods(old), methods(sources['launcher.py'])
    changed = [name for name in before if ast.dump(before[name],include_attributes=False)!=ast.dump(after[name],include_attributes=False)]
    assert changed==['_nested_source'] and set(after)-set(before)=={'_saved_source'}
    nested=copy.deepcopy(after['_nested_source'])
    inserted=next(i for i,node in enumerate(nested.body) if isinstance(node,ast.Assign)
        and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='saved')
    del nested.body[inserted:inserted+2]
    assert ast.dump(nested,include_attributes=False)==ast.dump(before['_nested_source'],include_attributes=False)
    old_live=old.decode().split("        observed = facts.get('source_start_observed')",1)[1].split('    def _check_previous_launch',1)[0]
    new_live=sources['launcher.py'].decode().split("        observed = facts.get('source_start_observed')",1)[1].split('    def _saved_source',1)[0]
    assert old_live.rstrip()==new_live.rstrip()
    compile(sources['launcher.py'],str(HERE/'launcher.py'),'exec')
    support=ast.parse((BASE/'runtime_support.py').read_bytes())
    namespace=dict(json=json,Path=Path,hashlib=hashlib)
    funcs=[node for node in support.body if isinstance(node,ast.FunctionDef) and node.name in ('strict','encoded','digest')]
    klass=ast.ClassDef(name='Fixture',bases=[],keywords=[],body=[after['_nested_source'],after['_saved_source']],decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=funcs+[klass],type_ignores=[])),'<actual-saved-source-closure>','exec'),namespace)
    groups=[]; rejects=0
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        directory=Path(temporary); worker=directory/'worker'; worker.mkdir()
        sid='a'*32; kept='b'*32
        native_owner=dict(pid=121,start_ticks=421,boot_id='0561d730-3cad-48e0-940a-fe3930c89665')
        manager=namespace['Fixture']()
        manager.store=types.SimpleNamespace(_artifact_path=lambda identity,path:directory/identity/path)
        manager.owner_probe=lambda identity:dict(closed=True,state='EXACT_OWNER_ABSENT')
        selection=dict(input_source='saved',diarizer='pyannote',embedding='redimnet')
        policy=dict(maximum_session_seconds=70,max_drain_seconds=60,cleanup_seconds=30)
        req=dict(selection=selection,policy=policy,binding_sha256='c'*64,
            saved_path='D:/processed.wav',saved_session_id=None,saved_store_root=None,
            data_root='D:/recordings',application=dict(mode='caption_only'))
        facts=dict(input_source='saved',processed_samples=966400,source_start_observed=True,
            physical_start_packet_observed=False,owner=None,child_returncode=None,
            source_thread_joined=True,source_error=None,physical_process_closed=False)
        result=dict(session_id=sid,failure=None,logical_cleanup_complete=True,cleanup_attempted=True,
            cleanup_error=None,source_facts=facts,
            cleanup=dict(attempted=True,model_lanes_owned=False,logical_cleanup_complete=True,
                errors=[],completed=['source_stop_join','engine_lanes_writers_joined','saved_spatial_lease']),
            result=dict(status='FUNCTIONAL_SESSION_COMPLETED',selection=selection,source_policy=policy,
                source_samples=966400,saved_spatial=None))
        def write(request, receipt, child_extra=None):
            (directory/'REQUEST.json').write_bytes(namespace['encoded'](request))
            child=dict(pid=native_owner['pid'],child_owner=native_owner,
                request_sha256=namespace['digest'](directory/'REQUEST.json'))
            if child_extra: child.update(child_extra)
            for path,value in ((directory/'CHILD_LAUNCH.json',child),
                (worker/'REGISTERED_OWNER.json',native_owner),
                (worker/'ENVELOPE.json',dict(owner=native_owner,policy=request['policy'])),
                (worker/'SESSION.json',dict(session_id=sid,worker=native_owner)),(worker/'RESULT.json',receipt)):
                path.write_bytes(namespace['encoded'](value))
        write(req,result)
        actual=manager._nested_source(worker)
        assert actual['closed'] is True and actual['physical_microphone'] is False and actual['processed_samples']==966400
        groups.append('plain_wav_inprocess_worker_closure')
        rich=copy.deepcopy(req);rich.update(saved_path=None,saved_session_id=kept,saved_store_root='D:/recordings')
        write(rich,result);assert manager._nested_source(worker)['closed'] is True
        groups.append('kept_nonspatial_inprocess_worker_closure')
        rich['application']['mode']='spatial_assisted'
        spatial=copy.deepcopy(result)
        spatial['result']['saved_spatial']=dict(schema='just-peachy.saved-spatial-replay.v1',session_id=kept,
            metadata_sha256='d'*64,source_verified_after_drain=True,source_shared_lease_closed=True,current_motion_used=False)
        write(rich,spatial);assert manager._nested_source(worker)['closed'] is True
        groups.append('rich_recorded_spatial_join_verified_lease_closed')
        cases=[]
        for path,value in ((('source_facts','processed_samples'),True),(('source_facts','input_source'),'live'),
            (('source_facts','owner'),native_owner),(('source_facts','child_returncode'),0),
            (('source_facts','physical_start_packet_observed'),True),(('source_facts','source_thread_joined'),False),
            (('result','source_samples'),True),(('result','selection'),dict(input_source='live')),
            (('result','source_policy'),dict(maximum_session_seconds=True)),
            (('cleanup','completed'),['saved_spatial_lease']), (('cleanup','logical_cleanup_complete'),False),
            (('result','saved_spatial','source_verified_after_drain'),False),
            (('result','saved_spatial','source_shared_lease_closed'),False),
            (('result','saved_spatial','current_motion_used'),True),
            (('result','saved_spatial','metadata_sha256'),'unknown'),
            (('result','saved_spatial','session_id'),'e'*32), (('session_id',),'e'*32)):
            bad=copy.deepcopy(spatial);target=bad
            for key in path[:-1]: target=target[key]
            target[path[-1]]=value;cases.append((rich,bad,None))
        bad_req=copy.deepcopy(rich);bad_req['selection']['input_source']='live';cases.append((bad_req,spatial,None))
        bad_req=copy.deepcopy(rich);bad_req['saved_store_root']='D:/foreign';cases.append((bad_req,spatial,None))
        cases.append((rich,spatial,dict(request_sha256='f'*64)))
        for request,receipt,child_extra in cases:
            write(request,receipt,child_extra)
            assert manager._nested_source(worker)['closed'] is False
            rejects+=1
        source=directory/sid/'work/source';source.mkdir(parents=True)
        (source/'REGISTERED_OWNER.json').write_text('{}')
        write(rich,spatial);assert manager._nested_source(worker)['closed'] is False;rejects+=1
        (source/'REGISTERED_OWNER.json').unlink()
        manager.owner_probe=lambda identity:dict(closed=False,state='ALIVE')
        assert manager._nested_source(worker)['closed'] is False;rejects+=1
        manager.owner_probe=lambda identity:dict(closed=True,state='EXACT_OWNER_ABSENT')
        (worker/'RESULT.json').unlink();assert manager._nested_source(worker)['closed'] is False;rejects+=1
        groups.append('strict_request_result_types_identity_and_source_domains')
        failed=copy.deepcopy(result);failed.update(result=None,failure='saved reader failure preserved',logical_cleanup_complete=False)
        failed['source_facts']['source_thread_joined']=False
        write(req,failed);actual=manager._nested_source(worker)
        assert actual['closed'] is True and actual['logical_cleanup_complete'] is False and actual['failure']==failed['failure']
        setup=dict(result=None,failure='session initialization: rejected source',session_id=sid,logical_cleanup_complete=False)
        write(req,setup);actual=manager._nested_source(worker)
        assert actual['closed'] is True and actual['source_thread_joined'] is None and actual['processed_samples']==0
        groups.append('failed_and_pre_reader_saved_physical_closure_without_logical_success')
    inspection=json.loads((Q/'operation-saved27-failure-inspect-01/dispatch/RESULT.json').read_bytes())['action_result']
    facts=inspection['records']['worker/RESULT.json']['facts']
    assert inspection['status']=='CLOSED_SAVED27_FAILURE_READ_ONLY'
    assert facts['source_facts']['input_source']=='saved' and facts['source_facts']['processed_samples']==966400
    assert facts['source_facts']['source_thread_joined'] is True and facts['source_facts']['owner'] is None
    assert inspection['records']['worker/REGISTERED_OWNER.json']['exact_absent'] is True
    assert inspection['records']['session/work/source/REGISTERED_OWNER.json']['present'] is False
    assert inspection['records']['NESTED_CLOSURE_PENDING.json']['facts']['state']=='SOURCE_OWNER_RECEIPT_MISSING'
    put('AST_REVIEW.json',dict(changed_methods=changed,added_methods=['_saved_source'],live_body_bytes_unchanged=True))
    report=dict(status='PASS_SAVED_INPROCESS_SOURCE_CLOSURE',groups=groups,rejects=rejects,
        original_saved27_whole_job_failure_preserved=True,actual_saved27_inspection_sha256=hashlib.sha256(
            (Q/'operation-saved27-failure-inspect-01/dispatch/RESULT.json').read_bytes()).hexdigest(),
        tests='actual extracted launcher methods with controlled receipts/owner probe; actual Saved27 scalar inspection retained',
        files=pins,native_actions=False,output=str(root),owner=owner)
    put('RESULT.json',report);print(json.dumps(report,sort_keys=True))


if __name__=='__main__':main()
