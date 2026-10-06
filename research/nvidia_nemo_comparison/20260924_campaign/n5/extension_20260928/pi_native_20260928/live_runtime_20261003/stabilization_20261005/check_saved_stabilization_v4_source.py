"""Changed SavedV4 source/plan review; README_NATIVE_SAVED_STABILIZATION_CHECK_V4.md."""
import ctypes
import os
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
handle=kernel.GetCurrentProcess()
if not kernel.SetProcessAffinityMask(handle,1<<14):raise ctypes.WinError(ctypes.get_last_error())
stamps=[ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())
import argparse
import json
import time
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--package-dir',type=Path,required=True)
parser.add_argument('--package-manifest-sha256',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();args.output.mkdir();started=time.time();written=0
def put(name,value):
    global written
    raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,allow_nan=False).encode()
    if len(raw)>262144 or written+len(raw)>8*1024**2 or time.time()-started>30:
        raise ValueError('Bounded changed-source review required')
    with (args.output/name).open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short review publication')
        stream.flush();os.fsync(stream.fileno())
    written+=len(raw)
    if (args.output/name).read_bytes()!=raw:raise OSError('Exact review readback differs')
owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),
    create_time=(stamps[0].value-116444736000000000)/10000000,
    creation_filetime=stamps[0].value,cpu=14,affinity_mask=16384)
put('REGISTERED_OWNER.json',owner)
put('HOST_SCOPE.json',dict(issued_unix=started,maximum_seconds=30,maximum_bytes=8*1024**2,
    native_action=False,changed_source_and_pure_allocation_only=True))
import ast
import copy
import hashlib
import importlib.util
import sys
from types import SimpleNamespace
status='FAILED';pins=[];raws={}
def definitions(raw):
    result={}
    for node in ast.parse(raw.decode('utf-8')).body:
        if isinstance(node,ast.FunctionDef):result[node.name]=ast.dump(node,include_attributes=False)
        elif isinstance(node,ast.ClassDef):
            for member in node.body:
                if isinstance(member,ast.FunctionDef):result[node.name+'.'+member.name]=ast.dump(member,include_attributes=False)
    return result
def load_pure(name):
    alias='saved4_source_'+name
    module=importlib.util.module_from_spec(importlib.util.spec_from_loader(alias,loader=None))
    sys.modules[alias]=module
    exec(compile(raws[str(args.package_dir/(name+'.py'))],str(args.package_dir/(name+'.py')),'exec'),module.__dict__)
    return module
try:
    names=('native_saved_stabilization_check_v3.py','native_saved_stabilization_check_v4.py',
        'prepare_saved_stabilization_payload_v3.py','prepare_saved_stabilization_payload_v4.py',
        'README_NATIVE_SAVED_STABILIZATION_CHECK_V4.md','README_PREPARE_SAVED_STABILIZATION_V4.md',
        'check_saved_stabilization_v4_source.py')
    package_names=('PACKAGE_MANIFEST.json','BINDING.json','storage.py','profiles.py','worker.py','release_authorization.py')
    paths=[args.source/name for name in names]+[args.package_dir/name for name in package_names]
    for index,path in enumerate(paths):
        raw=path.read_bytes()
        if path.is_symlink() or len(raw)>262144:raise ValueError('Finite regular source required')
        put('SOURCE_%02d.backup'%index,raw)
        restored=(args.output/('SOURCE_%02d.backup'%index)).read_bytes()
        put('SOURCE_%02d.restore'%index,restored)
        if raw!=restored or path.read_bytes()!=raw:raise OSError('Independent source restore differs')
        raws[str(path)]=raw
        pins.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    put('SOURCE_CLOSED.json',dict(pins=pins,closed_unix=time.time(),exact_backup=True,independent_restore=True,before_execution=True))
    old,new=(raws[str(args.source/name)] for name in names[:2])
    if hashlib.sha256(old).hexdigest()!='c52e95bcd8d0afda733ad93c37a535423aae5ec0e01348d3adb60a39ec5ba5c4':
        raise ValueError('Frozen SavedV3 source drift')
    a,b=definitions(old),definitions(new)
    changed={key for key in a if a[key]!=b[key]}
    if set(a)!=set(b) or changed!={'launch','ClassicDriver.source_snapshot'}:
        raise ValueError('Unexpected SavedV4 method AST changes: '+repr(changed))
    old_gen,new_gen=(raws[str(args.source/name)] for name in names[2:4])
    if hashlib.sha256(old_gen).hexdigest()!='556a00cdfcb12fc0b285478edd5abc6ff5865fcc4bdd928d758c6a07a54fe07d':
        raise ValueError('Frozen preparerV3 source drift')
    c,d=definitions(old_gen),definitions(new_gen)
    gen_changed={key for key in c if c[key]!=d[key]}
    if set(c)!=set(d) or gen_changed!={'main','validated'}:
        raise ValueError('Unexpected preparerV4 method AST changes: '+repr(gen_changed))
    helper_sha=hashlib.sha256(new).hexdigest()
    gen_tree=ast.parse(new_gen.decode('utf-8'))
    constants={node.targets[0].id:node.value.value for node in gen_tree.body
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)
        and isinstance(node.value,ast.Constant)}
    if constants.get('HELPER_PIN')!=helper_sha:raise ValueError('Actual helper pin differs')
    if 'Just Peachy \u00b7 choose backend' not in [node.value for node in ast.walk(ast.parse(new)) if isinstance(node,ast.Constant)]:
        raise ValueError('Actual retained UTF8 chooser title required')
    for name in (names[1],names[3],names[6]):compile(raws[str(args.source/name)],str(args.source/name),'exec')
    manifest_raw=raws[str(args.package_dir/'PACKAGE_MANIFEST.json')]
    if hashlib.sha256(manifest_raw).hexdigest()!=args.package_manifest_sha256:raise ValueError('Actual package manifest pin differs')
    manifest=json.loads(manifest_raw)
    if manifest['target']!='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-25':
        raise ValueError('Selected actual build25 package required')
    for name in package_names[1:]:
        raw=raws[str(args.package_dir/name)]
        row=next(row for row in manifest['files'] if row['path']==name)
        if row['bytes']!=len(raw) or row['sha256']!=hashlib.sha256(raw).hexdigest():
            raise ValueError('Actual package source pin differs: '+name)
    if hashlib.sha256(raws[str(args.package_dir/'storage.py')]).hexdigest()!='9205d10b63eb7e1a0ee60c2a539a292ae4977e8a73b71a1cd7aafca672bc2d6a':
        raise ValueError('Frozen repaired storage source required')
    sys.dont_write_bytecode=True
    storage=load_pure('storage');profiles=load_pure('profiles');worker=load_pure('worker')
    policy=profiles.SessionPolicy(maximum_session_seconds=70)
    if policy.total_deadline_seconds+150!=520:raise ValueError('Retained time guard changed')
    worker_tree=ast.parse(raws[str(args.package_dir/'worker.py')])
    spec_node=next(node.value for node in ast.walk(worker_tree) if isinstance(node,ast.Assign)
        and any(isinstance(target,ast.Name) and target.id=='spec' for target in node.targets)
        and isinstance(node.value,ast.Call) and any(key.arg=='metadata_split' for key in node.value.keywords))
    worker_spec_fields={key.arg:key.value for key in spec_node.keywords}
    def evaluate(node):return eval(compile(ast.Expression(node),'<pinned-pure-worker-spec>','eval'),{'__builtins__':{}},{'policy':policy})
    reserve=evaluate(worker_spec_fields['metadata_reserve_bytes'])
    terminal=evaluate(worker_spec_fields['terminal_metadata_reserve_bytes'])
    split=evaluate(worker_spec_fields['metadata_split'])
    if (reserve,terminal,split)!=(70254592,262144,'text1_sqlite1_v2'):
        raise ValueError('Actual worker/helper repaired spec differs')
    spec=dict(sample_rate=16000,mode='processed',duration_seconds=70,metadata_reserve_bytes=reserve,
        terminal_metadata_reserve_bytes=terminal,metadata_split=split)
    binding=json.loads(raws[str(args.package_dir/'BINDING.json')])
    storage_policy=storage.StoragePolicy(**binding.get('storage_policy',{}))
    stored=storage_policy.estimate_bytes(spec);plan=stored+32*1024**2;full=256*1024**2
    if (stored,plan)!=(78371636,111926068):raise ValueError('Actual repaired complete70s processed plan differs')
    actual_fn=next(node for node in worker_tree.body if isinstance(node,ast.FunctionDef) and node.name=='file_size_plan')
    class FixturePath:
        def __init__(self,size):self.size=size;self.parents=[]
        def __truediv__(self,name):return self
        def is_symlink(self):return False
        def exists(self):return True
        def stat(self):return SimpleNamespace(st_size=self.size)
    observed=[]
    for existing in (0,116916224,116916225):
        namespace={'Path':lambda root,size=existing:FixturePath(size)}
        exec(compile(ast.Module(body=[copy.deepcopy(actual_fn)],type_ignores=[]),'<actual-worker-allocator>','exec'),namespace)
        result=namespace['file_size_plan']('synthetic-owned-recordings',reserve+terminal,storage_policy,
            usage=SimpleNamespace(total=31268536320,free=14*1024**3))
        observed.append(dict(existing_history_bytes=existing,file_limit_bytes=result['file_limit_bytes'],fits256MiB=result['file_limit_bytes']<=full))
    if [row['fits256MiB'] for row in observed]!=[True,True,False] or observed[0]['file_limit_bytes']!=151519232:
        raise ValueError('Growing-history allocation boundary differs')
    for path in paths:
        if path.read_bytes()!=raws[str(path)]:raise ValueError('Source changed after backup')
    status='PASS_CHANGED_HOST_SAVED_STORAGE_AND_GROWING_HISTORY_PLAN'
    put('RESULT.json',dict(status=status,helper_sha256=helper_sha,helper_bytes=len(new),
        generator_sha256=hashlib.sha256(new_gen).hexdigest(),generator_bytes=len(new_gen),
        changed_helper_methods=sorted(changed),unchanged_helper_methods=len(a)-len(changed),
        changed_generator_methods=sorted(gen_changed),unchanged_generator_methods=len(c)-len(gen_changed),
        actual_worker_spec_verified=True,storage_spec=spec,full_processed_storage_bytes=stored,
        helper_margin_bytes=32*1024**2,complete70s_processed_plan_bytes=plan,
        independent_target_pc_reservation_bytes=full,allocator_synthetic_boundary_cases=observed,
        allocator_inputs_are_synthetic=True,actual_current_native_history_measured=False,
        native_tested=False,source_admitted=False,payload_issued=False,source_trimming=False,
        session_store_constructed=False,host_bytes=written,seconds=time.time()-started))
    print(json.dumps(dict(status=status,output=str(args.output),helper_sha256=helper_sha)))
finally:
    put('EXIT_INTENT.json',dict(owner=owner,status=status,physical_closure_claimed=False))
