"""Copy an actual reviewed build31 live/saved/hour JOB; README_EXTRACT_CORE_JOB31.md.

Narrow derivative of the frozen V6/savedV2 extraction pattern. Metadata only;
no SSH, native action, model, package import, SQLite open or invented JOB.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import time
import uuid

HERE = Path(__file__).resolve().parent
S = HERE.parent/'stabilization_20261005'
Q = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
NATIVE_TESTS = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003'
BOOT = 'e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
PIN = '4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
HELPERS = {
    'live': '5c6eab13e00076aabf3f022f69410e1f330dc16a4cbad69b49b8fe016109e37e',
    'saved': '01fc4288e8496a99eb318875e1aaebac51af8b2fca80b232798693d93cc27237',
}
PARENTS = {
    'extract_stabilization_job_v6.py': '5f97f0d6c56190dad10ffee18a2c2d313df9daeb400ab45a5c41d729d7b92ee8',
    'extract_saved_stabilization_job_v2.py': '5079476887b4b7fe04c490b0bde9a5dd885193ef5b4168230307ac599751411a',
}
UI_RESERVATION = 256*1024**2
HOUR_RESERVATION = 2306682336
WAV_SHA = '9a83534025736c2f057f20068f3c0584b45770815289a7842a501fcae52b65c8'
PCM_SHA = '0f13e54972e4140f5797b996bdeb48d802acd4dcbb9407065d46190bda887e97'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def read(path, limit):
    if not path.is_relative_to(Q) and path.parent not in (HERE, S):
        raise ValueError('Owned private/public source input required')
    before = path.lstat()
    if (path.resolve(strict=True) != path or path.is_symlink()
            or any(parent.is_symlink() for parent in path.parents)
            or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit):
        raise ValueError('Bounded canonical single-link ordinary input required')
    raw = path.read_bytes()
    if identity(before) != identity(path.stat()) or len(raw) != before.st_size:
        raise ValueError('Input changed')
    return raw


def bootstrap(label):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    handle = kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(handle, 16384):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root = Q/'audit-preparation'/('core-job31-'+label+'-'+uuid.uuid4().hex)
    root.mkdir(exist_ok=False)
    owner = dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
        affinity_mask=16384, creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/1e7)
    raw = encoded(owner)
    with (root/'REGISTERED_OWNER.json').open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short early-owner write')
        stream.flush()
        os.fsync(stream.fileno())
    if read(root/'REGISTERED_OWNER.json', 4096) != raw:
        raise OSError('Early-owner readback differs')
    return root, owner, len(raw)


def validate_job(result, args):
    job = result.get('action_result')
    if (type(job) is not dict or result.get('boot_id') != args.boot_id
            or result.get('utility_pid_absent_after_ssh') is not True):
        raise ValueError('Actual returned JOB/current-boot dispatch utility closure required')
    unit = 'jp-v29-'+args.label+'.service'
    group = '/user.slice/user-1000.slice/user@1000.service/app.slice/'+unit
    output = NATIVE_TESTS+'/'+args.label
    owner, properties = job.get('owner'), job.get('properties')
    if (job.get('schema') != 'just-peachy.native-component-job.v1'
            or job.get('boot_id') != args.boot_id or job.get('package_manifest_sha256') != args.manifest_sha256
            or job.get('output_root') != output or job.get('unit') != unit
            or job.get('control_group') != group
            or type(owner) is not dict or set(owner) != {'pid', 'start_ticks', 'boot_id'}
            or owner.get('boot_id') != args.boot_id
            or any(type(owner.get(key)) is not int or owner[key] <= 0 for key in ('pid', 'start_ticks'))
            or re.fullmatch('[0-9a-f]{32}', job.get('invocation_id', '')) is None
            or type(properties) is not dict or properties.get('ActiveState') != 'active'
            or properties.get('ControlGroup') != group
            or properties.get('InvocationID') != job['invocation_id']
            or properties.get('MainPID') != str(owner['pid'])):
        raise ValueError('Exact actual job owner/unit/invocation/cgroup/properties differ')
    clocks = [job.get(key) for key in ('issued_unix', 'deadline_unix')]
    if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in clocks):
        raise ValueError('Actual finite issued/deadline clocks required')
    lifetime = clocks[1]-clocks[0]
    if args.kind in HELPERS:
        if (job.get('helper_source_sha256') != HELPERS[args.kind]
                or type(job.get('maximum_output_bytes')) is not int
                or job['maximum_output_bytes'] != UI_RESERVATION
                or job.get('native_check_path') != output+'/NATIVE_CHECK.json'
                or not 0 < lifetime <= 600):
            raise ValueError('Exact actual V2 live/saved helper and256MiB/600s JOB required')
        # The actual V2 JOB does not carry a PC-copy field. Its pinned launch
        # implementation admits exactly256MiB for each side. Never add it.
        if ('independent_pc_copy_bytes' in job and
                (type(job['independent_pc_copy_bytes']) is not int or job['independent_pc_copy_bytes'] != UI_RESERVATION)):
            raise ValueError('Returned V2 copy reservation differs')
    else:
        source = job.get('original_source_verified')
        if (job.get('workflow') != 'continuous-full-application-repeated-wav'
                or type(job.get('duration_seconds')) is not int or job['duration_seconds'] != 3600
                or type(job.get('repeat_input_seconds')) is not int or job['repeat_input_seconds'] != 3600
                or type(job.get('maximum_output_files')) is not int or job['maximum_output_files'] != 2048
                or type(job.get('maximum_output_bytes')) is not int or job['maximum_output_bytes'] != HOUR_RESERVATION
                or type(job.get('independent_pc_copy_bytes')) is not int or job['independent_pc_copy_bytes'] != HOUR_RESERVATION
                or not 0 < lifetime <= 4725
                or job.get('endurance_scope') != 'One continuous wall-paced headless application session using repeated retained speech'
                or any(job.get(key) is not False for key in ('natural_conversation', 'gui_endurance', 'quality_evaluated'))
                or type(source) is not dict
                or source.get('source_session_id') != 'c24b685b2bd34d6bb04172965d712c0f'
                or type(source.get('frames')) is not int or source['frames'] != 966400
                or type(source.get('seconds')) not in (int, float) or source['seconds'] != 60.4
                or source.get('input_sha256') != WAV_SHA or source.get('source_pcm_sha256') != PCM_SHA
                or source.get('lossless_pcm_join') is not True
                or source.get('retained_pcm16_representation') is not True or source.get('reencoded') is not False):
            raise ValueError('Exact actual continuous c24 hour/full-copy reservation/source evidence required')
    return job, dict(native_output_bytes=job['maximum_output_bytes'],
        independent_pc_copy_bytes=UI_RESERVATION if args.kind in HELPERS else job['independent_pc_copy_bytes'],
        pc_copy_field_carried_by_job='independent_pc_copy_bytes' in job,
        issued_to_deadline_seconds=lifetime, maximum_job_lifetime_seconds=600 if args.kind in HELPERS else 4725)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--boot-id', required=True)
    parser.add_argument('--kind', choices=('live', 'saved', 'hour'), required=True)
    args = parser.parse_args()
    pattern = r'full-app-hour-[0-9]+' if args.kind == 'hour' else r'classic-ui-check-[0-9]+'
    if (re.fullmatch(pattern, args.label) is None or args.manifest_sha256 != PIN or args.boot_id != BOOT
            or str(uuid.UUID(args.boot_id)) != args.boot_id):
        raise ValueError('Exact actual31 pin/current boot and kind-compatible native label required')
    root, host_owner, used = bootstrap(args.label)  # Before all project input reads.
    began = time.monotonic()
    def write(path, raw):
        nonlocal used
        if used+len(raw) > 1048576 or time.monotonic()-began > 600:
            raise ValueError('Existing1MiB/600s metadata extraction scope')
        for drive, floor in (('C:/', 50*1024**3), ('G:/', 75*1024**3)):
            if shutil.disk_usage(drive).free < floor+1048576:
                raise OSError('Existing host physical storage floor')
        with path.open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Short extraction write')
            stream.flush()
            os.fsync(stream.fileno())
        used += len(raw)
        if read(path, 1048576) != raw:
            raise ValueError('Independent extraction readback differs')
    def triple(name, raw):
        for suffix in ('', '.backup', '.restore'):
            write(root/(name+suffix), raw)
    write(root/'HOST_SCOPE.json', encoded(dict(maximum_bytes=1048576, maximum_seconds=600,
        native_action=False, models_started=False, database_opened=False)))
    inputs = {}
    for path in (Path(__file__), HERE/'README_EXTRACT_CORE_JOB31.md', *(S/name for name in PARENTS)):
        raw = read(path, 65536)
        if path.parent == S and sha(raw) != PARENTS[path.name]:
            raise ValueError('Exact frozen extraction parent source differs')
        inputs[str(path)] = raw
        triple('SOURCE_'+path.name, raw)
    raw = read(args.result, 262144)
    result = strict(raw)
    job, reservation = validate_job(result, args)
    job_raw = encoded(job)
    if strict(job_raw) != job:
        raise ValueError('Serialized JOB changed returned fields')
    triple('DISPATCH_RESULT.json', raw)
    triple('JOB.json', job_raw)
    output = Q/(args.label+'-JOB.json')
    # CreateNew; an existing job/label is never overwritten or assigned a new
    # PID, invocation, source clock, reservation or deadline.
    write(output, job_raw)
    for suffix in ('.backup', '.restore'):
        write(Path(str(output)+suffix), job_raw)
    if read(args.result, 262144) != raw or any(read(path, 65536) != body for path, body in
            ((Path(name), body) for name, body in inputs.items())):
        raise ValueError('Actual dispatch result or extraction source changed')
    receipt = dict(status='ACTUAL_BUILD31_JOB_EXTRACTED', root=str(root), job=str(output), kind=args.kind,
        job_sha256=sha(job_raw), dispatch_result=str(args.result), dispatch_result_sha256=sha(raw),
        package_manifest_sha256=args.manifest_sha256, boot_id=args.boot_id, label=args.label,
        owner=job['owner'], invocation_id=job['invocation_id'], unit=job['unit'], control_group=job['control_group'],
        output_root=job['output_root'], reservation_evidence=reservation, host_owner=host_owner,
        returned_job_fields_unchanged=True, independent_backup_restores=True,
        native_action=False, functional_success_not_claimed=True, quality_evaluated=False)
    write(root/'RESULT.json', encoded(receipt))
    write(root/'SOURCE_CLOSED.json', encoded(dict(scope_closed=True, closed_unix=time.time(),
        prepared_bytes=used, native_action=False, sources_unchanged=True, dispatch_result_unchanged=True,
        source_sha256={name: sha(body) for name, body in inputs.items()}, job_sha256=sha(job_raw))))
    print(encoded(receipt).decode())


if __name__ == '__main__':
    main()
