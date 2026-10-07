"""Repeated recording allocation/state contract; README_FIELD_OPERATOR_BROKER_NATIVE_V1.md."""
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


from field_operator_broker_layout_v2 import allocation


def validate_policy(value, now=None):
    from field_runtime_policy_v3 import load_broker_policy
    return load_broker_policy(value,now=now)


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
