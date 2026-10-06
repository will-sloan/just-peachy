"""Focused actual self-FILETIME exclusion check; README_HOST_STABILIZATION_OPERATIONS_V5.md."""
import ast,ctypes,hashlib,json,math,os,psutil,shutil,time,uuid
from pathlib import Path
k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p;h=k.GetCurrentProcess()
k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
if not k.SetProcessAffinityMask(h,16384):raise ctypes.WinError(ctypes.get_last_error())
t=[ctypes.c_ulonglong() for _ in range(4)];k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
if not k.GetProcessTimes(h,*(ctypes.byref(v) for v in t)):raise ctypes.WinError(ctypes.get_last_error())
q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
n=Path(__file__).parent.parent;s=Path(__file__).parent;root=q/'audit-preparation'/('coordinator-filetime-check-'+uuid.uuid4().hex);root.mkdir();started=time.monotonic();used=0
enc=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode();sha=lambda v:hashlib.sha256(v).hexdigest()
def write(path,raw):
    global used
    if used+len(raw)>2097152 or time.monotonic()-started>600:raise ValueError('Finite2MiB/600s focused check')
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Host storage floor')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short backed write')
        stream.flush();os.fsync(stream.fileno())
    used+=len(raw)
    if path.read_bytes()!=raw:raise OSError('Independent readback differs')
def triple(name,raw):
    for suffix in ('','.backup','.restore'):write(root/(name+suffix),raw)
owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,creation_filetime=t[0].value,create_time=(t[0].value-116444736000000000)/10000000)
write(root/'REGISTERED_OWNER.json',enc(owner));write(root/'HOST_SCOPE.json',enc(dict(maximum_bytes=2097152,maximum_seconds=600,native_action=False)))
sources={}
paths=(Path(__file__),s/'coordinator_filetime_v1.py',s/'host_stabilization_operations_v4.py',s/'host_stabilization_operations_v5.py',s/'README_HOST_STABILIZATION_OPERATIONS_V5.md',n/'host_operations_v6.py',q/'inspection-preparation-expansion-baseline-v3/source.py.backup')
for index,path in enumerate(paths):
    before=path.stat();raw=path.read_bytes();after=path.stat()
    if before.st_size>131072 or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Stable bounded original source required')
    triple(str(index)+'-'+path.name,raw);sources[path.name]=raw
write(root/'SOURCE_CLOSED.json',enc(dict(independent_restores=True,source_sha256={key:sha(value) for key,value in sources.items()},closed_unix=time.time())))
base=ast.parse(sources['host_stabilization_operations_v4.py']);changed=ast.parse(sources['host_stabilization_operations_v5.py'])
new_functions=[node for node in changed.body if isinstance(node,ast.FunctionDef) and node.name=='coordinator_filetime_source']
if len(new_functions)!=1:raise ValueError('Exactly one added current-coordinator binding function required')
for node in changed.body:
    if isinstance(node,ast.FunctionDef) and node.name=='lifetime_decoder':
        last=node.body[-1]
        if not isinstance(last,ast.Return) or not isinstance(last.value,ast.Call) or not isinstance(last.value.func,ast.Name) or last.value.func.id!='coordinator_filetime_source' or len(last.value.args)!=1:raise ValueError('Exact single lifetime decoder return wrapper required')
        last.value=last.value.args[0]
changed.body.remove(new_functions[0]);changed.body[0].value=base.body[0].value
if ast.dump(base,include_attributes=False)!=ast.dump(changed,include_attributes=False):raise ValueError('Unrelated V4 wrapper AST change')
namespace={};exec(compile(ast.Module(body=new_functions,type_ignores=[]),'<backed-exact-current-filetime-binding>','exec'),namespace)
original=sources['source.py.backup']
if sha(original)!='df6b67fbc395e72f889c2dd3038deac7cff67930a0aa1b35996e0b981b76f80b':raise ValueError('Exact original full host decoder required')
bound=namespace['coordinator_filetime_source'](original);triple('BOUND_DECODER.py',bound)
decoder={};exec(compile(bound,'<backed-fixture-only-host-decoder>','exec'),decoder)
process=psutil.Process();current=dict(pid=process.pid,create_time=process.create_time(),affinity=[14]);actual_other=process.parent()
if actual_other is None or actual_other.pid==process.pid:raise ValueError('Actual existing other live process required')
def inspect_fixture(label,registered,additional=()):
    fixture=root/'fixtures'/label;local=fixture/'local';private=fixture/'private'
    write(local/'supervision/worker.json',enc(current));write(private/'LIFETIME/events.json',b'[]')
    write(private/'live-runtime-20261003/audit-preparation/self/REGISTERED_OWNER.json',enc(registered))
    for index,row in enumerate(additional):write(private/('registered-'+str(index)+'-OWNER.json'),enc(row))
    return decoder['inspect'](local,private,current_owner=current,deadline=time.monotonic()+5,guard=lambda:None)
good,details=inspect_fixture('actual-filetime-self',dict(owner,create_time=current['create_time']))
if good['alive_owners']:raise AssertionError('Exact actual FILETIME self must be excluded across float representations')
wrong=dict(owner,creation_filetime=owner['creation_filetime']+1)
bad,_=inspect_fixture('same-pid-wrong-filetime',wrong)
if not any(row['pid']==process.pid for row in bad['alive_owners']):raise AssertionError('Same PID wrong exact FILETIME must remain a live rejection')
other=dict(pid=actual_other.pid,create_time=actual_other.create_time(),affinity=[14])
foreign,_=inspect_fixture('actual-other-live-process',owner,[other])
if not any(row['pid']==actual_other.pid for row in foreign['alive_owners']):raise AssertionError('Actual other live PID must remain a live rejection')
# Deliberately use the exact current PID with wrong FILETIME that rounds to the
# same float key; the set preserves both records instead of hiding the mismatch.
canonical=owner['create_time'];collision=None
for delta in range(1,10):
    value=owner['creation_filetime']+delta
    if (value-116444736000000000)/10000000==canonical:collision=value;break
if collision is not None:
    bad_collision=dict(owner,creation_filetime=collision)
    fixture=root/'fixtures/mixed-filetime';local=fixture/'local';private=fixture/'private'
    write(local/'supervision/worker.json',enc(current));write(private/'LIFETIME/events.json',b'[]')
    for label,row in (('self',owner),('wrong',bad_collision)):write(private/('live-runtime-20261003/audit-preparation/'+label+'/REGISTERED_OWNER.json'),enc(row))
    mixed,_=decoder['inspect'](local,private,current_owner=current,deadline=time.monotonic()+5,guard=lambda:None)
    if not any(row['pid']==process.pid for row in mixed['alive_owners']):raise AssertionError('Float collision must not hide wrong exact FILETIME')
summary=dict(status='EXACT_CURRENT_COORDINATOR_FILETIME_CHECK_PASSED',root=str(root),self_filetime_exact=True,self_psutil_epoch=current['create_time'],self_kernel_epoch=canonical,float_representations_differ=current['create_time']!=canonical,same_pid_wrong_filetime_rejected=True,actual_other_live_pid_rejected=True,float_collision_checked=collision is not None,wrapper_v4_other_ast_exact=True,original_decoder_reversible=True,full_native_preread=False,native_action=False)
write(root/'RESULT.json',enc(summary));print(enc(summary).decode())
