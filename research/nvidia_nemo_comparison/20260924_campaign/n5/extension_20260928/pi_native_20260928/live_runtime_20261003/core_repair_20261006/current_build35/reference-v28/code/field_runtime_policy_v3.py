"""Finite offline user-release policy; see README_FIELD_RUNTIME_POLICY_V3.md."""
from datetime import datetime, timezone, timedelta
from pathlib import PurePosixPath
import hashlib
import json
import re

from field_local_release_plan_v2 import allocation, encoded

SCHEMA = 'just-peachy.offline-runtime-policy.v1'
OPERATION = 'just-peachy.offline-runtime-operation.v1'
ROOT = PurePosixPath('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
MIB = 1024 ** 2
GIB = 1024 ** 3
PROFILES = ('baseline', 'baseline-titanet', 'd1-delayed', 'd1-delayed-titanet', 'd1-streaming-saved', 'd1-streaming-titanet-saved', 'd1-chunk52-saved', 'd1-chunk52-titanet-saved', 'd1-anonymous', 'baseline-anonymous')
LIMITS = dict(device_bytes=31268536320, minimum_pi_free_bytes=5*GIB,
    minimum_c_free_bytes=50*GIB, minimum_g_free_bytes=75*GIB,
    cpus=[2, 3], cpu_percent=200, tasks=64, hard_as_bytes=768*MIB,
    metadata_as_bytes=128*MIB, stack_bytes=MIB, model_threads=1, gpu=False,
    initial_available_bytes=850*MIB, stop_available_bytes=192*MIB,
    idle_launch_seconds=86400, operation_seconds=600, recording_audio_seconds=120,
    child_seconds=300, child_soft_seconds=270, stop_grace_seconds=30,
    maximum_samples=2080000, automatic_capture=False, automatic_restart=False)


def integer(value, low=0, high=2**63-1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Bounded exact integer required')
    return value


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def pin(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Exact SHA256 required')
    return value


def timestamp(value):
    if type(value) is not str:
        raise ValueError('Aware timestamp string required')
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset().total_seconds() != 0:
        raise ValueError('UTC timestamp required')
    return result


def identity(value):
    if type(value) is not dict or set(value) != {'pid', 'start_ticks', 'boot_id'}:
        raise ValueError('Exact native identity required')
    integer(value['pid'], 1); integer(value['start_ticks'], 1)
    if type(value['boot_id']) is not str or not re.fullmatch(
            '[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', value['boot_id']):
        raise ValueError('Canonical boot UUID required')
    return value


def validate(value):
    fields = {'schema', 'release_id', 'manager_root', 'recording_roots', 'provisioned_utc',
        'allocation', 'limits', 'runtime_manifest_sha256', 'installed_manifest_sha256',
        'profiles', 'measured_target_bytes', 'measured_host_bytes', 'measured_payload_bytes',
        'combined_output_cap_bytes', 'total_payload_cap_bytes', 'storage_semantics'}
    if type(value) is not dict or set(value) != fields or value['schema'] != SCHEMA:
        raise ValueError('Exact offline runtime policy required')
    if type(value['release_id']) is not str or not re.fullmatch('field-runtime-v[1-9][0-9]*', value['release_id']):
        raise ValueError('Fresh immutable release ID required')
    if value['manager_root'] != str(ROOT/value['release_id']):
        raise ValueError('Canonical immediate runtime root required')
    timestamp(value['provisioned_utc'])
    a = value['allocation']
    if type(a) is not dict or 'recordings' not in a or 'launches' not in a:
        raise ValueError('Independent reservation required')
    expected = allocation(a['recordings'], a['launches'])
    if encoded(a) not in (encoded(expected),encoded(legacy_allocation(a['recordings'],a['launches']))):
        raise ValueError('Original full target/local/PC allocation required')
    # Three helper launches per recording plus an idle manager launch are real costs.
    if a['launches'] < 1 + 3*a['recordings']:
        raise ValueError('Manager and each recording need independent launch slots')
    roots = value['recording_roots']
    if type(roots) is not list or len(roots) != a['recordings'] or len(set(roots)) != len(roots):
        raise ValueError('One distinct never-reused broker root per recording')
    for root in roots:
        if type(root) is not str or PurePosixPath(root).parent != ROOT or not re.fullmatch(
                'field-operator-sessions-v[1-9][0-9]*', PurePosixPath(root).name):
            raise ValueError('Canonical independent broker root required')
        if str(PurePosixPath(root)) != root:
            raise ValueError('Canonical broker spelling required')
    if encoded(value['limits']) != encoded(LIMITS):
        raise ValueError('Reviewed CPU/RAM/disk/time/capture bounds required')
    for key in ('runtime_manifest_sha256', 'installed_manifest_sha256'):
        pin(value[key])
    profiles = value['profiles']
    if type(profiles) is not dict or set(profiles) != set(PROFILES):
        raise ValueError('Explicit complete supported-profile availability map required')
    for name, row in profiles.items():
        if type(row) is not dict or set(row) != {'available', 'input_kind', 'manifest_sha256', 'reason'}:
            raise ValueError('Exact profile fields required')
        if type(row['available']) is not bool or type(row['reason']) is not str or len(row['reason']) > 512:
            raise ValueError('Typed availability and bounded explanation required')
        expected_input = 'saved' if name.endswith('-saved') else 'microphone'
        if row['input_kind'] != expected_input:
            raise ValueError('Do not relabel saved qualification as live availability')
        if row['available']:
            pin(row['manifest_sha256'])
            if row['reason']:
                raise ValueError('Available profile must have a pinned implementation')
        elif row['manifest_sha256'] is not None or not row['reason'].strip():
            raise ValueError('Unavailable profile must explain why without a runnable pin')
    semantics = dict(local_backup_before_next=True, pc_copy_deferred_until_connected=True,
        pc_reservation_independent=True, original_preserved=True, copy_not_move=True,
        failed_deleted_unused_credit=False, automatic_replenishment=False,
        explicit_reprovision_required=True)
    if encoded(value['storage_semantics']) != encoded(semantics):
        raise ValueError('Offline local protection and independent deferred PC copy required')
    for key in ('measured_target_bytes', 'measured_host_bytes', 'measured_payload_bytes',
                'combined_output_cap_bytes', 'total_payload_cap_bytes'):
        integer(value[key])
    request = a['combined_request_bytes']
    if value['measured_target_bytes']+value['measured_host_bytes']+request > value['combined_output_cap_bytes']:
        raise ValueError('Full independent output reservation does not fit')
    if value['measured_payload_bytes']+request > value['total_payload_cap_bytes']:
        raise ValueError('Full independent payload reservation does not fit')
    if len(encoded(value)) > 65536:
        raise ValueError('Original policy member ceiling')
    return value


def issue_operation(policy, *, slot, profile, owner, now, seconds=600):
    """Pure proposal. Native supervisor must observe resources and persist before use."""
    validate(policy); identity(owner); integer(seconds, 1, 600)
    if now.tzinfo is None or now.utcoffset().total_seconds() != 0:
        raise ValueError('Current UTC observation required')
    if now < timestamp(policy['provisioned_utc']):
        raise ValueError('Clock predates provisioning')
    if slot not in policy['allocation']['recording_slots']:
        raise ValueError('Exact finite recording slot required')
    row = policy['profiles'].get(profile)
    if row is None or not row['available']:
        raise ValueError('Profile unavailable; no silent fallback')
    result = dict(schema=OPERATION, purpose='USER_RECORDING', policy_sha256=digest(policy),
        root=policy['recording_roots'][policy['allocation']['recording_slots'].index(slot)],
        slot=slot, profile=profile, profile_manifest_sha256=row['manifest_sha256'], owner=owner,
        issued_utc=now.isoformat(), expires_utc=(now+timedelta(seconds=seconds)).isoformat())
    validate_operation(result, policy, now=now)
    return result


def validate_operation(value, policy, *, now):
    validate(policy)
    fields = {'schema', 'purpose', 'policy_sha256', 'root', 'slot', 'profile',
        'profile_manifest_sha256', 'owner', 'issued_utc', 'expires_utc'}
    if type(value) is not dict or set(value) != fields or value['schema'] != OPERATION or value['purpose'] != 'USER_RECORDING':
        raise ValueError('Exact independently issued user operation required')
    if value['policy_sha256'] != digest(policy):
        raise ValueError('Current immutable policy digest required')
    identity(value['owner'])
    slot = value['slot']
    if slot not in policy['allocation']['recording_slots']:
        raise ValueError('Allocated recording slot required')
    if value['root'] != policy['recording_roots'][policy['allocation']['recording_slots'].index(slot)]:
        raise ValueError('Operation cannot escape its reserved root')
    row = policy['profiles'].get(value['profile'])
    if row is None or not row['available'] or value['profile_manifest_sha256'] != row['manifest_sha256']:
        raise ValueError('Available pinned profile required')
    start = timestamp(value['issued_utc']); end = timestamp(value['expires_utc'])
    if now.tzinfo is None or now.utcoffset().total_seconds() != 0:
        raise ValueError('Aware UTC observation required')
    if not timestamp(policy['provisioned_utc']) <= start <= now < end or not 0 < (end-start).total_seconds() <= 600:
        raise ValueError('Fresh finite600s operation including cleanup required')
    return value


def next_slot(policy, records):
    """No deletion credit. PC offload may be pending; verified local copy may not."""
    validate(policy)
    slots = policy['allocation']['recording_slots']
    if type(records) is not dict or set(records) != set(slots):
        raise ValueError('Complete finite recording ledger required')
    used = []
    for i, slot in enumerate(slots):
        row = records[slot]
        if row is None:
            continue
        if type(row) is not dict or set(row) != {'state', 'local_backup_sha256', 'pc_backup_sha256'}:
            raise ValueError('Exact recording state required')
        used.append(i)
        if row['state'] not in ('CLOSED_LOCAL_BACKED', 'FAILED_PRESERVED_LOCAL_BACKED'):
            raise RuntimeError('Previous source must be closed and locally backed')
        pin(row['local_backup_sha256'])
        if row['pc_backup_sha256'] is not None:
            pin(row['pc_backup_sha256'])
    if used != list(range(len(used))):
        raise ValueError('Immutable reservation gap')
    if len(used) == len(slots):
        raise RuntimeError('Recording reservations exhausted; explicit reprovision required')
    return slots[len(used)]

def validate_broker_policy(value, runtime, operation, *, now=None):
    """Bind one finite broker to the persistent policy and durable reservation."""
    fields = {'schema','root','issued_utc','expires_utc','allocation',
        'combined_output_cap_bytes','total_payload_cap_bytes','mode',
        'release_manifest_sha256','boot_id','host_window_bytes','target_before_bytes',
        'payload_before_bytes','runtime_policy_sha256','runtime_operation_sha256',
        'runtime_root','slot','profile'}
    if type(value) is not dict or set(value) != fields or value['schema'] != 'just-peachy.offline-broker-policy.v1':
        raise ValueError('Exact production broker policy required')
    now = datetime.now(timezone.utc) if now is None else now
    validate_operation(operation, runtime, now=now)
    expected = dict(root=operation['root'],issued_utc=operation['issued_utc'],
        expires_utc=operation['expires_utc'],allocation=runtime['allocation']['broker_allocation'],
        combined_output_cap_bytes=runtime['combined_output_cap_bytes'],
        total_payload_cap_bytes=runtime['total_payload_cap_bytes'],
        boot_id=operation['owner']['boot_id'],host_window_bytes=runtime['measured_host_bytes'],
        target_before_bytes=runtime['measured_target_bytes'],payload_before_bytes=runtime['measured_payload_bytes'],
        runtime_policy_sha256=digest(runtime),runtime_operation_sha256=digest(operation),
        runtime_root=runtime['manager_root'],slot=operation['slot'],profile=operation['profile'])
    for key, actual in expected.items():
        if encoded(value[key]) != encoded(actual):
            raise ValueError('Broker/runtime reservation drift: '+key)
    modes = {'baseline':'baseline','baseline-titanet':'baseline','baseline-anonymous':'baseline',
             'd1-delayed':'delayed','d1-delayed-titanet':'delayed','d1-anonymous':'delayed',
             'd1-streaming-saved':'streaming','d1-streaming-titanet-saved':'streaming',
             'd1-chunk52-saved':'chunk52','d1-chunk52-titanet-saved':'chunk52'}
    if value['mode'] != modes[operation['profile']]:
        raise ValueError('Explicit profile-to-engine mode required')
    pin(value['release_manifest_sha256'])
    return value


def load_broker_policy(value, *, now=None):
    """Native consumer reads actual immutable policy and RESERVED bytes."""
    from pathlib import Path
    from field_live_layout_v3 import finite_json
    if type(value) is not dict or type(value.get('runtime_root')) is not str:
        raise ValueError('Explicit installed runtime root required')
    root = Path(value['runtime_root'])
    if (root.parent.as_posix() != str(ROOT) or root.as_posix()!=value['runtime_root']
            or not re.fullmatch('field-runtime-v[1-9][0-9]*', root.name)):
        raise ValueError('Canonical installed runtime root')
    slot = value.get('slot')
    if type(slot) is not str or not re.fullmatch('recording-0[1-4]',slot):
        raise ValueError('Allocated recording slot required')
    def read_bound(path, cap):
        import stat
        for parent in path.parents:
            if parent.is_symlink() or not parent.is_dir():
                raise ValueError('Real runtime policy ancestors')
        before=path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>cap:
            raise ValueError('Bounded unique immutable metadata file')
        raw=path.read_bytes();after=path.lstat()
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise RuntimeError('Runtime policy changed while reading')
        if len(raw)!=before.st_size:
            raise RuntimeError('Runtime policy incomplete read')
        return finite_json(raw)
    runtime=read_bound(root/'control/RELEASE.json',65536)
    reservation=read_bound(root/'recordings'/slot/'RESERVED.json',16384)
    if (type(reservation) is not dict or set(reservation)!={'policy_sha256','slot','utc','operation'}
            or reservation['policy_sha256']!=digest(runtime) or reservation['slot']!='recordings/'+slot):
        raise ValueError('Actual immutable runtime reservation required')
    timestamp(reservation['utc'])
    return validate_broker_policy(value,runtime,reservation['operation'],now=now)

def legacy_allocation(recordings,launches):
    from copy import deepcopy
    result=deepcopy(allocation(recordings,launches))
    extra=33411072
    b=result['broker_allocation']
    for key in ('target_per_session','host_per_session','target_maximum_bytes','host_maximum_bytes'):b[key]-=extra
    b['combined_request_bytes']-=2*extra
    result['local_backup_per_recording']-=extra
    result['host_local_backup_per_recording']-=extra
    result['target_maximum_bytes']-=2*recordings*extra
    result['host_maximum_bytes']-=2*recordings*extra
    result['combined_request_bytes']-=4*recordings*extra
    return result
