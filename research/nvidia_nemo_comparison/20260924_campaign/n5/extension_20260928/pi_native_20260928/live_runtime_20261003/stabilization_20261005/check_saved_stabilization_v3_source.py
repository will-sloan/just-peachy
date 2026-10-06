"""CPU14 source/plan review; README_NATIVE_SAVED_STABILIZATION_CHECK_V3.md."""
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
args=parser.parse_args()
args.output.mkdir()
started=time.time();written=0
def put(name,raw):
    global written
    if not isinstance(raw,bytes):raw=json.dumps(raw,sort_keys=True,allow_nan=False).encode()
    if len(raw)>262144 or written+len(raw)>8*1024**2 or time.time()-started>30:
        raise ValueError('Bounded source/plan review required')
    with (args.output/name).open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short review publication')
        stream.flush();os.fsync(stream.fileno())
    written+=len(raw)
    if (args.output/name).read_bytes()!=raw:raise OSError('Review readback differs')
owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),
    create_time=(stamps[0].value-116444736000000000)/10000000,
    creation_filetime=stamps[0].value,cpu=14,affinity_mask=16384)
put('REGISTERED_OWNER.json',owner)
put('HOST_SCOPE.json',dict(issued_unix=started,maximum_seconds=30,maximum_bytes=8*1024**2,
    native_action=False,changed_source_and_pure_allocation_only=True))
import ast
import hashlib
import importlib.util
import sys
names=('native_saved_stabilization_check_v2.py','native_saved_stabilization_check_v3.py',
    'prepare_saved_stabilization_payload_v2.py','prepare_saved_stabilization_payload_v3.py',
    'README_NATIVE_SAVED_STABILIZATION_CHECK_V3.md','README_PREPARE_SAVED_STABILIZATION_V3.md',
    'check_saved_stabilization_v3_source.py')
pins=[];raws={};status='FAILED'
try:
    paths=[args.source/name for name in names]+[args.package_dir/name for name in
        ('PACKAGE_MANIFEST.json','BINDING.json','storage.py','profiles.py','release_authorization.py')]
    for index,path in enumerate(paths):
        raw=path.read_bytes()
        if path.is_symlink() or len(raw)>262144:raise ValueError('Finite actual source input required')
        put('SOURCE_%02d.backup'%index,raw)
        restore=(args.output/('SOURCE_%02d.backup'%index)).read_bytes()
        put('SOURCE_%02d.restore'%index,restore)
        if raw!=restore or path.read_bytes()!=raw:raise OSError('Independent source restore differs')
        raws[path.name]=raw
        pins.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    put('SOURCE_CLOSED.json',dict(pins=pins,closed_unix=time.time(),exact_backup=True,
        independent_restore=True,before_code_check=True))
    old=raws[names[0]];new=raws[names[1]]
    if hashlib.sha256(old).hexdigest()!='ca4570ca3411b743a20f4d510fb3065d149d2c9747bc10869c33d8ba8bfdc933':
        raise ValueError('Frozen Saved v2 differs')
    expected=old
    edits=((b'README_NATIVE_SAVED_STABILIZATION_CHECK_V2.md',b'README_NATIVE_SAVED_STABILIZATION_CHECK_V3.md'),
        (b'maximum_session_seconds=90',b'maximum_session_seconds=70'),
        (b'source_frames <= 90*16000',b'source_frames <= 70*16000'),
        (b'Complete kept <=90second source',b'Complete kept <=70second source'))
    for a,b in edits:
        if expected.count(a)!=1:raise ValueError('Exact70s helper transformation anchor required')
        expected=expected.replace(a,b)
    if expected!=new:raise ValueError('Unexpected Saved v3 helper bytes')
    helper_sha=hashlib.sha256(new).hexdigest()
    old_gen=raws[names[2]];new_gen=raws[names[3]]
    if hashlib.sha256(old_gen).hexdigest()!='0c776771867c2c9b5d32748b7db8730c9335abb44f7f6b43b5022dd063cde691':
        raise ValueError('Frozen generator v2 differs')
    expected_gen=old_gen
    gen_edits=((b'README_PREPARE_SAVED_STABILIZATION_V2.md',b'README_PREPARE_SAVED_STABILIZATION_V3.md'),
        (b'native_saved_stabilization_check_v2.py',b'native_saved_stabilization_check_v3.py'),
        (b'saved-stabilization-payload-v2-',b'saved-stabilization-payload-v3-'),
        (b'ca4570ca3411b743a20f4d510fb3065d149d2c9747bc10869c33d8ba8bfdc933',helper_sha.encode()),
        (b"source['processed_samples']<=90*16000",b"source['processed_samples']<=70*16000"))
    for a,b in gen_edits:
        if a not in expected_gen:raise ValueError('Exact70s generator transformation anchor required')
        expected_gen=expected_gen.replace(a,b)
    if expected_gen!=new_gen:raise ValueError('Unexpected Saved v3 generator bytes')
    def definitions(raw):
        result={}
        for node in ast.parse(raw.decode('utf-8',errors='strict')).body:
            if isinstance(node,ast.FunctionDef):result[node.name]=ast.dump(node,include_attributes=False)
            if isinstance(node,ast.ClassDef):
                for member in node.body:
                    if isinstance(member,ast.FunctionDef):
                        result[node.name+'.'+member.name]=ast.dump(member,include_attributes=False)
        return result
    a,b=definitions(old),definitions(new)
    changed={key for key in a if a[key]!=b[key]}
    if set(a)!=set(b) or changed!={'launch'}:raise ValueError('Unexpected Saved v3 function AST change')
    c,d=definitions(old_gen),definitions(new_gen)
    gen_changed={key for key in c if c[key]!=d[key]}
    if set(c)!=set(d) or gen_changed!={'main'}:raise ValueError('Unexpected generator function AST change')
    title='Just Peachy \u00b7 choose backend'
    for name in names[:2]:
        text=(args.source/name).read_text(encoding='utf-8',errors='strict')
        constants=[node.value for node in ast.walk(ast.parse(text)) if isinstance(node,ast.Constant)]
        if constants.count(title)!=1 or 'Just Peachy \u00c2\u00b7 choose backend' in constants:
            raise ValueError('Actual UTF8 title hook changed')
    for name in (names[1],names[3],names[6]):compile(raws[name],str(args.source/name),'exec')
    manifest_raw=raws['PACKAGE_MANIFEST.json']
    if hashlib.sha256(manifest_raw).hexdigest()!=args.package_manifest_sha256:
        raise ValueError('Actual package manifest pin differs')
    manifest=json.loads(manifest_raw)
    if manifest['target']!='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-24':
        raise ValueError('Actual build24 calculator sources required')
    for name in ('BINDING.json','storage.py','profiles.py','release_authorization.py'):
        row=next(row for row in manifest['files'] if row['path']==name)
        if row['bytes']!=len(raws[name]) or row['sha256']!=hashlib.sha256(raws[name]).hexdigest():
            raise ValueError('Actual package calculator/guard source pin differs')
    guard=ast.parse(raws['release_authorization.py'])
    if not any(isinstance(node,ast.BinOp) and isinstance(node.op,ast.Add) and
            isinstance(node.left,ast.Attribute) and node.left.attr=='total_deadline_seconds' and
            isinstance(node.right,ast.Constant) and node.right.value==150 for node in ast.walk(guard)):
        raise ValueError('Actual retained150-second remaining-time guard required')
    sys.dont_write_bytecode=True
    def load_pure(name):
        alias='saved70_plan_'+name
        spec=importlib.util.spec_from_file_location(alias,args.package_dir/(name+'.py'))
        module=importlib.util.module_from_spec(spec);sys.modules[alias]=module
        exec(compile(raws[name+'.py'],str(args.package_dir/(name+'.py')),'exec'),module.__dict__)
        return module
    storage=load_pure('storage');profiles=load_pure('profiles')
    binding=json.loads(raws['BINDING.json'])
    policy=profiles.SessionPolicy(maximum_session_seconds=70)
    policy_value=policy.validate()
    total=policy.total_deadline_seconds
    if total!=370 or total+150!=520:raise ValueError('Actual retained70s authorization arithmetic differs')
    spec=dict(sample_rate=16000,mode='processed',duration_seconds=70,
        metadata_reserve_bytes=16*1024**2+70*256*1024)
    stored=storage.StoragePolicy(**binding.get('storage_policy',{})).estimate_bytes(spec)
    plan=stored+32*1024**2
    if plan!=76536628 or plan>128*1024**2:raise ValueError('Actual complete70s processed plan differs or exceeds128MiB')
    for path in paths:
        if path.read_bytes()!=raws[path.name]:raise ValueError('Bound source changed during review')
    status='PASS_CHANGED_HOST_SAVED_70S_SOURCE_AND_PLAN'
    put('RESULT.json',dict(status=status,helper_sha256=helper_sha,helper_bytes=len(new),
        generator_sha256=hashlib.sha256(new_gen).hexdigest(),generator_bytes=len(new_gen),
        changed_helper_functions=sorted(changed),unchanged_helper_functions=len(a)-len(changed),
        changed_generator_functions=sorted(gen_changed),unchanged_generator_functions=len(c)-len(gen_changed),
        exact_source_transformations_verified=True,actual_utf8_title_verified=True,source_policy=policy_value,
        total_deadline_seconds=total,remaining_guard_reserve_seconds=150,required_remaining_seconds=520,
        unit_runtime_seconds=540,nominal_startup_allowance_seconds=20,driver_seconds=240,
        full_processed_storage_bytes=stored,helper_metadata_margin_bytes=32*1024**2,
        complete70s_plan_bytes=plan,independent_target_pc_reservation_bytes=128*1024**2,
        complete_plan_headroom_bytes=128*1024**2-plan,storage_spec=spec,
        pure_calculator_code_executed=True,session_store_constructed=False,native_tested=False,
        actual_source_admitted=False,source_trimming=False,host_bytes=written,seconds=time.time()-started))
    print(json.dumps(dict(status=status,output=str(args.output),helper_sha256=helper_sha,complete70s_plan_bytes=plan)))
finally:
    put('EXIT_INTENT.json',dict(owner=owner,status=status,physical_closure_claimed=False))
