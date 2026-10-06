"""Persist the real build25 selected-export JOB; see README_EXTRACT_STABILIZATION_EXPORT_JOB_V1.md."""
import argparse,ctypes,hashlib,json,os,re,shutil,stat,time,uuid
from pathlib import Path

PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BOOT='0561d730-3cad-48e0-940a-fe3930c89665'
PIN='6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
ACTION_SHA='931cdf6f24058485307ac40e84b9865f38fcec22c08ccd64d85050742c348d84'

def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))

def read(path,limit):
    if not path.is_relative_to(PRIVATE) and path.parent!=Path(__file__).parent:raise ValueError('Owned private/public source input required')
    before=path.lstat()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>limit:raise ValueError('Bounded real input required')
    raw=path.read_bytes();after=path.stat()
    if (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)!=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns):raise ValueError('Input changed')
    return raw

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--result',type=Path,required=True);ap.add_argument('--label',required=True)
    args=ap.parse_args()
    if args.label!='recording-export-10':raise ValueError('Exact actually launched selected-export label required')
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p
    h=k.GetCurrentProcess();k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(h,16384):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)];k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not k.GetProcessTimes(h,*(ctypes.byref(v) for v in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('export-job-extraction-'+args.label+'-'+uuid.uuid4().hex);root.mkdir()
    encoded=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
    (root/'REGISTERED_OWNER.json').write_bytes(encoded(owner));started=time.monotonic();used=0
    def write(path,raw):
        nonlocal used
        if used+len(raw)>1048576 or time.monotonic()-started>600:raise ValueError('Finite1MiB/600s extraction')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Host storage floor')
        with path.open('xb') as output:
            if output.write(raw)!=len(raw):raise OSError('Short extraction write')
            output.flush();os.fsync(output.fileno())
        used+=len(raw)
        if path.read_bytes()!=raw:raise ValueError('Independent readback differs')
    def triple(name,raw):
        for suffix in ('','.backup','.restore'):write(root/(name+suffix),raw)
    write(root/'HOST_SCOPE.json',encoded(dict(maximum_bytes=1048576,maximum_seconds=600,native_action=False)))
    rows={}
    for path in (Path(__file__),Path(__file__).with_name('README_EXTRACT_STABILIZATION_EXPORT_JOB_V1.md')):
        raw=read(path,65536);rows[path.name]=hashlib.sha256(raw).hexdigest();triple(path.name,raw)
    compile(read(Path(__file__),65536),'<source-backed-export-job-extractor>','exec')
    write(root/'SOURCE_CLOSED.json',encoded(dict(files=rows,independent_restores=True,closed_unix=time.time())))
    preparation=PRIVATE/'audit-preparation/stabilization-export-recording-export-10-e99dbd090e654fb1944c79e65c863660'
    action=read(preparation/'ACTION.py',65536);payload=strict(read(preparation/'PAYLOAD.json',262144));closed=strict(read(preparation/'HOST_CLOSED.json',65536))
    if hashlib.sha256(action).hexdigest()!=ACTION_SHA or action!=read(preparation/'ACTION.py.backup',65536) or action!=read(preparation/'ACTION.py.restore',65536) or closed.get('exact_owner_absent') is not True or closed.get('natural_exit_code')!=0 or payload.get('label')!=args.label or payload.get('session_id')!='c24b685b2bd34d6bb04172965d712c0f' or payload.get('package_manifest_sha256')!=PIN or payload.get('boot_id')!=BOOT:raise ValueError('Actual backed/closed export10 preparation required')
    raw=read(args.result,262144);result=strict(raw);job=result.get('action_result')
    if type(job) is not dict or result.get('status')!='CURRENT_OPERATION_INSPECTED' or result.get('boot_id')!=BOOT or result.get('utility_pid_absent_after_ssh') is not True:raise ValueError('Actual independently closed wrapper result required')
    expected_root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/'+args.label
    expected_unit='jp-v29-'+args.label+'.service';owner=job.get('owner');properties=job.get('properties')
    if (set(job)!={'schema','boot_id','unit','owner','invocation_id','control_group','properties','output_root','maximum_output_bytes','package_manifest_sha256','issued_unix','deadline_unix'} or job.get('schema')!='just-peachy.native-component-job.v1' or job.get('boot_id')!=BOOT or job.get('package_manifest_sha256')!=PIN or job.get('output_root')!=expected_root or job.get('unit')!=expected_unit or type(job.get('maximum_output_bytes')) is not int or job['maximum_output_bytes']!=256*1024**2 or
        type(owner) is not dict or set(owner)!={'pid','start_ticks','boot_id'} or owner.get('boot_id')!=BOOT or any(type(owner[k]) is not int or owner[k]<=0 for k in ('pid','start_ticks')) or not re.fullmatch(r'[0-9a-f]{32}',job.get('invocation_id','')) or
        job.get('control_group')!='/user.slice/user-1000.slice/user@1000.service/app.slice/'+expected_unit or type(properties) is not dict or set(properties)!={'ActiveState','ControlGroup','InvocationID','MainPID'} or properties.get('ActiveState')!='active' or properties.get('MainPID')!=str(owner['pid']) or properties.get('ControlGroup')!=job['control_group'] or properties.get('InvocationID')!=job['invocation_id'] or any(type(job.get(key)) not in (int,float) for key in ('issued_unix','deadline_unix')) or not 0<job['deadline_unix']-job['issued_unix']<=600):raise ValueError('Exact actual selected-export launch contract required')
    output=PRIVATE/(args.label+'-JOB.json');job_raw=encoded(job);triple('JOB.json',job_raw)
    triple('ACTUAL_PAYLOAD.json',encoded(payload));write(root/'DISPATCH_RESULT.json',raw);write(output,job_raw)
    receipt=dict(status='ACTUAL_SELECTED_EXPORT_JOB_EXTRACTED',job=str(output),root=str(root),job_sha256=hashlib.sha256(job_raw).hexdigest(),native_action=False,functional_success_not_claimed=True)
    write(root/'RESULT.json',encoded(receipt));print(encoded(receipt).decode())

if __name__=='__main__':main()
