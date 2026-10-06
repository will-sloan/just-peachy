"""Focused actual-byte acknowledgment checks. README_UNSENT_RECOVERY_ACKNOWLEDGMENT.md."""
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid


def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess();kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    clocks=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in clocks)):raise ctypes.WinError(ctypes.get_last_error())
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    out=private/'audit-preparation'/('unsent-recovery-check-'+uuid.uuid4().hex);out.mkdir();begun=time.monotonic();used=0
    encode=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
    def put(name,raw):
        nonlocal used
        raw=raw if type(raw) is bytes else encode(raw)
        if used+len(raw)>2097152 or time.monotonic()-begun>60:raise ValueError('Finite2MiB/60s host check')
        for drive,gib in (('C:/',50),('G:/',75)):
            if shutil.disk_usage(drive).free<gib*1024**3+len(raw):raise OSError('Host safety floor')
        with (out/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short host check output')
            stream.flush();os.fsync(stream.fileno())
        used+=len(raw)
        if (out/name).read_bytes()!=raw:raise OSError('Independent host check readback differs')
    put('REGISTERED_OWNER.json',dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=clocks[0].value,create_time=(clocks[0].value-116444736000000000)/10000000))
    put('HOST_SCOPE.json',dict(maximum_output_bytes=2097152,maximum_seconds=60,native_action=False))
    here=Path(__file__).resolve().parent;paths={
        'checker.py':Path(__file__),'readiness.py':here.parent/'ui_restore_20261004/xvf_readiness.py',
        'README.md':here/'README_UNSENT_RECOVERY_ACKNOWLEDGMENT.md','launcher.py':here/'launcher.py',
        'old-readiness.py':private/'audit-preparation/unsent-recovery-before-d5c5e755713e4eaeb6b3532158175769/xvf_readiness.py.backup',
        'inspection.json':private/'operation-closed-recovery-inspection-01/dispatch/RESULT.json'}
    sources={}
    for name,path in paths.items():
        before=path.stat();raw=path.read_bytes();after=path.stat()
        if len(raw)>262144 or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('Bounded stable actual/source check input required')
        sources[name]=raw
        for suffix in ('','.backup','.restore'):put(name+suffix,raw)
    pins={name:hashlib.sha256(raw).hexdigest() for name,raw in sources.items()}
    put('SOURCE_CLOSED.json',dict(pins=pins,independent_restores=True))
    old=ast.parse(sources['old-readiness.py']);new=ast.parse(sources['readiness.py'])
    names={'qualifying_unsent_manual_failure','preserved_unsent_manual_failure'}
    additions=[node for node in new.body if isinstance(node,ast.FunctionDef) and node.name in names]
    if {node.name for node in additions}!=names:raise AssertionError('Exact two acknowledgment APIs required')
    for node in additions:new.body.remove(node)
    if ast.dump(new,include_attributes=False)!=ast.dump(old,include_attributes=False):
        raise AssertionError('Existing readiness sequence/helper caller changed')
    compile(sources['readiness.py'],'<backed-readiness>','exec');compile(sources['launcher.py'],'<backed-launcher>','exec')
    pure=next(node for node in additions if node.name=='qualifying_unsent_manual_failure')
    namespace=dict(hashlib=hashlib,json=json)
    exec(compile(ast.Module(body=[pure],type_ignores=[]),'<exact-pure-unsent-validator>','exec'),namespace)
    actual=json.loads(sources['inspection.json'])['action_result']
    if (actual.get('status')!='CLOSED_RECOVERY_TREE_READ' or actual.get('membership_stable') is not True
            or actual.get('no_send_intent_observed') is not True or actual.get('total_bytes')!=2312):
        raise ValueError('Actual independent read-only seven-file inspection required')
    records={name:encode(value) for name,value in actual['selected_documents'].items()}
    records['REGISTERED_OWNER.json']=encode(actual['selected_documents']['HOST_CLOSURE.json']['owner'])
    records.update({'HELPER.stderr':b'','HELPER.stdout':b''})
    for row in actual['files']:
        raw=records[row['path']]
        if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise AssertionError('Reconstructed original bytes differ from native inspection')
    request=actual['selected_documents']['REQUEST.json']
    binding={key:request[key] for key in ('fault_sha256','fault_path','closed_path','closed_sha256','module_sha256','helper_sha256')}
    binding['boot_id']=actual['boot_id']
    check=namespace['qualifying_unsent_manual_failure'];closed=lambda owner:dict(closed=True)
    if check(records,binding,closed) is not True:raise AssertionError('Exact actual completed unsent error rejected')
    rejects=0
    cases=[]
    cases.append(dict(records,**{'RESTART_INTENT.json':encode(dict(command=['TEST_CORE_BURN','0']))}))
    cases.append({name:raw for name,raw in records.items() if name!='HOST_CLOSURE.json'})
    for field,value in (('maintenance_sends',1),('maintenance_sends_attempted',1),('commands',[{'command':'TEST_CORE_BURN'}]),
                        ('leases_released',False),('error',{'type':'TypeError','message':'different'})):
        altered=dict(actual['selected_documents']['RECOVERY.json'],**{field:value})
        cases.append(dict(records,**{'RECOVERY.json':encode(altered)}))
    altered=dict(actual['selected_documents']['HOST_CLOSURE.json'],timeout=True)
    cases.append(dict(records,**{'HOST_CLOSURE.json':encode(altered)}))
    for changed in cases:
        if check(changed,binding,closed):raise AssertionError('Changed/sent/uncertain old recovery admitted')
        rejects+=1
    for field,value in (('boot_id','00000000-0000-0000-0000-000000000000'),('closed_sha256','0'*64),
                        ('fault_path','/foreign/source.json'),('module_sha256','0'*64),('helper_sha256','0'*64)):
        if check(records,dict(binding,**{field:value}),closed):raise AssertionError('Changed provenance binding admitted')
        rejects+=1
    if check(records,binding,lambda owner:dict(closed=False)):raise AssertionError('Exact helper/old owner still live admitted')
    rejects+=1
    put('RESULT.json',dict(status='PASS_CHANGED_HOST_EXACT_UNSENT_ACKNOWLEDGMENT_ONLY',
        positive_groups=2,rejects=rejects,actual_members=7,actual_original_bytes=2312,
        prior_readiness_AST_unchanged=True,source_sha256=pins,old_recovery_mutated=False,
        native_executed=False,old_helper_retried=False,owner_callback_synthetic=True))
    print(str(out))


if __name__=='__main__':main()
