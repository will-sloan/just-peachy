"""Restore retained failed-runtime export on the PC only; README_RUNTIME_PRESERVATION_RESTORE_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,base64,hashlib,json,os,shutil,time
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('source','candidate-install','scope','output'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir();me=psutil.Process()
    def save(name,v):
        raw=(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
        if len(raw)>262144:raise ValueError('Metadata cap')
        with (a.output/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        if (a.output/name).read_bytes()!=raw:raise IOError('Metadata readback')
    save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    scope=json.loads(a.scope.read_bytes())
    policy=json.loads((a.candidate_install/'RELEASE.json').read_bytes());rid=policy['release_id']
    maximum=policy['allocation']['host_maximum_bytes']
    last=[0.]
    def guard():
        if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Finite host scope')
        if time.monotonic()-last[0]<1:return
        last[0]=time.monotonic()
        for drive,floor in [('C:/',50*1024**3),('G:/',75*1024**3)]:
            if shutil.disk_usage(drive).free<floor+maximum:raise RuntimeError('Original full host free reserve')
        if sum(p.stat().st_size for p in a.output.rglob('*') if p.is_file())>maximum:raise ValueError('Original independent host allocation')
    guard()
    raw=(a.source/'RESULT.json').read_bytes();value=json.loads(raw)
    proof=json.loads((a.source/'NATIVE_CLOSURE.json').read_bytes());phase=json.loads((a.source/'PHASE.json').read_bytes())
    if proof['owner']!=value['utility_owner'] or proof['exact_pid_absent'] is not True or phase['returncode']!=0 or phase['fault'] is not None or not phase['ssh_reaped'] or not phase['readers_joined']:
        raise ValueError('Actual retained clean native export and exact utility closure required')
    if value['policy_sha256']!=hashlib.sha256((a.candidate_install/'RELEASE.json').read_bytes()).hexdigest():raise ValueError('Exact original policy')
    if (a.source/'BACKUP.json').exists():raise ValueError('Do not repeat a healthy backup')
    save('INPUT.json',dict(source=str(a.source),result_sha256=hashlib.sha256(raw).hexdigest(),native_dispatched=False,policy_sha256=value['policy_sha256']))

    # Use actual immutable installation copies; no recopy of the neural assets.
    known={}
    stage=a.candidate_install/'stage-backup'
    for path in stage.rglob('*.py'):
        if not path.is_file() or path.is_symlink() or path.stat().st_size>131072:raise ValueError('Bounded backed code')
        data=path.read_bytes();known[hashlib.sha256(data).hexdigest()]=data
    common_paths=list(stage.rglob('COMMON_BUNDLE.json'))
    if len(common_paths)!=1:raise ValueError('Exact installed common source copy')
    common=json.loads(common_paths[0].read_bytes())
    for name,token in common['files'].items():
        data=base64.b64decode(token,validate=True)
        if len(data)>131072:raise ValueError('Original code member ceiling')
        known[hashlib.sha256(data).hexdigest()]=data
    if len(known)>128 or sum(map(len,known.values()))>2097152:raise ValueError('Complete bounded known source set')


    preserved=value['preservation']
    if not preserved['exact_manager_dead'] or preserved['status']!='FAILED_SOURCE_AND_MANAGER_CLOSED_CENSUS':
        raise ValueError('Actual failed source closure required')
    import zlib
    destination=a.output/'tree';destination.mkdir()
    copies={}
    for rootname,tree in preserved['roots'].items():
        if rootname not in (rid,Path(next(v['operation'] for k,v in value['recording_controls'].items() if k.endswith('/RESERVED.json'))['root']).name):
            raise ValueError('Exact two admitted source roots')
        folder=destination/rootname;folder.mkdir()
        for relative in tree['directories']:
            if not relative:continue
            parts=PurePosixPath(relative).parts
            if PurePosixPath(relative).is_absolute() or '..' in parts or '\\' in relative or ':' in relative:raise ValueError('Portable directory')
            folder.joinpath(*parts).mkdir()
        rows={}
        for name,row in tree['files'].items():
            guard()
            parts=PurePosixPath(name).parts
            if PurePosixPath(name).is_absolute() or '..' in parts or '\\' in name or ':' in name:raise ValueError('Portable file')
            if 'zlib_base64' in row:
                packed=base64.b64decode(row['zlib_base64'],validate=True)
                obj=zlib.decompressobj();data=obj.decompress(packed,row['bytes']+1)
                if not obj.eof or obj.unused_data or obj.unconsumed_tail or len(data)!=row['bytes']:raise ValueError('Bounded exact decompression')
            else:data=known[row['sha256']]
            if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Complete member hash')
            target=folder.joinpath(*parts)
            with target.open('xb') as f:
                for offset in range(0,len(data),16384):
                    block=data[offset:offset+16384]
                    if f.write(block)!=len(block):raise IOError('Full backup short write')
                f.flush();os.fsync(f.fileno())
            rows[name]=dict(bytes=len(data),sha256=row['sha256'])
        actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
        dirs={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_dir()}|{''}
        if actual!=set(rows) or dirs!=set(tree['directories']):raise ValueError('Complete file/empty-directory membership')
        for name,row in rows.items():
            q=folder/name
            with q.open('rb') as f:
                if q.stat().st_size!=row['bytes'] or hashlib.file_digest(f,'sha256').hexdigest()!=row['sha256']:
                    raise IOError('Independent complete PC readback')
        copies[rootname]=dict(files=len(rows),directories=len(dirs),bytes=sum(r['bytes'] for r in rows.values()),
           manifest_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    save('BACKUP.json',dict(status='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY',copies=copies,
        native_utility_exact_absent=True,manager_exact_dead=True,recording_success=False,
        verified_local_source_reconstruction=True,all_prior_failures_preserved=True))

    print(json.dumps(dict(status='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY',copies=copies,native_dispatched=False)))
if __name__=='__main__':main()
