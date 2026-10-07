"""Closed-copy numeric backlog analysis; README_HOUR01_LANES.md.

No models/native commands; CPU14 owner precedes project and evidence reads.
"""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import ast
import collections
import ctypes
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import uuid
import zlib

PIN = 'b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569'
MAX = 3 * 1024**3


def save(path, value):
    data = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    if len(data) > 2 * 1024**2:
        raise ValueError('Numeric report exceeds bounded working set')
    with path.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    if path.read_bytes() != data:
        raise OSError('Report independent readback differs')


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def numeric(value):
    if type(value) is dict:
        return {key: numeric(item) for key, item in value.items()
                if finite(item) or type(item) is dict}
    return value if finite(value) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mirror', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root / ('hour01-lanes-' + uuid.uuid4().hex)
    output.mkdir()
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    times = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(), *(ctypes.byref(v) for v in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    save(output / 'REGISTERED_OWNER.json', dict(schema='just-peachy.host-registered-owner.v1',
        pid=os.getpid(), cpu=14, affinity_mask=16384, creation_filetime=times[0].value,
        create_time=(times[0].value - 116444736000000000) / 10000000))
    started = time.monotonic()
    sys.dont_write_bytecode = True
    for name in ('review_hour01_lanes.py', 'README_HOUR01_LANES.md'):
        source = Path(__file__).with_name(name)
        data = source.read_bytes()
        for suffix in ('.backup', '.restore'):
            with (output / (name + suffix)).open('xb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
        if sha(source) != sha(output / (name + '.restore')):
            raise OSError('Independent source restore differs')
    package = args.package.resolve(strict=True)
    if args.package.is_symlink() or package != args.package or sha(package / 'PACKAGE_MANIFEST.json') != PIN:
        raise ValueError('Exact ordinary frozen build30 package required')
    manifest = json.loads((package / 'PACKAGE_MANIFEST.json').read_bytes())
    inventory = {row['path']: row for row in manifest['files']}
    for relative, row in inventory.items():
        path = package / relative
        info = path.lstat()
        if (path.is_symlink() or path.resolve() != path or not path.is_file()
                or info.st_nlink != 1 or info.st_size != row['bytes'] or sha(path) != row['sha256']):
            raise ValueError('Frozen package member differs')
    # Only already inventoried pure storage/event decoder modules are loaded.
    sys.path.insert(0, str(package))
    events_module = importlib.import_module('event_compaction')
    for name in ('event_compaction', 'runtime_support'):
        module = sys.modules[name]
        if Path(module.__file__) != package / (name + '.py'):
            raise ValueError('Pure decoder import origin differs')
    tree = ast.parse((package / 'storage.py').read_bytes())
    decoder = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_unpack_event']
    if len(decoder) != 1:
        raise ValueError('Exact event decoder required')
    space = dict(json=json, hashlib=hashlib, re=re, zlib=zlib, StorageError=ValueError)
    exec(compile(ast.Module(body=decoder, type_ignores=[]), '<pinned-read-only-event-decoder>', 'exec'), space)
    mirror = args.mirror.resolve(strict=True)
    transport = json.loads((mirror / 'RESULT.json').read_bytes())
    complete = json.loads((mirror / 'MIRROR_COMPLETE.json').read_bytes())
    rows = json.loads((mirror / 'MIRROR_MANIFEST.json').read_bytes())
    job = transport['job']; closure = complete['closure']
    if (transport.get('status') != 'FULL_CLOSED_OUTPUT_MIRRORED' or complete.get('kind') != 'COMPLETE'
            or job.get('unit') != 'jp-v29-full-app-hour-01.service' or job.get('package_manifest_sha256') != PIN
            or not all(closure.get(k) is True for k in ('closed', 'exact_owner_gone', 'cgroup_empty'))
            or any(closure.get(k) != job[k] for k in ('owner', 'unit', 'invocation_id', 'control_group'))
            or len(rows) > 2048 or complete['bytes'] > MAX
            or hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() != complete['manifest_sha256']):
        raise ValueError('Exact full closed hour01 mirror required')
    root = mirror / 'closed-output'; members = {row['path']: row for row in rows}; checked = {}
    def member(relative):
        row = members[relative]; path = root / relative; info = path.lstat()
        if (path.is_symlink() or path.resolve() != path or not path.is_file() or info.st_nlink != 1
                or info.st_size != row['identity']['bytes'] or sha(path) != row['sha256']):
            raise ValueError('Selected closed-copy member differs')
        checked[relative] = row['sha256']
        return path
    database = member('data/recordings/history.sqlite3')
    for suffix in ('-journal', '-wal', '-shm'):
        sidecar = database.with_name(database.name + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise ValueError('Immutable review cannot ignore a SQLite sidecar')
    health = []
    with sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON'); db.execute('PRAGMA cache_size=-2048')
        deadline = time.monotonic() + 30
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
        if [row[0] for row in db.execute('PRAGMA quick_check')] != ['ok']:
            raise ValueError('Closed database integrity failed')
        for row in db.execute("SELECT * FROM events WHERE event_type='health' ORDER BY seq"):
            if len(health) >= 6000:
                raise ValueError('Bounded health rows required')
            value = space['_unpack_event'](dict(row))
            health.append(dict(seq=row['seq'], created=row['created'], **{
                key: numeric(value.get(key)) for key in ('at_monotonic', 'elapsed', 'source_samples',
                    'backlog_seconds', 'cpu_seconds', 'rss', 'pss_bytes', 'available_ram',
                    'temperature_millicelsius', 'costs', 'diarizer_rolling')}))
    if not health:
        raise ValueError('Stored health evidence absent')
    maximum = max(health, key=lambda row: row['backlog_seconds'])
    event_indexes = [name for name in members if name.endswith('/events.jsonl.index.json')]
    if len(event_indexes) != 1:
        raise ValueError('One model-session event stream required')
    index_name = event_indexes[0]; base_name = index_name.removesuffix('.index.json')
    index = json.loads(member(index_name).read_bytes())
    for number in range(index['segment_count']):
        member(base_name + '.%06d' % number)
    member(base_name + '.compaction.json')
    selected = []; kind_counts = collections.Counter(); origin = None
    for event in events_module.iter_events(root / base_name, maximum_bytes=MAX, maximum_records=60000):
        kind = event.get('event_type', event.get('kind')); kind_counts[kind] += 1
        payload = event.get('payload', {})
        if kind == 'source_started':
            origin = payload.get('source_epoch_monotonic_sec', origin)
        if kind not in ('research_scheduler_watermark', 'n2_diarization_frames', 'research_embedding',
                        'failure', 'source_stopped', 'session_completed'):
            continue
        row = dict(kind=kind)
        for key in ('publication_monotonic_sec', 'publication_sequence', 'publication_source_cursor_sec',
                    'compute_finished_elapsed_sec', 'lower_bound_sec', 'lane_closed', 'frame_start',
                    'frame_step_sec', 'audio_received_sec', 'native_frame_end_sec', 'compute_sec',
                    'source_start_sec', 'source_end_sec', 'compute_ms', 'is_final'):
            value = payload.get(key)
            if finite(value) or type(value) is bool:
                row[key] = value
        if payload.get('lane') in ('asr', 'speaker'):
            row['lane'] = payload['lane']
        if kind == 'n2_diarization_frames':
            row['frame_count'] = len(payload.get('probabilities', []))
            row['analyzed_end_sec'] = min(payload['audio_received_sec'],
                (payload['frame_start'] + row['frame_count']) * payload['frame_step_sec'])
        selected.append(row)
    if not finite(origin) or not finite(maximum['at_monotonic']):
        raise ValueError('Source origin and failure-time health clock required')
    before = [row for row in selected if row.get('publication_monotonic_sec', math.inf) <= maximum['at_monotonic']]
    latest = {}
    for row in before:
        if row['kind'] == 'research_scheduler_watermark' and 'lower_bound_sec' in row:
            latest[row.get('lane', 'unknown')] = row
        elif row['kind'] == 'n2_diarization_frames':
            latest['latest_native_frames_published'] = row
    speaker = latest.get('speaker')
    if speaker:
        frames = [row for row in before if row['kind'] == 'n2_diarization_frames'
                  and row['publication_monotonic_sec'] <= speaker['publication_monotonic_sec']]
        latest['frames_before_last_completed_speaker_accept'] = frames[-1] if frames else None
    nearby = [row for row in health if abs(row['at_monotonic'] - maximum['at_monotonic']) <= 35]
    buckets = []
    for end in (30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360, 420, 480, 540):
        samples = [row for row in health if end-30 < row['elapsed'] <= end]
        if samples:
            first, last = samples[0], samples[-1]
            costs = {}
            for key in set(first['costs']) | set(last['costs']):
                a, b = first['costs'].get(key, {}), last['costs'].get(key, {})
                costs[key] = {name: b.get(name, 0)-a.get(name, 0) for name in ('seconds', 'samples', 'calls')}
            buckets.append(dict(end_elapsed=end, source_samples_delta=last['source_samples']-first['source_samples'],
                wall_delta=last['at_monotonic']-first['at_monotonic'], backlog_first=first['backlog_seconds'],
                backlog_last=last['backlog_seconds'], cost_delta=costs))
    trace_stats = {}
    trace_names = [name for name in members if re.search(r'/s7_clocks\.jsonl\.[0-9]{6}$', name)]
    for name in sorted(trace_names):
        with member(name).open('rb') as stream:
            for line in stream:
                if len(line) > 16384 or time.monotonic()-started > 180:
                    raise ValueError('Bounded trace record and finite host review required')
                row = json.loads(line); kind = row['kind']
                stats = trace_stats.setdefault(kind, dict(count=0, up_to_max_health=0,
                    durations_seconds={}, durations_up_to_max_seconds={}))
                stats['count'] += 1
                if row.get('monotonic_sec', math.inf) <= maximum['at_monotonic']:
                    stats['up_to_max_health'] += 1
                for stage in ('tracker', 'naming', 'caption_policy'):
                    start, finish = row.get(stage+'_start_monotonic_sec'), row.get(stage+'_finish_monotonic_sec')
                    if kind == 'policy_'+stage+'_finish' and finite(start) and finite(finish):
                        stats['durations_seconds'][stage] = stats['durations_seconds'].get(stage, 0.) + finish-start
                        if row.get('monotonic_sec', math.inf) <= maximum['at_monotonic']:
                            stats['durations_up_to_max_seconds'][stage] = stats['durations_up_to_max_seconds'].get(stage, 0.) + finish-start
    for relative, digest in checked.items():
        if sha(root / relative) != digest:
            raise ValueError('Selected evidence changed during read-only review')
    result = dict(schema='just-peachy.hour01-lane-review.v1', package_manifest_sha256=PIN,
        source_epoch_monotonic=origin, exact_max_health=maximum, health_35s_around_max=nearby,
        max_health_elapsed_from_source_epoch=maximum['at_monotonic']-origin,
        latest_numeric_lane_events_before_max=latest,
        numeric_engine_events_35s_around_max=[row for row in selected
            if abs(row.get('publication_monotonic_sec', math.inf)-maximum['at_monotonic']) <= 35],
        health_interval_deltas=buckets, engine_event_type_counts=dict(kind_counts), trace_costs=trace_stats,
        selected_member_sha256=checked, selected_sources_unchanged=True, immutable_read_only_database=True,
        no_models_native_commands_audio_text_vectors_output=True,
        limitations=['Persisted health omits individual ASR/speaker lag values.',
            'Watermarks/frame publications reconstruct lane progress; they are not invented missing telemetry.',
            'Trace cost stages are only measured stages; residual wall time is not isolated association CPU.'])
    save(output / 'REVIEW.json', result)
    save(output / 'SOURCE_CLOSED.json', dict(source_sha256=sha(Path(__file__)),
        readme_sha256=sha(Path(__file__).with_name('README_HOUR01_LANES.md')),
        independent_restore=True, selected_sources_unchanged=True, database_connection_closed=True))
    print(json.dumps(dict(output=str(output), maximum_health_backlog=maximum['backlog_seconds'],
        health_rows=len(health), selected_events=len(selected), sources_unchanged=True)))


if __name__ == '__main__':
    main()
