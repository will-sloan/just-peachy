"""Eight focused HOST groups for actual Start continuation AST; README_SAME_START_CHECK.md."""
import argparse
import ast
import ctypes
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import time
import types
import uuid

HERE=Path(__file__).resolve().parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def strict(raw):
    def pairs(values):
        result={}
        for key,value in values:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))


def bootstrap():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,1<<14):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('same-start-check-'+uuid.uuid4().hex)
    root.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    (root/'REGISTERED_OWNER.json').write_bytes(encoded(owner))
    return root


def main():
    root=bootstrap()  # BEFORE all project/private failure reads.
    began=time.monotonic();written=(root/'REGISTERED_OWNER.json').stat().st_size
    def write(name,raw):
        nonlocal written
        if written+len(raw)>2*1024**2 or time.monotonic()-began>600:
            raise RuntimeError('Finite 2MiB/600s host check scope')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Original host floor')
        with (root/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short host check output')
            stream.flush();os.fsync(stream.fileno())
        if (root/name).read_bytes()!=raw:raise OSError('Independent host check readback differs')
        written+=len(raw)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--failure-inspection',type=Path,required=True)
    parser.add_argument('--source-owner-pid',type=int,required=True)
    parser.add_argument('--source-owner-ticks',type=int,required=True)
    parser.add_argument('--source-boot-id',required=True)
    args=parser.parse_args()
    write('HOST_SCOPE.json',encoded(dict(maximum_bytes=2*1024**2,maximum_seconds=600,
        native_action=False,synthetic_execution=True,issued_unix=time.time())))
    inputs={'CHECK.py':Path(__file__),'README.md':HERE/'README_SAME_START_CHECK.md',
        'LAUNCHER.py':HERE/'launcher.py',
        'READINESS.py':HERE.parent/'ui_restore_20261004/xvf_readiness.py',
        'HELPER.py':HERE.parent/'ui_restore_20261004/xvf_readiness_helper.py'}
    source={}
    for name,path in inputs.items():
        if path.is_symlink() or path.stat().st_size>262144:raise ValueError('Bounded real check source')
        raw=path.read_bytes();source[name]=raw
        for suffix in ('','.backup','.restore'):write(name+suffix,raw)
    write('SOURCE_CLOSED.json',encoded(dict(closed_unix=time.time(),independent_restores=True,
        inputs={name:hashlib.sha256(raw).hexdigest() for name,raw in source.items()},native_action=False)))
    if args.failure_inspection.is_symlink() or args.failure_inspection.stat().st_size>2*1024**2:
        raise ValueError('Bounded actual failure inspection required')
    inspection_raw=args.failure_inspection.read_bytes();inspection=strict(inspection_raw)
    records=inspection['action_result']['records']
    expected_owner=dict(pid=args.source_owner_pid,start_ticks=args.source_owner_ticks,boot_id=args.source_boot_id)
    matches=[]
    for row in records:
        if str(row.get('path','')).endswith('work/source/SOURCE_CLOSE.json') and type(row.get('text')) is str:
            raw=row['text'].encode()
            if len(raw)<=65536 and hashlib.sha256(raw).hexdigest()==row.get('sha256'):
                value=strict(raw)
                if value.get('owner')==expected_owner:matches.append((raw,value,row['sha256']))
    if len(matches)!=1:raise ValueError('Exactly one full hash-matching actual source fault required')
    fault_raw,physical,fault_sha=matches[0]
    write('ACTUAL_FAILURE_INPUT.json',encoded(dict(inspection_sha256=hashlib.sha256(inspection_raw).hexdigest(),
        source_sha256=fault_sha,source_bytes=len(fault_raw),source_owner=expected_owner,
        current_process_identity_claim=False,actual_native_receipt_read_only=True)))
    def extract(raw,name):
        nodes=[node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name==name]
        if len(nodes)!=1:raise ValueError('Exact AST function required: '+name)
        return nodes[0]
    qualifying_space={}
    exec(compile(ast.Module(body=[extract(source['READINESS.py'],'qualifying_fault')],type_ignores=[]),
        '<actual-retained-qualifying-fault>','exec'),qualifying_space)
    qualifying=qualifying_space['qualifying_fault']
    if not qualifying(physical):raise ValueError('Actual inspected failure must qualify without invented fields')

    # Every runtime control fixture below is IN MEMORY. No synthetic native
    # OWNER, closure, source, control or session files enter the evidence tree.
    class MemoryPath:
        files={};directories=set()
        def __init__(self,*parts):self.path=PurePosixPath(*(str(part) for part in parts))
        def __truediv__(self,name):return MemoryPath(self.path/str(name))
        def __str__(self):return str(self.path)
        def __eq__(self,other):return str(self)==str(other)
        def __hash__(self):return hash(str(self))
        @property
        def name(self):return self.path.name
        @property
        def parent(self):return MemoryPath(self.path.parent)
        def with_name(self,name):return MemoryPath(self.path.with_name(name))
        def absolute(self):return self
        def exists(self):return str(self) in self.files or str(self) in self.directories
        def is_dir(self):return str(self) in self.directories
        def is_symlink(self):return False
        def mkdir(self,*args,**kwargs):self.directories.add(str(self))
        def stat(self):return types.SimpleNamespace(st_size=len(self.read_bytes()))
        def read_bytes(self):return self.files[str(self)]
        def read_text(self):return self.read_bytes().decode()
        def touch(self,exist_ok=False):
            if self.exists() and not exist_ok:raise FileExistsError(str(self))
            self.files[str(self)]=b''
        def open(self,mode):
            path=self
            if 'x' in mode and self.exists():raise FileExistsError(str(self))
            class MemoryStream(io.BytesIO):
                def fileno(self):return -1
                def close(self):
                    if not self.closed:path.files[str(path)]=self.getvalue()
                    super().close()
            return MemoryStream()
    def publish(path,value,replace=False):
        if path.exists() and not replace:raise FileExistsError(str(path))
        MemoryPath.files[str(path)]=encoded(value)
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    class Event:
        def __init__(self):self.value=False
        def set(self):self.value=True
        def clear(self):self.value=False
        def is_set(self):return self.value
    class Thread:
        def __init__(self,target,**kwargs):self.target=target;self.started=False;self.done=False
        def start(self):self.started=True
        def finish(self):
            if not self.done:
                try:self.target()
                finally:self.done=True
        def join(self,*args):self.finish()
        def is_alive(self):return self.started and not self.done
    class Selection:
        def __init__(self,**values):self.__dict__.update(values)
        def validate(self):return dict(self.__dict__)
    class Policy:
        def __init__(self,**values):self.__dict__.update(values)
        def validate(self):return dict(self.__dict__)
        def maximum_samples(self):return 4800000
    class Process:
        def __init__(self,pid):self.pid=pid;self.stdout=io.BytesIO();self.returncode=None
        def poll(self):return self.returncode
        def wait(self):return self.returncode
    class Decoder:
        def __init__(self,*args):pass
        def feed(self,raw):pass
        def finish(self):pass
    synthetic_manager=dict(pid=900001,start_ticks=1,boot_id='00000000-0000-0000-0000-000000000001')
    fake_os=types.SimpleNamespace(name='nt',environ={},fsync=lambda fd:None,getpid=lambda:900002)
    fake_subprocess=types.SimpleNamespace(DEVNULL=-1,PIPE=-2,STDOUT=-3,Popen=type('NeverRealPopen',(),{}))
    manager_tree=next(node for node in ast.parse(source['LAUNCHER.py']).body
        if isinstance(node,ast.ClassDef) and node.name=='Manager')
    required={'readiness_pending','start','_readiness_fault','_previous_readiness_fault',
        '_begin_readiness','_poll_readiness','stop','poll'}
    methods=[node for node in manager_tree.body if isinstance(node,ast.FunctionDef) and node.name in required]
    if len(methods)!=len(required):raise ValueError('Exact eight current Manager method ASTs required')
    cls=ast.ClassDef(name='ManagerFixture',bases=[],keywords=[],body=methods,decorator_list=[])
    space=dict(Path=MemoryPath,strict=strict,encoded=encoded,publish=publish,digest=digest,
        RuntimeSelection=Selection,SessionPolicy=Policy,os=fake_os,subprocess=fake_subprocess,
        threading=types.SimpleNamespace(Thread=Thread),uuid=uuid,time=time,
        current_owner=lambda:dict(synthetic_manager),__file__='/synthetic/package/launcher.py')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),
        '<actual-manager-methods-with-memory-fixtures>','exec'),space)
    Manager=space['ManagerFixture']
    modules={
        'application_contract':dict(validate=lambda value,selection:value,default=lambda encoder:dict(mode='open_with_names')),
        'developer_replay':dict(validate_repeat=lambda *args:None,pin_repeat_input=lambda *args:None),
        'release_authorization':dict(authorize_session=lambda *args:{},require_service_room=lambda *args:None),
        'optional_refiner_dispatch':dict(request_receipt=lambda *args:None),
        'runtime_ui_channel':dict(StreamDecoder=Decoder),
        'xvf_readiness':dict(qualifying_fault=qualifying),
    }
    if set(modules)&set(sys.modules):raise ValueError('Fresh host fixture module namespace required')
    for name,values in modules.items():
        module=types.ModuleType(name);module.__dict__.update(values);sys.modules[name]=module
    rows=[]
    try:
        def make(prior=False):
            MemoryPath.files.clear();MemoryPath.directories.clear()
            obj=object.__new__(Manager);obj.data_root=MemoryPath('/synthetic/data');obj.launches=obj.data_root/'launches'
            obj.binding_path=MemoryPath('/synthetic/package/BINDING.json')
            MemoryPath.files[str(obj.binding_path)]=b'{}'
            obj.binding=dict(native_launch_enabled=True,python='synthetic-python')
            obj.unit='synthetic.service';obj.unit_ownership=None;obj.session_authorizer=obj.service_room_check=None
            obj.closed=False;obj.process=None;obj.export_task=None;obj.last=None
            obj._readiness_thread=None;obj._readiness_done=Event();obj._readiness_cancel=Event()
            obj._continuation_used=False;obj._resuming_start=False;obj._start_context=None
            obj._readiness_result=obj._readiness_error=None;obj._readiness_origin=None;obj.readiness_notice=None
            obj.stop_requested=None;obj.watchdog_requested=False;obj.spatial_visible=False
            obj.owner_probe=lambda owner:dict(closed=type(owner) is dict)
            obj.store=types.SimpleNamespace(root=MemoryPath('/synthetic/store'),
                _artifact_path=lambda sid,name:MemoryPath('/synthetic/store')/sid/name)
            obj._check_previous_launch=lambda:None
            obj._nested_source=lambda path:dict(closed=True,physical_receipt=physical)
            counts=dict(workers=0,helpers=0)
            def process_factory(*args,**kwargs):
                counts['workers']+=1
                return Process(900100+counts['workers'])
            obj.process_factory=process_factory
            def recover(manager):counts['helpers']+=1;return dict(status='SYNTHETIC_HELPER_CLOSED')
            sys.modules['xvf_readiness'].recover_previous_source=recover
            selection=Selection(diarizer='pyannote',embedding='redimnet',input_source='live',
                nemotron_profile='current_delayed',provisional_correction=False)
            policy=Policy(total_deadline_seconds=600,max_drain_seconds=20,cleanup_seconds=20)
            def close_worker(qualifies=True):
                sid='1'*32
                publish(obj.owner_dir/'REGISTERED_OWNER.json',dict(synthetic_manager,pid=obj.process.pid))
                publish(obj.owner_dir/'SESSION.json',dict(session_id=sid))
                MemoryPath.files[str(obj.store._artifact_path(sid,'work/source/SOURCE_CLOSE.json'))]=fault_raw
                obj._nested_source=lambda path:dict(closed=True,physical_receipt=physical if qualifies else dict(kind='CLOSED'))
                obj.process.returncode=1 if qualifies else 0
                return obj.poll()
            if prior:
                origin=obj.launches/('a'*32);publish(obj.data_root/'CURRENT_LAUNCH.json',dict(launch_id=origin.name))
                publish(origin/'REQUEST.json',dict(selection=selection.validate()))
                publish(origin/'worker/SESSION.json',dict(session_id='1'*32))
                MemoryPath.files[str(obj.store._artifact_path('1'*32,'work/source/SOURCE_CLOSE.json'))]=fault_raw
                publish(origin/'HOST_CLOSURE.json',dict(returncode=1,direct_child_reaped=True,
                    stdout_reader_joined=True,registered_owner=dict(synthetic_manager,pid=900099),
                    receipt_errors=[],output_error=None,nested_source=dict(closed=True,physical_receipt=physical)))
            return obj,selection,policy,counts,close_worker
        def check(name,fn):fn();rows.append(dict(name=name,status='PASS'))
        def previous_same_click():
            obj,selection,policy,counts,_=make(True);obj.start(selection,policy)
            assert obj.readiness_pending and obj.process is None and counts==dict(workers=0,helpers=0)
            obj._readiness_thread.finish();obj.poll()
            assert not obj.readiness_pending and obj.process is not None and counts==dict(workers=1,helpers=1)
            assert obj.request['selection']==selection.validate() and obj._continuation_used
        check('previous_exact_fault_one_helper_one_fresh_worker_same_Start',previous_same_click)
        def first_fault_same_click():
            obj,selection,policy,counts,close_worker=make();obj.start(selection,policy)
            close_worker();assert obj.readiness_pending and counts['workers']==1
            obj._readiness_thread.finish();obj.poll()
            assert counts==dict(workers=2,helpers=1) and obj.process is not None
        check('new_first_source_fault_closes_before_same_Start_continuation',first_fault_same_click)
        def cancel():
            obj,selection,policy,counts,_=make(True);obj.start(selection,policy);obj.stop()
            obj._readiness_thread.finish();result=obj.poll()
            assert counts['workers']==0 and not obj.readiness_pending and result['readiness_continuation']['cancelled']
        check('Stop_cancels_pending_request_and_prevents_fresh_worker',cancel)
        def second_fault():
            obj,selection,policy,counts,close_worker=make();obj.start(selection,policy);close_worker()
            obj._readiness_thread.finish();obj.poll();result=close_worker()
            assert counts==dict(workers=2,helpers=1) and not obj.readiness_pending and result is not None
        check('continued_worker_second_fault_has_no_retry_loop',second_fault)
        def healthy():
            obj,selection,policy,counts,close_worker=make();obj.start(selection,policy);close_worker(False)
            assert counts==dict(workers=1,helpers=0) and not obj.readiness_pending
        check('healthy_Live_has_no_readiness_helper',healthy)
        def saved():
            obj,selection,policy,counts,_=make(True);selection.input_source='saved'
            obj.start(selection,policy,'/synthetic/replay.wav')
            assert counts==dict(workers=1,helpers=0) and not obj.readiness_pending
        check('Saved_skips_prior_physical_fault_maintenance',saved)

        helper_space=dict(bounded=lambda path:MemoryPath(path).read_bytes(),strict=strict,
            hashlib=hashlib,math=math,time=time,re=re,Path=MemoryPath,os=fake_os,
            owner_closed=lambda owner:False)
        props=dict(MainPID='900001',InvocationID='synthetic-invocation',ControlGroup='/user.slice/test',
            ActiveState='active',AllowedCPUs='2-3',CPUQuotaPerSecUSec='2s',TasksMax='64',RuntimeMaxUSec='infinity')
        helper_space['subprocess']=types.SimpleNamespace(run=lambda *args,**kwargs:
            types.SimpleNamespace(stdout='\n'.join(key+'='+value for key,value in props.items())))
        exec(compile(ast.Module(body=[extract(source['HELPER.py'],'unit_checks')],type_ignores=[]),
            '<actual-unit-checks-with-synthetic-systemctl>','exec'),helper_space)
        unit_checks=helper_space['unit_checks']
        def unit_request(manual=True):
            MemoryPath.files['/proc/self/cgroup']=b'0::/user.slice/test\n'
            MemoryPath.files['/sys/fs/cgroup/user.slice/test/cgroup.procs']=b'900001 900002\n'
            receipt=dict(unit='synthetic.service',owner=synthetic_manager,main_pid=900001,
                invocation_id='synthetic-invocation',control_group='/user.slice/test',
                runtime_max_seconds=None if manual else 600,
                deadline_monotonic=None if manual else time.monotonic()+120,idle_timeout_seconds=300)
            if manual:receipt['lifetime_policy']='manual_stop_storage_guarded'
            path='/synthetic/unit.json';raw=encoded(receipt);MemoryPath.files[path]=raw
            return receipt,dict(unit='synthetic.service',manager_owner=synthetic_manager,
                unit_ownership=path,unit_ownership_sha256=hashlib.sha256(raw).hexdigest())
        def rejected(fn):
            try:fn()
            except (ValueError,RuntimeError):return
            raise AssertionError('Expected specific owned-unit rejection')
        def manual_units():
            receipt,request=unit_request();props['RuntimeMaxUSec']='infinity';unit_checks(request)
            props['RuntimeMaxUSec']='10min';rejected(lambda:unit_checks(request))
            props['RuntimeMaxUSec']='infinity';props['MainPID']='900999';rejected(lambda:unit_checks(request))
            props['MainPID']='900001'
            MemoryPath.files['/sys/fs/cgroup/user.slice/test/cgroup.procs']=b'900001 900002 900003'
            rejected(lambda:unit_checks(request))
        check('explicit_manual_None_lifetime_requires_actual_infinity_and_exact_members',manual_units)
        def finite_units():
            receipt,request=unit_request(False);props['RuntimeMaxUSec']='10min';unit_checks(request)
            props['RuntimeMaxUSec']='infinity';rejected(lambda:unit_checks(request))
            props['RuntimeMaxUSec']='9min';rejected(lambda:unit_checks(request))
            props['RuntimeMaxUSec']='10min';receipt['deadline_monotonic']=time.monotonic()+1
            raw=encoded(receipt);MemoryPath.files[request['unit_ownership']]=raw
            request['unit_ownership_sha256']=hashlib.sha256(raw).hexdigest();rejected(lambda:unit_checks(request))
        check('finite_lifetime_preserves_remaining_time_and_actual_runtime_checks',finite_units)
    finally:
        for name in modules:sys.modules.pop(name,None)
    if any(path.read_bytes()!=source[name] for name,path in inputs.items()):
        raise ValueError('Bound source changed during focused host check')
    if args.failure_inspection.read_bytes()!=inspection_raw:
        raise ValueError('Actual private failure inspection changed')
    receipt=dict(output=str(root),status='PASS_CHANGED_HOST_SAME_START_READINESS',groups=rows,
        positive_groups=len(rows),unit_rejects=6,actual_fault_sha256=fault_sha,
        source_hashes={name:hashlib.sha256(raw).hexdigest() for name,raw in source.items()},
        exact_current_Manager_method_AST=True,exact_current_unit_checks_AST=True,
        all_owners_helpers_units_processes_threads_runtime_paths_synthetic=True,
        synthetic_control_files_in_memory_only=True,native_action=False,
        native_start_or_reset_or_audio_or_model_proof=False,closed_unix=time.time(),elapsed=time.monotonic()-began)
    write('RESULT.json',encoded(receipt));print(encoded(receipt).decode())


if __name__=='__main__':
    sys.dont_write_bytecode=True
    main()
