"""CPU14 source-only review; README_NATIVE_SAVED_STABILIZATION_CHECK_V2.md.

Review only the new 90s/128MiB/240s instrumentation derivatives. No Pi contact.
"""
import ctypes
import os
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
handle=kernel.GetCurrentProcess()
if not kernel.SetProcessAffinityMask(handle,1<<14):
    raise ctypes.WinError(ctypes.get_last_error())
stamps=[ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())
import argparse
import json
import time
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir()
started=time.time()
written=0
def put(name,raw):
    global written
    if not isinstance(raw,bytes):
        raw=json.dumps(raw,sort_keys=True,allow_nan=False).encode()
    if len(raw)>262144 or written+len(raw)>8*1024**2 or time.time()-started>30:
        raise ValueError('Bounded source check bytes/time required')
    with (args.output/name).open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short host check publication')
        stream.flush();os.fsync(stream.fileno())
    written+=len(raw)
    if (args.output/name).read_bytes()!=raw:raise OSError('Host check readback differs')
owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),
    create_time=(stamps[0].value-116444736000000000)/10000000,
    creation_filetime=stamps[0].value,cpu=14,affinity_mask=16384)
put('REGISTERED_OWNER.json',owner)
put('HOST_SCOPE.json',dict(issued_unix=started,maximum_bytes=8*1024**2,
    maximum_seconds=30,native_action=False,changed_source_only=True))
import ast
import hashlib
names=('native_saved_stabilization_check.py','native_saved_stabilization_check_v2.py',
    'prepare_saved_stabilization_payload_v1.py','prepare_saved_stabilization_payload_v2.py',
    'README_NATIVE_SAVED_STABILIZATION_CHECK_V2.md','README_PREPARE_SAVED_STABILIZATION_V2.md',
    'check_saved_stabilization_v2_source.py')
pins=[];sources={}
status='FAILED'
try:
    for index,name in enumerate(names):
        path=args.source/name
        raw=path.read_bytes()
        if path.is_symlink() or len(raw)>128*1024:raise ValueError('Finite actual source required')
        put('SOURCE_%02d.backup'%index,raw)
        restored=(args.output/('SOURCE_%02d.backup'%index)).read_bytes()
        put('SOURCE_%02d.restore'%index,restored)
        if raw!=restored or raw!=path.read_bytes():raise OSError('Independent source restore differs')
        sources[name]=raw
        pins.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    put('SOURCE_CLOSED.json',dict(closed_unix=time.time(),pins=pins,exact_backup=True,
        independent_restore=True,before_code_check=True))
    old=sources['native_saved_stabilization_check.py']
    if hashlib.sha256(old).hexdigest()!='35c0a3c2206be240b065ac91e018a4263385be39d55669b8297e02aac67c06fd':
        raise ValueError('Frozen source helper differs')
    expected=old
    edits=((b'README_NATIVE_SAVED_STABILIZATION_CHECK.md',b'README_NATIVE_SAVED_STABILIZATION_CHECK_V2.md'),
        (b'if total > 96*MIB:',b'if total > 128*MIB:'),
        (b'maximum_session_seconds=30',b'maximum_session_seconds=90'),
        (b'source_frames <= 30*16000',b'source_frames <= 90*16000'),
        (b'Complete kept <=30second source',b'Complete kept <=90second source'),
        (b'full = 96*MIB',b'full = 128*MIB'),
        (b'Exact independent96MiB native',b'Exact independent128MiB native'),
        (b'driver_seconds=180,',b'driver_seconds=240,'))
    for a,b in edits:
        if expected.count(a)!=1:raise ValueError('Exact source helper anchor required')
        expected=expected.replace(a,b)
    new=sources['native_saved_stabilization_check_v2.py']
    if new!=expected:raise ValueError('Unexpected source helper change')
    helper_sha=hashlib.sha256(new).hexdigest()
    old_gen=sources['prepare_saved_stabilization_payload_v1.py']
    if hashlib.sha256(old_gen).hexdigest()!='b4f13bc106c9c45b2d3ca087ed979eb1377706a44cba152addd8e8f61c015988':
        raise ValueError('Frozen payload generator differs')
    expected_gen=old_gen
    gen_edits=((b'README_PREPARE_SAVED_STABILIZATION.md',b'README_PREPARE_SAVED_STABILIZATION_V2.md'),
        (b'RESERVATION = 96*MIB',b'RESERVATION = 128*MIB'),
        (b'35c0a3c2206be240b065ac91e018a4263385be39d55669b8297e02aac67c06fd',helper_sha.encode()),
        (b'saved-stabilization-payload-v1-',b'saved-stabilization-payload-v2-'),
        (b'native_saved_stabilization_check.py',b'native_saved_stabilization_check_v2.py'),
        (b"source['processed_samples']<=30*16000",b"source['processed_samples']<=90*16000"))
    for a,b in gen_edits:
        if a not in expected_gen:raise ValueError('Exact generator anchor required')
        expected_gen=expected_gen.replace(a,b)
    new_gen=sources['prepare_saved_stabilization_payload_v2.py']
    if new_gen!=expected_gen:raise ValueError('Unexpected generator change')
    def definitions(raw):
        result={}
        for node in ast.parse(raw).body:
            if isinstance(node,ast.FunctionDef):result[node.name]=ast.dump(node,include_attributes=False)
            if isinstance(node,ast.ClassDef):
                for member in node.body:
                    if isinstance(member,ast.FunctionDef):
                        result[node.name+'.'+member.name]=ast.dump(member,include_attributes=False)
        return result
    a,b=definitions(old),definitions(new)
    if set(a)!=set(b):raise ValueError('Unexpected helper definition addition/removal')
    changed={key for key in a if a[key]!=b[key]}
    if changed!={'ClassicDriver.source_snapshot','launch'}:
        raise ValueError('Unexpected helper function AST changes: '+str(changed))
    c,d=definitions(old_gen),definitions(new_gen)
    gen_changed={key for key in c if c[key]!=d[key]}
    if set(c)!=set(d) or gen_changed!={'main'}:raise ValueError('Unexpected generator function AST changes')
    for name in ('native_saved_stabilization_check_v2.py','prepare_saved_stabilization_payload_v2.py',
                 'check_saved_stabilization_v2_source.py'):
        compile(sources[name],name,'exec')
    if len(new)>65536:raise ValueError('Unchanged injected helper frame bound exceeded')
    status='PASS_CHANGED_HOST_SAVED_90S_SOURCE_ONLY'
    put('RESULT.json',dict(status=status,helper_sha256=helper_sha,helper_bytes=len(new),
        generator_sha256=hashlib.sha256(new_gen).hexdigest(),generator_bytes=len(new_gen),
        changed_helper_functions=sorted(changed),unchanged_helper_functions=len(a)-len(changed),
        changed_generator_functions=sorted(gen_changed),unchanged_generator_functions=len(c)-len(gen_changed),
        exact_source_transformations_verified=True,source_policy_seconds=90,driver_seconds=240,
        independent_target_pc_reservation_bytes=128*1024**2,source_trimming=False,
        project_code_executed=False,native_tested=False,payload_issued=False,
        host_bytes=written,seconds=time.time()-started))
    print(json.dumps(dict(output=str(args.output),status=status,helper_sha256=helper_sha)))
finally:
    put('EXIT_INTENT.json',dict(owner=owner,status=status,physical_closure_claimed=False))
