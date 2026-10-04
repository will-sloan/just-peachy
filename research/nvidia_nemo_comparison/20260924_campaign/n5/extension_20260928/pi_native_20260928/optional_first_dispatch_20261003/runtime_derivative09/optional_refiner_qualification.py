"""Finite optional qualification, same frozen runtime. README_OPTIONAL_QUALIFICATION.md."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import threading
import time

MIB=1024**2
SCHEMA='just-peachy.optional-first-combined-qualification.v2'
STATE={}
LOCK=threading.Lock()


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def read_json(path,pin,maximum=262144):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>maximum:
        raise ValueError('Bounded regular qualification input required')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Qualification input pin changed')
    return strict(raw),raw


def strict(raw):
    def pairs(items):
        value={}
        for key,item in items:
            if key in value:raise ValueError('Duplicate qualification key')
            value[key]=item
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))


def pin(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}',value):raise ValueError('Exact SHA256 required')
    return value


def validate_permit(raw,sha256,selection,policy,expected_pins,context,phase):
    if phase not in ('pre_primary','pre_child'):raise ValueError('Explicit admission phase required')
    if type(raw) is not bytes or len(raw)>262144 or hashlib.sha256(raw).hexdigest()!=pin(sha256):
        raise ValueError('Exact finite qualification permit required')
    row=strict(raw);selected=selection.validate();reserved=policy.validate()
    stage=row.get('stage')
    purposes={'initial':'FIRST_COMBINED_MEASUREMENT_ONLY','followup_policy':'FOLLOWUP_POLICY_MEASUREMENT_ONLY'}
    if (stage not in purposes or row.get('schema')!=SCHEMA or row.get('purpose')!=purposes.get(stage) or
        row.get('production_eligible') is not False or row.get('prior_production_pass_claimed') is not False or
        row.get('base_target')!=context['target'] or row.get('base_content_sha256')!=expected_pins['candidate_content_sha256'] or
        row.get('selection')!=selected or row.get('policy')!=reserved or row.get('pins')!=expected_pins):
        raise ValueError('Separate exact first-qualification scope required')
    if (selected.get('optional_d1_refiner') is not True or selected['diarizer']!='pyannote' or
        selected['allow_experimental'] is not True or
        selected['provisional_correction'] or selected['speaker_attribution']!='retained' or
        selected['refinement_profile']!='current_delayed' or reserved['developer_soak'] or
        not 1<=reserved['maximum_session_seconds']<=(60 if stage=='initial' else 300)):
        raise ValueError('Qualification requires finite ordinary Pyannote plus anonymous delayed D1 policy')
    if stage=='initial' and (selected['input_source']!='saved' or row.get('prior_combined_pass_claimed') is not False):
        raise ValueError('Initial qualification requires short saved source and no claimed prior combined pass')
    if stage=='followup_policy':
        if row.get('prior_combined_pass_claimed') is not True:
            raise ValueError('Follow-up requires explicitly reviewed prior combined feasibility')
        validate_feasibility(row.get('reviewed_feasibility'),selection,expected_pins)
    keys={'candidate_content_sha256','installed_manifest_sha256','operational_binding_sha256','selected_asset_inventory_sha256'}
    if set(expected_pins)!=keys:
        raise ValueError('Complete exact frozen execution and asset pins required')
    for value in expected_pins.values():pin(value)
    issued,expires=row.get('issued_unix'),row.get('expires_unix')
    if (type(issued) not in (int,float) or type(expires) not in (int,float) or
        not all(math.isfinite(v) for v in (issued,expires)) or not issued<=context['now_unix']<expires or
        not 0<expires-issued<=900 or row.get('boot_id')!=context['boot_id'] or row.get('unit')!=context['unit'] or
        context['unit_remaining_seconds']<policy.total_deadline_seconds+30):
        raise ValueError('Current boot, exact unit and finite remaining lifetime required')
    if not re.fullmatch('[0-9a-f]{32}',row.get('nonce','')):raise ValueError('One-use qualification nonce required')
    if not 1536*MIB<=context['physical_ram_bytes']<=2048*MIB or row.get('physical_ram_bytes')!=context['physical_ram_bytes']:
        raise ValueError('Exact current 2GB MemTotal required')
    limits=row.get('limits',{})
    required=dict(primary_as_bytes=768*MIB,child_as_bytes=768*MIB,
        whole_unit_rss_soft_stop_bytes=1024*MIB,available_ram_floor_bytes=192*MIB,
        initial_available_ram_bytes=1216*MIB,child_physical_planning_reserve_bytes=256*MIB,
        reserved_optional_output_bytes=4*MIB)
    if any(type(limits.get(key)) is not int or limits[key]!=value for key,value in required.items()):
        raise ValueError('Reviewed separate virtual/physical/output envelope required')
    lag=limits.get('maximum_lag_seconds')
    if type(lag) is not int or not 22<=lag<=selected['revision_window_seconds']:
        raise ValueError('Finite useful delayed-D1 lag within the revision window required')
    available=context['available_ram_bytes'];rss=context['whole_unit_rss_bytes']
    if type(available) is not int or type(rss) is not int or not 0<=rss<=limits['whole_unit_rss_soft_stop_bytes']:
        raise ValueError('Actual whole-unit physical-memory measurement required')
    if phase=='pre_primary':
        if available<limits['initial_available_ram_bytes']:raise MemoryError('Initial available RAM below1216MiB qualification guard')
    elif (available<limits['available_ram_floor_bytes']+limits['child_physical_planning_reserve_bytes'] or
          rss+limits['child_physical_planning_reserve_bytes']>limits['whole_unit_rss_soft_stop_bytes']):
        raise MemoryError('Loaded primary leaves insufficient reviewed physical child headroom')
    # This is permission to collect evidence, never a MEASURED_* result.
    return row


def validate_feasibility(value,selection,pins):
    """Reviewed closed short trial permits measurement only, never production."""
    if type(value) is not dict:raise ValueError('Explicit reviewed feasibility evidence required')
    previous=value.get('selection',{})
    actual=dict(selection.validate())
    old=dict(previous)
    if old.get('input_source')!=actual['input_source']:
        if value.get('source_change_reviewed') is not True:raise ValueError('Explicit saved-to-live source review required')
        old['input_source']=actual['input_source']
    # Source changes also change selected host assets; reviewer records both inventories.
    if (value.get('schema')!='just-peachy.optional-feasibility-review.v1' or value.get('reviewed') is not True or
        value.get('production_eligible') is not False or old!=actual or
        value.get('followup_pins')!=pins or value.get('candidate_content_sha256')!=pins['candidate_content_sha256'] or
        value.get('operational_binding_sha256')!=pins['operational_binding_sha256'] or
        any(value.get(k) is not True for k in ('complete_primary_eof','complete_refiner_eof','all_models_closed',
            'all_owners_dead','cgroup_empty','full_mirror_verified','allow_followup_policy_measurement')) or
        type(value.get('source_samples')) is not int or value['source_samples']<=0 or value.get('dropped_samples')!=0):
        raise ValueError('Same-runtime closed measured feasibility review required')
    for key in ('execution','measurement','closure'):
        if type(value.get(key)) is not dict or set(value[key])!={'path','sha256'}:raise ValueError('Exact feasibility evidence references required')
        pin(value[key]['sha256'])
    return value


def _owner(pid):
    return dict(pid=pid,start_ticks=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def launch_context_sha256(request):
    return hashlib.sha256(encoded({key:value for key,value in request.items()
        if key!='optional_refiner_qualification'})).hexdigest()


def context():
    from optional_refiner_resources import snapshot
    value=snapshot(STATE['row']['unit'])
    return dict(value,now_unix=time.time(),boot_id=STATE['owner']['boot_id'],
        target=STATE['binding']['target'],unit=STATE['row']['unit'],
        unit_remaining_seconds=STATE['unit']['deadline_monotonic']-time.monotonic())


def qualification_output_plan(binding,selection,policy,stage):
    """Complete finite physical output reservation, separate from process AS."""
    if stage not in ('initial','followup_policy'):
        raise ValueError('Explicit qualification allocation stage required')
    from storage import StoragePolicy
    disk=StoragePolicy(**binding.get('storage_policy',{}))
    metadata=16*MIB+policy.maximum_session_seconds*256*1024
    spec=dict(duration_seconds=policy.maximum_session_seconds,sample_rate=16000,
              mode='processed',metadata_reserve_bytes=metadata)
    if binding.get('raw_adapter_enabled') is True and selection.input_source=='live':
        # Allocation only. The unchanged worker independently verifies its exact
        # raw proof before opening a physical source or accepting samples.
        spec.update(mode='raw_processed',raw=dict(sample_rate=16000,channels=4,
            sample_width_bytes=4,encoding='PCM_S32LE',
            qualification=dict(qualified=True,evidence='allocation only; worker verifies actual receipt')))
    audio_metadata=disk.estimate_bytes(spec)
    primary_extra=metadata+disk.metadata_allowance_bytes+10*MIB
    optional_bytes=4*MIB
    unit_trace_bytes=16*MIB
    complete=audio_metadata+primary_extra+optional_bytes+unit_trace_bytes
    maximum=256*MIB if stage=='initial' else max(256*MIB,complete)
    if complete>maximum or maximum>512*MIB:
        raise ValueError('Complete qualification output exceeds exact finite stage allocation')
    return dict(schema='just-peachy.optional-output-plan.v1',stage=stage,
        source_kind=selection.input_source,session_seconds=policy.maximum_session_seconds,
        mode=spec['mode'],audio_and_metadata_bytes=audio_metadata,
        additional_primary_allocation_bytes=primary_extra,optional_output_bytes=optional_bytes,
        outer_unit_trace_bytes=unit_trace_bytes,computed_output_bytes=complete,
        native_maximum_output_bytes=maximum,maximum_files=256)


def initialize(request,binding,owner_directory,identity,authorization):
    if authorization.get('authorization_kind')!='qualification':
        raise ValueError('First-combined permit requires the separate finite qualification entry point')
    ref=request['optional_refiner_qualification']
    if type(ref) is not dict or set(ref)!={'path','sha256'}:raise ValueError('Exact first-qualification permit reference required')
    row,raw=read_json(ref['path'],ref['sha256'])
    if row.get('launch_context_sha256')!=launch_context_sha256(request):
        raise ValueError('Permit does not cover this exact complete launch request')
    target=Path(binding['target'])
    if not re.fullmatch('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-[0-9]+',str(target)):
        raise ValueError('Explicit frozen runtime target required')
    if not re.fullmatch(r'[A-Za-z0-9_.@-]+\.(service|scope)',request['unit']):raise ValueError('Exact unit required')
    manifest,_=read_json(target/'PACKAGE_MANIFEST.json',row['package_manifest_sha256'],1048576)
    if manifest['candidate_content_sha256']!=binding['candidate_content_sha256'] or manifest['target']!=str(target):
        raise ValueError('Qualification must execute the exact frozen candidate being measured')
    for entry in manifest['files']:
        relative=Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts or digest(target/relative)!=entry['sha256']:
            raise ValueError('Frozen qualification runtime bytes changed')
    if digest(request['binding'])!=request['binding_sha256']:
        raise ValueError('Actual measured raw binding changed')
    from optional_refiner_admission import operational_binding_sha256
    from profiles import RuntimeSelection,SessionPolicy
    selection=RuntimeSelection(**request['selection']);policy=SessionPolicy(**request['policy'])
    from release_authorization import selected_inventory_sha256
    pins=dict(candidate_content_sha256=binding['candidate_content_sha256'],installed_manifest_sha256=binding['installed_manifest_sha256'],
        operational_binding_sha256=operational_binding_sha256(binding),
        selected_asset_inventory_sha256=selected_inventory_sha256(binding,selection,row['assets']))
    if row.get('pins')!=pins:raise ValueError('Exact runtime, operational binding and asset inventory required')
    unit,_=read_json(row['unit_ownership_path'],row['unit_ownership_sha256'])
    if (unit['unit']!=request['unit'] or unit['unit']!=row['unit'] or unit['main_pid']!=unit['owner']['pid'] or
        not 1<=unit['runtime_max_seconds']<=900 or _owner(unit['owner']['pid'])!=unit['owner'] or
        unit['owner']['boot_id']!=row['boot_id']):
        raise ValueError('Actual live owner, boot and finite unit required')
    properties=subprocess.run(['systemctl','--user','show',request['unit'],
        '--property=ActiveState,AllowedCPUs,CPUQuotaPerSecUSec,TasksMax,MainPID,InvocationID,ControlGroup,RuntimeMaxUSec'],
        capture_output=True,text=True,timeout=5,check=True).stdout
    props=dict(line.split('=',1) for line in properties.splitlines() if '=' in line)
    text=props.get('RuntimeMaxUSec','');units={'us':.000001,'ms':.001,'s':1.,'min':60.,'h':3600.,'d':86400.}
    pieces=re.findall(r'([0-9]+(?:\.[0-9]+)?)(us|ms|min|s|h|d)',text)
    remainder=re.sub(r'([0-9]+(?:\.[0-9]+)?)(us|ms|min|s|h|d)','',text).strip()
    if (not pieces or remainder or abs(sum(float(v)*units[k] for v,k in pieces)-unit['runtime_max_seconds'])>.01 or
        props.get('ActiveState')!='active' or props.get('AllowedCPUs') not in ('2-3','2,3') or
        props.get('CPUQuotaPerSecUSec')!='2s' or props.get('TasksMax')!='64' or
        props.get('MainPID')!=str(unit['main_pid']) or props.get('InvocationID')!=unit['invocation_id'] or
        props.get('ControlGroup')!=unit['control_group'] or
        os.environ.get('INVOCATION_ID')!=unit['invocation_id'] or
        Path('/proc/self/cgroup').read_text().strip()!='0::'+unit['control_group']):
        raise ValueError('Actual finite shared CPU2/3, quota200%, Tasks64 scope differs')
    job=Path(row['job_root']).resolve();output=Path(owner_directory).resolve()
    if (output!=job/'worker' or not str(job).startswith('/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/') or
        request['data_root']!=str(job/'recordings') or request.get('repeat_input_seconds') is not None or request.get('saved_session_id')):
        raise ValueError('Qualification requires one fresh isolated finite source, without repeated input')
    allocation,_=read_json(row['allocation_path'],row['allocation_sha256'])
    output_plan=qualification_output_plan(binding,selection,policy,row['stage'])
    output_bytes=output_plan['native_maximum_output_bytes']
    if (allocation.get('schema')!='just-peachy.optional-first-allocation.v1' or allocation.get('job_root')!=str(job) or
        allocation.get('native_maximum_output_bytes')!=output_bytes or allocation.get('output_plan')!=output_plan or
        type(allocation.get('independent_backup_reserved_bytes')) is not int or allocation['independent_backup_reserved_bytes']<output_bytes or
        allocation.get('free_space_floor_bytes')!=5*1024**3):
        raise ValueError('Exact complete stage-specific native and independent mirror reservations required')
    import shutil
    if shutil.disk_usage(job).free<output_bytes+5*1024**3:raise OSError('Actual free-space floor unavailable')
    claim=job/('CLAIM-'+row['nonce']+'.json')
    with claim.open('xb') as stream:
        stream.write(encoded(dict(owner=identity,permit_sha256=ref['sha256'])));stream.flush();os.fsync(stream.fileno())
    if any(os.environ.get(key) for key in ('LD_PRELOAD','LD_LIBRARY_PATH')):
        raise ValueError('First qualification requires unmodified native library environment')
    from profiles import RuntimeSelection,SessionPolicy
    selection=RuntimeSelection(**request['selection']);policy=SessionPolicy(**request['policy'])
    from release_authorization import _verify_assets
    _verify_assets(binding,selection,dict(assets=row['assets']))
    if row['stage']=='followup_policy':
        feasibility,unused=read_json(row['feasibility_review_path'],row['feasibility_review_sha256'])
        if feasibility!=row.get('reviewed_feasibility'):raise ValueError('Reviewed feasibility bytes differ')
        validate_feasibility(feasibility,selection,pins)
        for key in ('execution','measurement','closure'):
            read_json(feasibility[key]['path'],feasibility[key]['sha256'],1048576)
    gate,_=read_json(row['prerequisite_gate_path'],row['prerequisite_gate_sha256'])
    primary=dict(selection.validate(),optional_d1_refiner=False)
    # Permission-only opt-in is allowed to differ if the reviewer says so;
    # every model/source/identity/presentation field must still match.
    actual_primary=gate.get('primary_selection',{})
    if actual_primary.get('allow_experimental')!=primary['allow_experimental']:
        if gate.get('permission_only_difference_reviewed') is not True:raise ValueError('Explicit prerequisite permission-bit review required')
        primary['allow_experimental']=actual_primary.get('allow_experimental')
    if (gate.get('schema')!='just-peachy.optional-first-prerequisites.v2' or gate.get('reviewed') is not True or
        gate.get('candidate_content_sha256')!=binding['candidate_content_sha256'] or actual_primary!=primary or
        gate.get('source')!=row['source'] or gate.get('primary_functional_pass') is not True or
        gate.get('gui_functional_pass') is not True or gate.get('all_owners_closed') is not True or
        gate.get('allow_first_combined_measurement') is not True):
        raise ValueError('Reviewed same-candidate primary and GUI gates required')
    for key in ('primary_review','gui_review'):read_json(gate[key]['path'],gate[key]['sha256'])
    source=row['source']
    if selection.input_source=='saved':
        if source.get('kind')!='saved':raise ValueError('Saved qualification source contract required')
        from developer_replay import pin_repeat_input
        path=Path(request['saved_path'])
        if str(path)!=source['path'] or pin_repeat_input(path,policy)!=source['sha256']:
            raise ValueError('Exact bounded matched source SHA required')
        import wave
        with wave.open(str(path),'rb') as audio:
            if (audio.getnchannels(),audio.getsampwidth(),audio.getframerate(),audio.getcomptype())!=(1,2,16000,'NONE') or audio.getnframes()!=source['samples']:
                raise ValueError('Exact mono PCM16 16kHz input required')
        if not 0<source['samples']<=policy.maximum_samples():raise ValueError('Source exceeds qualification policy')
    else:
        if (source!={'kind':'live','config_sha256':hashlib.sha256(encoded(binding['live_config'])).hexdigest()} or
                request.get('saved_path') is not None):
            raise ValueError('Exact installed live source settings required for follow-up')
    data=job/'recordings'
    if data.exists():
        if data.is_symlink() or not data.is_dir() or any(data.iterdir()):raise ValueError('Fresh empty qualification recordings directory required')
    else:data.mkdir()
    STATE.update(row=row,raw=raw,sha=ref['sha256'],unit=unit,owner=identity,binding=binding,pins=pins,output=output)
    admitted=validate_claimed(raw,ref['sha256'],selection,policy,pins,'pre_primary')
    receipt=dict(schema='just-peachy.optional-first-execution.v2',purpose=admitted['purpose'],
        candidate_content_sha256=binding['candidate_content_sha256'],package_manifest_sha256=row['package_manifest_sha256'],
        operational_binding_sha256=pins['operational_binding_sha256'],actual_binding_sha256=request['binding_sha256'],
        permit_sha256=ref['sha256'],launch_context_sha256=row['launch_context_sha256'],selection=selection.validate(),policy=policy.validate(),
        production_eligible=False,prior_combined_pass_claimed=row['prior_combined_pass_claimed'],
        prior_production_pass_claimed=False,stage=row['stage'],owner=identity)
    with (output/'OPTIONAL_QUALIFICATION_EXECUTION.json').open('xb') as stream:
        stream.write(encoded(receipt));stream.flush();os.fsync(stream.fileno())
    return dict(binding_path=request['binding'],binding_sha256=request['binding_sha256'],
        admission_raw=raw,admission_sha256=ref['sha256'],expected_pins=pins,unit=request['unit'],reserved_output_bytes=4*MIB)


def validate_claimed(raw,sha,selection,policy,pins,phase):
    if raw!=STATE.get('raw') or sha!=STATE.get('sha') or pins!=STATE.get('pins') or _owner(os.getpid())!=STATE.get('owner'):
        raise ValueError('Qualification permit was not initialized and claimed by this exact worker')
    sample=context()
    row=validate_permit(raw,sha,selection,policy,pins,sample,phase)
    record=encoded(dict(phase=phase,measurement=sample))+b'\n'
    if len(record)>16384:raise ValueError('Admission measurement record capacity')
    with (STATE['output']/'OPTIONAL_ADMISSION_PHASES.jsonl').open('ab') as stream:stream.write(record)
    return row
