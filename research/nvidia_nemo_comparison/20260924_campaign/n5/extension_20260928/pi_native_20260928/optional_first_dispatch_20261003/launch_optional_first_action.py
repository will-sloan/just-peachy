"""Injected finite optional-first service action. No execution on import. See README.md."""
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
TARGET=CAMPAIGN/'field-runtime-v29-build-08'
MANIFEST='2ec99c80d5d070c30a1b4a7959be1a9e552d5fc7688fe703ab9ad650891ee841'
BINDING='95140086d3dd68cd881d91de1414857102e23dd80408db0e26c004a95ffe9180'
CONTENT='f807d39a8155eafb6414a7f91d8856ff63507e73b027c60301db218c6fb15c10'
COMMON='f98750ac8938b3d2c485806b10cd17b7503a8075ac15d57e51bd41230d234cd5'
RECEIVER='7ab8a362770a9cc062b8d306c89968c637f3f201796853427d0787f48f0a2cae'
MIB=1024**2


def digest(raw):return hashlib.sha256(raw).hexdigest()


def document(row,maximum=262144):
    if type(row) is not dict or set(row)!={'sha256','base64'}:raise ValueError('Exact encoded source/evidence reference required')
    raw=base64.b64decode(row['base64'],validate=True)
    if len(raw)>maximum or digest(raw)!=row['sha256']:raise ValueError('Source/evidence extent or pin changed')
    return raw


def shape(p,now=None):
    now=time.time() if now is None else now
    if (p.get('schema')!='just-peachy.optional-first-dispatch.v1' or p.get('reviewed') is not True or
        p.get('package')!=TARGET.as_posix() or p.get('package_manifest_sha256')!=MANIFEST or
        p.get('binding_sha256')!=BINDING or p.get('candidate_content_sha256')!=CONTENT or
        p.get('maximum_output_bytes')!=256*MIB or p.get('independent_pc_copy_bytes')!=256*MIB or
        p.get('runtime_seconds')!=585 or not re.fullmatch(r'optional-first-\d{2}',p.get('label','')) or
        not re.fullmatch('[0-9a-f]{64}',p.get('dispatcher_sha256','')) or
        type(p.get('expires_unix')) not in (int,float) or not now<p['expires_unix']<=now+600):
        raise ValueError('Exact fresh reviewed08 short optional dispatch scope required')
    selected=p['selection'];policy=p['policy'];source=p['source']
    if (selected.get('diarizer')!='pyannote' or selected.get('input_source')!='saved' or
        selected.get('optional_d1_refiner') is not True or selected.get('allow_experimental') is not True or
        selected.get('speaker_attribution')!='retained' or selected.get('provisional_correction') is not False or
        policy.get('maximum_session_seconds')!=45 or policy.get('developer_soak') is not False or
        policy.get('max_drain_seconds')!=60 or policy.get('max_backlog_seconds')!=30 or
        source!={'kind':'saved','path':(CAMPAIGN/'d1-geometry-delayed-a76-v1/source.wav').as_posix(),
            'sha256':'0ee26e8aa6f815d8b202419aafb71ff5bc25093d193e95e972036f488c5040b8','samples':715127} or
        type(p.get('maximum_lag_seconds')) is not int or not 22<=p['maximum_lag_seconds']<=selected['revision_window_seconds']):
        raise ValueError('Explicit matched saved45 Pyannote/CurrentDelayed qualification required')
    if type(p.get('assets')) is not list or not 1<=len(p['assets'])<=512:raise ValueError('Exact bounded selected native inventory required')
    receiver=document(p['receiver'],65536)
    if digest(receiver)!=RECEIVER:raise ValueError('Only the exact reviewed owned receiver is allowed')
    compile(receiver,'<pinned-optional-receiver>','exec')
    if set(p.get('evidence',{}))!={'primary','gui'}:raise ValueError('Actual primary and GUI reviewed evidence required')
    for value in p['evidence'].values():json.loads(document(value))
    gate=p['prerequisites'];primary=dict(selected,optional_d1_refiner=False)
    if gate.get('permission_only_difference_reviewed') is True:primary['allow_experimental']=gate.get('primary_selection',{}).get('allow_experimental')
    if (gate.get('schema')!='just-peachy.optional-first-prerequisites.v2' or gate.get('reviewed') is not True or
        gate.get('candidate_content_sha256')!=CONTENT or gate.get('source')!=source or gate.get('primary_selection')!=primary or
        any(gate.get(key) is not True for key in ('primary_functional_pass','gui_functional_pass','all_owners_closed','allow_first_combined_measurement'))):
        raise ValueError('Actual same-candidate reviewed prerequisites required; no automatic pass')
    return receiver


def derive_wrapper(common,settings):
    original=common.wrapper_source(settings)
    # The two exact changes are orchestration only: bounded1Hz memory observation
    # and hash verification of external receiver/intent before it can be read.
    boundary="if SETTINGS['kind']!='full_app_hour' or unit_receipt is None"
    if original.count(boundary)!=1:raise ValueError('Frozen wrapper memory boundary changed')
    derived=original.replace(boundary,"if SETTINGS['kind'] not in ('full_app_hour','optional_first') or unit_receipt is None")
    boundary=' watcher.start();sys.argv=argv'
    if derived.count(boundary)!=1:raise ValueError('Frozen wrapper receiver boundary changed')
    insertion=""" for entry in SETTINGS['external_inputs']:
  path=out/entry['name']
  if path.is_symlink() or path.stat().st_nlink!=1 or path.stat().st_size!=entry['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Exact external qualification input changed')
 watcher.start();sys.argv=argv"""
    derived=derived.replace(boundary,insertion)
    compile(derived,'<derived-optional-wrapper>','exec')
    return derived,dict(schema='just-peachy.optional-wrapper-derivation.v1',frozen_helper_sha256=COMMON,
        original_wrapper_sha256=digest(original.encode()),derived_wrapper_sha256=digest(derived.encode()),
        changes=['enable existing bounded1Hz whole-unit memory trace for optional_first','verify exact external inputs before receiver'],
        runtime_code_changed=False)


def launch(p,baseline):
    receiver=shape(p)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot!=p['boot_id'] or any(baseline.get(key) for key in ('current_project_processes','active_recorded_owners','live_manager_owners')):
        raise ValueError('Current boot and clear existing owners required')
    helper=TARGET/'launch_raw_qualification_action.py'
    if helper.is_symlink() or digest(helper.read_bytes())!=COMMON:raise ValueError('Exact frozen common helper required')
    sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('optional_verified_common',helper)
    common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
    manifest=common.inventory(TARGET,MANIFEST)
    binding=common.strict((TARGET/'BINDING.json').read_bytes())
    if common.sha(TARGET/'BINDING.json')!=BINDING or manifest['candidate_content_sha256']!=CONTENT:raise ValueError('Frozen08 raw binding/content changed')
    profiles=common.load_pure(TARGET,'profiles')
    selection=profiles.RuntimeSelection(**p['selection']);policy=profiles.SessionPolicy(**p['policy'])
    if selection.validate()!=p['selection'] or policy.validate()!=p['policy'] or policy.total_deadline_seconds!=285:
        raise ValueError('Complete explicit unchanged finite policy required')
    if shutil.disk_usage(CAMPAIGN).free<5*1024**3+256*MIB:raise OSError('Native independent output reservation unavailable')
    unit='jp-v29-'+p['label']+'.service'
    old=subprocess.run(['systemctl','--user','show',unit,'--property=LoadState'],capture_output=True,text=True,timeout=5,check=True)
    if old.stdout.strip()!='LoadState=not-found':raise ValueError('Fresh unused unit required')
    parent=CAMPAIGN/'live-runtime-tests-20261003'
    if parent.is_symlink():raise ValueError('Real trial parent required')
    parent.mkdir(exist_ok=True);out=parent/p['label'];out.mkdir()
    gate=dict(p['prerequisites'])
    inputs=[]
    def write(name,raw):
        with (out/name).open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short owned input write')
            stream.flush();__import__('os').fsync(stream.fileno())
        if (out/name).read_bytes()!=raw:raise OSError('Owned input readback differs')
        inputs.append(dict(name=name,bytes=len(raw),sha256=digest(raw)))
    for role,row in p['evidence'].items():
        name=role.upper()+'_REVIEW.json';write(name,document(row))
        gate[role+'_review']=dict(path=str(out/name),sha256=row['sha256'])
    write('PREREQUISITES.json',common.encoded(gate))
    write('ALLOCATION.json',common.encoded(dict(schema='just-peachy.optional-first-allocation.v1',job_root=str(out),
        native_maximum_output_bytes=256*MIB,independent_backup_reserved_bytes=256*MIB,free_space_floor_bytes=5*1024**3)))
    intent={key:p[key] for key in ('package','package_manifest_sha256','selection','policy','source','assets','maximum_lag_seconds','expires_unix','dispatcher_sha256')}
    write('INTENT.json',common.encoded(intent));write('receiver.py',receiver)
    budget=dict(maximum_output_bytes=256*MIB,runtime_seconds=585,stop_seconds=30,file_limit_bytes=256*MIB,maximum_files=256)
    settings=dict(output=str(out),package=str(TARGET),unit=unit,boot_id=boot,expires_unix=p['expires_unix'],
        package_manifest_sha256=MANIFEST,scope_sha256=common.sha(TARGET/'native_scope.py'),
        research_lock=str(CAMPAIGN/'B05_PREVIEW_DISPATCH.lock'),budget=budget,kind='optional_first',
        argv=[str(out/'receiver.py'),str(out)],external_inputs=inputs)
    wrapper,derivation=derive_wrapper(common,settings)
    common.put(out/'WRAPPER_DERIVATION.json',derivation)
    # Derivation includes wrapperSHA, so it cannot be included inside that same
    # wrapper. It is independently bound by the complete worker request context.
    write('wrapper.py',wrapper.encode())
    deadline=time.time()+630
    common.put(out/'ADMISSION.json',dict(payload=p,budget=budget,binding_sha256=BINDING,
        wrapper_sha256=digest(wrapper.encode()),receiver_sha256=digest(receiver),
        independent_host_reservation_bytes=256*MIB,target_reservation_bytes=256*MIB,deadline_unix=deadline,
        source_only=False,capture=False,asr=True,native_qualification_claimed=False))
    args=['systemd-run','--user','--unit='+unit,'--description=JustPeachyOptionalFirstQualification',
        '--property=AllowedCPUs=2,3','--property=CPUQuota=200%','--property=TasksMax=64','--property=RuntimeMaxSec=585',
        '--property=TimeoutStopSec=30','--property=KillMode=control-group']
    env={'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1',
         'MALLOC_ARENA_MAX':'1','MALLOC_MMAP_THRESHOLD_':'131072','MALLOC_TRIM_THRESHOLD_':'131072','PYTHONDONTWRITEBYTECODE':'1'}
    args.extend('--setenv='+key+'='+value for key,value in env.items())
    args.extend([binding['python'],'-B',str(out/'wrapper.py')])
    started=subprocess.run(args,capture_output=True,text=True,timeout=10)
    common.put(out/'SYSTEMD_RUN.json',dict(returncode=started.returncode,stdout=started.stdout[:4096],stderr=started.stderr[:4096]))
    if started.returncode:raise RuntimeError('Owned optional service creation failed; evidence retained')
    limit=time.monotonic()+5
    while not (out/'OWNER.json').exists() and time.monotonic()<limit:time.sleep(.05)
    owner=common.strict((out/'OWNER.json').read_bytes()) if (out/'OWNER.json').exists() else None
    shown=subprocess.run(['systemctl','--user','show',unit,'--property=InvocationID,MainPID,ActiveState,ControlGroup'],capture_output=True,text=True,timeout=5,check=True)
    props=dict(line.split('=',1) for line in shown.stdout.splitlines() if '=' in line)
    result=dict(schema='just-peachy.native-component-job.v1',boot_id=boot,unit=unit,invocation_id=props.get('InvocationID'),
        control_group=props.get('ControlGroup'),owner=owner,output_root=str(out),maximum_output_bytes=256*MIB,
        maximum_output_files=256,independent_pc_copy_bytes=256*MIB,package_manifest_sha256=MANIFEST,
        issued_unix=time.time(),deadline_unix=deadline,properties=props,workflow='optional-first-finite-saved')
    common.put(out/'JOB.json',result)
    return result


if 'PAYLOAD' in globals():RESULT=launch(PAYLOAD,BASELINE)
