"""Verified previous batch binding; README_RUNTIME_REPROVISION_V1.md."""
import hashlib,json,re
from pathlib import Path
from field_local_manager_owners_v1 import identity

def strict(raw):
    def pairs(rows):
        out={}
        for k,v in rows:
            if k in out:raise ValueError('Duplicate JSON key')
            out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError(v)))

def read(path,maximum=262144):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>maximum:
        raise ValueError('Bounded regular previous receipt')
    return strict(path.read_bytes())

def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()

def previous(installation,preservation,guard):
    installation=Path(installation);preservation=Path(preservation)
    result=read(installation/'RESULT.json');admission=read(installation/'ADMISSION.json')
    policy_raw=(installation/'RELEASE.json').read_bytes();policy=strict(policy_raw);ph=digest(policy_raw)
    rid=policy['release_id']
    if not re.fullmatch('field-runtime-v[1-9][0-9]*',rid) or policy['manager_root']!=result['root'] or result['root']!=admission['root'] or ph!=result['policy_sha256']:
        raise ValueError('Exact previous installation')
    backup=read(preservation/'BACKUP.json')
    interrupted=backup['status']=='COMPLETE_REBOOT_INTERRUPTED_MANAGER_PC_COPY'
    if backup['status'] not in ('COMPLETE_CLOSED_RUNTIME_BATCH_PC_COPY','COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY','COMPLETE_REBOOT_INTERRUPTED_MANAGER_PC_COPY') or backup.get('manager_old_boot_only' if interrupted else 'manager_exact_dead') is not True or backup['native_utility_exact_absent'] is not True or backup['verified_complete_stream_and_readback'] is not True:
        raise ValueError('Complete normally closed batch required')
    if interrupted:
        proof=read(preservation/'RESULT.json');p=proof['preservation']
        if rid!='field-runtime-v27' or p['status']!='REBOOT_INTERRUPTED_RUNTIME_BATCH_CENSUS' or p['normal_manager_exit'] is not None or p['manager_owner']['boot_id']==proof['utility_owner']['boot_id'] or backup['recording_success'] is not True:
            raise ValueError('Exact interrupted old-boot manager preservation')
        if (preservation/'tree'/rid/'launches/launch-01/EXIT.json').exists():raise ValueError('Do not invent an exit for interrupted manager')
    failed_previous=backup['status']=='COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY'
    if failed_previous:
        if backup['recording_success'] is not False or backup['all_prior_failures_preserved'] is not True:
            raise ValueError('Failed source must stay failed')
        proof=read(preservation/'RESULT.json')
        if proof['preservation']['status']!='FAILED_SOURCE_AND_MANAGER_CLOSED_CENSUS' or proof['preservation']['exact_manager_dead'] is not True:
            raise ValueError('Independent failed manager closure required')
    roots=backup['copies']
    if rid not in roots or not set(roots)<={rid}|{Path(p).name for p in policy['recording_roots']}:
        raise ValueError('Exact complete previous roots')
    if not 1<=len(roots)<=5:raise ValueError('Bounded batch roots')
    total=0
    for name,copy in roots.items():
        guard();census=read(preservation/('CENSUS-'+name+'.json'))
        pins={p:{k:r[k] for k in ('bytes','sha256')} for p,r in census['files'].items()}
        if digest(encoded(pins))!=copy['manifest_sha256'] or len(pins)!=copy['files'] or len(census['directories'])!=copy['directories']:
            raise ValueError('Exact complete previous census')
        tree=preservation/'tree'/name
        if tree.is_symlink() or not tree.is_dir():raise ValueError('Previous copy root')
        if any(p.is_symlink() for p in tree.rglob('*')):raise ValueError('Previous copy symlink')
        actual_files={p.relative_to(tree).as_posix() for p in tree.rglob('*') if p.is_file()}
        actual_dirs={p.relative_to(tree).as_posix() for p in tree.rglob('*') if p.is_dir()}|{''}
        if actual_files!=set(pins) or actual_dirs!=set(census['directories']):raise ValueError('Previous complete membership')
        if len(pins)>1162 or len(actual_dirs)>264:raise ValueError('Original cardinality')
        for rel,row in pins.items():
            p=tree/rel
            if p.is_symlink() or p.stat().st_nlink!=1 or type(row['bytes']) is not int or not 0<=row['bytes']<=33554432 or p.stat().st_size!=row['bytes']:
                raise ValueError('Previous regular file identity/size')
            h=hashlib.sha256();count=0
            with p.open('rb') as f:
                while True:
                    block=f.read(16384)
                    if not block:break
                    h.update(block);count+=len(block);guard()
            if count!=row['bytes'] or h.hexdigest()!=row['sha256']:raise IOError('Previous independent full readback')
        subtotal=sum(row['bytes'] for row in pins.values())
        if subtotal!=copy['bytes'] or subtotal!=census['bytes']:raise ValueError('Previous extent')
        total+=subtotal
    if total>policy['allocation']['target_maximum_bytes']:raise ValueError('Previous full target allocation')
    if failed_previous:
        failures=[]
        for name in roots:
            if name==rid:continue
            gate=read(preservation/'tree'/name/'broker/GATE_RESULT.json')
            if gate['capture_closed'] is not True or gate['worker_exact_dead'] is not True or gate['pipe_closed'] is not True:
                raise ValueError('Exact failed source physical closure')
            if gate['logical_success'] is False:failures.append(name)
        if len(failures)!=1:raise ValueError('Exactly one preserved failed operation')
    nested=dict(admission['nested']);prior={}
    for row in admission['prior']:
        v=identity(row);prior[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    tree=preservation/'tree'/rid
    for path in sorted((tree/'launches').glob('*/OWNER.json')):
        raw=path.read_bytes();row=strict(raw);slot=path.parent.name
        if slot not in policy['allocation']['launch_slots'] or set(row)!={'owner','policy_sha256','slot','utc','purpose'}:
            raise ValueError('Exact previous launch envelope')
        if row['slot']!='launches/'+slot or row['policy_sha256']!=ph or row['purpose'] not in ('USER_RUNTIME_MANAGER','USER_RUNTIME_STAGE','USER_RUNTIME_GATE','USER_RUNTIME_COPY'):
            raise ValueError('Previous launch policy/role')
        rel=rid+'/'+row['slot']+'/OWNER.json'
        pin=dict(sha256=digest(raw),policy_sha256=ph,slot=row['slot'],purpose=row['purpose'])
        if rel in nested and nested[rel]!=pin:raise ValueError('Historical envelope conflict')
        nested[rel]=pin;v=identity(row['owner']);prior[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    proof=read(preservation/'RESULT.json')
    for v in (read(preservation/'NATIVE_OWNER.json'),proof['rollback_after_preservation']['owner']):
        v=identity(v);prior[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    if len(prior)>1088:raise ValueError('Original prior identity bound')
    return dict(release_id=rid,policy=policy,policy_sha256=ph,nested=nested,prior=list(prior.values()),
        complete_copy_bytes=total,complete_roots=sorted(roots),preservation=str(preservation),
        admission=admission)
