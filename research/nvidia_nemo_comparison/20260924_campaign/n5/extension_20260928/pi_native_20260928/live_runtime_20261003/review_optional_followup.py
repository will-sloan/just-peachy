"""Closed, numeric-only optional review. See README_OPTIONAL_FOLLOWUP_REVIEW.md."""
import psutil
psutil.Process().cpu_affinity([14])
import os
import json
import uuid
from pathlib import Path

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
OUTPUT = PRIVATE/('presets-preparation-optional-followup-review-'+uuid.uuid4().hex)
OUTPUT.mkdir()
with (OUTPUT/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=os.getpid(), create_time=psutil.Process().create_time(), affinity=[14]), stream)
    stream.flush(); os.fsync(stream.fileno())

import argparse
import hashlib
import importlib.util
import sys
from collections import Counter

READER_SHA = '5a104a19aeda0ef221cacda4f34732d62c49016ba41e82c9dc6e094a8f28248f'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--monitor', required=True, type=Path)
    parser.add_argument('--expected-payload', required=True, type=Path)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    source = Path(__file__).with_name('review_research_comparison.py')
    if hashlib.sha256(source.read_bytes()).hexdigest() != READER_SHA:
        raise ValueError('Pinned bounded mirror reader differs')
    spec = importlib.util.spec_from_file_location('pinned_optional_review', source)
    r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
    root, names, mirror = r.verify_mirror(args.monitor)
    expected = r.read_json(args.expected_payload, 256*1024)
    worker = r.read_json(root/'worker/RESULT.json'); result = worker.get('result', {})
    execution = r.read_json(root/'worker/OPTIONAL_QUALIFICATION_EXECUTION.json')
    permit = r.read_json(root/'PERMIT.json')
    r.require(worker.get('failure') is None and worker.get('logical_cleanup_complete') is True and
              result.get('status') == 'FUNCTIONAL_SESSION_COMPLETED', 'Primary completion missing')
    r.require(result['selection'] == expected['selection'] == execution['selection'] and
              result['source_policy'] == expected['policy'] == execution['policy'], 'Exact selection/policy differs')
    r.require(execution['package_manifest_sha256'] == expected['package_manifest_sha256'] and
              execution['actual_binding_sha256'] == expected['binding_sha256'], 'Actual executed package differs')
    session = root/'recordings/sessions'/worker['session_id']
    manifest = r.read_json(session/'session.json')
    count = result['source_samples']; raw_count = manifest['raw_samples']
    r.require(count == manifest['processed_samples'] == 4800000 and raw_count == count,
              'Exact live300 primary/raw source count required')
    child_path = session/'work/optional-refiner/CLOSURE.json'
    recorded_child = r.read_json(child_path)
    child = result['optional_refiner_closure']
    # The supervisor writes CLOSURE inside its thread; the parent subsequently
    # joins it and adds the authoritative join flag to the final worker result.
    comparable = dict(child); comparable.pop('supervisor_thread_closed', None)
    recorded_comparable = dict(recorded_child); recorded_comparable.pop('supervisor_thread_closed', None)
    r.require(comparable == recorded_comparable and child['child_dead'] is True and
              child['supervisor_thread_closed'] is True and child['primary_audio_dropped'] is False,
              'Authoritative child closure differs or primary audio was dropped')
    source_close = r.read_json(session/'work/source/SOURCE_CLOSE.json')
    r.require(source_close['stream_closed'] is True and source_close['lease_released'] is True and
              source_close['sent_samples'] == count and source_close['status']['dropped_frames'] == 0 and
              source_close['integrity']['restoration_ok'] is True, 'Live source/route closure differs')
    db = r.open_database(root/'recordings/history.sqlite3')
    try:
        streams = {}
        for kind, width in (('processed', 4), ('raw', 16)):
            digest = hashlib.sha256(); cursor = parts = 0
            for row in db.execute('SELECT * FROM segments WHERE session_id=? AND kind=? ORDER BY idx',
                                  (worker['session_id'], kind)):
                r.require(parts < 256 and row['start_sample'] == cursor and row['samples'] > 0,
                          'Source interval gap or segment capacity')
                r.require(Path(row['data_name']).name == row['data_name'], 'Source member must be local')
                path = r.real(session/row['data_name'])
                r.require(path.stat().st_size == row['samples']*width, 'Exact source byte extent differs')
                with path.open('rb') as stream:
                    while block := stream.read(r.MIB): r.budget(); digest.update(block)
                cursor += row['samples']; parts += 1
            r.require(cursor == count, 'Source stream incomplete')
            streams[kind] = dict(samples=cursor, bytes=cursor*width, segments=parts, sha256=digest.hexdigest())
        health = []
        for row in db.execute("SELECT * FROM events WHERE session_id=? AND event_type='health' ORDER BY seq", (worker['session_id'],)):
            r.require(len(health) < 4096, 'Health row bound')
            health.append(r._unpack_event(dict(row)))
    finally:
        db.close()
    r.require(streams['raw']['sha256'] == source_close['raw_capture']['sha256'], 'Physical raw stream hash differs')
    child_result = child.get('child_result')
    if child['complete_eof']:
        r.require(child['processed_samples'] == child['sent_samples'] == count and child['returned_frames'] == count//160+1 and
                  child['process_returncode'] == 0 and child_result['model_closed'] is True and
                  child_result['delivered_f32_sha256'] == streams['processed']['sha256'], 'Complete child EOF/source hash differs')
    outer = list(r.lines(root/'WHOLE_UNIT_MEMORY.jsonl', maximum_bytes=16*r.MIB, maximum_records=1024))
    combined = list(r.lines(session/'work/optional-refiner/COMBINED_RESOURCES.jsonl', maximum_bytes=2*r.MIB, maximum_records=1024))
    r.require(len(combined) >= 2 and outer, 'Actual whole-unit resource samples required')
    boot = mirror['closure']['owner']['boot_id']; owner = child['child_owner']
    child_samples = [p for sample in combined for p in sample['owners'] if
                     (p['pid'],p['start_ticks'],p['boot_id']) == (owner['pid'],owner['start_ticks'],boot)]
    r.require(child_samples, 'Actual child residency samples required')
    native_dir = r.only(list((session/'work/sessions').glob('*/session_summary.json')), 'One native event directory required').parent
    counts = Counter(); optional_events = optional_history = 0
    for event in r.iter_events(native_dir/'events.jsonl', maximum_bytes=r.MAX_BYTES, maximum_records=r.MAX_EVENTS):
        r.budget(); kind = event.get('event_type'); counts[kind] += 1; payload = event.get('payload', {})
        if kind == 'transcript_label_revision' and str(payload.get('event_id','')).startswith('optional-d1:'):
            optional_events += 1
        if kind == 's6d_display':
            for word in payload.get('word_spans', []):
                optional_history += sum(str(h.get('event_id','')).startswith('optional-d1:') for h in word.get('speaker_history', []))
    max_value = lambda key: max((h[key] for h in health if r.finite(h.get(key))), default=None)
    timings = [(s['at_monotonic'],s['cgroup_cpu_seconds']) for s in combined]
    r.require(all(b[0] > a[0] and b[1] >= a[1] for a,b in zip(timings,timings[1:])), 'Cgroup trace clock regressed')
    resources = dict(samples=len(combined), outer_samples=len(outer),
        peak_combined_rss_bytes=max([s['whole_unit_rss_bytes'] for s in combined]+[s['combined_rss_bytes'] for s in outer]),
        peak_combined_pss_bytes=max([s['whole_unit_pss_bytes'] for s in combined]+[s['combined_pss_bytes'] for s in outer]),
        minimum_available_ram_bytes=min([s['available_ram_bytes'] for s in combined]+[s['available_ram'] for s in outer]),
        total_ram_bytes=combined[0]['physical_ram_bytes'], peak_child_rss_bytes=max(p['rss_bytes'] for p in child_samples),
        peak_child_virtual_bytes=max(p['virtual_bytes'] for p in child_samples),
        maximum_owned_swap_bytes=max(s['whole_unit_swap_bytes'] for s in combined),
        maximum_temperature_millicelsius=max((s['temperature_millicelsius'] for s in outer if s.get('temperature_millicelsius') is not None), default=None),
        cgroup_cpu_interval_seconds=timings[-1][1]-timings[0][1], cgroup_elapsed_interval_seconds=timings[-1][0]-timings[0][0],
        cgroup_interval_monotonic=[timings[0][0],timings[-1][0]],
        scope='Whole owned cgroup samples; maxima can miss peaks. CPU delta uses this explicit interval, not duplicate audio denominators or a full-lifetime claim.')
    report = dict(schema='just-peachy.optional-live-followup-review.v2', reviewed=False, production_eligible=False,
        mirror=mirror, selection=result['selection'], policy=result['source_policy'], execution=execution,
        worker_result_sha256=r.checksum(root/'worker/RESULT.json'), permit_sha256=r.checksum(root/'PERMIT.json'), pins=permit['pins'],
        child=child, child_closure_sha256=r.checksum(child_path), resources=resources, streams=streams,
        primary_paced_eof_wall_seconds=result['combined_paced_eof_wall_seconds'], health_samples=len(health),
        maximum_primary_backlog_seconds=max_value('backlog_seconds'), maximum_observed_primary_drops=max_value('dropped_audio'),
        maximum_observed_label_lag_seconds=max((h.get('refinement',{}).get('label_backlog_seconds',0) or 0 for h in health), default=None),
        event_counts=dict(counts), optional_label_revision_events=optional_events, optional_history_observations=optional_history,
        limits=permit['limits'], source_close_sha256=r.checksum(session/'work/source/SOURCE_CLOSE.json'),
        reader_sha256=READER_SHA, reviewer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        native_executed_by_reviewer=False, quality_qualified=False,
        limitations=['Primary transcript_label_revision counts are not optional correction proof.',
                    'No DER, enrolled identity accuracy, or improvement claim. Explicit review is required before a separate normal receipt.'])
    raw = r.encoded(report); r.require(len(raw) <= 128*1024, 'Review report capacity exceeded')
    path = OUTPUT/'REVIEW.json'; path.write_bytes(raw)
    print(json.dumps(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),child_eof=child['complete_eof'],
        primary_samples=count,child_samples=child['processed_samples'],child_frames=child['returned_frames'],
        optional_revision_events=optional_events,optional_history_observations=optional_history,resources=resources)))


if __name__ == '__main__':
    main()
