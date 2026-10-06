"""Exact Saved extractorV2 derivation; README_EXTRACT_SAVED_STABILIZATION_JOB_V2.md."""
import ctypes
import os
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
handle=kernel.GetCurrentProcess()
if not kernel.SetProcessAffinityMask(handle,1<<14):raise ctypes.WinError(ctypes.get_last_error())
stamps=[ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in stamps)):raise ctypes.WinError(ctypes.get_last_error())
import argparse
import ast
import hashlib
import json
from pathlib import Path
import time
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();args.output.mkdir();started=time.time();written=0
def put(name,value):
    global written
    raw=value if type(value) is bytes else json.dumps(value,sort_keys=True,allow_nan=False).encode()
    if len(raw)>262144 or written+len(raw)>1048576 or time.time()-started>30:raise ValueError('Finite source review required')
    with (args.output/name).open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short source publication')
        stream.flush();os.fsync(stream.fileno())
    written+=len(raw)
    if (args.output/name).read_bytes()!=raw:raise OSError('Exact source readback differs')
owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),creation_filetime=stamps[0].value,
    create_time=(stamps[0].value-116444736000000000)/10000000,cpu=14,affinity_mask=16384)
put('REGISTERED_OWNER.json',owner)
put('HOST_SCOPE.json',dict(issued_unix=started,maximum_seconds=30,maximum_bytes=1048576,native_action=False))
status='FAILED';raws={};pins=[]
try:
    names=('extract_saved_stabilization_job_v1.py','extract_saved_stabilization_job_v2.py',
           'README_EXTRACT_SAVED_STABILIZATION_JOB_V2.md','native_saved_stabilization_check_v4.py',
           'check_saved_job_v2_source.py')
    for index,name in enumerate(names):
        path=args.source/name;raw=path.read_bytes()
        if path.is_symlink() or len(raw)>262144:raise ValueError('Finite real source required')
        put('SOURCE_%02d.backup'%index,raw)
        restored=(args.output/('SOURCE_%02d.backup'%index)).read_bytes()
        put('SOURCE_%02d.restore'%index,restored)
        if raw!=restored or path.read_bytes()!=raw:raise OSError('Independent source restore differs')
        raws[name]=raw;pins.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    put('SOURCE_CLOSED.json',dict(pins=pins,closed_unix=time.time(),exact_backup=True,independent_restore=True,before_execution=True))
    expected=raws[names[0]].decode('utf-8')
    replacements=(('README_EXTRACT_SAVED_STABILIZATION_JOB_V1.md','README_EXTRACT_SAVED_STABILIZATION_JOB_V2.md'),
        ('saved-v1-job-extraction-','saved-v2-job-extraction-'),
        ('6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8',
         'f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0'))
    for old,new in replacements:expected=expected.replace(old,new)
    actual=raws[names[1]].decode('utf-8')
    if expected!=actual:raise ValueError('Unexpected whole-source change from frozen V4')
    if ast.dump(ast.parse(expected),include_attributes=False)!=ast.dump(ast.parse(actual),include_attributes=False):raise ValueError('Unexpected method AST change')
    helper_sha=hashlib.sha256(raws[names[3]]).hexdigest()
    if helper_sha!='b0421293707f9d8abd79e6f6970d85581b5417aadc347b247d94b0a8cab6e203':raise ValueError('Frozen Saved helper changed')
    compile(actual,str(args.source/names[1]),'exec')
    compile(raws[names[3]],'<unchanged-backed-saved-helper>','exec')
    if any((args.source/name).read_bytes()!=raws[name] for name in names):raise ValueError('Source changed after backup')
    status='PASS_EXACT_SAVED_V2_EXTRACTOR_DERIVATION'
    put('RESULT.json',dict(status=status,replacements=replacements,whole_source_exact=True,module_ast_exact_after_authorized_constants=True,
        helper_sha256=helper_sha,helper_changed=False,model_or_native_executed=False,payload_issued=False,pins=pins,host_bytes=written,elapsed_seconds=time.time()-started))
    print(json.dumps(dict(status=status,output=str(args.output))))
finally:
    put('EXIT_INTENT.json',dict(owner=owner,status=status,physical_closure_claimed=False))
