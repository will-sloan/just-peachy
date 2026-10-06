"""Focused actual backup09 binding; README_HOST_STABILIZATION_OPERATIONS_V4.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import copy
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import time
import textwrap
import uuid

HERE=Path(__file__).resolve().parent
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(),*(ctypes.byref(item) for item in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('backup-guard-v4-check-'+uuid.uuid4().hex)
    root.mkdir();started=time.monotonic();written=0
    def put(name,value):
        nonlocal written
        raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,allow_nan=False).encode()
        if written+len(raw)>1024**2 or time.monotonic()-started>600:raise RuntimeError('Finite host review')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Original host floor')
        with (root/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short host review write')
            stream.flush();os.fsync(stream.fileno())
        written+=len(raw)
        if (root/name).read_bytes()!=raw:raise OSError('Independent readback differs')
    owner=dict(schema='just-peachy.host-registered-owner.v1',cpu=14,affinity_mask=16384,
        pid=os.getpid(),creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    put('REGISTERED_OWNER.json',owner)
    sources={name:(HERE/name).read_bytes() for name in
        ('host_stabilization_operations_v3.py','host_stabilization_operations_v4.py',
         'README_HOST_STABILIZATION_OPERATIONS_V4.md','check_backup_guard_binding_v4_v2.py')}
    for name,raw in sources.items():
        for suffix in ('.backup','.restore'):put(name+suffix,raw)
    put('SOURCE_CLOSED.json',dict(closed_unix=time.time(),independent_restore=True,
        sources={name:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in sources.items()}))
    old=ast.parse(sources['host_stabilization_operations_v3.py']);new=ast.parse(sources['host_stabilization_operations_v4.py'])
    funcs=lambda tree:{node.name:node for node in tree.body if isinstance(node,ast.FunctionDef)}
    old_funcs=funcs(old);new_funcs=funcs(new)
    changed_functions=[name for name in old_funcs if ast.dump(old_funcs[name],include_attributes=False)!=ast.dump(new_funcs[name],include_attributes=False)]
    if changed_functions!=['actual_nested_unit_map','bind'] or set(new_funcs)-set(old_funcs)!={'actual_backup_guard'}:
        raise AssertionError('Only exact map/branch and backup09 helper may change')
    copy_bind=copy.deepcopy(new_funcs['bind'])
    old_addition=next(node for node in old_funcs['bind'].body if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='addition')
    new_addition=next(node for node in copy_bind.body if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='addition')
    addition=new_addition.value.value;new_addition.value=copy.deepcopy(old_addition.value)
    if ast.dump(copy_bind,include_attributes=False)!=ast.dump(old_funcs['bind'],include_attributes=False):
        raise AssertionError('Unknown-owner and all other native bind behavior unchanged')
    namespace=dict(json=json,hashlib=hashlib,math=math,re=re,
        NATIVE_PREFIX='/home/peachyprototype/JustPeachy/research/nemotron-20260928/',
        KEYS={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','main_pid','owner','runtime_max_seconds','unit'})
    exec(compile(ast.Module(body=[new_funcs[name] for name in ('encoded','sha','strict','identity','actual_backup_guard')],type_ignores=[]),'<actual-backup09-helper>','exec'),namespace)
    mirror=PRIVATE/'production-backup-09-reconcile-01/guard-monitor'
    rows=namespace['strict']((mirror/'MIRROR_MANIFEST.json').read_bytes())
    complete=namespace['strict']((mirror/'MIRROR_COMPLETE.json').read_bytes())
    result=namespace['strict']((mirror/'RESULT.json').read_bytes());job=result['job']
    if result.get('status')!='FULL_CLOSED_OUTPUT_MIRRORED' or complete.get('files')!=len(rows) or complete.get('manifest_sha256')!=namespace['sha'](namespace['encoded'](rows)):
        raise AssertionError('Complete actual independent mirror required')
    values={}
    for row in rows:
        path=mirror/'closed-output'/row['path']
        if path.is_symlink() or not path.is_file() or path.stat().st_size>262144:raise ValueError('Bounded real actual mirror file')
        raw=path.read_bytes()
        if len(raw)!=row['identity']['bytes'] or namespace['sha'](raw)!=row['sha256']:raise AssertionError('Every actual mirrored member must hash exactly')
        if row['path'] in ('UNIT_OWNERSHIP.json','JOB.json','OWNER.json','JOB_EXIT.json','SNAPSHOT_RELEASED.json'):
            values[row['path']]=(raw,namespace['strict'](raw))
    member=lambda name:values[name]
    pin=namespace['actual_backup_guard'](job,complete,member);rejects=0
    def reject(call):
        nonlocal rejects
        try:call()
        except (ValueError,AssertionError):rejects+=1
        else:raise AssertionError('Expected strict backup09 rejection')
    reject(lambda:namespace['actual_backup_guard'](dict(job,owner=dict(job['owner'],pid=True)),complete,member))
    bad_complete=copy.deepcopy(complete);bad_complete['closure']['cgroup_empty']=False
    reject(lambda:namespace['actual_backup_guard'](job,bad_complete,member))
    changed=dict(values);changed['UNIT_OWNERSHIP.json']=(values['UNIT_OWNERSHIP.json'][0]+b' ',values['UNIT_OWNERSHIP.json'][1])
    reject(lambda:namespace['actual_backup_guard'](job,complete,lambda name:changed[name]))
    changed=dict(values);exit_raw,exit_row=values['JOB_EXIT.json'];changed['JOB_EXIT.json']=(exit_raw,dict(exit_row,natural_returncode=True))
    reject(lambda:namespace['actual_backup_guard'](job,complete,lambda name:changed[name]))
    rel='live-runtime-tests-20261003/production-backup-09/UNIT_OWNERSHIP.json'
    native='if False:\n pass\n'+textwrap.dedent(addition)
    native_namespace=dict(namespace,rel=rel,raw=values['UNIT_OWNERSHIP.json'][0],v=copy.deepcopy(pin['document']),
        ACTUAL_NESTED_UNIT_OWNERS={rel:pin},boot=job['boot_id'],ticks=lambda pid:None)
    exec(compile(native,'<actual-generated-native-backup09-branch>','exec'),native_namespace)
    if native_namespace['v']!=job['owner']:raise AssertionError('Native decoder returns only exact process identity')
    live=dict(native_namespace,v=copy.deepcopy(pin['document']),ticks=lambda pid:job['owner']['start_ticks'])
    reject(lambda:exec(compile(native,'<actual-generated-native-live-reject>','exec'),live))
    report=dict(status='PASS_ACTUAL_BACKUP09_GUARD_NATIVE_BRANCH_BINDING',output=str(root),owner=owner,
        complete_members_verified=len(rows),positive_groups=2,rejects=rejects,
        changed_functions=changed_functions,added_functions=['actual_backup_guard'],
        owner_pin=pin,source_backup_restore=True,native_action=False)
    put('RESULT.json',report);print(json.dumps(report,sort_keys=True))


if __name__=='__main__':main()
