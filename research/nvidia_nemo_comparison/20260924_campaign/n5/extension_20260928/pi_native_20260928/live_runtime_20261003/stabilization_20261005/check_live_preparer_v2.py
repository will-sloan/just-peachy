"""Freeze only remaining-live host preparation; README_LIVE_CHECK_PAYLOAD_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import shutil
import stat
import sys
import time
import types
import uuid

HERE=Path(__file__).resolve().parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    times=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(),*(ctypes.byref(item) for item in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('live-five-preparer-v2-check-'+uuid.uuid4().hex)
    root.mkdir();started=time.monotonic();written=0
    def put(name,value):
        nonlocal written
        raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,allow_nan=False).encode()
        if written+len(raw)>1024**2 or time.monotonic()-started>600:raise RuntimeError('Finite host freeze')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Original host floor')
        with (root/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short host freeze write')
            stream.flush();os.fsync(stream.fileno())
        written+=len(raw)
        if (root/name).read_bytes()!=raw:raise OSError('Exact source restore readback differs')
    owner=dict(schema='just-peachy.host-registered-owner.v1',cpu=14,affinity_mask=16384,
        pid=os.getpid(),creation_filetime=times[0].value,
        create_time=(times[0].value-116444736000000000)/10000000)
    put('REGISTERED_OWNER.json',owner)
    names=('prepare_stabilization_live_check.py','prepare_stabilization_live_check_v2.py',
        'native_stabilization_check_v5.py','README_LIVE_CHECK_PAYLOAD_V2.md','check_live_preparer_v2.py')
    sources={name:(HERE/name).read_bytes() for name in names}
    for name,raw in sources.items():
        for suffix in ('.backup','.restore'):put(name+suffix,raw)
    put('SOURCE_CLOSED.json',dict(closed_unix=time.time(),independent_restores=True,
        files={name:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in sources.items()},native_action=False))
    if hashlib.sha256(sources['native_stabilization_check_v5.py']).hexdigest()!='0690f255b0fc8fef4ee76b6c32aefc2297de9751d18508ac0a29a7e89a5e1dce':
        raise AssertionError('Unchanged accepted V5 helper required')
    old=ast.parse(sources['prepare_stabilization_live_check.py']);new=ast.parse(sources['prepare_stabilization_live_check_v2.py'])
    old_funcs={node.name:node for node in old.body if isinstance(node,ast.FunctionDef)}
    new_funcs={node.name:node for node in new.body if isinstance(node,ast.FunctionDef)}
    changed=[name for name in old_funcs if ast.dump(old_funcs[name],include_attributes=False)!=ast.dump(new_funcs[name],include_attributes=False)]
    if changed!=['main'] or set(new_funcs)-set(old_funcs)!={'allocation'}:raise AssertionError('Only V5 parameter main/pure allocation may change')
    old_class=next(node for node in old.body if isinstance(node,ast.ClassDef));new_class=next(node for node in new.body if isinstance(node,ast.ClassDef))
    if ast.dump(old_class,include_attributes=False)!=ast.dump(new_class,include_attributes=False):raise AssertionError('Original host writer guards unchanged')
    namespace=dict(globals(),NATIVE_PARENT='/home/peachyprototype/JustPeachy/research/nemotron-20260928',RESERVE=256*1024**2)
    pure=('encoded','strict','sha','read','inventory','selected','allocation')
    exec(compile(ast.Module(body=[new_funcs[name] for name in pure],type_ignores=[]),'<unchanged-chooser-and-exact-storage-plan>','exec'),namespace)
    package=PRIVATE/'audit-preparation/stabilization-package-41186a7a33004f1f8656e7be91e54e12/package'
    pin='6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
    manifest,files=namespace['inventory'](package,pin)
    cases=(('Pyannote + TitaNet',dict(diarizer='pyannote',embedding='titanet',input_source='live')),
        ('Nemotron Delayed + ReDimNet',dict(diarizer='nemotron',embedding='redimnet',input_source='live',nemotron_profile='current_delayed')),
        ('Nemotron Delayed + TitaNet',dict(diarizer='nemotron',embedding='titanet',input_source='live',nemotron_profile='current_delayed')),
        ('Nemotron Chunk52 2T + ReDimNet',dict(diarizer='nemotron',embedding='redimnet',input_source='live',nemotron_profile='chunk52_threads2',allow_experimental=True)),
        ('Nemotron Chunk52 2T + TitaNet',dict(diarizer='nemotron',embedding='titanet',input_source='live',nemotron_profile='chunk52_threads2',allow_experimental=True)))
    rows=[]
    for label,request in cases:
        actual,identifier=namespace['selected'](files,label,request)
        rows.append(dict(chooser_label=label,operator_id=identifier,selection=actual))
    allocation=namespace['allocation'](files)
    if allocation['complete_plan_bytes']>256*1024**2 or allocation['spec']['duration_seconds']!=70:
        raise AssertionError('Full unchanged independent allocation must cover exact70s spec')
    report=dict(status='PASS_REMAINING_LIVE_PREPARER_V2_SOURCE_FREEZE',output=str(root),owner=owner,
        changed_functions=changed,added_functions=['allocation'],catalogue_rows=rows,
        full_pinned_package_members=len(files)+1,allocation=allocation,
        helper_source_sha256=hashlib.sha256(sources['native_stabilization_check_v5.py']).hexdigest(),
        prepares_expiring_payload=False,native_action=False,source_backup_restore=True)
    put('RESULT.json',report);print(json.dumps(report,sort_keys=True))


if __name__=='__main__':main()
