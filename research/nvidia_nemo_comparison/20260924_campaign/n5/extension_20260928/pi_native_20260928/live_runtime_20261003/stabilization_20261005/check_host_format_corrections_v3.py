"""Actual first-decoder format binding; README_HOST_STABILIZATION_OPERATIONS_V3.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import ctypes
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import time
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
    root=PRIVATE/'audit-preparation'/('host-format-v3-check-'+uuid.uuid4().hex)
    root.mkdir();started=time.monotonic();written=0
    def put(name,value):
        nonlocal written
        raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,allow_nan=False).encode()
        if written+len(raw)>1024**2 or time.monotonic()-started>600:raise RuntimeError('Finite host check scope')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Existing host free-space floor')
        with (root/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short host check write')
            stream.flush();os.fsync(stream.fileno())
        written+=len(raw)
        if (root/name).read_bytes()!=raw:raise OSError('Host check readback differs')
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=times[0].value,
        create_time=(times[0].value-116444736000000000)/10000000)
    put('REGISTERED_OWNER.json',owner)
    sources={name:(HERE/name).read_bytes() for name in
        ('host_stabilization_operations_v2.py','host_stabilization_operations_v3.py',
         'README_HOST_STABILIZATION_OPERATIONS_V3.md','check_host_format_corrections_v3.py')}
    sources['driver.py']=(HERE.parent/'host_operations_v6.py').read_bytes()
    sources['first_decoder.py']=(PRIVATE/'inspection-preparation-expansion-baseline-v3/source.py.backup').read_bytes()
    for name,raw in sources.items():
        for suffix in ('.backup','.restore'):put(name+suffix,raw)
    if hashlib.sha256(sources['first_decoder.py']).hexdigest()!='df6b67fbc395e72f889c2dd3038deac7cff67930a0aa1b35996e0b981b76f80b':
        raise ValueError('Exact retained first decoder required')
    put('SOURCE_CLOSED.json',dict(closed_unix=time.time(),independent_restore=True,
        files={name:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in sources.items()}))
    old=ast.parse(sources['host_stabilization_operations_v2.py'])
    new=ast.parse(sources['host_stabilization_operations_v3.py'])
    old_funcs={node.name:node for node in old.body if isinstance(node,ast.FunctionDef)}
    new_funcs={node.name:node for node in new.body if isinstance(node,ast.FunctionDef)}
    changed=[name for name in old_funcs if ast.dump(old_funcs[name],include_attributes=False)!=ast.dump(new_funcs[name],include_attributes=False)]
    if changed!=['lifetime_decoder'] or set(old_funcs)!=set(new_funcs):raise AssertionError('Only exact correction function changes')
    normalized=ast.parse(ast.unparse(new_funcs['lifetime_decoder']))
    body=normalized.body[0].body
    additions=[node for node in body if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)
        and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='extend'
        and isinstance(node.value.func.value,ast.Name) and node.value.func.value.id=='actual_checks']
    if len(additions)!=1:raise AssertionError('Exactly one explicit correction table extension')
    body.remove(additions[0])
    if ast.dump(normalized.body[0],include_attributes=False)!=ast.dump(old_funcs['lifetime_decoder'],include_attributes=False):
        raise AssertionError('All retained lifetime correction behavior must stay exact')
    driver_tree=ast.parse(sources['driver.py']);driver_main=next(node for node in driver_tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    assignments={node.targets[0].id:node.value for node in driver_main.body if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)}
    corrections=ast.literal_eval(assignments['corrections']);anchor=ast.literal_eval(assignments['owner_anchor']);prefix=ast.literal_eval(assignments['owner_prefix'])
    original=sources['first_decoder.py'].decode()
    if original.count(anchor)!=1:raise ValueError('Original first decoder insertion boundary')
    raw=('HOST_OWNER_FORMAT_CORRECTIONS='+repr(corrections)+'\n'+original.replace(anchor,prefix+anchor)).encode()
    namespace=dict(PRIVATE=PRIVATE,started=time.monotonic(),Path=Path,stat=stat,time=time,
        json=json,hashlib=hashlib,math=math,re=re)
    selected=[new_funcs[name] for name in ('strict','read','sha','lifetime_decoder')]
    original_decoder=next(node for node in driver_tree.body if isinstance(node,ast.FunctionDef) and node.name=='bounded_lifetime_decoder')
    exec(compile(ast.Module(body=[original_decoder],type_ignores=[]),'<retained-bounded-decoder>','exec'),namespace)
    namespace['original_lifetime_decoder']=namespace['bounded_lifetime_decoder']
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<actual-v3-correction-function>','exec'),namespace)
    generated=namespace['lifetime_decoder'](raw)
    generated_tree=ast.parse(generated)
    if not isinstance(generated_tree.body[0],ast.Assign) or not isinstance(generated_tree.body[1],ast.Expr):raise AssertionError('First decoder map applied before execution')
    check_ns=dict(hashlib=hashlib,math=math,datetime=datetime,private=PRIVATE.parent,host={})
    exec(compile(ast.Module(body=generated_tree.body[:2],type_ignores=[]),'<actual-first-decoder-map>','exec'),check_ns)
    inspector=next(node for node in generated_tree.body if isinstance(node,ast.FunctionDef) and node.name=='inspect')
    identities=next(node for node in inspector.body if isinstance(node,ast.FunctionDef) and node.name=='identities')
    exec(compile(ast.Module(body=[identities],type_ignores=[]),'<actual-first-identities>','exec'),check_ns)
    labels=('stabilization-v5-source-1c0d89648d9a40369f513fb637c8f3fe',
        'stabilization-v5-source-corrected-01','speech19-independent-restore-82def6dd72ec44f58a86713a36075d6a')
    positives=rejects=0
    for label in labels:
        path=PRIVATE/'audit-preparation'/label/'REGISTERED_OWNER.json'
        document=namespace['strict'](path.read_bytes());check_ns['path']=path
        check_ns['identities'](document);positives+=1
        bad=dict(document,schema='unexpected-schema')
        try:check_ns['identities'](bad)
        except ValueError:rejects+=1
        else:raise AssertionError('Changed original completed document must reject')
    check_ns['path']=PRIVATE/'audit-preparation/unbound-format/REGISTERED_OWNER.json'
    try:check_ns['identities'](document)
    except ValueError:rejects+=1
    else:raise AssertionError('Unbound missing-schema registration must reject')
    if len(check_ns['host'])!=3:raise AssertionError('All exact actual FILETIME identities must decode')
    result=dict(status='PASS_EXACT_FIRST_DECODER_HOST_FORMAT_BINDINGS',output=str(root),owner=owner,
        actual_positives=positives,rejects=rejects,changed_functions=changed,
        exact_host_identities=sorted(check_ns['host']),native_action=False,source_backup_restore=True)
    put('RESULT.json',result);print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
