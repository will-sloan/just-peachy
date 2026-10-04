"""Closed mirrored optional-child decoder. README_HOST_OPERATIONS_V6.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import ast
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
import re
import os
import shutil
from pathlib import Path
import sys
import types

P = Path(__file__).resolve().parent.parent
B = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
Q = B/'live-runtime-20261003'


def closed_unit_owner(job, raw, entry, closure):
    """Bind one exact mirrored supervisor receipt; never treat it as a new PID."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate unit ownership field')
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs)
    keys = {'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id',
            'main_pid','owner','runtime_max_seconds','unit'}
    # One observed completed component-hour wrapper predates the GUI lifetime
    # fields. Its exact immutable mirrored bytes are the only six-field form.
    component_hour=(set(value)==keys-{'deadline_monotonic','idle_timeout_seconds'} and
        job.get('output_root')=='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/chunk52-threads2-hour-01' and
        job.get('unit')=='jp-v29-chunk52-threads2-hour-01.service' and
        job.get('package_manifest_sha256')=='6f8297ee7699f8c724d2246bf9a552ffcfa80bd0adcc9ace46002f48584cba89' and
        value.get('runtime_max_seconds')==4530 and
        hashlib.sha256(raw).hexdigest()=='3146b28d6ef3ccc9fe90fd331bded738d4c4d81c22cd882e32f605132eb59dc7')
    if set(value) not in (keys, keys | {'raw_admission_sha256'}) and not component_hour:
        raise ValueError('Exact supported unit ownership fields required')
    if (entry['path'] != 'UNIT_OWNERSHIP.json' or entry['identity']['bytes'] != len(raw)
        or hashlib.sha256(raw).hexdigest() != entry['sha256'] or len(raw)>16384):
        raise ValueError('Complete mirrored unit receipt pin differs')
    for name in ('unit','invocation_id','control_group','owner'):
        if value[name] != job[name] or closure[name] != job[name]:
            raise ValueError('Unit ownership is not bound to the actual job')
    if not all(closure.get(k) is True for k in ('closed','exact_owner_gone','cgroup_empty')):
        raise ValueError('Independent exact job closure required')
    owner=value['owner']
    if (set(owner)!={'pid','start_ticks','boot_id'}
        or any(type(owner[k]) is not int or owner[k]<=0 for k in ('pid','start_ticks'))
        or owner['boot_id']!=job['boot_id'] or type(value['main_pid']) is not int
        or value['main_pid']!=owner['pid']):
        raise ValueError('Actual strict process identity required')
    for key in (('runtime_max_seconds',) if component_hour else
                ('deadline_monotonic','runtime_max_seconds','idle_timeout_seconds')):
        if type(value[key]) not in (int,float) or not math.isfinite(value[key]) or value[key]<=0:
            raise ValueError('Finite unit lifetime field required')
    if 'raw_admission_sha256' in value:
        digest=value['raw_admission_sha256']
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Exact raw admission pin required')
    return dict(sha256=entry['sha256'],owner=owner)


def verify_optional_source_mirror(job,entry,complete,rows,closure):
    """Permit only the actual optional live-followup layout under a complete closed mirror."""
    def require(condition,message):
        if not condition:raise ValueError(message)
    def positive(value):return type(value) is int and value>0
    def digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
    root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/'
    name=job.get('output_root','').removeprefix(root)
    require(job.get('schema')=='just-peachy.native-component-job.v1' and
        job.get('output_root')==root+name and re.fullmatch(r'optional-followup-[0-9]{2}',name) and
        job.get('unit')=='jp-v29-'+name+'.service' and
        job.get('control_group')=='/user.slice/user-1000.slice/user@1000.service/app.slice/'+job['unit'] and
        isinstance(job.get('invocation_id'),str) and re.fullmatch('[0-9a-f]{32}',job['invocation_id']) and
        digest(job.get('package_manifest_sha256')),'Exact optional followup unit/package required')
    require(job.get('workflow')=='optional-followup-live-policy' and
        type(job.get('duration_seconds')) is int and job['duration_seconds']==300 and
        type(job.get('runtime_seconds')) is int and job['runtime_seconds']==840 and
        type(job.get('maximum_output_files')) is int and job['maximum_output_files']==256 and
        positive(job.get('maximum_output_bytes')) and job['maximum_output_bytes']<=512*1024**2 and
        type(job.get('independent_pc_copy_bytes')) is int and
        job['independent_pc_copy_bytes']==job['maximum_output_bytes'],
        'Exact finite optional live-followup workflow required')
    parent=job.get('owner');boot=job.get('boot_id')
    require(type(parent) is dict and set(parent)=={'pid','start_ticks','boot_id'} and
        positive(parent['pid']) and positive(parent['start_ticks']) and parent['boot_id']==boot and
        isinstance(boot,str) and re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot),
        'Strict actual optional parent identity required')
    require(type(rows) is list and 1<=len(rows)<=256,'Finite complete optional mirror membership required')
    names=set();total=0
    for row in rows:
        require(type(row) is dict and set(row)=={'path','identity','sha256'},'Exact mirror member fields required')
        member=row['path'];identity=row['identity']
        require(isinstance(member,str) and member and not member.startswith('/') and '\\' not in member and
            all(part not in ('','.','..') for part in member.split('/')) and member not in names,
            'Unique safe optional mirror path required')
        require(type(identity) is dict and set(identity)=={'bytes','ctime_ns','mtime_ns','device','inode'} and
            all(type(identity[key]) is int and identity[key]>=0 for key in identity) and digest(row['sha256']),
            'Exact optional mirror file identity/hash required')
        names.add(member);total+=identity['bytes']
    manifest_sha=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(type(complete) is dict and complete.get('kind')=='COMPLETE' and
        complete.get('mirror_scope')=='all_regular_output_files' and complete.get('files')==len(rows) and
        complete.get('bytes')==total and total<=job['maximum_output_bytes'] and
        complete.get('manifest_sha256')==manifest_sha and entry in rows and complete.get('closure')==closure,
        'Full optional source mirror count/extent/hash/closure required')
    require(type(closure) is dict and all(closure.get(key)==job[key] for key in
        ('unit','invocation_id','control_group','owner')) and
        all(closure.get(key) is True for key in ('closed','exact_owner_gone','cgroup_empty')) and
        closure.get('observed_owner') is None and closure.get('owner_recaptured') is True,
        'Actual closed optional followup owner/cgroup required')

def closed_source_owner(job, raw, entry, closure, *, complete=None, rows=None):
    """Exact source bootstrap envelope from a closed job's verified file tree."""
    def pairs(items):
        value={}
        for key,item in items:
            if key in value: raise ValueError('Duplicate source owner field')
            value[key]=item
        return value
    value=json.loads(raw,object_pairs_hook=pairs)
    optional_source=re.fullmatch(r'recordings/sessions/[0-9a-f]{32}/work/source/REGISTERED_OWNER\.json',entry['path'])
    if optional_source:
        verify_optional_source_mirror(job,entry,complete,rows,closure)
    elif not re.fullmatch(r'(qualification|data)/recordings/sessions/[0-9a-f]{32}/work/source/REGISTERED_OWNER\.json',entry['path']):
        raise ValueError('Exact known source owner path required')
    expected={'address_space_bytes':268435456,'cpu':3,'project_imports_started':False,
              'schema':'just-peachy.source-owner.v1','stack_bytes':1048576}
    if set(value)!=set(expected)|{'owner'} or any(type(value[k]) is not type(v) or value[k]!=v for k,v in expected.items()):
        raise ValueError('Exact source bootstrap envelope required')
    if len(raw)>16384 or entry['identity']['bytes']!=len(raw) or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
        raise ValueError('Mirrored source owner bytes differ')
    owner=value['owner']
    if (set(owner)!={'pid','start_ticks','boot_id'} or owner['boot_id']!=job['boot_id']
        or any(type(owner[k]) is not int or owner[k]<=0 for k in ('pid','start_ticks'))):
        raise ValueError('Strict actual source identity required')
    if optional_source and (owner['pid']==job['owner']['pid'] or owner['start_ticks']<job['owner']['start_ticks']):
        raise ValueError('Optional source must be a later distinct child identity')
    if any(closure[k]!=job[k] for k in ('unit','invocation_id','control_group','owner')) or not all(closure.get(k) is True for k in ('closed','exact_owner_gone','cgroup_empty')):
        raise ValueError('Independent actual job closure required')
    return dict(sha256=entry['sha256'],owner=owner)


def closed_optional_owner(job, raw, entry, complete, child_raw, child_entry, rows):
    """Return an exact reaped child identity, without asserting a quality pass."""
    def require(condition,message):
        if not condition:raise ValueError(message)
    def positive(value):return type(value) is int and value>0
    def digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
    root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/'
    name=job.get('output_root','').removeprefix(root)
    require(job.get('schema')=='just-peachy.native-component-job.v1' and
        job.get('output_root')==root+name and re.fullmatch(r'optional-(first|followup)-[0-9]{2}',name),
        'Known optional job root required')
    require(job.get('unit')=='jp-v29-'+name+'.service' and
        job.get('control_group')=='/user.slice/user-1000.slice/user@1000.service/app.slice/'+job['unit'] and
        isinstance(job.get('invocation_id'),str) and re.fullmatch('[0-9a-f]{32}',job['invocation_id']) and
        digest(job.get('package_manifest_sha256')),'Exact optional unit and package binding required')
    parent=job.get('owner');boot=job.get('boot_id')
    require(isinstance(boot,str) and re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot) and
        type(parent) is dict and set(parent)=={'pid','start_ticks','boot_id'} and
        positive(parent['pid']) and positive(parent['start_ticks']) and parent['boot_id']==boot,
        'Strict actual parent identity required')
    path=entry.get('path','')
    require(re.fullmatch(r'recordings/sessions/[0-9a-f]{32}/work/optional-refiner/child/REGISTERED_OWNER\.json',path),
        'Exact optional session child path required')
    close_path=path.removesuffix('child/REGISTERED_OWNER.json')+'CLOSURE.json'
    def checked(data,item,wanted,maximum):
        require(type(data) is bytes and 0<len(data)<=maximum and item.get('path')==wanted and
            item.get('identity',{}).get('bytes')==len(data) and digest(item.get('sha256')) and
            hashlib.sha256(data).hexdigest()==item['sha256'],'Mirrored optional receipt extent/path/hash differs')
        def pairs(items):
            value={}
            for key,field in items:
                require(key not in value,'Duplicate optional receipt key');value[key]=field
            return value
        return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite receipt')))
    value=checked(raw,entry,path,16384);child=checked(child_raw,child_entry,close_path,65536)
    require(type(rows) is list and positive(job.get('maximum_files',256)) and
        len(rows)<=min(job.get('maximum_files',256),256),'Finite optional mirror membership required')
    names=set();total=0
    for row in rows:
        require(type(row) is dict and set(row)=={'path','identity','sha256'},'Exact mirror member fields required')
        member=row['path'];identity=row['identity']
        require(isinstance(member,str) and member and not member.startswith('/') and '\\' not in member and
            all(part not in ('','.','..') for part in member.split('/')) and member not in names,
            'Unique safe mirror membership required')
        require(type(identity) is dict and set(identity)=={'bytes','ctime_ns','mtime_ns','device','inode'} and
            type(identity['bytes']) is int and identity['bytes']>=0 and
            all(type(identity[k]) is int and identity[k]>=0 for k in ('ctime_ns','mtime_ns','device','inode')) and
            digest(row['sha256']),'Exact mirror member identity and hash required')
        names.add(member);total+=identity['bytes']
    manifest_sha=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(entry in rows and child_entry in rows and complete.get('kind')=='COMPLETE' and
        complete.get('mirror_scope')=='all_regular_output_files' and complete.get('files')==len(rows) and
        complete.get('bytes')==total and complete.get('manifest_sha256')==manifest_sha and
        positive(job.get('maximum_output_bytes')) and total<=job['maximum_output_bytes']<=512*1024**2,
        'Full bounded closed optional mirror required')
    require(type(value) is dict and set(value)=={'affinity','parent_pid','pid','start_ticks','boot_id'} and
        value['affinity']==[2,3] and all(type(cpu) is int for cpu in value['affinity']) and
        positive(value['pid']) and value['pid']!=parent['pid'] and positive(value['start_ticks']) and
        value['start_ticks']>=parent['start_ticks'] and type(value['parent_pid']) is int and
        value['parent_pid']==parent['pid'] and value['boot_id']==boot,'Exact registered optional child identity required')
    keys={'schema','failure','child_owner','child_result','process_returncode','child_dead','sent_samples',
        'processed_samples','returned_frames','complete_eof','diagnostic_drops','primary_audio_dropped','quality_qualified'}
    require(type(child) is dict and set(child)==keys and child['schema']=='just-peachy.optional-refiner-closure.v1' and
        child['child_owner']==value and child['child_dead'] is True and type(child['process_returncode']) is int and
        -64<=child['process_returncode']<=255 and type(child['complete_eof']) is bool and
        child['primary_audio_dropped'] is False and child['quality_qualified'] is False and
        all(type(child[k]) is int and child[k]>=0 for k in ('sent_samples','processed_samples','returned_frames','diagnostic_drops')),
        'Exact observed optional child reap receipt required')
    require(child['failure'] is None or (isinstance(child['failure'],str) and 0<len(child['failure'])<=2048),
        'Bounded original child failure required')
    if child['complete_eof']:
        result=child['child_result']
        require(child['failure'] is None and child['process_returncode']==0 and type(result) is dict and
            result.get('owner')==value and result.get('complete_eof') is True and result.get('model_closed') is True and
            result.get('failure') is None,'Complete EOF must retain actual successful child evidence')
    else:
        require(child['failure'] is not None,'Incomplete optional execution must retain its failure')
    closure=complete.get('closure',{});exit_row=closure.get('job_exit',{})
    require(all(closure.get(k)==job[k] for k in ('unit','invocation_id','control_group','owner')) and
        all(closure.get(k) is True for k in ('closed','exact_owner_gone','cgroup_empty')) and
        closure.get('observed_owner') is None and closure.get('owner_recaptured') is True and
        all(exit_row.get(k)==job[k] for k in ('unit','invocation_id','owner')) and
        exit_row.get('leases_released') is True and type(exit_row.get('natural_returncode')) is int,
        'Independent actual whole-unit closure and reap required')
    return value

def bind_native_owner_references(native,new_owners,unit_owners):
    """Exact historical decoder insertion, including already verified unit pins."""
    boundary='owner_hash=hashlib.sha256();count=0;typed=0;all_ids=set()'
    if native.count(boundary)!=1:raise ValueError('Strict native owner binding boundary')
    native=native.replace(boundary,'HISTORICAL.update('+repr(new_owners)+')\nNEW_UNIT_OWNERS='+repr(unit_owners)+'\n'+boundary)
    boundary=" elif 'owner' in v:\n  assert rel in NESTED"
    if native.count(boundary)!=1:raise ValueError('Exact nested-owner decoder boundary')
    return native.replace(boundary,
        " elif rel in NEW_UNIT_OWNERS:\n  expected=NEW_UNIT_OWNERS[rel]\n  assert sha(raw)==expected['sha256'] and v['owner']==expected['owner']\n  v=v['owner']\n"+boundary)


def output_copy_reservation(action_name,data):
    """An hour application gets its own explicit independently copied scope."""
    reservation=data.get('maximum_output_bytes',0)
    maximum=512*1024**2
    if action_name=='launch_gui_check_action.py' and data.get('workflow')=='capture-save-replay-discard' and data.get('runtime_seconds')==1500:
        maximum=1024**3
    if action_name=='launch_full_app_soak_action.py':
        if (data.get('schema')!='just-peachy.full-app-hour-admission.v1' or data.get('reviewed') is not True
                or data.get('workflow')!='continuous-full-application-repeated-wav'
                or data.get('repeat_input_seconds')!=3600 or data.get('runtime_seconds')!=4680
                or data.get('independent_pc_copy_bytes')!=reservation or type(reservation) is not int or reservation<=0):
            raise ValueError('Explicit separate full-application hour reservation required')
        maximum=3*1024**3
    if type(reservation) is not int or not 0<=reservation<=maximum:
        raise ValueError('Explicit finite independent native-output copy allocation')
    return reservation


def backup_copy_action_allowed(action_name,data):
    if action_name=='launch_backup_action.py':return True
    pins={
        'launch_backup_external_action.py':('just-peachy.external-backup-common.v1',20362,
            '103c24c099b946289172cf432288ef1db5abf1c744afb2f27b3f7b361d6d7aa8'),
        'launch_backup_external_action_v2.py':('just-peachy.external-backup-common.v2',20433,
            'aba044705f9e4938261cd82d46264b5c4868206abcac290a31580f971a1d50ef')}
    if action_name not in pins:return False
    schema,size,pin=pins[action_name]
    document=data.get('external_backup_common',{})
    if (type(document) is not dict or set(document)!={'schema','bytes','sha256','base64'}
            or document.get('schema')!=schema or document.get('bytes')!=size or document.get('sha256')!=pin
            or data.get('maximum_output_bytes')!=16*1024**2):return False
    try:raw=base64.b64decode(document['base64'],validate=True)
    except (ValueError,TypeError):return False
    return len(raw)==document['bytes'] and hashlib.sha256(raw).hexdigest()==document['sha256']


def bounded_lifetime_decoder(raw):
    """Preserve the exact old inventory digest, stream only bounded events-only evidence."""
    text=raw.decode('utf-8')
    old="""        if not stat.S_ISREG(before.st_mode) or getattr(before,'st_file_attributes',0)&0x400 or before.st_size>32*1024**2:
            raise ValueError('Bounded real evidence file')
        raw=path.read_bytes();after=path.lstat()
        if len(raw)!=before.st_size or (before.st_ino,before.st_mtime_ns,before.st_size)!=(after.st_ino,after.st_mtime_ns,after.st_size):
            raise RuntimeError('Evidence changed during preread')
        read_bytes+=len(raw);h.update(str(path).encode()+b'\\0'+hashlib.sha256(raw).digest())
"""
    new="""        if not stat.S_ISREG(before.st_mode) or getattr(before,'st_file_attributes',0)&0x400:
            raise ValueError('Bounded real evidence file: '+str(path))
        if before.st_size>32*1024**2:
            if kinds!=('lifetime',) or path.name!='events.jsonl' or before.st_size>64*1024**2:
                raise ValueError('Bounded evidence parse/stream extent: '+str(path))
            entry_hash=hashlib.sha256();entry_bytes=0
            with path.open('rb') as stream:
                opened=os.fstat(stream.fileno())
                if (opened.st_ino,opened.st_mtime_ns,opened.st_size)!=(before.st_ino,before.st_mtime_ns,before.st_size):
                    raise RuntimeError('Evidence changed before stream')
                while True:
                    guard()
                    if time.monotonic()>=deadline:raise TimeoutError('Full host preread deadline')
                    block=stream.read(32768)
                    if not block:break
                    entry_bytes+=len(block)
                    if entry_bytes>before.st_size:raise RuntimeError('Evidence grew during preread')
                    entry_hash.update(block)
                ended=os.fstat(stream.fileno())
            after=path.lstat()
            identity=(before.st_ino,before.st_mtime_ns,before.st_size)
            if (entry_bytes!=before.st_size or identity!=(ended.st_ino,ended.st_mtime_ns,ended.st_size)
                or identity!=(after.st_ino,after.st_mtime_ns,after.st_size)
                or not stat.S_ISREG(after.st_mode) or getattr(after,'st_file_attributes',0)&0x400):
                raise RuntimeError('Evidence changed during streamed preread')
            entry_digest=entry_hash.digest();raw=None
        else:
            raw=path.read_bytes();after=path.lstat();entry_bytes=len(raw)
            if len(raw)!=before.st_size or (before.st_ino,before.st_mtime_ns,before.st_size)!=(after.st_ino,after.st_mtime_ns,after.st_size):
                raise RuntimeError('Evidence changed during preread')
            entry_digest=hashlib.sha256(raw).digest()
        read_bytes+=entry_bytes;h.update(str(path).encode()+b'\\0'+entry_digest)
"""
    # The embedded Python source uses a literal backslash-zero, not NUL bytes.
    old=old.replace("b'\\\\0'","b'\\0'")
    new=new.replace("b'\\\\0'","b'\\0'")
    if text.count(old)!=1:raise ValueError('Exact historical evidence reader boundary')
    return text.replace(old,new).encode('utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--label', required=True)
    ap.add_argument('--action', type=Path, required=True)
    ap.add_argument('--payload', type=Path, required=True)
    ap.add_argument('--writes', action='store_true')
    a = ap.parse_args()
    if not a.label.replace('-', '').isalnum():
        raise ValueError('Fresh simple operation label')
    out = Q/('operation-'+a.label)
    out.mkdir()
    def put(name, raw):
        with (out/name).open('xb') as f:
            if f.write(raw) != len(raw): raise OSError('Short host receipt write')
            f.flush(); os.fsync(f.fileno())
        if (out/name).read_bytes() != raw: raise OSError('Host receipt readback')
    def save(name, value):
        put(name, json.dumps(value, sort_keys=True, allow_nan=False).encode())
    me = psutil.Process()
    save('REGISTERED_OWNER.json', dict(pid=me.pid, create_time=me.create_time(), affinity=[14]))
    if a.action.is_symlink() or a.payload.is_symlink() or a.action.stat().st_size > 131072 or a.payload.stat().st_size > 2*1024**2:
        raise ValueError('Finite local action and payload')
    action, payload = a.action.read_bytes(), a.payload.read_bytes()
    compile(action, '<reviewed-candidate-action>', 'exec')
    data = json.loads(payload)
    reservation = output_copy_reservation(a.action.name,data)
    backup_reservation=data.get('full_backup_reservation_bytes',0)
    if type(backup_reservation) is not int or not 0<=backup_reservation<2**63:
        raise ValueError('Explicit full-backup PC reservation required')
    if backup_reservation and (not backup_copy_action_allowed(a.action.name,data) or
        data.get('backup_scope',{}).get('maximum_payload_bytes')!=backup_reservation):
        raise ValueError('Independent release/data copy is allowed only for the exact snapshot action')
    reservations = []
    for drive, gib in (('C:/', 50), ('G:/', 75)):
        free = shutil.disk_usage(drive).free
        required = gib*1024**3 + reservation + backup_reservation
        if free < required:
            raise OSError('Host reserve plus complete independent output copy unavailable: '+drive)
        reservations.append(dict(drive=drive, free_bytes=free, safety_floor_bytes=gib*1024**3,
                                 independent_copy_bytes=reservation, full_backup_copy_bytes=backup_reservation,
                                 required_free_bytes=required))
    save('OUTPUT_COPY_RESERVATION.json', dict(maximum_output_bytes=reservation, drives=reservations,
        full_backup_reservation_bytes=backup_reservation,
        separate_from_preparation_scope=True, ssh_started=False))
    now = datetime.now(timezone.utc)
    save('SCOPE.json', dict(issued_utc=now.isoformat(), expires_utc=(now+timedelta(seconds=600)).isoformat(),
        maximum_bytes=16*1024**2, purpose='new runtime integration; no historical campaign renewal'))
    for name, raw in (('ACTION.py', action), ('PAYLOAD.json', payload), ('RUNNER.py', Path(__file__).read_bytes())):
        put(name+'.backup', raw); put(name+'.restore', raw)
    save('SOURCE_CLOSED.json', dict(action_sha256=hashlib.sha256(action).hexdigest(),
        payload_sha256=hashlib.sha256(payload).hexdigest(), independent_restore=True, utc=datetime.now(timezone.utc).isoformat()))
    decoder = Q/'inspection-preparation-expansion-baseline-v3/source.py.backup'
    raw = decoder.read_bytes()
    if hashlib.sha256(raw).hexdigest() != 'df6b67fbc395e72f889c2dd3038deac7cff67930a0aa1b35996e0b981b76f80b':
        raise ValueError('Reviewed exact historical host timestamp decoder')
    module = types.ModuleType('field_runtime_host_precheck_v2')
    # Six exact completed preparations omitted format fields; their actual
    # PID/FILETIME bytes are preserved. Never normalize any other owner path.
    corrections = {'live-runtime-20261003/audit-preparation/acceptance-links-final-171a1d6e778744a8a8df735b0068c160/REGISTERED_OWNER.json': {'sha256': 'e7a7884714d1d28e2b8bbe9f902fce9c34d938dc6fc07b06369269870c03fb82', 'original': {'pid': 4224, 'cpu': 14, 'creation_filetime': 134355540921332158, 'create_time': 1791080492.133216}}, 'live-runtime-20261003/audit-preparation/hour-review-null-exit-fix-6ae2bf0256aa4e83a206a545175a64bc/REGISTERED_OWNER.json': {'sha256': 'dcc2792a7b8e397ce03838669646742d5253d5f23412b5c951c7d1d1b1a3e890', 'original': {'pid': 49896, 'cpu': 14, 'creation_filetime': 134355556823003457, 'create_time': 1791082082.3003457}}, 'live-runtime-20261003/audit-preparation/interpreter-builder-fix-8666dedf3f9a48e9887eed52edf41fff/REGISTERED_OWNER.json': {'sha256': '1509cc597d72f6679cc2335624acc00b79515e52171ba49adcfa783197de1d4f', 'original': {'pid': 7280, 'cpu': 14, 'creation_filetime': 134355538996019511, 'create_time': 1791080299.6019511}}, 'live-runtime-20261003/audit-preparation/interpreter-fix-preparation-760d80961fbe4d9d94813bc838ef844f/REGISTERED_OWNER.json': {'sha256': 'dce76d71e1987e5601ecc435fcfe58996191287b9c12e79ad3f3dcfcafb4bb51', 'original': {'pid': 18408, 'cpu': 14, 'affinity_mask': 16384, 'creation_filetime': 134355538290021033, 'create_time': 1791080229.002103}}, 'live-runtime-20261003/audit-preparation/interpreter-source-review-b53f2a64bbf24ab5919aba45158da001/REGISTERED_OWNER.json': {'sha256': '9ea9758973f6a1999c902633989f3bad97392db0191bfe18d0a3e1c714433f31', 'original': {'pid': 40904, 'cpu': 14, 'creation_filetime': 134355543564911141, 'create_time': 1791080756.491114}}, 'live-runtime-20261003/audit-preparation/production13-plan-fda43f06a54c42df9d75b9f8c556a446/REGISTERED_OWNER.json': {'sha256': 'ac3221ceb0c8543d46e71d9517edcfa7bf4b0e3812fa416a41130933a86523dc', 'original': {'cpu': 14, 'create_time': 1791080645.836157, 'creation_filetime': 134355542458361573, 'pid': 76012}}}
    owner_anchor = "            if relative == 'live-runtime-20261003/presets-preparation-f8695921eb904d2cbdfa0ebb20b7b982/REGISTERED_OWNER.json':"
    if raw.decode().count(owner_anchor)!=1:raise ValueError('Exact host decoder correction boundary')
    owner_prefix = "            if relative in HOST_OWNER_FORMAT_CORRECTIONS:\n                correction=HOST_OWNER_FORMAT_CORRECTIONS[relative]\n                if value!=correction['original'] or hashlib.sha256(path.read_bytes()).hexdigest()!=correction['sha256']:\n                    raise ValueError('Exact original host registration changed')\n                value=dict(value,schema='just-peachy.host-registered-owner.v1',affinity_mask=16384)\n"
    raw=("HOST_OWNER_FORMAT_CORRECTIONS="+repr(corrections)+"\n"+raw.decode().replace(owner_anchor,owner_prefix+owner_anchor)).encode()
    raw=bounded_lifetime_decoder(raw)
    exec(compile(raw, '<reviewed-host-owner-decoder>', 'exec'), module.__dict__)
    sys.modules[module.__name__] = module
    source = (B/'desktop-exit-20261003/preparation-expansion-baseline-v3/SOURCE.py.backup').read_bytes()
    if hashlib.sha256(source).hexdigest() != '0aab2f169e6a00f9dd22ae0d09e0fdceaa684e1b1ccc5f55ac3c2a3f0cf16ceb':
        raise ValueError('Preserved current inspector source pin')
    s = source.decode()
    tree = ast.parse(s)
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'NATIVE' for t in n.targets))
    native = ast.literal_eval(node.value)
    # Bind only actual previously launched benchmark identities. The immutable
    # benchmark's extra affinity field is not a generic owner-schema exemption.
    new_owners = {}; unit_owners = {}
    for job_path in sorted(Q.glob('*-JOB.json')):
        job = json.loads(job_path.read_bytes())
        if job.get('schema') != 'just-peachy.native-component-job.v1':
            raise ValueError('Unexpected native job schema')
        owner = job['owner']
        if (type(owner) is not dict or set(owner) != {'pid','start_ticks','boot_id'}
            or type(owner['pid']) is not int or owner['pid'] <= 0
            or type(owner['start_ticks']) is not int or owner['start_ticks'] <= 0
            or owner['boot_id'] != job['boot_id']):
            raise ValueError('Actual launch owner required for historical binding')
        root_prefix = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/'
        if not job['output_root'].startswith(root_prefix+'live-runtime-tests-20261003/'):
            raise ValueError('Unexpected job evidence path')
        relative = job['output_root'][len(root_prefix):]
        if len(relative.split('/')) != 2 or '..' in relative or '\\' in relative:
            raise ValueError('Unsafe benchmark evidence path')
        new_owners[relative+'/benchmark/REGISTERED_OWNER.json'] = dict(owner, affinity=[2,3])
        # Backup guards retain the normal complete mirror inside one exact named
        # reconciliation. Other nested results are not ownership exceptions.
        mirrors=list(Q.glob('*-monitor-*/RESULT.json'))
        mirrors.extend(path for path in Q.glob('production-backup-*-reconcile-*/guard-monitor/RESULT.json')
            if re.fullmatch(r'production-backup-\d{2}-reconcile-\d{2}',path.parents[1].name))
        for result_path in sorted(mirrors):
            result=json.loads(result_path.read_bytes())
            if result.get('status')!='FULL_CLOSED_OUTPUT_MIRRORED': continue
            if result.get('job',{}).get('output_root')!=job['output_root']: continue
            mirror=result_path.parent
            rows=json.loads((mirror/'MIRROR_MANIFEST.json').read_bytes())
            complete=json.loads((mirror/'MIRROR_COMPLETE.json').read_bytes())
            for entry in rows:
                if entry['path'].endswith('/work/optional-refiner/child/REGISTERED_OWNER.json'):
                    child_path=entry['path'].removesuffix('child/REGISTERED_OWNER.json')+'CLOSURE.json'
                    child_entries=[row for row in rows if row['path']==child_path]
                    if len(child_entries)!=1:raise ValueError('Unique mirrored optional child closure required')
                    value=closed_optional_owner(job,(mirror/'closed-output'/entry['path']).read_bytes(),entry,
                        complete,(mirror/'closed-output'/child_path).read_bytes(),child_entries[0],rows)
                    key=relative+'/'+entry['path']
                    if key in new_owners and new_owners[key]!=value:raise ValueError('Conflicting optional ownership copies')
                    new_owners[key]=value
                if entry['path'].endswith('/work/source/REGISTERED_OWNER.json'):
                    source_path=mirror/'closed-output'/entry['path']
                    pin=closed_source_owner(job,source_path.read_bytes(),entry,complete['closure'],complete=complete,rows=rows)
                    key=relative+'/'+entry['path']
                    if key in unit_owners and unit_owners[key]!=pin: raise ValueError('Conflicting source ownership copies')
                    unit_owners[key]=pin
            unit_path=mirror/'closed-output/UNIT_OWNERSHIP.json'
            if not unit_path.exists(): continue
            entries=[r for r in rows if r['path']=='UNIT_OWNERSHIP.json']
            if len(entries)!=1: raise ValueError('Unique complete mirrored unit owner required')
            pin=closed_unit_owner(job,unit_path.read_bytes(),entries[0],complete['closure'])
            key=relative+'/UNIT_OWNERSHIP.json'
            if key in unit_owners and unit_owners[key]!=pin: raise ValueError('Conflicting unit ownership copies')
            unit_owners[key]=pin
    native=bind_native_owner_references(native,new_owners,unit_owners)
    if a.writes:
        native = native.replace('(resource.RLIMIT_FSIZE,0)', '(resource.RLIMIT_FSIZE,33554432)')
    before = "raw=json.dumps(value)"
    if native.count(before) != 1: raise ValueError('Native dispatch insertion boundary')
    added = """
assert not value['current_project_processes'], 'Preserve other running applications'
assert not value['active_recorded_owners'] and not value['live_manager_owners']
assert value['candidate_unit']['ActiveState']=='inactive'
assert mem['MemAvailable']>=850*1024**2
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(OPERATION_EXPIRES)
action_namespace=dict(__name__='candidate_native_action',PAYLOAD=ACTION_PAYLOAD,BASELINE=value)
exec(compile(ACTION_SOURCE,'<pinned-native-action>','exec'),action_namespace)
value['action_result']=action_namespace['RESULT']
value['native_writes']=OPERATION_WRITES
"""
    native = native.replace(before, added+'\n'+before)
    lines = s.splitlines(True)
    s = ''.join(lines[:node.lineno-1])+'NATIVE='+repr(native)+'\n'+''.join(lines[node.end_lineno:])
    # Include every new independent native utility identity before dispatch.
    anchor = "    guard()\n    if datetime.now(timezone.utc)+timedelta(seconds=90)"
    if s.count(anchor) != 1: raise ValueError('Host native-owner continuation boundary')
    s = s.replace(anchor, "    for path in (a.private/'live-runtime-20261003').rglob('NATIVE_OWNER.json'):\n        v=identity(json.loads(path.read_bytes()));identities[(v['boot_id'],v['pid'],v['start_ticks'])]=v\n"+anchor)
    anchor = "    compile(code,'<runtime-install-inspection>','exec')"
    if s.count(anchor) != 1: raise ValueError('Command-bound native source boundary')
    prefix = 'ACTION_SOURCE='+repr(action.decode())+'\nACTION_PAYLOAD='+repr(data)+'\nOPERATION_WRITES='+repr(a.writes)+'\nOPERATION_EXPIRES='+repr((now+timedelta(seconds=600)).isoformat())+'\n'
    s = s.replace(anchor, '    code='+repr(prefix)+'+code\n'+anchor+"\n    put('NATIVE_SOURCE.py',code.encode())")
    s = s.replace('native_writes=False,capture=False,precheck_sha256=', 'native_writes='+repr(a.writes)+',capture=False,precheck_sha256=')
    s = s.replace("value=json.loads(out)", "value=json.loads(out)")
    put('DISPATCH_SOURCE.py.backup', s.encode()); put('DISPATCH_SOURCE.py.restore', s.encode())
    compile(s, '<fresh-candidate-dispatch>', 'exec')
    sys.path.insert(0, str(P))
    sys.argv = ['candidate_dispatch', '--private', str(B), '--local', str(B.parents[2]),
        '--prior-closure', str(B/'NATIVE_CLOSURE_V315.json'),
        '--previous-inspection', str(B/'desktop-exit-20261003/inspection-expansion-baseline-v3'),
        '--scope', str(out/'SCOPE.json'), '--output', str(out/'dispatch'),
        '--candidate-install', str(B/'field-runtime-v28-install')]
    exec(compile(s, '<fresh-candidate-dispatch>', 'exec'), dict(__name__='__main__', __file__=str(P/'inspect_runtime_session_v10.py')))


if __name__ == '__main__':
    main()
