"""Current snapshot and SQLite capacity binding; README_CORE_OPERATIONS_V3.md."""
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
for path in (Path(__file__), Path(__file__).with_name('README_CORE_OPERATIONS_V3.md'), parent):
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
# Only this exact backed action may receive a capacity-derived initial FSIZE.
_main_source = space['_main_source']
_before = "    if a.writes:\n        native = native.replace('(resource.RLIMIT_FSIZE,0)', '(resource.RLIMIT_FSIZE,33554432)')"
_after = """    if a.writes:
        if a.action.name == 'recover_core_database_v2.py':
            if (hashlib.sha256(action).hexdigest() != '3f5c7e608f7e6713f0581835b8d4fcca1e2bd916948493b298b0062b4be5aac4'
                or data.get('schema') != 'just-peachy.core-database-recovery.v2'
                or type(data.get('maximum_file_bytes')) is not int
                or not 33554432 <= data['maximum_file_bytes'] <= 2**63-1):
                raise ValueError('Exact recovery action/schema/finite physical allowance required')
            if native.count('(resource.RLIMIT_FSIZE,0)') != 1:
                raise ValueError('Exact initial native file-size boundary required')
            native = native.replace('(resource.RLIMIT_FSIZE,0)',
                "(resource.RLIMIT_FSIZE,min(ACTION_PAYLOAD['maximum_file_bytes'],os.statvfs('/home/peachyprototype/JustPeachy/data/runtime-v29/recordings').f_blocks*os.statvfs('/home/peachyprototype/JustPeachy/data/runtime-v29/recordings').f_frsize-5*1024**3))")
        else:
            native = native.replace('(resource.RLIMIT_FSIZE,0)', '(resource.RLIMIT_FSIZE,33554432)')"""
if _main_source.count(_before) != 1:
    raise ValueError('Exact action-specific initial FSIZE derivative required')
_main_source = _main_source.replace(_before, _after)
compile(_main_source, '<core-capacity-recovery-dispatch>', 'exec')
exec(compile(_main_source, '<core-capacity-recovery-dispatch>', 'exec'), space['driver'].__dict__)
space['put']('RECOVERY_FSIZE_DERIVATION.json', space['encoded'](dict(
    action='recover_core_database_v2.py',
    action_sha256='3f5c7e608f7e6713f0581835b8d4fcca1e2bd916948493b298b0062b4be5aac4',
    schema='just-peachy.core-database-recovery.v2',
    bound='min(admitted maximum, actual filesystem capacity minus 5 GiB)',
    all_other_actions_file_limit_bytes=33554432,
    baseline_owner_resource_and_ssh_guards_retained=True)))
space['driver'].main()
