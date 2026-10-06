"""Persist only an actual successful V5 launch JOB; see README_EXTRACT_STABILIZATION_JOB_V6.md."""
import argparse,ctypes,hashlib,json,os,re,shutil,stat,time,uuid
from pathlib import Path

PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BOOT='0561d730-3cad-48e0-940a-fe3930c89665'
PIN='f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0'
HELPER='0690f255b0fc8fef4ee76b6c32aefc2297de9751d18508ac0a29a7e89a5e1dce'

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
    raw=path.read_bytes()
    after=path.stat()
    if (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)!=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns):raise ValueError('Input changed')
    return raw

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--result',type=Path,required=True);ap.add_argument('--label',required=True)
    args=ap.parse_args()
    if re.fullmatch(r'classic-ui-check-[0-9]{2}',args.label) is None:raise ValueError('Exact native check label required')
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p
    h=k.GetCurrentProcess();k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(h,16384):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)];k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not k.GetProcessTimes(h,*(ctypes.byref(v) for v in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('v5-job-extraction-'+args.label+'-'+uuid.uuid4().hex);root.mkdir()
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
    write(root/'HOST_SCOPE.json',encoded(dict(maximum_bytes=1048576,maximum_seconds=600,native_action=False)))
    rows={}
    for path in (Path(__file__),Path(__file__).with_name('README_EXTRACT_STABILIZATION_JOB_V6.md')):
        raw=read(path,65536);rows[path.name]=hashlib.sha256(raw).hexdigest()
        for suffix in ('backup','restore'):write(root/(path.name+'.'+suffix),raw)
    write(root/'SOURCE_CLOSED.json',encoded(dict(files=rows,independent_restores=True,closed_unix=time.time())))
    raw=read(args.result,262144);result=strict(raw);job=result.get('action_result')
    if type(job) is not dict:raise ValueError('Actual successful wrapper action_result JOB required')
    expected_root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/'+args.label
    owner=job.get('owner')
    if (job.get('schema')!='just-peachy.native-component-job.v1' or job.get('boot_id')!=BOOT or job.get('package_manifest_sha256')!=PIN or job.get('helper_source_sha256')!=HELPER or job.get('output_root')!=expected_root or job.get('unit')!='jp-v29-'+args.label+'.service' or job.get('maximum_output_bytes')!=256*1024**2 or
        type(owner) is not dict or set(owner)!={'pid','start_ticks','boot_id'} or owner.get('boot_id')!=BOOT or any(type(owner[k]) is not int or owner[k]<=0 for k in ('pid','start_ticks')) or not re.fullmatch(r'[0-9a-f]{32}',job.get('invocation_id','')) or
        job.get('control_group')!='/user.slice/user-1000.slice/user@1000.service/app.slice/jp-v29-'+args.label+'.service' or not 0<job['deadline_unix']-job['issued_unix']<=600):raise ValueError('Exact actual V5 launch contract required')
    output=PRIVATE/(args.label+'-JOB.json');job_raw=encoded(job)
    for suffix in ('','.backup','.restore'):write(root/('JOB.json'+suffix),job_raw)
    write(root/'DISPATCH_RESULT.json',raw);write(output,job_raw)
    receipt=dict(status='ACTUAL_V5_JOB_EXTRACTED',job=str(output),root=str(root),job_sha256=hashlib.sha256(job_raw).hexdigest(),native_action=False,functional_success_not_claimed=True)
    write(root/'RESULT.json',encoded(receipt));print(encoded(receipt).decode())

if __name__=='__main__':main()
