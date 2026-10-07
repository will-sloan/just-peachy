"""Repeated recording allocation/state contract; README_FIELD_OPERATOR_SESSIONS_V1.md."""
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import PurePosixPath

TARGET_PER_SESSION = 180331052
HOST_PER_SESSION = 184525356
MAX_SESSIONS = 4
RECORDS = ('RESERVED', 'STAGED', 'STARTED', 'CLOSED', 'FAILED', 'RECOVERED')
HARD_DEADLINE = datetime.fromisoformat('2026-10-01T17:42:44+00:00')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def allocation(count):
    if type(count) is not int or not 1 <= count <= MAX_SESSIONS:
        raise ValueError('One to four independently reserved sessions')
    # RELEASE primary+pending; six 16KiB primary+pending records per slot;
    # root, recordings parent and per-slot metadata directory reservations.
    metadata = 2*65536 + count*len(RECORDS)*2*16384 + (2+count)*65536
    target = count*TARGET_PER_SESSION + metadata
    host = count*HOST_PER_SESSION + metadata
    return dict(schema='just-peachy.operator-session-allocation.v1', count=count,
        slot_names=['slot-%02d' % i for i in range(1, count+1)],
        target_per_session=TARGET_PER_SESSION, host_per_session=HOST_PER_SESSION,
        metadata_maximum_bytes=metadata, target_maximum_bytes=target,
        host_maximum_bytes=host, combined_request_bytes=target+host,
        slot_file_bytes=16384, slot_write_bytes=16384,
        maximum_slot_files=2*len(RECORDS), maximum_release_bytes=65536,
        maximum_session_files=256, maximum_session_directories=64,
        reuse_deleted_or_failed_reservation=False)


def validate_policy(value, now=None):
    fields={'schema','root','issued_utc','expires_utc','allocation',
            'combined_output_cap_bytes','total_payload_cap_bytes','mode',
            'release_manifest_sha256','boot_id','host_window_bytes','target_before_bytes','payload_before_bytes'}
    if type(value) is not dict or set(value)!=fields:
        raise ValueError('Exact repeated-session policy fields')
    if value['schema']!='just-peachy.operator-session-policy.v1' or value['mode']!='delayed':
        raise ValueError('Only explicit delayed live composition is available')
    root=PurePosixPath(value['root'])
    if (str(root)!=value['root'] or not str(root).startswith(
        '/home/peachyprototype/JustPeachy/research/nemotron-20260928/')
        or '..' in root.parts or not re.fullmatch(r'field-operator-sessions-v[1-9][0-9]*',root.name)):
        raise ValueError('Fresh dedicated native sessions root')
    if encoded(value['allocation'])!=encoded(allocation(value['allocation']['count'])):
        raise ValueError('Full independent session and metadata allocation required')
    for key in ('combined_output_cap_bytes','total_payload_cap_bytes'):
        if type(value[key]) is not int or value[key]<=value['allocation']['combined_request_bytes']:
            raise ValueError('Measured explicit cumulative policy required')
    for key in ('host_window_bytes','target_before_bytes','payload_before_bytes'):
        if type(value[key]) is not int or value[key]<0:raise ValueError('Nonnegative measured census')
    request=value['allocation']['combined_request_bytes']
    if value['host_window_bytes']+value['target_before_bytes']+request>value['combined_output_cap_bytes']:
        raise ValueError('Measured output admission shortfall')
    if value['payload_before_bytes']+request>value['total_payload_cap_bytes']:
        raise ValueError('Measured payload admission shortfall')
    if not re.fullmatch('[0-9a-f]{64}',value['release_manifest_sha256']):
        raise ValueError('Exact release manifest digest')
    if not re.fullmatch('[0-9a-f-]{36}',value['boot_id']):
        raise ValueError('Exact native boot identity')
    issued=datetime.fromisoformat(value['issued_utc']);end=datetime.fromisoformat(value['expires_utc'])
    now=datetime.now(timezone.utc) if now is None else now
    if issued.tzinfo is None or end.tzinfo is None or not issued<=now<end<=HARD_DEADLINE:
        raise ValueError('Live policy within immutable delivery boundary')
    if (end-issued).total_seconds()>600:
        raise ValueError('Fresh bounded batch must include closure and backup within600s')
    return value


def state(records):
    if type(records) is not dict or set(records)-set(RECORDS):
        raise ValueError('Unknown session record')
    if not records:return 'UNUSED'
    if 'RESERVED' not in records:raise ValueError('Session reservation missing')
    if 'STAGED' in records and 'RESERVED' not in records:raise ValueError('Missing reservation')
    if 'STARTED' in records and 'STAGED' not in records:raise ValueError('Start before staging')
    if 'CLOSED' in records and ('STARTED' not in records or 'FAILED' in records):
        raise ValueError('Successful closure must follow a started, nonfailed session')
    if 'RECOVERED' in records and 'FAILED' not in records:
        raise ValueError('Recovery needs the preserved failure')
    if 'FAILED' in records:return 'FAILED_CLOSED' if 'RECOVERED' in records else 'FAILED_OPEN'
    if 'CLOSED' in records:return 'CLOSED'
    return 'ACTIVE'


def next_slot(plan, records):
    expected=plan['slot_names']
    if set(records)!=set(expected):raise ValueError('Exact slot membership')
    phases=[state(records[name]) for name in expected]
    if any(s in ('ACTIVE','FAILED_OPEN') for s in phases):
        raise RuntimeError('Prior session must be physically closed before next allocation')
    used=[i for i,s in enumerate(phases) if s!='UNUSED']
    if used!=list(range(len(used))):raise ValueError('Reservation gap')
    if len(used)==len(expected):raise RuntimeError('All reservations consumed')
    return expected[len(used)]


def rebase(value, old_root, new_root):
    """Move only exact rooted path values, never arbitrary text or digest bytes."""
    old=PurePosixPath(old_root);new=PurePosixPath(new_root)
    if not old.is_absolute() or not new.is_absolute() or '..' in old.parts or '..' in new.parts:
        raise ValueError('Absolute roots without traversal')
    if isinstance(value,dict):return {k:rebase(v,str(old),str(new)) for k,v in value.items()}
    if isinstance(value,list):return [rebase(v,str(old),str(new)) for v in value]
    if type(value) is str and (value==str(old) or value.startswith(str(old)+'/')):
        return str(new)+value[len(str(old)):]
    return value


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()
