"""Prepare only normal GUI action/payload/backups; README_NORMAL_GUI_WORKFLOW.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
OUT=PRIVATE/'audit-preparation'/('normal-gui-workflow-'+uuid.uuid4().hex)
OUT.mkdir()
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
times=[ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(kernel.GetCurrentProcess(),*(ctypes.byref(item) for item in times)):raise ctypes.WinError(ctypes.get_last_error())
owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),creation_filetime=times[0].value,create_time=(times[0].value-116444736000000000)/10000000,cpu=14,affinity_mask=16384)


def put(path,raw):
    with path.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short workflow preparation write')
        stream.flush();os.fsync(stream.fileno())
    with path.open('rb') as stream:restored=stream.read(len(raw)+1)
    if restored!=raw:raise OSError('Independent workflow preparation readback differs')


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


put(OUT/'REGISTERED_OWNER.json',encoded(owner))
import argparse
import ast
import base64
import math
import re
import stat


def read(path,maximum=262144):
    path=Path(path);before=path.lstat()
    if path.resolve(strict=True)!=path or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or not 0<=before.st_size<=maximum:
        raise ValueError('Canonical bounded ordinary host source required')
    with path.open('rb') as stream:raw=stream.read(maximum+1)
    after=path.lstat()
    if len(raw)>maximum or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError('Host source changed during admission')
    return raw


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    parser.add_argument('--boot-id',required=True)
    parser.add_argument('--expires-unix',required=True,type=float)
    parser.add_argument('--desktop',required=True)
    parser.add_argument('--desktop-sha256',required=True)
    parser.add_argument('--production-acceptance-sha256',required=True)
    args=parser.parse_args()
    if (re.fullmatch('production-normal-[0-9]{2}',args.label) is None
            or re.fullmatch('[0-9a-f-]{36}',args.boot_id) is None
            or not math.isfinite(args.expires_unix) or not time.time()<args.expires_unix<=time.time()+600
            or any(re.fullmatch('[0-9a-f]{64}',value) is None for value in (args.desktop_sha256,args.production_acceptance_sha256))
            or not args.desktop.startswith('/home/peachyprototype/Desktop/') or '/' in args.desktop[len('/home/peachyprototype/Desktop/'):]
            or not args.desktop.endswith('.desktop')):
        raise ValueError('Fresh actual native desktop/current-boot admission required')
    here=Path(__file__).resolve().parent
    reference=here.parent.parent/'full_application_20261004/launch_manual_idle_action_v2.py'
    sources=[Path(__file__).resolve(),here/'launch_normal_gui_action.py',here/'normal_gui_control.py',here/'README_NORMAL_GUI_WORKFLOW.md',reference]
    pins=[];raws={}
    for path in sources:
        raw=read(path);digest=hashlib.sha256(raw).hexdigest();raws[path.name]=raw
        for suffix in ('.backup','.restore'):put(OUT/(path.name+suffix),raw)
        pins.append(dict(path=str(path),bytes=len(raw),sha256=digest))
    if hashlib.sha256(raws[reference.name]).hexdigest()!='b123694a1c530090ff860f1a544227ada4e8a5d413dfc5078f6a14cf7d79d40e':raise ValueError('Preserved idle reference pin differs')
    for name in ('launch_normal_gui_action.py','normal_gui_control.py'):
        compile(raws[name],name,'exec')
    space={'__name__':'normal_gui_source_preparation','__file__':str(here/'launch_normal_gui_action.py')}
    exec(compile(raws['launch_normal_gui_action.py'],'<reviewed-normal-action>','exec'),space)
    derived=space['derive_reference'](raws[reference.name]);compile(derived,'<derived-production-dispatch>','exec')
    put(OUT/'DERIVED_REFERENCE.py',derived.encode())
    payload=dict(schema='just-peachy.normal-production-gui-launch.v1',normal_start_stop_discard=True,
        package=space['NATIVE_PACKAGE'],package_manifest_sha256=space['PACKAGE_PIN'],
        label=args.label,boot_id=args.boot_id,expires_unix=args.expires_unix,
        desktop=args.desktop,desktop_sha256=args.desktop_sha256,
        production_acceptance_sha256=args.production_acceptance_sha256,maximum_output_bytes=32*1024**2)
    for key,name in (('reference_source',reference.name),('control_source','normal_gui_control.py')):
        payload[key+'_b64']=base64.b64encode(raws[name]).decode();payload[key+'_sha256']=hashlib.sha256(raws[name]).hexdigest()
    put(OUT/'PAYLOAD.json',encoded(payload));put(OUT/'ACTION.py',raws['launch_normal_gui_action.py'])
    for pin in pins:
        if (len(read(pin['path'])),hashlib.sha256(read(pin['path'])).hexdigest())!=(pin['bytes'],pin['sha256']):raise ValueError('Prepared source changed before closure')
    put(OUT/'SOURCE_CLOSED.json',encoded(dict(schema='just-peachy.normal-gui-source-preparation.v1',owner=owner,source_pins=pins,backup_and_independent_restore=True,source_unchanged=True,dispatch_reverse_ast_verified=True,native_action=False,native_qualified=False,closed_unix=time.time())))
    print(json.dumps(dict(status='PREPARED',output=str(OUT),action=str(OUT/'ACTION.py'),action_sha256=hashlib.sha256(raws['launch_normal_gui_action.py']).hexdigest(),payload=str(OUT/'PAYLOAD.json'),payload_sha256=hashlib.sha256(encoded(payload)).hexdigest(),native_action=False)))


if __name__=='__main__':main()
