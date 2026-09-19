"""Freeze an additive S6C execution epoch. README_S6C_FREEZE_V2.md."""
import argparse
import ast
from dataclasses import asdict
from importlib.metadata import version
import shutil
import sys
from s6c_common import *

def native_worker_functions(path):
    names={'worker_init','worker_job','extract','job_identity','make_job','validate_job','verify_job'}
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    result={n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names}
    if set(result)!=names:raise ValueError('Missing native worker/identity/validation source function')
    return result

def check_environment(previous):
    if Path(sys.executable).resolve()!=EDGE.resolve() or sys.version!=previous['python']:raise ValueError('Exact original EDGE interpreter required')
    if {name:version(name) for name in previous['versions']}!=previous['versions']:raise ValueError('Original package versions changed')
    for asset in previous['assets']:bind(asset['path'],asset['sha256'])

def freeze(epoch,registry_path,gallery_path,extra_scripts=()):
    if not epoch.isalnum():raise ValueError('Simple epoch name required')
    for name in extra_scripts:
        if Path(name).name!=name or not name.endswith('.py'):raise ValueError('Extra script must be a plain Python filename')
    previous=verified(bind(REPORT/'EPOCH2_EXECUTION_MANIFEST.json','1f7f0e10186eb1187d05d9be258372d6dfbe39ec3741c2ce2976a2ca3d005cdb'))
    for b in previous['execution_files']:bind(b['path'],b['sha256'])
    check_environment(previous)
    target=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json')
    registry_binding=bind(registry_path);gallery_binding=bind(gallery_path)
    if target.exists():
        spec=read(target)
        if spec['epoch']!=epoch or Path(spec['root']).resolve()!=(STAGING/epoch).resolve():raise ValueError('Existing epoch namespace differs')
        if spec['execution_digest']!=digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')}):raise ValueError('Existing execution digest mismatch')
        if any(spec[k]!=previous[k] for k in ('assets','versions','python','state_policy','input_index','scene_manifest')):raise ValueError('Existing native authority differs from original')
        if spec['effective_profile_registry']!=registry_binding or spec['gallery_index']!=gallery_binding:raise ValueError('Existing epoch inputs differ')
        if spec['profiles']!=verified(registry_binding)['profiles']:raise ValueError('Existing embedded profiles differ from registry')
        inventory={Path(b['path']).resolve() for b in spec['execution_files']}
        if any((Path(spec['root'])/'scripts'/name).resolve() not in inventory for name in extra_scripts):raise ValueError('Requested extra script absent from existing frozen inventory')
        for b in spec['execution_files']+spec['documentation_files']:bind(b['path'],b['sha256'])
        previous_app=Path(previous['root'])/'app'
        expected={str(Path(b['path']).relative_to(previous_app)):b['sha256'] for b in previous['execution_files'] if previous_app in Path(b['path']).parents}
        actual={str(p.relative_to(Path(spec['root'])/'app')):bind(p)['sha256'] for p in (Path(spec['root'])/'app').rglob('*.py')}
        if actual!=expected:raise ValueError('Existing copied APP inventory or bytes differ')
        for name in ('s6c_common.py','s6c_execution.py'):
            authority=next(b for b in previous['execution_files'] if Path(b['path']).name==name)
            bind(Path(spec['root'])/'scripts'/name,authority['sha256'])
        return bind(target)
    registry=verified(registry_binding);galleries=verified(gallery_binding)
    if registry['status']!='VALIDATED_REAL_V3_API' or galleries['status']!='COMPLETE':raise ValueError('Completed actual API profiles and gallery index required')
    keys=[(r['gallery_condition'],r['enrollment_tier'],r.get('case_id')) for r in galleries['rows']]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate gallery assignments')
    for row in registry['profiles']:
        if verified(row['profile_binding'])!=row['profile']:raise ValueError('Effective profile bytes differ')
        if row['gallery_condition']!='NONE' and not any(k[:2]==(row['gallery_condition'],row['enrollment_tier']) for k in keys):
            raise ValueError('Registered named condition lacks assigned gallery')
    core=['s6c_common.py','s6c_execution.py','s6c_profiles.py','s6c_replay.py','s6c_jobs.py','s6c_cue_variants.py',
        's6c_native_replay_v3.py','s6c_policy_matrix.py','s6c_policy_matrix_v2.py','s6c_policy_matrix_v3.py',
        's6c_calibrated_profiles.py','s6c_rescue_design.py','s6c_common_roster_profiles.py','s6c_freeze_v2.py']
    for name in extra_scripts:
        if Path(name).name!=name or not name.endswith('.py'):raise ValueError('Extra script must be a plain Python filename')
        if name not in core:core.append(name)
    prior_execution=next(b for b in previous['execution_files'] if Path(b['path']).name=='s6c_execution.py')
    # This freezer is standalone. The entire original worker/coordinator module
    # can therefore stay byte-identical, including imports and global settings.
    sources={name:bind(SIM/'scripts'/name) for name in core}
    sources['s6c_execution.py']=prior_execution
    prior_common=next(b for b in previous['execution_files'] if Path(b['path']).name=='s6c_common.py')
    if sources['s6c_common.py']['sha256']!=prior_common['sha256']:raise ValueError('Worker common utilities differ from original epoch2')
    if bind(S6B/'INPUT_INDEX.json')!=previous['input_index'] or bind(BANK)!=previous['scene_manifest']:raise ValueError('Canonical input/scene authority differs')
    previous_app=Path(previous['root'])/'app'
    expected={str(Path(b['path']).relative_to(previous_app)):b['sha256'] for b in previous['execution_files'] if previous_app in Path(b['path']).parents}
    actual={str(p.relative_to(APP.parent)):bind(p)['sha256'] for p in APP.rglob('*.py')}
    if actual!=expected:raise ValueError('Application bytes changed; this additive freezer requires exact original v3 app')
    admit_work(full=True);root=STAGING/epoch
    if root.exists():raise ValueError('Unreceipted epoch root exists; preserve it and use a diagnosed new namespace')
    shutil.copytree(APP,root/'app/edge_speech_pipeline',ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo'))
    copied={str(p.relative_to(root/'app')):bind(p)['sha256'] for p in (root/'app').rglob('*.py')}
    if copied!=expected:raise ValueError('Copied application bytes differ; preserve failed freeze namespace')
    (root/'scripts').mkdir()
    for name,b in sources.items():
        shutil.copy2(b['path'],root/'scripts'/name);bind(root/'scripts'/name,b['sha256'])
    for path in (SIM/'scripts').glob('README_S6C*.md'):shutil.copy2(path,root/'scripts'/path.name)
    sys.path.insert(0,str(H2/'app'))
    from edge_speech_pipeline.config import PipelineConfig
    assets=[]
    for asset in PipelineConfig().assets:
        row=asdict(asset);row['path']=str(row['path']);row['binding']=bind(asset.path,asset.sha256);assets.append(row)
    versions={name:version(name) for name in ('onnxruntime','sherpa-onnx','numpy','psutil')}
    if assets!=previous['assets'] or versions!=previous['versions'] or sys.version!=previous['python']:raise ValueError('Original model/environment authority changed')
    spec=dict(schema='jp_s6c_execution_epoch.v1',epoch=epoch,created_utc=utc(),root=str(root),
        execution_files=[bind(p) for p in sorted(root.rglob('*.py'))],documentation_files=[bind(p) for p in sorted(root.rglob('*.md'))],
        assets=assets,versions=versions,python=sys.version,profiles=registry['profiles'],effective_profile_registry=registry_binding,
        input_index=bind(S6B/'INPUT_INDEX.json'),registered_design=bind(REPORT/'design/REGISTERED_DESIGN_V1.json'),
        panel=bind(REPORT/'design/REGISTERED_PANEL_V1.json'),scene_manifest=bind(BANK),state_policy=previous['state_policy'],
        resources=previous['resources'],ordinary_conditions_truth_oracle_inputs=False,
        nominal_geometry_diagnostic=previous['nominal_geometry_diagnostic'],hardware_playback=False,
        gallery_index=gallery_binding,cue_variant_index=bind(REPORT/'CUE_VARIANT_INDEX_V1.json'),
        component_readiness=bind(REPORT/'COMPONENT_PLUMBING_READY_V2.json'),
        registration_amendment=bind(REPORT/'design/C_ONLY_CALIBRATION_AMENDMENT_V1.json'),
        rescue_registration=registry.get('rescue_registration'),common_roster_registration=registry.get('common_roster_registration'),
        followup_registration=registry.get('followup_registration'),freezer=bind(root/'scripts/s6c_freeze_v2.py'),
        additive_scope='Exact original v3 APP/models/environment, explicitly extended registry/gallery assignments and separately bound orchestration sources; previous epochs stay immutable.')
    spec['execution_digest']=digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')})
    if spec['input_index']!=previous['input_index'] or spec['scene_manifest']!=previous['scene_manifest']:raise ValueError('Canonical authority changed during freeze')
    save(target,spec,immutable=True);return bind(target)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--epoch',required=True);p.add_argument('--registry',required=True,type=Path)
    p.add_argument('--gallery-index',required=True,type=Path);p.add_argument('--extra-script',action='append',default=[])
    a=p.parse_args();print(json.dumps(freeze(a.epoch,a.registry,a.gallery_index,a.extra_script),indent=2))
