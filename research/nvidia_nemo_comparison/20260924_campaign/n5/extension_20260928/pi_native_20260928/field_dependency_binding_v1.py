"""Small contract binding over immutable pins; README_FIELD_DEPENDENCY_BINDING_V1.md."""
import json
from pathlib import Path
import field_dependencies_v2 as pins

SCHEMA='just-peachy.retained-contract-binding.v1'
CANONICAL='6b066469dc6baca11450d3710928a282416eadb5a17dcaa557a6c797191d89fd'
KEYS={'schema','base_lock','base_release','selected_release','patch','artifact_limits'}


def release_record(root):
    root=Path(root)
    if not root.is_absolute() or root.resolve()!=root:raise ValueError('Release path must be canonical')
    return dict(path=str(root),manifest_sha256=pins.sha(root/'RELEASE_MANIFEST.json'),
                contract_sha256=pins.sha(root/'config/field_contract.json'))


def checked_shape(binding):
    if type(binding) is not dict or set(binding)!=KEYS or binding['schema']!=SCHEMA:
        raise ValueError('Contract binding schema; catalogue overrides forbidden')
    if set(binding['base_lock'])!={'path','sha256'}:raise ValueError('Base lock schema')
    for key in ['base_release','selected_release']:
        if set(binding[key])!={'path','manifest_sha256','contract_sha256'}:raise ValueError('Release binding schema')
    if set(binding['artifact_limits'])!={'file','sha256','canonical_sha256','maximum_artifact_bytes'}:
        raise ValueError('Artifact binding schema')


def validate_contracts(binding):
    checked_shape(binding)
    lock=Path(binding['base_lock']['path'])
    if not lock.is_absolute() or lock.is_symlink() or lock.resolve()!=lock:raise ValueError('Base lock path')
    if pins.sha(lock)!=binding['base_lock']['sha256']:raise ValueError('Base catalogue hash mismatch')
    base=pins.read(lock)
    if base.get('schema')!='just-peachy.retained-dependencies.v1':raise ValueError('Base catalogue schema')
    for key in ['base_release','selected_release']:
        if release_record(binding[key]['path'])!=binding[key]:raise ValueError('Release binding changed')
    if base['release_contract_sha256']!=binding['base_release']['contract_sha256']:
        raise ValueError('Base catalogue contract mismatch')
    old=pins.read(Path(binding['base_release']['path'])/'config/field_contract.json')
    root=Path(binding['selected_release']['path']);new=pins.read(root/'config/field_contract.json')
    from field_artifact_binding_v1 import bound_limits
    from field_artifact_limits_v1 import digest
    limits=bound_limits(root,new)
    if digest(limits)!=CANONICAL or new['artifact_limits']!=binding['artifact_limits']:
        raise ValueError('Unsupported artifact contract')
    expected={'maximum_recording_seconds':[30,125],
              'session_reservation_bytes':[32*1024**2,64*1024**2],
              'sustained_target_seconds':[None,120],
              'archive_interchange_for_extended_recording':[None,'UNQUALIFIED'],
              'artifact_limits':[None,new['artifact_limits']]}
    actual={k:[old.get(k),new.get(k)] for k in old.keys()|new.keys() if old.get(k)!=new.get(k)}
    if actual!=expected or binding['patch']!=expected:raise ValueError('Unexpected contract patch')
    return base,limits


def describe(lock,old,new):
    old=release_record(old);new=release_record(new)
    a=pins.read(Path(old['path'])/'config/field_contract.json');b=pins.read(Path(new['path'])/'config/field_contract.json')
    value=dict(schema=SCHEMA,base_lock=dict(path=str(Path(lock)),sha256=pins.sha(lock)),base_release=old,selected_release=new,
               patch={k:[a.get(k),b.get(k)] for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)},artifact_limits=b['artifact_limits'])
    validate_contracts(value)
    return value


def verify(path,expected_sha,release_tools):
    path=Path(path)
    if path.stat().st_size>32768:raise ValueError('Small binding byte bound')
    if pins.sha(path)!=expected_sha:raise ValueError('Contract binding hash mismatch')
    value=pins.read(path);base,limits=validate_contracts(value)
    for key in ['base_release','selected_release']:release_tools.verify_release(Path(value[key]['path']))
    # Recheck all original paths, symlinks, membership and file hashes; never recollect/override.
    exact=pins.verify(value['base_lock']['path'],value['base_lock']['sha256'])
    return dict(status='RETAINED_CATALOGUE_WITH_EXACT_CONTRACT_BINDING',binding_sha256=expected_sha,
                binding_bytes=path.stat().st_size,base_catalogue_sha256=value['base_lock']['sha256'],
                base_catalogue_bytes=Path(value['base_lock']['path']).stat().st_size,
                dependency_check=exact,selected_release=value['selected_release'],artifact_limits=limits,
                catalogue_copied=False,recollection=False,import_probe=False,ldd=False,models=False,capture=False)
