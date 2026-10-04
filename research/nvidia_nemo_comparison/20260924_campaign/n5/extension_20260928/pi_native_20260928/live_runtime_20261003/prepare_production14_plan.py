"""Host-only unaccepted production14 plan; README_PRODUCTION14_PLAN.md."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import uuid

CONTENT = '5cae6376494d703a9600c020ebce725ed0f86999d1ed4ffa613a5f1485a0fd79'
MATRIX = 'fad0ad4e8728e0f7629eac0cd35001e36acce91124a622cc1c1c39e06da40b74'
ASSETS = '43d2d73160466587be1615e245a2b7d5aa212219597a82b2c40b06462e1e8ea1'
BUILDER = '8deb7b4f6ae26071597b00e27b85b401f3f9606205f026fcd451b85a46099876'
PARENT = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/'
SOURCE = PARENT+'field-runtime-v29-build-13'
DESTINATION = PARENT+'field-runtime-v29-build-14'
AUTH = {'native_launch_enabled','authorization_kind','production_acceptance_sha256','admission_sha256'}
DEPENDENCIES = ('install_candidate.py','profiles.py','optional_refiner_admission.py',
                'optional_refiner_dispatch.py','release_authorization.py')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, maximum=2*1024**2):
    path = Path(path)
    if path.is_symlink() or path.resolve(strict=True) != path or path.stat().st_size > maximum:
        raise ValueError('Canonical bounded regular input required')
    before = path.stat(); raw = path.read_bytes(); after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('Input changed while reading')
    return raw


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw): raise OSError('Short write')
        stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != raw: raise OSError('Independent readback failed')


def inventory(source, manifest_sha):
    raw = read(source/'PACKAGE_MANIFEST.json'); manifest = strict(raw)
    if sha(raw) != manifest_sha or manifest['target'] != SOURCE or manifest['candidate_content_sha256'] != CONTENT:
        raise ValueError('Exact frozen13 source pins required')
    rows = manifest['files']
    if not 1 <= len(rows) <= 512: raise ValueError('Bounded source inventory required')
    names = set(); total = 0
    for row in rows:
        name = row['path']; rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or str(rel) != name or name in names:
            raise ValueError('Unique canonical source member required')
        names.add(name); member = read(source.joinpath(*rel.parts))
        if (len(member), sha(member)) != (row['bytes'], row['sha256']): raise ValueError('Source member pin differs')
        total += len(member)
        if total > 32*1024**2: raise ValueError('Source inventory byte bound')
    actual = set()
    for path in source.rglob('*'):
        if path.is_symlink(): raise ValueError('Source link refused')
        if path.is_file(): actual.add(path.relative_to(source).as_posix())
    if actual != names|{'PACKAGE_MANIFEST.json'}: raise ValueError('Source membership differs')
    return manifest


def relocation(binding, manifest_sha, binding_raw):
    destination = copy.deepcopy(binding); changes = []
    def move(field, value):
        if value != SOURCE and not value.startswith(SOURCE+'/'): raise ValueError('Unexpected source path')
        updated = DESTINATION+value[len(SOURCE):]
        changes.append(dict(field=field, source=value, destination=updated)); return updated
    for key in ('target','reference_code','raw_factory_path'): destination[key] = move(key, binding[key])
    for key, row in destination['profiles'].items(): row['path'] = move('profiles.'+key+'.path',row['path'])
    certificate = dict(schema='just-peachy.reviewed-runtime-relocation.v1', reviewed=False,
        reviewer='PENDING actual source/evidence review', reviewed_unix=0,
        source_target=SOURCE, destination_target=DESTINATION, source_manifest_sha256=manifest_sha,
        source_binding_sha256=sha(binding_raw), candidate_content_sha256=CONTENT,
        installed_manifest_sha256=binding['installed_manifest_sha256'],
        source_operational_binding_sha256=sha(encoded({k:v for k,v in binding.items() if k not in AUTH})),
        destination_operational_binding_sha256=sha(encoded({k:v for k,v in destination.items() if k not in AUTH})),
        relocations=sorted(changes,key=lambda row:row['field']), runtime_behavior_changed=False,
        measurement_reuse_requires_separate_review=True)
    destination.update(native_launch_enabled=False,authorization_kind='qualification',
                       production_acceptance_sha256=None,admission_sha256=None)
    return destination, certificate


def prepare(source, manifest_sha, matrix_path, assets_path, builder_path, output):
    source = Path(source).resolve(strict=True); manifest = inventory(source,manifest_sha)
    binding_raw = read(source/'BINDING.json'); binding = strict(binding_raw)
    if binding['target'] != SOURCE or binding['candidate_content_sha256'] != CONTENT:
        raise ValueError('Binding source identity differs')
    matrix_raw=read(matrix_path); assets_raw=read(assets_path); builder_raw=read(builder_path)
    if (sha(matrix_raw),sha(assets_raw),sha(builder_raw)) != (MATRIX,ASSETS,BUILDER):
        raise ValueError('Exact reviewed matrix, actual assets and external builder required')
    matrix = strict(matrix_raw); actual_assets = strict(assets_raw); rows=matrix['rows']
    profile_raw=read(source/'profiles.py')
    if sha(profile_raw)!=matrix['profiles_source_sha256'] or len(rows)!=246:
        raise ValueError('Standard matrix source or count differs')
    name='_production14_profiles'; spec=importlib.util.spec_from_file_location(name,source/'profiles.py')
    module=importlib.util.module_from_spec(spec); sys.modules[name]=module
    try:
        exec(compile(profile_raw,str(source/'profiles.py'),'exec'),module.__dict__)
        for row in rows:
            if module.RuntimeSelection(**row).validate()!=row or row['optional_d1_refiner'] or row['provisional_correction']:
                raise ValueError('Matrix contains unreviewed optional/provisional selection')
    finally: sys.modules.pop(name,None)
    if len({encoded(row) for row in rows})!=246: raise ValueError('Duplicate standard selection')
    assets=copy.deepcopy(actual_assets['assets']); mapped=[]
    if len(assets)!=61 or sum(row['bytes'] for row in assets)!=664806204:
        raise ValueError('Actual selected61 asset census differs')
    for row in assets:
        original=copy.deepcopy(row)
        for key in ('path','resolved'):
            if row[key].startswith(actual_assets['package']+'/'):
                suffix=row[key][len(actual_assets['package'])+1:]
                member=read(source.joinpath(*PurePosixPath(suffix).parts))
                if (len(member),sha(member))!=(row['bytes'],row['sha256']): raise ValueError('Relocated asset differs')
                row[key]=DESTINATION+'/'+suffix
        if row!=original: mapped.append(dict(actual_source=original,destination=row))
    if len(mapped)!=1: raise ValueError('Exactly one package-local asset mapping expected')
    destination,certificate=relocation(binding,manifest_sha,binding_raw)
    plan=dict(schema='just-peachy.production-release-plan.v1',accepted=False,accepted_unix=None,
        native_launch_enabled=False,source_native_execution_claimed=False,source_frozen_manifest_sha256=manifest_sha,
        target=DESTINATION,candidate_content_sha256=CONTENT,installed_manifest_sha256=binding['installed_manifest_sha256'],
        previous_desktop_sha256=None,allowed_selections=rows,optional_refiner_admissions=[],assets=assets,
        limits=dict(maximum_session_seconds=300,maximum_developer_seconds=3600,max_drain_seconds=600,max_backlog_seconds=600),
        full_backup=None)
    values={'PRODUCTION_PLAN_NOT_AUTHORIZATION.json':plan,'RELOCATION_REQUIRES_REVIEW.json':certificate,
        'DISABLED_DESTINATION_BINDING_PREVIEW.json':destination,
        'ASSET_MAPPING_REQUIRES_REVIEW.json':dict(accepted=False,source_native_inventory_sha256=ASSETS,
            actual_source_package=actual_assets['package'],destination_target=DESTINATION,mapped_package_members=mapped,
            destination_native_inventory_claimed=False,unchanged_asset_paths=60),
        'ACTUAL_PROOFS_REQUIRED.json':dict(accepted=False,qualification13_proof_review=None,
            history_export04_closed_review=None,backup03_complete_full_backup=None,previous_desktop_sha256=None,
            standard246_selection_review=None,optional_actual13_measured_proof_and_separate14_reuse_review=None,
            actual13_research_outcomes_and_explicit_limitations=None,full_app_hour04_status='FAILED; no sustained-application pass')}
    for name,value in values.items(): write(output/name,encoded(value))
    for name,raw in (('SELECTED_ASSETS_ACTUAL_SOURCE.json',assets_raw),('SUPPORTED_DEFAULT_SELECTIONS_REQUIRES_REVIEW.json',matrix_raw)):
        write(output/name,raw)
    tools=output/'pinned-builder';write(tools/'prepare_package.py',builder_raw)
    for name in DEPENDENCIES: write(tools/name,read(source/name))
    for path in list(tools.iterdir()):
        raw=read(path)
        for suffix in ('.backup','.restore'):write(output/'tool-backups'/(path.name+suffix),raw)
    inventory(source,manifest_sha)
    review=dict(status='UNACCEPTED_PLAN_ONLY',native_executed=False,package_built=False,
        source=str(source),source_manifest_sha256=manifest_sha,source_binding_sha256=sha(binding_raw),
        candidate_content_sha256=CONTENT,standard_selection_count=246,selection_limit=256,optional_slots_remaining=10,
        asset_count=61,actual_asset_bytes=664806204,mapped_package_members=1,
        production_acceptance_limit_bytes=262144,plan_bytes=len(encoded(plan)),source_files=len(manifest['files']),
        builder_sha256=BUILDER,proofs_pending=True,full_backup03_pending=True,independent_tool_backup_restore=True)
    write(output/'REVIEW.json',encoded(review));return review


def main():
    import psutil
    process=psutil.Process();process.cpu_affinity([14])
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','source-manifest-sha256','matrix','assets','builder','output-root'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    output=Path(args.output_root)/('production14-plan-'+uuid.uuid4().hex);output.mkdir(parents=True,exist_ok=False)
    write(output/'REGISTERED_OWNER.json',encoded(dict(pid=process.pid,create_time=process.create_time(),affinity=process.cpu_affinity())))
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free<floor+16*1024**2:raise ValueError('Host free-space floor')
    result=prepare(args.source,args.source_manifest_sha256,Path(args.matrix).resolve(strict=True),
        Path(args.assets).resolve(strict=True),Path(args.builder).resolve(strict=True),output)
    print(encoded(dict(output=str(output),review=result)).decode())


if __name__=='__main__':main()
