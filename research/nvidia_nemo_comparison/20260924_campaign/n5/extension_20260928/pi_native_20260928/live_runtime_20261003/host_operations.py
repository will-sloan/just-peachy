"""Fresh bounded host dispatch using current full ownership inspection. README_HOST_OPERATIONS.md."""
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


def closed_source_owner(job, raw, entry, closure):
    """Exact source bootstrap envelope from a closed job's verified file tree."""
    def pairs(items):
        value={}
        for key,item in items:
            if key in value: raise ValueError('Duplicate source owner field')
            value[key]=item
        return value
    value=json.loads(raw,object_pairs_hook=pairs)
    if not re.fullmatch(r'(qualification|data)/recordings/sessions/[0-9a-f]{32}/work/source/REGISTERED_OWNER\.json',entry['path']):
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
    if any(closure[k]!=job[k] for k in ('unit','invocation_id','control_group','owner')) or not all(closure.get(k) is True for k in ('closed','exact_owner_gone','cgroup_empty')):
        raise ValueError('Independent actual job closure required')
    return dict(sha256=entry['sha256'],owner=owner)


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
                if entry['path'].endswith('/work/source/REGISTERED_OWNER.json'):
                    source_path=mirror/'closed-output'/entry['path']
                    pin=closed_source_owner(job,source_path.read_bytes(),entry,complete['closure'])
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
