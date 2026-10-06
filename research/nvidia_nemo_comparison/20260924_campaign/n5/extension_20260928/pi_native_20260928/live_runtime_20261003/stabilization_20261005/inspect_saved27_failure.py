"""Read only the exact closed Saved27 launch. README_INSPECT_SAVED27_FAILURE.md."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

MIB=1024**2
DATA=Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
PACKAGE=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-25')
PIN='6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
BOOT='0561d730-3cad-48e0-940a-fe3930c89665'
LAUNCH='8d61371110d0470c93f4ff58cc73027d'
REQUEST='476ce3fdb28db38f97a9395d55d934c2a9a30800d4e3a046777eaba1567cbc28'
JOB_PIN='72957f93d74bd0ec510485c8fa7fdc293bb0ed3bb6fc11c9c7714482f1e0a648'
SOURCE='c24b685b2bd34d6bb04172965d712c0f'
SOURCE_PIN='7da45b76193d3ddd1e2aa29bbc6792b019643c8a945edd3959d9458db4fc6c69'
JOB_ROOT=PACKAGE.parent/'live-runtime-tests-20261003/classic-ui-check-27'


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate diagnostic field')
            result[key]=value
        return result
    def number(value):
        result=float(value)
        if not math.isfinite(result):raise ValueError('Nonfinite diagnostic number')
        return result
    return json.loads(raw,object_pairs_hook=pairs,parse_float=number,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))


def identity(path,maximum):
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Canonical diagnostic source required')
    item=path.lstat()
    if not stat.S_ISREG(item.st_mode) or item.st_nlink!=1 or item.st_size>maximum:
        raise ValueError('Bounded independent diagnostic file required')
    return [item.st_dev,item.st_ino,item.st_size,item.st_mtime_ns,item.st_ctime_ns]


def read(path,maximum=262144):
    before=identity(path,maximum);raw=path.read_bytes()
    if len(raw)!=before[2] or identity(path,maximum)!=before:
        raise ValueError('Diagnostic source changed')
    return raw


def snapshot(folder):
    rows=[];pending=[folder];total=0;visited=0
    while pending:
        directory=pending.pop()
        if directory.is_symlink():raise ValueError('Diagnostic tree symlink')
        with os.scandir(directory) as entries:
            for entry in entries:
                visited+=1
                if visited>768 or entry.is_symlink():raise ValueError('Bounded diagnostic membership required')
                path=Path(entry.path)
                if entry.is_dir(follow_symlinks=False):pending.append(path);continue
                if len(rows)>=512:raise ValueError('Diagnostic file-count limit')
                before=identity(path,32*MIB);total+=before[2]
                if total>256*MIB:raise ValueError('Diagnostic whole-tree allocation limit')
                digest=hashlib.sha256()
                with path.open('rb') as stream:
                    while data:=stream.read(65536):digest.update(data)
                if identity(path,32*MIB)!=before:raise ValueError('Diagnostic tree changed while hashing')
                rows.append(dict(path=path.relative_to(folder).as_posix(),identity=before,sha256=digest.hexdigest()))
    rows.sort(key=lambda row:row['path'])
    return dict(files=len(rows),bytes=total,sha256=hashlib.sha256(encoded(rows)).hexdigest())


def filtered(value,depth=0):
    if depth>8 or type(value) is not dict:return None
    scalars={'processed_samples','raw_samples','sent_samples','source_frames','source_start_observed',
        'physical_start_packet_observed','source_thread_joined','child_returncode','physical_process_closed',
        'logical_cleanup_complete','post_stop_choice_pending','cleanup_attempted','closed','complete_recording',
        'current_motion_used','recorded_spatial_replay','replayed_anchors','replayed_beams','source_queries',
        'source_verified_after_drain','shared_source_lease_closed','source_lease_closed','thread_joined',
        'worker_joined','model_closed','source_closed','saved_source_finished','source_end_sample',
        'recorded_current_sensor_used','models_loaded','error_count','returncode','direct_child_reaped',
        'stdout_reader_joined','source_store_closed','lease_closed','processed_input_samples','input_samples',
        'owner','source_stop_join','source_done','closed_before_release','verified'}
    enums={'saved','live','file','kept_recording','STOPPED','CLOSED','RUNNING','FAILED','OPEN','kept',
        'stopped','failed','source_owner_receipt_missing','SOURCE_OWNER_RECEIPT_MISSING','SOURCE_START_UNVERIFIABLE'}
    result={}
    for key,item in value.items():
        if key in scalars and (item is None or type(item) in (bool,int,float)):
            if type(item) is float and not math.isfinite(item):raise ValueError('Nonfinite diagnostic fact')
            result[key]=item
        elif key in ('mode','input_source','source_kind','state','status') and type(item) is str and item in enums:
            result[key]=item
        elif key=='completed' and type(item) is list and len(item)<=32 and all(
                type(name) is str and re.fullmatch('[a-z_]{1,64}',name) for name in item):
            result[key]=item
        elif key in ('failure','cleanup_error','error','source_error','output_error'):
            result[key+'_present']=item is not None
            if item is not None:result[key+'_sha256']=hashlib.sha256(encoded(item)).hexdigest()
        elif type(item) is dict and key in ('result','source_facts','cleanup','saved_spatial','source',
                'source_final','source_closed','source_metrics','source_stopped','source_close',
                'nested_source','spatial','stop','integrity','timing','saved_source_metrics'):
            result[key]=filtered(item,depth+1)
    return result


def inspect(payload,baseline):
    if (type(payload) is not dict or set(payload)!={'package_manifest_sha256','boot_id','launch_id','expires_unix'}
        or payload['package_manifest_sha256']!=PIN or payload['boot_id']!=BOOT or payload['launch_id']!=LAUNCH
        or type(payload['expires_unix']) not in (int,float) or not math.isfinite(payload['expires_unix'])
        or not time.time()<payload['expires_unix']<=time.time()+600 or baseline.get('boot_id')!=BOOT):
        raise ValueError('Exact fresh closed Saved27 diagnostic required')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=BOOT:
        raise ValueError('Actual boot changed')
    for key in ('current_project_processes','active_recorded_owners','live_manager_owners'):
        if key not in baseline or baseline[key]:raise ValueError('Complete current-owner census must be clear')
    raw=read(PACKAGE/'PACKAGE_MANIFEST.json')
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Actual package pin changed')
    manifest=strict(raw);row=next(row for row in manifest['files'] if row['path']=='native_scope.py')
    scope_raw=read(PACKAGE/'native_scope.py',2*MIB)
    if len(scope_raw)!=row['bytes'] or hashlib.sha256(scope_raw).hexdigest()!=row['sha256']:
        raise ValueError('Pinned scope differs')
    sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('_saved27_read_scope',PACKAGE/'native_scope.py')
    scope=importlib.util.module_from_spec(spec);spec.loader.exec_module(scope)
    if scope.verified_inventory(PACKAGE,PIN)!=manifest:raise ValueError('Complete package changed')
    job=strict(read(JOB_ROOT/'JOB.json',65536))
    if (hashlib.sha256(encoded(job)).hexdigest()!=JOB_PIN or job.get('boot_id')!=BOOT or
        job.get('package_manifest_sha256')!=PIN or job.get('unit')!='jp-v29-classic-ui-check-27.service' or
        scope.alive(job['owner']) or not scope.cgroup_empty(job['control_group'])):
        raise ValueError('Saved27 exact main owner/cgroup must be closed')
    launch=DATA/'launches'/LAUNCH;before=snapshot(launch)
    request_raw=read(launch/'REQUEST.json',65536)
    if hashlib.sha256(request_raw).hexdigest()!=REQUEST:raise ValueError('Failed launch request changed')
    request=strict(request_raw)
    if request.get('saved_session_id')!=SOURCE or request.get('selection',{}).get('input_source')!='saved':
        raise ValueError('Actual Saved27 source request differs')
    records={};worker_owner=None;session_id=None
    for name in ('CURRENT_LAUNCH.json',):
        path=DATA/name
        if path.exists():
            raw=read(path,65536);value=strict(raw)
            records[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                launch_id=value.get('launch_id') if re.fullmatch('[0-9a-f]{32}',value.get('launch_id','')) else None)
    for name in ('CLOSED.json','START_FAILURE.json','HOST_CLOSURE.json','RECOVERED_CLOSURE.json',
            'NESTED_CLOSURE_PENDING.json','worker/SESSION.json','worker/RESULT.json','worker/EXIT.json',
            'worker/REGISTERED_OWNER.json','WORKER.log'):
        path=launch/name
        if not path.exists():records[name]=dict(present=False);continue
        raw=read(path,32*MIB if name.endswith('.log') else 262144)
        row=dict(present=True,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if name.endswith('.json'):
            value=strict(raw);row['keys']=sorted(value)[:128];row['facts']=filtered(value)
            if name=='worker/REGISTERED_OWNER.json':
                worker_owner=value
                if set(value)!={'pid','start_ticks','boot_id'} or value['boot_id']!=BOOT or any(type(value[k]) is not int or value[k]<=0 for k in ('pid','start_ticks')):
                    raise ValueError('Exact recorded worker identity required')
                row['owner']=value;row['exact_absent']=not scope.alive(value)
                if not row['exact_absent']:raise ValueError('Saved worker remains alive')
            if name=='worker/SESSION.json':
                session_id=value.get('session_id')
                if re.fullmatch('[0-9a-f]{32}',session_id or '') is None or session_id==SOURCE:
                    raise ValueError('Distinct actual replay-output session required')
                row['session_id']=session_id
            if name=='worker/RESULT.json' and type(value.get('result')) is dict:
                row['result_keys']=sorted(value['result'])[:128]
        else:
            row['exception_classes']=sorted(set(re.findall(rb'(?m)^([A-Za-z][A-Za-z0-9_]*(?:Error|Exception)):',raw)))
            row['exception_classes']=[value.decode('ascii') for value in row['exception_classes']]
        records[name]=row
    output_tree=None
    if session_id is not None:
        folder=DATA/'recordings/sessions'/session_id
        if folder.exists():
            first=snapshot(folder)
            for name in ('session.json','work/source/REGISTERED_OWNER.json','work/source/SOURCE_CLOSE.json'):
                path=folder/name;key='session/'+name
                if path.exists():
                    raw=read(path,262144);value=strict(raw)
                    records[key]=dict(present=True,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),facts=filtered(value))
                else:records[key]=dict(present=False)
            if snapshot(folder)!=first:raise ValueError('Replay-output tree changed during diagnostic')
            output_tree=first
    if snapshot(launch)!=before or read(launch/'REQUEST.json',65536)!=request_raw:
        raise ValueError('Closed replay launch changed during diagnostic')
    source_raw=read(DATA/'recordings/sessions'/SOURCE/'session.json',65536)
    if hashlib.sha256(source_raw).hexdigest()!=SOURCE_PIN:raise ValueError('Original kept source metadata changed')
    result=dict(status='CLOSED_SAVED27_FAILURE_READ_ONLY',launch_id=LAUNCH,session_id=session_id,
        package_manifest_sha256=PIN,boot_id=BOOT,request_sha256=REQUEST,source_session_id=SOURCE,
        source_metadata_sha256=SOURCE_PIN,selection=request.get('selection'),
        application_mode=request.get('application',{}).get('mode'),launch_tree=before,output_tree=output_tree,
        worker_owner=worker_owner,records=records,native_payload_writes=False,models_started=False,
        capture_started=False,private_caption_vector_text_returned=False,fence_cleared=False,
        own_physical_closure_claimed=False)
    if len(encoded(result))>65536:raise ValueError('Finite sanitized diagnostic response')
    return result


if 'PAYLOAD' in globals():RESULT=inspect(PAYLOAD,BASELINE)
