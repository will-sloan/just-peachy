"""Finite local release lifecycle contract; README_FIELD_LOCAL_CAPSULE_V1.md."""
from datetime import datetime, timezone
from pathlib import PurePosixPath
import hashlib
import json
import re
from field_operator_broker_layout_v2 import allocation as broker_allocation

KIB=1024
MIB=1024*KIB
CAMPAIGN=PurePosixPath('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
HARD_DEADLINE=datetime.fromisoformat('2026-10-01T17:42:44+00:00')
LAUNCH_RECORDS={'OWNER':16*KIB,'EXIT':32*KIB,'FAILURE':16*KIB}
RECORDING_RECORDS={'RESERVED':16*KIB,'STARTED':16*KIB,'CLOSED':32*KIB,
                   'FAILED':16*KIB,'PHYSICAL_CLOSURE':32*KIB,'BACKUP':256*KIB}
CONTROL_RECORDS={'RELEASE':64*KIB,'MANIFEST':128*KIB,'ACTIVATION':64*KIB,'ROLLBACK':64*KIB}

def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()

def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError('Bounded exact integer')
    return value

def allocation(recordings,launches):
    integer(recordings,1,4);integer(launches,1,16)
    one=broker_allocation(1)
    # Root/control/code/recordings/launches/backups plus each metadata slot.
    dirs=6+recordings+launches
    metadata=2*sum(CONTROL_RECORDS.values())+2*recordings*sum(RECORDING_RECORDS.values())
    metadata+=2*launches*sum(LAUNCH_RECORDS.values())+dirs*64*KIB+2*MIB
    # Each recording owns one full one-slot broker AND an independent local mirror.
    # Keep the original broker host mirror AND a full independent host copy
    # of the local backup. No small/unused/failed output credit is granted.
    target=metadata+2*recordings*one['target_maximum_bytes']
    host=metadata+recordings*(one['host_maximum_bytes']+one['target_maximum_bytes'])
    return dict(schema='just-peachy.local-release-allocation.v2',recordings=recordings,
        launches=launches,recording_slots=['recording-%02d'%i for i in range(1,recordings+1)],
        launch_slots=['launch-%02d'%i for i in range(1,launches+1)],
        broker_allocation=one,local_backup_per_recording=one['target_maximum_bytes'],
        host_local_backup_per_recording=one['target_maximum_bytes'],
        metadata_maximum_bytes=metadata,target_maximum_bytes=target,host_maximum_bytes=host,
        combined_request_bytes=target+host,metadata_directories=dirs,code_files=16,
        code_bytes=2*MIB,code_member_bytes=128*KIB,write_bytes=16*KIB,
        failed_deleted_unused_credit=False,automatic_replenishment=False)

def _root(value,pattern):
    if type(value) is not str:raise ValueError('Canonical native root string')
    p=PurePosixPath(value)
    if str(p)!=value or p.parent!=CAMPAIGN or not re.fullmatch(pattern,p.name):
        raise ValueError('Exact immediate campaign child root')
    return p

def validate_release(value):
    fields={'schema','root','recording_roots','allocation','release_manifest_sha256',
        'installed_manifest_sha256','mode_registry_sha256','activation_plan_sha256',
        'measured_target_before_bytes','measured_host_before_bytes','measured_payload_before_bytes',
        'combined_output_cap_bytes','total_payload_cap_bytes','limits'}
    if type(value) is not dict or set(value)!=fields or value['schema']!='just-peachy.local-release-policy.v2':
        raise ValueError('Exact local release policy')
    _root(value['root'],r'field-local-release-v[1-9][0-9]*')
    a=value['allocation']
    if encoded(a)!=encoded(allocation(a['recordings'],a['launches'])):raise ValueError('Full release allocation')
    roots=value['recording_roots']
    if type(roots) is not list or len(roots)!=a['recordings'] or len(set(roots))!=len(roots):
        raise ValueError('One distinct broker root per recording')
    for root in roots:_root(root,r'field-operator-sessions-v[1-9][0-9]*')
    for k in ('release_manifest_sha256','installed_manifest_sha256','mode_registry_sha256','activation_plan_sha256'):
        if type(value[k]) is not str or not re.fullmatch('[0-9a-f]{64}',value[k]):
            raise ValueError('Actual immutable receipt digest required')
    limits=dict(device_bytes=31268536320,minimum_pi_free_bytes=5*1024**3,
        minimum_c_free_bytes=50*1024**3,minimum_g_free_bytes=75*1024**3,
        cpus=[2,3],cpu_percent=200,tasks=64,hard_as_bytes=768*MIB,stack_bytes=MIB,
        model_threads=1,gpu=False,initial_available_bytes=850*MIB,stop_available_bytes=192*MIB,
        child_seconds=300,child_soft_seconds=270,stop_grace_seconds=30,
        recording_audio_seconds=120,maximum_samples=2080000,batch_seconds=600,
        idle_launch_seconds=86400,automatic_capture=False,automatic_restart=False)
    if encoded(value['limits'])!=encoded(limits):raise ValueError('Explicit release resource/lifetime limits')
    for k in ('measured_target_before_bytes','measured_host_before_bytes','measured_payload_before_bytes',
              'combined_output_cap_bytes','total_payload_cap_bytes'):
        integer(value[k],0,2**63-1)
    request=a['combined_request_bytes']
    if value['measured_target_before_bytes']+value['measured_host_before_bytes']+request>value['combined_output_cap_bytes']:
        raise ValueError('Target, local mirror and host output reservation')
    if value['measured_payload_before_bytes']+request>value['total_payload_cap_bytes']:
        raise ValueError('Full payload reservation')
    return value

def validate_research_operation(value,now=None):
    """This contract issues no production admission and cannot extend research."""
    if type(value) is not dict or set(value)!={'issued_utc','expires_utc','purpose'} or value['purpose']!='LOCAL_RELEASE_QUALIFICATION':
        raise ValueError('Explicit qualification operation only')
    start=datetime.fromisoformat(value['issued_utc']);end=datetime.fromisoformat(value['expires_utc'])
    now=datetime.now(timezone.utc) if now is None else now
    if start.tzinfo is None or end.tzinfo is None or not start<=now<end<=HARD_DEADLINE or (end-start).total_seconds()>600:
        raise ValueError('Fresh600s operation including closure/backup before hard deadline')
    return value

def recording_state(records):
    if type(records) is not dict or set(records)-set(RECORDING_RECORDS):
        raise ValueError('Known immutable recording records')
    if not records:return 'UNUSED'
    keys=set(records)
    if 'RESERVED' not in keys:raise ValueError('Reservation required even for failed staging')
    if 'CLOSED' in keys and ('STARTED' not in keys or 'FAILED' in keys):raise ValueError('Successful closure order')
    if 'PHYSICAL_CLOSURE' in keys and 'FAILED' not in keys:raise ValueError('Failure closure requires preserved failure')
    if 'BACKUP' in keys and not ('CLOSED' in keys or 'PHYSICAL_CLOSURE' in keys):
        raise ValueError('Backup requires recorded physical closure')
    if 'CLOSED' in keys:return 'CLOSED_BACKED' if 'BACKUP' in keys else 'CLOSED_UNBACKED'
    if 'FAILED' in keys:
        if 'PHYSICAL_CLOSURE' not in keys:return 'FAILED_OPEN'
        return 'FAILED_PRESERVED_BACKED' if 'BACKUP' in keys else 'FAILED_CLOSED_UNBACKED'
    return 'ACTIVE'

def next_recording(plan,records):
    if type(records) is not dict or set(records)!=set(plan['recording_slots']):raise ValueError('Exact recording membership')
    phases=[recording_state(records[n]) for n in plan['recording_slots']]
    used=[i for i,s in enumerate(phases) if s!='UNUSED']
    if used!=list(range(len(used))):raise ValueError('Reservation gap')
    if any(s not in ('UNUSED','CLOSED_BACKED','FAILED_PRESERVED_BACKED') for s in phases):
        raise RuntimeError('Full closure and independent verified backup before next recording')
    if len(used)==len(phases):raise RuntimeError('Finite recording reservations exhausted')
    return plan['recording_slots'][len(used)]

def next_launch(plan,records):
    if type(records) is not dict or set(records)!=set(plan['launch_slots']):raise ValueError('Exact launch membership')
    used=[]
    for i,name in enumerate(plan['launch_slots']):
        v=records[name]
        if type(v) is not dict or set(v)-set(LAUNCH_RECORDS):raise ValueError('Launch record fields')
        if not v:continue
        if 'OWNER' not in v:raise ValueError('Launch identity required')
        used.append(i)
        if 'EXIT' not in v:raise RuntimeError('Prior launch needs actual physical closure; restart fenced')
    if used!=list(range(len(used))):raise ValueError('Launch reservation gap')
    if len(used)==len(plan['launch_slots']):raise RuntimeError('Finite launch reservations exhausted')
    return plan['launch_slots'][len(used)]

def recovery_decision(*,owner_identities_complete,active_owners,capture_closed,leases_free,
                      unit_inactive,backup_verified,successful_application):
    values=(owner_identities_complete,capture_closed,leases_free,unit_inactive,backup_verified,successful_application)
    if any(type(v) is not bool for v in values) or type(active_owners) is not int or active_owners<0:
        raise ValueError('Typed observed recovery facts')
    if not owner_identities_complete:return 'FENCED_IDENTITY_GAP'
    if active_owners or not capture_closed or not leases_free or not unit_inactive:return 'FENCED_ACTIVE'
    if not backup_verified:return 'CLOSED_BACKUP_REQUIRED'
    return 'CLOSED_BACKED' if successful_application else 'FAILED_PRESERVED_BACKED'
