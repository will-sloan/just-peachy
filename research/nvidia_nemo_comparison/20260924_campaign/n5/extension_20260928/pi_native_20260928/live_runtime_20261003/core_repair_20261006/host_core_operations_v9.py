"""Exact build31 stage payload allowance; README_CORE_OPERATIONS_V9.md."""
import psutil
psutil.Process().cpu_affinity([14])
import hashlib
import ctypes
import json
import math
import os
from pathlib import Path
import re
import sys
import uuid

_private = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
_early = _private / 'audit-preparation' / ('core-operations-source-' + uuid.uuid4().hex)
_early.mkdir()
_kernel = ctypes.WinDLL('kernel32', use_last_error=True)
_kernel.GetCurrentProcess.restype = ctypes.c_void_p
_kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
_times = [ctypes.c_ulonglong() for _ in range(4)]
if not _kernel.GetProcessTimes(_kernel.GetCurrentProcess(), *(ctypes.byref(value) for value in _times)):
    raise ctypes.WinError(ctypes.get_last_error())
with (_early / 'REGISTERED_OWNER.json').open('x') as _stream:
    json.dump(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
        affinity_mask=16384, creation_filetime=_times[0].value,
        create_time=(_times[0].value - 116444736000000000) / 10000000), _stream)
    _stream.flush(); os.fsync(_stream.fileno())

parent = Path(__file__).resolve().parent.parent / 'stabilization_20261005/host_stabilization_operations_v5.py'
raw = parent.read_bytes()
marker = "if sys.argv[1:]==['--host-review']:"
if raw.decode().count(marker) != 1:
    raise ValueError('Exact existing dispatcher entry boundary')
space = dict(__name__='core_operations', __file__=str(parent))
exec(compile(raw.decode().split(marker)[0], str(parent), 'exec'), space)
# The original prefix registers CPU14 and exact FILETIME before data reads.
early = space['early']
for path in (Path(__file__), Path(__file__).with_name('README_CORE_OPERATIONS_V9.md'), parent):
    data = path.read_bytes()
    for suffix in ('.backup', '.restore'):
        destination = early / (path.name + suffix)
        with destination.open('xb') as stream:
            stream.write(data); stream.flush()
            space['os'].fsync(stream.fileno())
        if destination.read_bytes() != data:
            raise OSError('Independent dispatcher source readback')
old_map = space['actual_nested_unit_map']


def current_map():
    pins, summary = old_map()
    private = space['PRIVATE']
    paths = list(private.glob('production-backup-*-*-monitor-*/RESULT.json'))
    paths += list(private.glob('production-backup-*-reconcile-*/guard-monitor/RESULT.json'))
    added = 0
    for result_path in sorted(set(paths)):
        result = space['strict'](space['read'](result_path, 262144))
        if result.get('status') != 'FULL_CLOSED_OUTPUT_MIRRORED':
            continue
        job = result['job']; label = job['output_root'].rsplit('/', 1)[1]
        if label == 'production-backup-09':
            continue
        if re.fullmatch('production-backup-[0-9]{2}', label) is None:
            raise ValueError('Exact snapshot root required')
        root = result_path.parent
        rows = space['strict'](space['read'](root / 'MIRROR_MANIFEST.json'))
        complete = space['strict'](space['read'](root / 'MIRROR_COMPLETE.json'))
        closure = complete['closure']
        if (complete.get('kind') != 'COMPLETE' or complete.get('files') != len(rows)
            or complete.get('manifest_sha256') != space['sha'](space['encoded'](rows))
            or any(closure.get(key) != job[key] for key in ('unit', 'invocation_id', 'owner', 'control_group'))
            or any(closure.get(key) is not True for key in ('closed', 'exact_owner_gone', 'cgroup_empty'))):
            raise ValueError('Independent snapshot mirror and exact physical closure required')
        entries = {row['path']: row for row in rows}
        def member(name):
            value = space['read'](root / 'closed-output' / name, 16384)
            entry = entries[name]
            if len(value) != entry['identity']['bytes'] or space['sha'](value) != entry['sha256']:
                raise ValueError('Exact independent snapshot member readback')
            return value, space['strict'](value)
        value_raw, value = member('UNIT_OWNERSHIP.json')
        _, owner = member('OWNER.json')
        _, actual_job = member('JOB.json')
        _, exit_row = member('JOB_EXIT.json')
        _, released = member('SNAPSHOT_RELEASED.json')
        expected_unit = 'jp-v29-' + label + '.service'
        if (set(value) != space['KEYS'] or value['owner'] != owner or owner != job['owner']
            or actual_job != {key: val for key, val in job.items() if key != 'output_identity'}
            or value['unit'] != job['unit'] or job['unit'] != expected_unit
            or value['invocation_id'] != job['invocation_id'] or value['control_group'] != job['control_group']
            or type(value['main_pid']) is not int or value['main_pid'] != owner['pid']
            or type(value['runtime_max_seconds']) is not int or not 180 <= value['runtime_max_seconds'] <= 3600
            or value['idle_timeout_seconds'] != 300 or type(value['idle_timeout_seconds']) is not int
            or type(value['deadline_monotonic']) not in (int, float) or not math.isfinite(value['deadline_monotonic'])
            or exit_row != closure.get('job_exit') or exit_row.get('leases_released') is not True
            or released.get('owner') != owner or released.get('hardware_lease_released') is not True):
            raise ValueError('Exact closed snapshot supervisor provenance required')
        space['identity'](owner)
        key = 'live-runtime-tests-20261003/' + label + '/UNIT_OWNERSHIP.json'
        pin = dict(sha256=space['sha'](value_raw), bytes=len(value_raw), owner=owner, document=value, kind='backup_guard')
        if key in pins and pins[key] != pin:
            raise ValueError('Conflicting exact snapshot supervisor')
        pins[key] = pin; added += 1
    return pins, dict(summary, additional_closed_snapshots=added, failed_source_verification_not_promoted=True)


space['actual_nested_unit_map'] = current_map
old_bind = space['driver'].bind_native_owner_references


def bind(native, new_owners, unit_owners):
    text = old_bind(native, new_owners, unit_owners)
    first = "  elif expected['kind']=='backup_guard':\n"
    last = "  else:\n   assert expected['kind']=='watchdog'"
    if text.count(first) != 1 or text.count(last) != 1:
        raise ValueError('Exact snapshot-only decoder boundary')
    begin = text.index(first); end = text.index(last, begin)
    replacement = """  elif expected['kind']=='backup_guard':
   assert re.fullmatch(r'live-runtime-tests-20261003/production-backup-[0-9]{2}/UNIT_OWNERSHIP.json',rel)
   assert set(v)=={'control_group','deadline_monotonic','idle_timeout_seconds','invocation_id','main_pid','owner','runtime_max_seconds','unit'}
   assert v==expected['document'] and v['owner']==expected['owner']
   assert v['unit']=='jp-v29-'+rel.split('/')[1]+'.service'
   assert type(v['runtime_max_seconds']) is int and 180<=v['runtime_max_seconds']<=3600
   assert type(v['idle_timeout_seconds']) is int and v['idle_timeout_seconds']==300
   assert type(v['deadline_monotonic']) in (int,float) and math.isfinite(v['deadline_monotonic']) and v['deadline_monotonic']>0
"""
    return text[:begin] + replacement + text[end:]


space['driver'].bind_native_owner_references = bind
old_decoder = space['driver'].bounded_lifetime_decoder
def decoder(raw):
    text = old_decoder(raw).decode()
    anchor = '            if relative in HOST_OWNER_FORMAT_CORRECTIONS:'
    if text.count(anchor) != 1:
        raise ValueError('Exact retained host-format boundary')
    correction = '''            if relative == 'live-runtime-20261003/audit-preparation/backup10-export-seed-7c8a0e57506645fca306e136e7271deb/REGISTERED_OWNER.json':
                if (hashlib.sha256(path.read_bytes()).hexdigest() != '65734f0d65a2ef61d6fbe8d0e5a7867466d3e3a8e64460d553b36f11cc5b67a5'
                    or value != {'schema':'just-peachy.host-registered-owner.v1','pid':52104,'cpu14':True,'affinity_mask':16384,'creation_filetime':134357782255738241,'create_time':1791304625.573824}):
                    raise ValueError('Exact preserved seed owner registration changed')
                value = dict(value, cpu=14)
'''
    return text.replace(anchor, correction + anchor).encode()
space['driver'].bounded_lifetime_decoder = decoder
_prior_metadata_bind = space['driver'].bind_native_owner_references
def metadata_memory_bind(native, new_owners, unit_owners):
    native = _prior_metadata_bind(native, new_owners, unit_owners)
    memory = '(resource.RLIMIT_AS,134217728)'
    floor = "mem['MemAvailable']>=192*1024**2"
    output = 'raw=json.dumps(value)'
    if any(native.count(anchor) != 1 for anchor in (memory,floor,output)):
        raise ValueError('Exact metadata utility memory admission boundaries required')
    native = native.replace(memory,'(resource.RLIMIT_AS,268435456)')
    native = native.replace(floor,"mem['MemAvailable']>=978*1024**2")
    native = native.replace(output,"value['metadata_utility_memory']=dict(hard_address_space_bytes=resource.getrlimit(resource.RLIMIT_AS)[1],peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,initial_available_floor_bytes=978*1024**2)\n"+output)
    return native
space['driver'].bind_native_owner_references = metadata_memory_bind


def stage31_payload_ceiling(args):
    """Keep 2 MiB normally; admit only the sealed stage31-02 payload up to 3 MiB."""
    default = 2*1024**2
    if args.payload.stat().st_size <= default or args.payload.stat().st_size > 3*1024**2:
        return default
    if args.label != 'core-stage31-02' or args.writes is not True:
        return default
    import base64
    from pathlib import PurePosixPath
    payload_sha = '5af9ec3f9c5fb8a7fedae0f7c2c00eb80515cfe8039723e23feb79b50ef8eb6d'
    action_sha = '4f5876f32a634db420baf78583a7a0ebac7d27b17bab52aace867d78df0d1c74'
    installer_sha = 'b4cbc107259556f901da1e47462b9ba238b766e56b7910c3c5982ea3fee68ad6'
    archive_sha = 'e6d5e40c8c14ef5cc0e2e02d7d02894cdb48ac7a663cf34a334da36a0cd66db3'
    manifest_sha = '4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
    review_sha = '6894adf19266061a15a71dc103d7317303652d68d58a4e27b74016430caaf4ca'
    boot = 'e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
    target = space['NATIVE_PREFIX'] + 'field-runtime-v29-build-31'
    action_raw = space['read'](args.action, 131072)
    payload_raw = space['read'](args.payload, 3*1024**2)
    if (space['sha'](action_raw) != action_sha or len(payload_raw) != 2142512
        or space['sha'](payload_raw) != payload_sha):
        raise ValueError('Only the exact sealed build31 action and payload receive 3 MiB')
    data = space['strict'](payload_raw)
    if (set(data) != {'archive_base64', 'archive_sha256', 'expected_boot_id',
        'installer_source_base64', 'installer_source_sha256', 'manifest_sha256',
        'production_backup_admission', 'source_review_sha256', 'target_reservation_bytes'}
        or data['archive_sha256'] != archive_sha or data['manifest_sha256'] != manifest_sha
        or data['installer_source_sha256'] != installer_sha or data['expected_boot_id'] != boot
        or data['source_review_sha256'] != review_sha):
        raise ValueError('Exact sealed build31 payload bindings required')
    backup = _private / 'production-backup-14-reconcile-01'
    accepted = {
        'COMPLETE.json': '9aa11fd4932bb64accda5a8155e735110c20bfb29189c4dc07563c7a171ee80e',
        'RESULT.json': '1154c795a07e35941d21f99fc81617f0534dd3de51771c070d031ce526d2f879',
        'CENSUS.json': '509432c01072df2d33b12cdf7de17f1fe450fede5f3521df051744107f68a263',
    }
    admission = data['production_backup_admission']
    if (admission.get('schema') != 'just-peachy.core-stage-backup-admission.v1'
        or Path(admission['backup_root']) != backup or Path(admission['root']) != backup / 'payload'
        or admission['boot_id'] != boot or admission['completion_sha256'] != accepted['COMPLETE.json']
        or admission['result_sha256'] != accepted['RESULT.json']
        or any(admission.get(key) is not True for key in ('source_before_after_verified',
            'external_asset_pins_verified', 'exact_owner_gone', 'cgroup_empty'))
        or admission.get('natural_returncode') != 0
        or admission.get('owner') != dict(boot_id=boot, pid=68815, start_ticks=1489488)):
        raise ValueError('Root accepted closed backup14 admission required')
    for name, expected in accepted.items():
        raw = space['read'](backup / name, 2*1024**2)
        pin = admission['input_pins'][name]
        if pin['sha256'] != expected or pin['bytes'] != len(raw) or space['sha'](raw) != expected:
            raise ValueError('Accepted backup14 metadata changed: ' + name)
    if (len(data['archive_base64']) > 4*((2*1024**2+2)//3)
        or len(data['installer_source_base64']) > 4*((131072+2)//3)):
        raise ValueError('Finite sealed archive and installer encodings required')
    archive = base64.b64decode(data['archive_base64'], validate=True)
    installer = base64.b64decode(data['installer_source_base64'], validate=True)
    if (len(archive) != 1592165 or len(archive) > default or space['sha'](archive) != archive_sha
        or len(installer) > 131072 or space['sha'](installer) != installer_sha):
        raise ValueError('Exact bounded build31 archive and installer required')
    # This immutable module defines its pure validator; its guarded main does not run.
    validator = dict(__name__='core_v9_sealed_archive_validation')
    exec(compile(installer, '<sealed-build31-installer-validator>', 'exec'), validator)
    manifest, members = validator['validate_payload'](archive, archive_sha, manifest_sha)
    expanded = sum(map(len, members.values()))
    directories = {str(parent) for name in members for parent in PurePosixPath(name).parents
                   if str(parent) != '.'}
    reservation = expanded + len(archive) + (len(directories)+1)*65536 + 65536
    if (manifest.get('target') != target or len(members) != 425 or expanded != 7078265
        or len(directories) != 8 or type(data['target_reservation_bytes']) is not int
        or data['target_reservation_bytes'] != reservation or reservation != 9325790):
        raise ValueError('Exact canonical build31 inventory and full reservation required')
    space['put']('STAGE31_PAYLOAD_ADMISSION.json', dict(
        schema='just-peachy.core-stage31-payload-admission.v1', label=args.label,
        default_payload_bytes=default, admitted_payload_bytes=3*1024**2,
        actual_payload_bytes=len(payload_raw), payload_sha256=payload_sha,
        action_sha256=action_sha, archive_sha256=archive_sha, archive_bytes=len(archive),
        installer_sha256=installer_sha, manifest_sha256=manifest_sha,
        source_review_sha256=review_sha, target=target, expanded_bytes=expanded,
        members=len(members), target_reservation_bytes=reservation,
        accepted_backup_metadata_sha256=accepted, pure_host_validation=True))
    return 3*1024**2


_payload_anchor = 'a.payload.stat().st_size > 2*1024**2'
_payload_main = space['_main_source']
if _payload_main.count(_payload_anchor) != 1:
    raise ValueError('Exactly one retained local payload stat boundary required')
_payload_replacement = 'a.payload.stat().st_size > stage31_payload_ceiling(a)'
_payload_main = _payload_main.replace(_payload_anchor, _payload_replacement)
if _payload_main.replace(_payload_replacement, _payload_anchor) != space['_main_source']:
    raise ValueError('Only the exact payload stat boundary may change')
space['driver'].__dict__['stage31_payload_ceiling'] = stage31_payload_ceiling
exec(compile(_payload_main, '<core-v9-exact-stage31-payload-main>', 'exec'), space['driver'].__dict__)
space['driver'].main()
