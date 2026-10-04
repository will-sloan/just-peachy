"""Exact reviewed post08 initial/followup qualification action. See README.md."""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

CAMPAIGN=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
COMMON='be42aa3dd44c01420a097a3aa6997545fa8b4b85138e18a160b32cac8b0c60e0'
QUALIFICATION='92b91aa392876d2448b22bc0180b8888e314720d19cc30ddb0ffc81120678cc6'
RECEIVER='b888b2bbdf0d3b9d01f3bb5623706a52bac6ea20ed7d16d05a038fa7108e0d20'
MIB=1024**2


def digest(raw):return hashlib.sha256(raw).hexdigest()


def document(row,maximum=262144):
    if type(row) is not dict or set(row)!={'sha256','base64'}:raise ValueError('Exact encoded reviewed document required')
    raw=base64.b64decode(row['base64'],validate=True)
    if len(raw)>maximum or digest(raw)!=row['sha256']:raise ValueError('Document extent/pin differs')
    return raw


def shape(p,now=None):
    now=time.time() if now is None else now
    if len(json.dumps(p,sort_keys=True,separators=(',',':'),allow_nan=False).encode())>220000:
        raise ValueError('Complete dispatch payload must fit bounded native admission receipt')
    followup=p.get('stage')=='followup_policy'
    if p.get('stage') not in ('initial','followup_policy'):raise ValueError('Explicit finite qualification stage required')
    runtime=840 if followup else 585;seconds=300 if followup else 45
    label=r'optional-followup-\d{2}' if followup else r'optional-first-\d{2}'
    if (p.get('schema')!='just-peachy.optional-owned-dispatch.v1' or p.get('reviewed') is not True or
        not re.fullmatch(re.escape(CAMPAIGN.as_posix())+r'/field-runtime-v29-build-[0-9]{2}',p.get('package','')) or
        p.get('common_sha256')!=COMMON or p.get('runtime_seconds')!=runtime or
        not re.fullmatch(label,p.get('label','')) or type(p.get('maximum_output_bytes')) is not int or
        not 256*MIB<=p['maximum_output_bytes']<=512*MIB or
        p.get('independent_pc_copy_bytes')!=p['maximum_output_bytes'] or
        type(p.get('expires_unix')) not in (int,float) or not now<p['expires_unix']<=now+600):
        raise ValueError('Exact reviewed09 finite owner/output scope required')
    for key in ('package_manifest_sha256','binding_sha256','candidate_content_sha256','common_sha256','dispatcher_sha256'):
        if not re.fullmatch('[0-9a-f]{64}',p.get(key,'')):raise ValueError('Exact candidate/action pins required')
    selected=p['selection'];policy=p['policy'];source=p['source']
    if (selected.get('diarizer')!='pyannote' or selected.get('input_source')!=('live' if followup else 'saved') or
        selected.get('optional_d1_refiner') is not True or selected.get('allow_experimental') is not True or
        selected.get('speaker_attribution')!='retained' or selected.get('provisional_correction') is not False or
        policy!={'maximum_session_seconds':seconds,'developer_soak':False,'max_drain_seconds':60,
            'max_backlog_seconds':30,'model_load_seconds':120,'cleanup_seconds':60} or
        type(p.get('maximum_lag_seconds')) is not int or not 22<=p['maximum_lag_seconds']<=selected['revision_window_seconds']):
        raise ValueError('Exact finite Pyannote/CurrentDelayed policy required')
    if followup:
        if set(source)!={'kind','config_sha256'} or source['kind']!='live' or not re.fullmatch('[0-9a-f]{64}',source['config_sha256']):
            raise ValueError('Exact qualified live config source required')
        if set(p.get('feasibility_evidence',{}))!={'execution','measurement','closure'}:
            raise ValueError('Actual first combined execution/measurement/closure required')
        for value in p['feasibility_evidence'].values():json.loads(document(value))
        json.loads(document(p['feasibility_review']))
    elif (source!={'kind':'saved','path':(CAMPAIGN/'d1-geometry-delayed-a76-v1/source.wav').as_posix(),
            'sha256':'0ee26e8aa6f815d8b202419aafb71ff5bc25093d193e95e972036f488c5040b8','samples':715127} or
        p.get('feasibility_evidence') is not None or p.get('feasibility_review') is not None):
        raise ValueError('Initial matched source and no invented prior combined pass required')
    if type(p.get('assets')) is not list or not 1<=len(p['assets'])<=512:raise ValueError('Bounded actual asset inventory required')
    if set(p.get('evidence',{}))!={'primary','gui'}:raise ValueError('Actual primary/GUI review bytes required')
    for value in p['evidence'].values():json.loads(document(value))
    candidate=json.loads(document(p['candidate_review']))
    expected=dict(schema='just-peachy.optional-reviewed-candidate.v1',reviewed=True,target=p['package'],
        package_manifest_sha256=p['package_manifest_sha256'],binding_sha256=p['binding_sha256'],
        candidate_content_sha256=p['candidate_content_sha256'],qualification_module_sha256=QUALIFICATION,
        common_sha256=p['common_sha256'],source_difference_reviewed=True,native_execution_claimed=False)
    if any(candidate.get(key)!=value for key,value in expected.items()):raise ValueError('Explicit actual09 derivative review required')
    document(candidate['derivation_receipt'])
    receiver=document(p['receiver'],65536)
    if digest(receiver)!=RECEIVER:raise ValueError('Exact09 receiver source required')
    compile(receiver,'<reviewed09-receiver>','exec')
    return receiver


def derive_wrapper(common,settings):
    original=common.wrapper_source(settings)
    boundary="if SETTINGS['kind']!='full_app_hour' or unit_receipt is None"
    if original.count(boundary)!=1:raise ValueError('Reviewed wrapper memory boundary changed')
    derived=original.replace(boundary,"if SETTINGS['kind'] not in ('full_app_hour','optional_first','optional_followup') or unit_receipt is None")
    boundary=' watcher.start();sys.argv=argv'
    if derived.count(boundary)!=1:raise ValueError('Reviewed wrapper receiver boundary changed')
    inserted=""" for entry in SETTINGS['external_inputs']:
  path=out/entry['name']
  if path.is_symlink() or path.stat().st_nlink!=1 or path.stat().st_size!=entry['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Exact optional external input changed')
 watcher.start();sys.argv=argv"""
    derived=derived.replace(boundary,inserted);compile(derived,'<reviewed09-wrapper>','exec')
    return derived,dict(schema='just-peachy.optional-wrapper-derivation.v1',
        frozen_helper_sha256=settings['common_sha256'],original_wrapper_sha256=digest(original.encode()),
        derived_wrapper_sha256=digest(derived.encode()),runtime_code_changed=False,
        changes=['enable existing bounded1Hz whole-unit memory trace for optional qualification','verify exact external inputs before receiver'])


def launch(p,baseline):
    receiver=shape(p);followup=p['stage']=='followup_policy'
    target=Path(p['package'])
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot!=p['boot_id'] or any(baseline.get(key) for key in ('current_project_processes','active_recorded_owners','live_manager_owners')):
        raise ValueError('Current boot and clear exact existing ownership required')
    helper=target/'launch_raw_qualification_action.py'
    if helper.is_symlink() or digest(helper.read_bytes())!=p['common_sha256']:raise ValueError('Exact pinned09 shared wrapper helper required')
    sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('optional09_verified_common',helper)
    common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
    manifest=common.inventory(target,p['package_manifest_sha256']);binding=common.strict((target/'BINDING.json').read_bytes())
    if (common.sha(target/'BINDING.json')!=p['binding_sha256'] or manifest['candidate_content_sha256']!=p['candidate_content_sha256'] or
        binding['target']!=str(target) or common.sha(target/'optional_refiner_qualification.py')!=QUALIFICATION):
        raise ValueError('Complete exact09 execution identity required')
    sys.path.insert(0,str(target))
    profiles=common.load_pure(target,'profiles');qualification=common.load_pure(target,'optional_refiner_qualification')
    selection=profiles.RuntimeSelection(**p['selection']);policy=profiles.SessionPolicy(**p['policy'])
    if selection.validate()!=p['selection'] or policy.validate()!=p['policy']:raise ValueError('Explicit complete controls required')
    plan=qualification.qualification_output_plan(binding,selection,policy,p['stage'])
    if p.get('output_plan')!=plan or p['maximum_output_bytes']!=plan['native_maximum_output_bytes']:
        raise ValueError('Complete calculated native and PC output reservations differ')
    from optional_refiner_admission import operational_binding_sha256
    from release_authorization import selected_inventory_sha256
    pins=dict(candidate_content_sha256=binding['candidate_content_sha256'],installed_manifest_sha256=binding['installed_manifest_sha256'],
        operational_binding_sha256=operational_binding_sha256(binding),selected_asset_inventory_sha256=selected_inventory_sha256(binding,selection,p['assets']))
    if p.get('pins')!=pins:raise ValueError('Actual selected runtime/asset pins differ')
    row=dict(stage=p['stage'],source=p['source'])
    if followup:
        feasible=json.loads(document(p['feasibility_review']))
        row.update(reviewed_feasibility=feasible,feasibility_review_sha256=p['feasibility_review']['sha256'])
        qualification.validate_feasibility(feasible,selection,pins)
    qualification.validate_prerequisite_gate(p['prerequisites'],row,selection,binding,pins)
    if shutil.disk_usage(CAMPAIGN).free<5*1024**3+p['maximum_output_bytes']:raise OSError('Full native output reserve unavailable')
    unit='jp-v29-'+p['label']+'.service'
    old=subprocess.run(['systemctl','--user','show',unit,'--property=LoadState'],capture_output=True,text=True,timeout=5,check=True)
    if old.stdout.strip()!='LoadState=not-found':raise ValueError('Fresh unused unit required')
    parent=CAMPAIGN/'live-runtime-tests-20261003'
    if parent.is_symlink():raise ValueError('Real owned trial parent required')
    parent.mkdir(exist_ok=True);out=parent/p['label'];out.mkdir();inputs=[]
    def write(name,raw):
        with (out/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short owned input write')
            stream.flush();__import__('os').fsync(stream.fileno())
        if (out/name).read_bytes()!=raw:raise OSError('Input readback differs')
        inputs.append(dict(name=name,bytes=len(raw),sha256=digest(raw)))
    gate=dict(p['prerequisites'])
    for role,value in p['evidence'].items():
        name=role.upper()+'_REVIEW.json';write(name,document(value))
        if gate[role+'_review']['sha256']!=value['sha256']:raise ValueError('Exact original prerequisite review differs')
        gate[role+'_review']=dict(path=str(out/name),sha256=value['sha256'])
    if followup:
        for role,value in p['feasibility_evidence'].items():
            name='FIRST_'+role.upper()+'.json'
            if feasible[role]!={'path':str(out/name),'sha256':value['sha256']}:
                raise ValueError('Exact copied first-trial evidence reference required')
            write(name,document(value))
        write('FEASIBILITY_REVIEW.json',document(p['feasibility_review']))
    write('PREREQUISITES.json',common.encoded(gate));write('CANDIDATE_REVIEW.json',document(p['candidate_review']))
    write('ALLOCATION.json',common.encoded(dict(schema='just-peachy.optional-first-allocation.v1',job_root=str(out),
        native_maximum_output_bytes=p['maximum_output_bytes'],independent_backup_reserved_bytes=p['maximum_output_bytes'],
        free_space_floor_bytes=5*1024**3,output_plan=plan)))
    intent={key:p[key] for key in ('stage','package','package_manifest_sha256','selection','policy','source','assets','maximum_lag_seconds','expires_unix','dispatcher_sha256')}
    write('INTENT.json',common.encoded(intent));write('receiver.py',receiver)
    budget=dict(maximum_output_bytes=p['maximum_output_bytes'],runtime_seconds=p['runtime_seconds'],stop_seconds=30,
        file_limit_bytes=p['maximum_output_bytes'],maximum_files=256)
    settings=dict(output=str(out),package=str(target),unit=unit,boot_id=boot,expires_unix=p['expires_unix'],
        package_manifest_sha256=p['package_manifest_sha256'],common_sha256=p['common_sha256'],scope_sha256=common.sha(target/'native_scope.py'),
        research_lock=str(CAMPAIGN/'B05_PREVIEW_DISPATCH.lock'),budget=budget,kind='optional_followup' if followup else 'optional_first',
        argv=[str(out/'receiver.py'),str(out)],external_inputs=inputs)
    wrapper,derivation=derive_wrapper(common,settings);common.put(out/'WRAPPER_DERIVATION.json',derivation)
    write('wrapper.py',wrapper.encode());deadline=time.time()+p['runtime_seconds']+45
    common.put(out/'ADMISSION.json',dict(payload=p,budget=budget,binding_sha256=p['binding_sha256'],
        wrapper_sha256=digest(wrapper.encode()),receiver_sha256=digest(receiver),
        independent_host_reservation_bytes=p['maximum_output_bytes'],target_reservation_bytes=p['maximum_output_bytes'],deadline_unix=deadline,
        source_only=False,capture=followup,asr=True,native_qualification_claimed=False))
    args=['systemd-run','--user','--unit='+unit,'--description=JustPeachyOptionalQualification',
        '--property=AllowedCPUs=2,3','--property=CPUQuota=200%','--property=TasksMax=64',
        '--property=RuntimeMaxSec='+str(p['runtime_seconds']),'--property=TimeoutStopSec=30','--property=KillMode=control-group']
    env={'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1',
        'MALLOC_ARENA_MAX':'1','MALLOC_MMAP_THRESHOLD_':'131072','MALLOC_TRIM_THRESHOLD_':'131072','PYTHONDONTWRITEBYTECODE':'1'}
    args.extend('--setenv='+key+'='+value for key,value in env.items());args.extend([binding['python'],'-B',str(out/'wrapper.py')])
    started=subprocess.run(args,capture_output=True,text=True,timeout=10)
    common.put(out/'SYSTEMD_RUN.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    if started.returncode:raise RuntimeError('Optional unit creation failed; evidence retained')
    limit=time.monotonic()+5
    while not (out/'OWNER.json').exists() and time.monotonic()<limit:time.sleep(.05)
    owner=common.strict((out/'OWNER.json').read_bytes()) if (out/'OWNER.json').exists() else None
    shown=subprocess.run(['systemctl','--user','show',unit,'--property=InvocationID,MainPID,ActiveState,ControlGroup'],capture_output=True,text=True,timeout=5,check=True)
    props=dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
    result=dict(schema='just-peachy.native-component-job.v1',boot_id=boot,unit=unit,invocation_id=props.get('InvocationID'),
        control_group=props.get('ControlGroup'),owner=owner,output_root=str(out),maximum_output_bytes=p['maximum_output_bytes'],
        maximum_output_files=256,independent_pc_copy_bytes=p['maximum_output_bytes'],package_manifest_sha256=p['package_manifest_sha256'],
        issued_unix=time.time(),deadline_unix=deadline,properties=props,
        workflow='optional-followup-live-policy' if followup else 'optional-first-finite-saved',
        output_plan=plan,runtime_seconds=p['runtime_seconds'],duration_seconds=policy.maximum_session_seconds)
    common.put(out/'JOB.json',result);return result


if 'PAYLOAD' in globals():RESULT=launch(PAYLOAD,BASELINE)
