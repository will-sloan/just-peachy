"""Exact closed normal02 numeric inspection; README_NORMAL02_CLOSED.md."""
# This runs only inside the reviewed guarded native metadata dispatcher.
import os
import resource
import signal
import sys
os.sched_setaffinity(0, {3})
for _kind, _ceiling in ((resource.RLIMIT_AS, 128*1024**2),
        (resource.RLIMIT_STACK, 1024**2), (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_CORE, 0)):
    _soft, _hard = resource.getrlimit(_kind)
    _limit = _ceiling if _hard == resource.RLIM_INFINITY else min(_ceiling, _hard)
    resource.setrlimit(_kind, (_limit, _limit))
signal.alarm(20)

import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import time

ROOT = Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
PACKAGE = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-35')
PIN = '5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f'
BOOT = 'e60e67c2-f3f5-4b8b-8eab-2613df2de37e'
LAUNCH_ID = '1c846cf0acba464485dc5222a6158529'
SESSION_ID = '2013dbd12ca74e979d9b809c41e3a90f'
APP = dict(pid=145677, start_ticks=3512160, boot_id=BOOT)
WORKER = dict(pid=145686, start_ticks=3512244, boot_id=BOOT)
UNIT = 'jp-v29-51710ec90cfc4684a7385f42933fd29e.service'
MAXIMUM = 262144

def identity(pid):
    try:
        text = Path('/proc', str(pid), 'stat').read_text()
    except FileNotFoundError:
        return None
    return dict(pid=pid, start_ticks=int(text.rsplit(')', 1)[1].split()[19]), boot_id=BOOT)

# Registration is emitted to stderr before any project-data read. The guarded
# dispatcher separately preserves its exact native utility owner and closure.
INSPECTOR_OWNER = identity(os.getpid())
os.write(2, (json.dumps(dict(schema='just-peachy.native-readonly-owner.v1',
    owner=INSPECTOR_OWNER, cpu=3, address_space=list(resource.getrlimit(resource.RLIMIT_AS)),
    stack=list(resource.getrlimit(resource.RLIMIT_STACK)), file_size=list(resource.getrlimit(resource.RLIMIT_FSIZE)),
    wall_seconds=20), sort_keys=True)+'\n').encode())

def strict(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('Duplicate diagnostic field')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite diagnostic')))

def snapshot(path):
    info = path.lstat()
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)

def read(path, maximum=MAXIMUM):
    before = snapshot(path)
    if (path.resolve(strict=True) != path or not stat.S_ISREG(before[2])
            or before[3] != 1 or not 0 <= before[4] <= maximum
            or any(p.is_symlink() for p in path.parents)):
        raise ValueError('Exact canonical bounded ordinary diagnostic required')
    with path.open('rb') as stream: raw = stream.read(maximum+1)
    if len(raw) != before[4] or snapshot(path) != before:
        raise ValueError('Closed diagnostic changed during read')
    return raw

def summarized(value, depth=0):
    # Never return recognized text, word spans, people, vectors or whole logs.
    if depth > 5: return None
    if value is None or type(value) in (bool, int, float): return value
    if type(value) is str: return value[:768]
    if type(value) is list: return [summarized(v, depth+1) for v in value[:16]]
    if type(value) is not dict: raise ValueError('Unexpected diagnostic type')
    permitted = {'result','unit','status','state','session_id','owner','worker','manager','child_owner','pid',
        'start_ticks','boot_id','failure','error','cleanup_error','returncode','exit_code',
        'logical_cleanup_complete','physical_process_closed','post_stop_choice_pending',
        'stdout_reader_joined','output_error','receipt_errors','nested_source','closed','reaped',
        'source_facts','source_start_observed','physical_start_packet_observed','processed_samples',
        'raw_samples','sent_samples','captured_samples','captured_seconds','stream_closed',
        'lease_released','integrity','ok','policy','manual_stop','max_backlog_seconds',
        'maximum_session_seconds','max_drain_seconds','address_space','stack','selection',
        'asr','diarizer','embedding','input_source','model','mode','reason','operation',
        'sqlite_errorcode','sqlite_errorname','failure_diagnostics','registered_owner',
        'source_close','stop_requested','runtime_max_seconds','lifetime_policy','backend',
        'source_samples','backlog_seconds','speaker_lag_seconds','asr_lag_seconds',
        'speaker_cursor_seconds','speaker_analyzed_through_seconds','asr_cursor_seconds',
        'dropped_audio','rss','virtual_bytes','available_ram','source_returncode','source_reaped'}
    return {key:summarized(item, depth+1) for key,item in value.items() if key in permitted}

def metadata(path):
    if not path.exists(): return dict(path=str(path), exists=False)
    raw = read(path)
    return dict(path=str(path), exists=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                facts=summarized(strict(raw)))

def properties(unit):
    names = ('ActiveState','SubState','MainPID','InvocationID','ControlGroup','RuntimeMaxUSec')
    output = subprocess.run(['systemctl','--user','show',unit,'--property='+','.join(names)],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=3)
    if len(output.stdout)+len(output.stderr) > 16384: raise ValueError('Bounded unit status exceeded')
    return dict(returncode=output.returncode,
        values=dict(line.split('=',1) for line in output.stdout.decode().splitlines() if '=' in line))

def inspect():
    expected = {'schema','package_manifest_sha256','boot_id','launch_id','session_id','expires_unix'}
    if (type(PAYLOAD) is not dict or set(PAYLOAD) != expected
            or PAYLOAD['schema'] != 'just-peachy.normal02-closed-inspection.v1'
            or PAYLOAD['package_manifest_sha256'] != PIN or PAYLOAD['boot_id'] != BOOT
            or PAYLOAD['launch_id'] != LAUNCH_ID or PAYLOAD['session_id'] != SESSION_ID
            or type(PAYLOAD['expires_unix']) not in (int,float)
            or not time.time() < PAYLOAD['expires_unix'] <= time.time()+600):
        raise ValueError('Fresh exact closed normal02 payload required')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if (boot != BOOT or BASELINE['boot_id'] != BOOT or BASELINE['current_project_processes']
            or BASELINE['active_recorded_owners'] or BASELINE['live_manager_owners']):
        raise ValueError('Current boot and closed project/source ownership required')
    if identity(APP['pid']) == APP or identity(WORKER['pid']) == WORKER:
        raise ValueError('Exact normal02 app or worker is still alive')
    manifest = read(PACKAGE/'PACKAGE_MANIFEST.json')
    if hashlib.sha256(manifest).hexdigest() != PIN: raise ValueError('Actual activated package differs')
    launch = ROOT/'launches'/LAUNCH_ID
    session = ROOT/'recordings/sessions'/SESSION_ID
    registered = strict(read(launch/'worker/REGISTERED_OWNER.json'))
    indexed = strict(read(launch/'worker/SESSION.json'))
    if registered != WORKER or indexed != {'session_id':SESSION_ID,'worker':WORKER}:
        raise ValueError('Actual closed worker/session binding differs')
    result = dict(schema='just-peachy.normal02-closed-inspection.v1', inspector_owner=INSPECTOR_OWNER,
        boot_id=boot, package_manifest_sha256=PIN, launch_id=LAUNCH_ID, session_id=SESSION_ID,
        runtime_mutated=False, capture_started=False, models_started=False,
        audio_or_transcript_read=False, current_unit=properties(UNIT), rows={})
    for relative in ('REQUEST.json','CHILD_LAUNCH.json','HOST_CLOSURE.json','START_FAILURE.json',
            'worker/ENVELOPE.json','worker/SESSION.json','worker/RESULT.json','worker/EXIT.json'):
        result['rows'][relative] = metadata(launch/relative)
    for relative in ('REGISTERED_OWNER.json','SOURCE_CLOSE.json'):
        result['rows']['source/'+relative] = metadata(session/'work/source'/relative)
    source_path = session/'work/source/REGISTERED_OWNER.json'
    if source_path.exists():
        registration = strict(read(source_path))
        expected_keys = {'schema','owner','cpu','address_space_bytes','stack_bytes','project_imports_started'}
        if (type(registration) is not dict or set(registration) != expected_keys
                or registration['schema'] != 'just-peachy.source-owner.v1'
                or type(registration['cpu']) is not int or registration['cpu'] != 3
                or type(registration['address_space_bytes']) is not int or registration['address_space_bytes'] != 256*1024**2
                or type(registration['stack_bytes']) is not int or registration['stack_bytes'] != 1024**2
                or registration['project_imports_started'] is not False):
            raise ValueError('Exact installed source envelope differs')
        source = registration['owner']
        if (type(source) is not dict or set(source) != {'pid','start_ticks','boot_id'}
                or type(source['pid']) is not int or source['pid'] < 1
                or type(source['start_ticks']) is not int or source['start_ticks'] < 1
                or source['boot_id'] != BOOT):
            raise ValueError('Exact source registration differs')
        result['source_owner'] = source
        result['source_exact_owner_gone'] = identity(source['pid']) != source
        if not result['source_exact_owner_gone']: raise ValueError('Exact source remains alive')
    log = launch/'WORKER.log'
    if log.exists():
        raw = read(log, 512*1024)
        markers = (b'AEC_MIC_ARRAY_TYPE255',b'Traceback',b'MemoryError',b'OperationalError',
            b'CapacityError',b'session initialization',b'BrokenPipeError',b'TimeoutError',b'Ready',b'listening')
        result['worker_log'] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
            diagnostic_marker_counts={key.decode():raw.count(key) for key in markers},
            exception_class_lines=[line.decode('ascii','replace').split(':',1)[0][:80]
                for line in raw[-8192:].splitlines() if re.match(rb'^(?:[A-Za-z]+Error|[A-Za-z]+Exception):',line)][:12],
            private_log_content_returned=False)
    import sqlite3
    path = ROOT/'recordings/history.sqlite3'
    before = snapshot(path)
    if path.resolve(strict=True) != path or not stat.S_ISREG(before[2]) or before[3] != 1:
        raise ValueError('Canonical ordinary history database required')
    db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=.2)
    deadline = time.monotonic()+3
    try:
        db.execute('PRAGMA query_only=ON'); db.execute('PRAGMA trusted_schema=OFF')
        db.execute('PRAGMA cache_size=-256')
        db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000); db.execute('BEGIN')
        row = db.execute('SELECT status,processed_samples,raw_samples FROM sessions WHERE id=?',(SESSION_ID,)).fetchone()
        result['database'] = dict(session=None if row is None else dict(status=row[0],processed_samples=row[1],raw_samples=row[2]),
            counts={name:db.execute('SELECT COUNT(*) FROM '+name+' WHERE session_id=?',(SESSION_ID,)).fetchone()[0]
                for name in ('segments','captions','events','caption_projections')},
            processed_segments=db.execute("SELECT COUNT(*),COALESCE(SUM(samples),0),COALESCE(MAX(start_sample+samples),0) FROM segments WHERE session_id=? AND kind='processed'",(SESSION_ID,)).fetchone())
    finally: db.rollback(); db.close()
    if snapshot(path) != before: raise ValueError('Closed database changed during inspection')
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':',1)
        if key in ('MemAvailable','MemFree','SwapFree','SwapTotal'): memory[key] = int(value.split()[0])*1024
    space = os.statvfs(ROOT)
    result['current_resources'] = dict(memory_bytes=memory, available_disk_bytes=space.f_bavail*space.f_frsize,
        free_inodes=space.f_favail)
    result['current_lease_paths'] = {str(path):dict(exists=os.path.lexists(path),
        existence_is_not_lock_ownership=True) for path in
        (ROOT.parent/'xvf-hardware.lock',ROOT/'launcher.lock')}
    result['current_recorded_lease_owners'] = dict(active_recorded_owners=BASELINE['active_recorded_owners'],
        live_manager_owners=BASELINE['live_manager_owners'])
    if len(json.dumps(result,allow_nan=False).encode()) > 65536: raise ValueError('Compact numeric diagnostic exceeded')
    return result

RESULT = inspect()
