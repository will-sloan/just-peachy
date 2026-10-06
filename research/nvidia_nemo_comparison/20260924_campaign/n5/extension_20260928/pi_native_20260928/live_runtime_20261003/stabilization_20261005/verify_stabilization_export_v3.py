"""Read back actual export10 and indexed members; see README_VERIFY_STABILIZATION_EXPORT_V3.md."""
import ast,ctypes,hashlib,json,os,re,shutil,stat,struct,time,uuid,wave,zipfile
from pathlib import Path,PurePosixPath

Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
N=Path('G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003')
BOOT='0561d730-3cad-48e0-940a-fe3930c89665';PIN='6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
SID='c24b685b2bd34d6bb04172965d712c0f'

def strict(raw):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('Duplicate JSON key')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))

def read(path,maximum=262144):
    before=path.lstat()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>maximum:raise ValueError('Bounded regular input required')
    raw=path.read_bytes();after=path.stat();identity=lambda v:(v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns)
    if identity(before)!=identity(after):raise ValueError('Input changed')
    return raw

def main():
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p;h=k.GetCurrentProcess()
    k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(h,16384):raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)];k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not k.GetProcessTimes(h,*(ctypes.byref(v) for v in stamps)):raise ctypes.WinError(ctypes.get_last_error())
    root=Q/'audit-preparation'/('export10-readback-'+uuid.uuid4().hex);root.mkdir();started=time.monotonic();used=0
    enc=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode();sha=lambda v:hashlib.sha256(v).hexdigest()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,creation_filetime=stamps[0].value,create_time=(stamps[0].value-116444736000000000)/10000000)
    (root/'REGISTERED_OWNER.json').write_bytes(enc(owner))
    def write(name,raw):
        nonlocal used
        if used+len(raw)>1048576 or time.monotonic()-started>600:raise ValueError('Finite1MiB/600s review')
        for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
            if shutil.disk_usage(drive).free<floor+len(raw):raise OSError('Host storage floor')
        with (root/name).open('xb') as output:
            if output.write(raw)!=len(raw):raise OSError('Short review write')
            output.flush();os.fsync(output.fileno())
        used+=len(raw)
        if (root/name).read_bytes()!=raw:raise OSError('Independent readback differs')
    def triple(name,raw):
        for suffix in ('','.backup','.restore'):write(name+suffix,raw)
    write('HOST_SCOPE.json',enc(dict(maximum_bytes=1048576,maximum_seconds=600,native_action=False,private_media_printed=False)))
    for path in (Path(__file__),Path(__file__).with_name('README_VERIFY_STABILIZATION_EXPORT_V3.md'),N/'verify_recording_offload.py'):
        triple(path.name,read(path,65536))
    original=read(N/'verify_recording_offload.py',65536)
    if sha(original)!='b02a16bb329188bbd6ef5ed61020126b7d0596a34cc6bd00b5c2b4243e1dff87':raise ValueError('Exact original verifier source required')
    functions=[n for n in ast.parse(original).body if isinstance(n,ast.FunctionDef) and n.name in ('digest','central_bound','verify')]
    if [n.name for n in functions]!=['digest','central_bound','verify']:raise ValueError('Exactly three original verifier functions required')
    namespace=dict(hashlib=hashlib,os=os,Path=Path,PurePosixPath=PurePosixPath,re=re,stat=stat,struct=struct,zipfile=zipfile)
    write('SOURCE_CLOSED.json',enc(dict(original_verifier_sha256=sha(original),function_ast_exact=True,independent_restores=True,closed_unix=time.time())))
    exec(compile(ast.Module(body=functions,type_ignores=[]),'<unchanged-source-backed-verifier-functions>','exec'),namespace)
    monitor=Q/'recording-export-10-monitor-01';out=monitor/'closed-output'
    manifest_raw=read(monitor/'MIRROR_MANIFEST.json');manifest=strict(manifest_raw);complete_raw=read(monitor/'MIRROR_COMPLETE.json');complete=strict(complete_raw)
    result_raw=read(monitor/'RESULT.json');result=strict(result_raw);job=strict(read(Q/'recording-export-10-JOB.json',16384))
    if sha(manifest_raw)!='e8a443d9439eef12fd920aff61988ae13cefc444ec72bf1c5fb5ed9241872fb7' or sha(complete_raw)!='b94f2d0382b7470746489f115598d3db642011481464afa0c2fad4a0e87c1a88' or complete.get('manifest_sha256')!=sha(manifest_raw) or complete.get('files')!=24 or result.get('status')!='FULL_CLOSED_OUTPUT_MIRRORED' or result.get('functional_success') is not True or Path(result['copied_root'])!=out:raise ValueError('Actual complete independently copied export10 mirror required')
    monitored=dict(result['job']);output_identity=monitored.pop('output_identity',None)
    closure=complete['closure']
    if monitored!=job or closure.get('output_identity')!=output_identity or job.get('boot_id')!=BOOT or job.get('package_manifest_sha256')!=PIN or any(closure.get(key) is not True for key in ('closed','exact_owner_gone','cgroup_empty')) or closure.get('owner')!=job['owner'] or closure['job_exit'].get('natural_returncode')!=0 or closure['job_exit'].get('error') is not None:raise ValueError('Actual natural main closure and exact output identity required')
    paths=set();total=0
    for row in manifest:
        path=PurePosixPath(row['path'])
        if path.is_absolute() or '..' in path.parts or path.as_posix()!=row['path'] or row['path'] in paths:raise ValueError('Exact unique mirror membership required')
        target=out/row['path'];before=target.lstat()
        if target.is_symlink() or any(p.is_symlink() for p in target.parents) or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size!=row['identity']['bytes']:raise ValueError('Mirror regular member extent differs')
        with target.open('rb') as stream:actual=namespace['digest'](stream)
        after=target.stat()
        if actual!=row['sha256'] or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Mirror member changed or SHA differs')
        paths.add(row['path']);total+=before.st_size
    if total!=complete['bytes'] or paths!={p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}:raise ValueError('Whole complete mirror byte/membership mismatch')
    export_raw=read(out/'EXPORT.json',16384);export=strict(export_raw)
    if export.get('status')!='EXPORTED' or export.get('session_id')!=SID or export.get('session_ids')!=[SID] or export.get('original_session_preserved') is not True or any(export.get(key) is not False for key in ('source_deleted','capture','models_loaded')) or export.get('zip_path')!=job['output_root']+'/selected-recording.zip':raise ValueError('Actual selected copy-only export required')
    child=Path(export['child_receipt_directory']).name;child_closed=strict(read(out/'exports'/child/'CHILD_CLOSURE.json',16384));child_terminal=strict(read(out/'exports'/child/'child/CLOSED.json',16384))
    if any(child_closed.get(key) is not True for key in ('direct_child_reaped','exact_owner_gone')) or child_closed.get('exit_code')!=0 or child_closed.get('forced_reap') is not False or child_closed.get('error') is not None or child_terminal.get('status')!='EXPORTED' or child_terminal.get('error') is not None or child_closed['owner']!=child_terminal['owner']:raise ValueError('Actual direct export child natural closure required')
    verification=namespace['verify'](out/'selected-recording.zip',export['zip_sha256'],export['zip_bytes'],export['maximum_bytes'])
    members=[];expected={SID+'/'+name for name in ('session.json','segments.jsonl','captions.jsonl','events.jsonl','transcript.txt','artifacts.jsonl')}
    with zipfile.ZipFile(out/'selected-recording.zip') as archive:
        def small(name,maximum=65536):
            info=archive.getinfo(SID+'/'+name)
            if info.file_size>maximum:raise ValueError('Bounded index required')
            return archive.read(info)
        session_raw=small('session.json');session=strict(session_raw)
        if session.get('session_id')!=SID or session.get('status')!='kept' or session.get('processed_samples')!=966400:raise ValueError('Actual kept speech21 metadata required')
        segments=[strict(line) for line in small('segments.jsonl',131072).splitlines() if line];artifacts=[strict(line) for line in small('artifacts.jsonl',131072).splitlines() if line]
        cursors={'processed':0,'raw':0};segment_count={'processed':0,'raw':0}
        for segment in segments:
            kind=segment['kind'];samples=segment['samples']
            if kind not in cursors or type(samples) is not int or samples<=0 or segment['start_sample']!=cursors[kind] or segment['session_id']!=SID:raise ValueError('Contiguous exact selected audio segments required')
            frame_bytes=4 if kind=='processed' else session['spec']['raw']['channels']*session['spec']['raw']['sample_width_bytes']
            data=SID+'/'+segment['data_name'];expected.add(data)
            if archive.getinfo(data).file_size!=samples*frame_bytes:raise ValueError('Audio segment sample/byte extent differs')
            if segment['replay_name']:
                replay=SID+'/'+segment['replay_name'];expected.add(replay)
                with archive.open(replay) as source, wave.open(source,'rb') as wav:
                    if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getnframes())!=(1,2,16000,samples):raise ValueError('Exact processed replay WAV required')
            cursors[kind]+=samples;segment_count[kind]+=1
        if cursors['processed']!=session['processed_samples'] or cursors['raw']!=session['raw_samples']:raise ValueError('Complete saved sample clocks required')
        for artifact in artifacts:
            name=SID+'/'+artifact['path'];expected.add(name)
            if set(artifact)!={'path','role','bytes'} or type(artifact['path']) is not str or type(artifact['role']) is not str or type(artifact['bytes']) is not int or artifact['bytes']<0 or archive.getinfo(name).file_size!=artifact['bytes']:raise ValueError('Exact selected registered artifact index/extent differs')
        if expected!=set(archive.namelist()):raise ValueError('Complete export membership differs from session/segment/artifact indices')
        for info in archive.infolist():
            with archive.open(info) as source:d=hashlib.sha256();count=0
            with archive.open(info) as source:
                while block:=source.read(65536):d.update(block);count+=len(block)
            if count!=info.file_size:raise ValueError('Complete hashed member extent differs')
            members.append(dict(path=info.filename,bytes=count,sha256=d.hexdigest()))
    for name,raw in (('ACTUAL_EXPORT.json',export_raw),('MIRROR_MANIFEST.json',manifest_raw),('MIRROR_COMPLETE.json',complete_raw),('ACTUAL_JOB.json',enc(job))):triple(name,raw)
    write('ZIP_MEMBERS.json',enc(members));write('VERIFY.json',enc(verification))
    summary=dict(status='ACTUAL_EXPORT_COMPLETE_PC_READBACK_PASSED',root=str(root),zip_path=str(out/'selected-recording.zip'),zip_sha256=export['zip_sha256'],zip_bytes=export['zip_bytes'],members=len(members),processed_samples=cursors['processed'],raw_samples=cursors['raw'],segment_counts=segment_count,all_indexed_members_present=True,per_member_pc_sha256_recorded=True,original_source_per_member_sha256_not_supplied=True,exported_session_json_sha256=sha(session_raw),original_session_raw_byte_sha256=None,original_session_raw_byte_hash_pending=True,source_deleted=False,native_action=False,accuracy_evaluated=False)
    write('RESULT.json',enc(summary));print(enc(summary).decode())

if __name__=='__main__':main()
