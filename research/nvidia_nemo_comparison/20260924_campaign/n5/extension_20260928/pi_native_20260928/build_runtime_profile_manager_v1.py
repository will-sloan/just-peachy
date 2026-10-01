"""Assemble the selected shared-profile manager; README_RUNTIME_MANAGER_ASSEMBLY_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,hashlib,json,os,shutil
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('manager-bundle','profile-bundle','sources','output','scope'):
        ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();a.output.mkdir()
    def encode(v):return (json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    def put(p,raw):
        with p.open('xb') as f:
            if f.write(raw)!=len(raw):raise IOError('Short write')
            f.flush();os.fsync(f.fileno())
        if p.read_bytes()!=raw:raise IOError('Readback')
    me=psutil.Process();put(a.output/'REGISTERED_OWNER.json',encode(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    scope=json.loads(a.scope.read_bytes());origin=a.scope.parent.resolve()
    if a.output.resolve().parent!=origin:raise ValueError('Scope output location')
    def guard(extra=0):
        if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Host scope expired')
        if sum(p.stat().st_size for p in origin.rglob('*') if p.is_file())+extra>scope['maximum_bytes']:raise ValueError('Cumulative host reservation')
        for drive,floor in [('C:/',50*1024**3),('G:/',75*1024**3)]:
            if shutil.disk_usage(drive).free<floor+extra:raise RuntimeError('Host floors')
    guard()
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    def bundle(path,pin):
        if path.is_symlink() or path.stat().st_size>1048576:raise ValueError('Bounded real bundle')
        raw=path.read_bytes()
        if sha(raw)!=pin:raise ValueError('Previously backed capsule pin')
        v=json.loads(raw);out={n:base64.b64decode(r,validate=True) for n,r in v['files'].items()}
        rows=v['manifest']['files']
        if rows!=[dict(path=n,bytes=len(r),sha256=sha(r)) for n,r in sorted(out.items())]:raise ValueError('Complete capsule pins')
        return out
    old=bundle(a.manager_bundle,'77aa8fa3e1dade3942db3af9a064f21a5c7f7820a2fc5079a3281c4e255f449c')
    common=bundle(a.profile_bundle,'4ec6d0f422bffbcbf85365b39707b6f0942625aeed2989e697f529b5bb051eae')
    files={n:r.replace(b'field_runtime_policy_v2',b'field_runtime_policy_v3').replace(b'field_runtime_journal_v2',b'field_runtime_journal_v3').replace(b'field_runtime_backup_v1',b'field_runtime_backup_v2') for n,r in old.items()}
    replacements={'field_runtime_manager_v1':'field_runtime_manager_v2','field_runtime_journal_v2':'field_runtime_journal_v3','field_runtime_backup_v1':'field_runtime_backup_v2','field_runtime_policy_v2':'field_runtime_policy_v3'}
    for before,after in replacements.items():
        del files['code/'+before+'.py'];raw=(a.sources/(after+'.py')).read_bytes()
        closed=json.loads((origin/('SOURCE_CLOSED_V19.json' if 'policy' not in after else 'SOURCE_CLOSED_V12.json')).read_bytes())
        # Current policy is additionally bound by the common capsule; source backup location varies historically.
        if 'policy' in after:
            if raw!=common['code/'+after+'.py']:raise ValueError('Common policy pin')
        elif closed['files'][after+'.py']!={'bytes':len(raw),'sha256':sha(raw)}:raise ValueError('Backed source drift')
        files['code/'+after+'.py']=raw
    for n in ('field_operator_session_plan_v3.py','field_operator_session_ledger_v4.py'):
        files['code/'+n]=common['code/'+n]
    key='code/field_operator_health_v1.py';text=files[key].decode()
    oldguard="""                if not model['closed'] or not model['finish_observed'] or model['samples']!=samples or stop['archive']['recorded_samples']!=samples or not stop['archive']['closed'] or stop['archive']['archive_error'] is not None:
                    raise ValueError('Closed source/model/archive accounting')"""
    newguard="""                if model['samples']!=samples or stop['archive']['recorded_samples']!=samples or not stop['archive']['closed'] or stop['archive']['archive_error'] is not None:
                    raise ValueError('Closed source/archive accounting')
                if policy['mode']=='baseline':
                    expected='E1' if policy['profile']=='baseline-titanet' else 'E0'
                    if (model.get('schema')!='just-peachy.process-owned-d0-models.v1'
                        or model.get('owner')!=parent['child_owner'] or model.get('profile')!=policy['profile']
                        or model.get('embedding')!=expected or any(x['exact_alive'] for x in owners)
                        or type(model.get('asr_loads')) is not int or type(model.get('speaker_loads')) is not int
                        or model['asr_loads']!=1 or model['speaker_loads']!=1
                        or model.get('release_requires_exact_process_exit') is not True
                        or model.get('physical_process_death_claimed') is not False):
                        raise ValueError('Actual D0 route and independently observed process closure required')
                elif not model['closed'] or not model['finish_observed']:
                    raise ValueError('Actual D1 closure/EOF accounting')"""
    if text.count(oldguard)!=1:raise ValueError('Original health boundary changed')
    files[key]=text.replace(oldguard,newguard).encode()
    names={PurePosixPath(n).stem for n in files}
    if len(files)!=16 or any(len(r)>131072 for r in files.values()) or sum(map(len,files.values()))>2097152:raise ValueError('Original manager module bounds')
    for n,r in files.items():
        compile(r,n,'exec')
        for node in ast.walk(ast.parse(r)):
            deps=[x.name.split('.')[0] for x in node.names] if isinstance(node,ast.Import) else [node.module.split('.')[0]] if isinstance(node,ast.ImportFrom) and node.module else []
            for dep in deps:
                if dep.startswith(('field_','d1_')) and dep not in names and dep!='field_operator_broker_gate_v8':raise ValueError('Missing transitive project dependency '+dep)
    manifest=dict(schema='just-peachy.local-release-manifest.v1',files=[dict(path=n,bytes=len(r),sha256=sha(r)) for n,r in sorted(files.items())])
    raw=encode(dict(manifest=manifest,files={n:base64.b64encode(r).decode() for n,r in files.items()}))
    guard(2*len(raw)+sum(map(len,files.values()))+65536)
    put(a.output/'BUNDLE.json',raw);put(a.output/'BUNDLE_BACKUP.json',raw)
    restore=a.output/'independent-restore';restore.mkdir()
    for n,s in json.loads((a.output/'BUNDLE_BACKUP.json').read_bytes())['files'].items():
        p=restore.joinpath(*PurePosixPath(n).parts);p.parent.mkdir(exist_ok=True);put(p,base64.b64decode(s,validate=True))
    if {p.relative_to(restore).as_posix() for p in restore.rglob('*') if p.is_file()}!=set(files):raise ValueError('Restore membership')
    for n,r in files.items():
        if (restore/n).read_bytes()!=r:raise ValueError('Full independent restore')
    review=dict(status='PREPARED_COMMON_PROFILE_MANAGER_BACKED_RESTORED',modules=len(files),code_bytes=sum(map(len,files.values())),
        bundle_bytes=len(raw),bundle_sha256=sha(raw),manifest_sha256=sha(encode(manifest).rstrip(b'\n')),
        closed_utc=datetime.now(timezone.utc).isoformat(),native_executed=False,policy_issued=False,
        changes={n:dict(bytes=len(r),sha256=sha(r)) for n,r in files.items() if old.get(n)!=r})
    put(a.output/'REVIEW.json',encode(review));guard();print(json.dumps({k:v for k,v in review.items() if k!='changes'}))


if __name__=='__main__':main()

