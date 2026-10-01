"""Build and independently restore the common profile capsule; README_RUNTIME_PROFILE_CAPSULE_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,base64,hashlib,json,os,shutil
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('source-bundle','policy-source','profiles-source','controller-source','output','scope'):
        ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();args.output.mkdir()
    me=psutil.Process()
    def put(path,raw):
        with path.open('xb') as f:
            if f.write(raw)!=len(raw):raise IOError('Short write')
            f.flush();os.fsync(f.fileno())
        if path.read_bytes()!=raw:raise IOError('Independent readback')
    def encoded(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    put(args.output/'REGISTERED_OWNER.json',encoded(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    def bounded(path,cap):
        if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:raise ValueError('Real bounded source')
        raw=path.read_bytes()
        if len(raw)>cap:raise ValueError('Growing source')
        return raw
    scope=json.loads(bounded(args.scope,16384));scope_root=args.scope.parent.resolve()
    if args.output.resolve().parent!=scope_root:raise ValueError('Output must be direct scope child')
    def guard(extra=0):
        if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Host scope expired')
        used=sum(p.stat().st_size for p in scope_root.rglob('*') if p.is_file())
        if used+extra>scope['maximum_bytes']:raise ValueError('Cumulative scope allocation')
        for drive,floor in [('C:/',50*1024**3),('G:/',75*1024**3)]:
            if shutil.disk_usage(drive).free<floor+extra:raise RuntimeError('Original host floors')
    guard()
    from field_runtime_profile_capsule_v1 import derive
    raw,review=derive(bounded(args.source_bundle,1048576),bounded(args.policy_source,131072),
        bounded(args.profiles_source,131072),bounded(args.controller_source,131072))
    value=json.loads(raw);members={}
    for name,text in value['files'].items():
        parts=PurePosixPath(name).parts
        if PurePosixPath(name).is_absolute() or '..' in parts or '\\' in name or ':' in name:
            raise ValueError('Canonical relative member')
        members[name]=base64.b64decode(text,validate=True)
    if len({n.casefold() for n in members})!=len(members):raise ValueError('Case alias')
    projected=2*len(raw)+sum(map(len,members.values()))+65536
    guard(projected)
    put(args.output/'BUNDLE.json',raw);put(args.output/'REVIEW.json',encoded(review))
    put(args.output/'BUNDLE_BACKUP.json',raw)
    restore=args.output/'independent-restore';restore.mkdir()
    restored={}
    # Reparse the packed backup independently; no alias to the first decoded object.
    for name,text in json.loads((args.output/'BUNDLE_BACKUP.json').read_bytes())['files'].items():
        guard();data=base64.b64decode(text,validate=True);path=restore.joinpath(*PurePosixPath(name).parts)
        path.parent.mkdir(parents=True,exist_ok=True);put(path,data)
        restored[name]=dict(path=name,bytes=len(data),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if sorted(restored.values(),key=lambda r:r['path'])!=value['manifest']['files']:
        raise ValueError('Complete independently restored manifest')
    actual={p.relative_to(restore).as_posix() for p in restore.rglob('*') if p.is_file()}
    if actual!=set(restored):raise ValueError('Exact restored membership')
    guard()
    receipt=dict(status='EXACT_PACKED_BACKUP_AND_INDEPENDENT_EXPANDED_RESTORE',
        closed_utc=datetime.now(timezone.utc).isoformat(),bundle_sha256=hashlib.sha256(raw).hexdigest(),
        files=len(restored),restored_bytes=sum(r['bytes'] for r in restored.values()),
        native_executed=False,policy_issued=False)
    put(args.output/'BACKUP.json',encoded(receipt));guard()
    print(json.dumps({**receipt,'code_members':review['code_members'],'code_bytes':review['code_bytes']}))


if __name__=='__main__':main()

