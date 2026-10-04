"""Read-only, transcript-free matched-run review. See README_RESEARCH_COMPARISON.md."""
import psutil
psutil.Process().cpu_affinity([14])
import os
import json
import uuid
from pathlib import Path

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
OUTPUT = PRIVATE / ('presets-preparation-research-comparison-' + uuid.uuid4().hex)
OUTPUT.mkdir()
with (OUTPUT/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=os.getpid(), create_time=psutil.Process().create_time(), affinity=[14]), stream)
    stream.flush(); os.fsync(stream.fileno())

# No project imports or input reads occur before the registered CPU14 owner.
import argparse
from collections import Counter
import hashlib
import math
import sqlite3
import stat
import sys
import time

sys.dont_write_bytecode = True
from runtime_support import strict, encoded
from storage import _unpack_event
from event_compaction import iter_events
from final_snapshot import iter_rows

MIB = 1024**2
MAX_BYTES = 256*MIB
MAX_FILES = 256
MAX_ROWS = 4096
MAX_EVENTS = 100000
START = time.monotonic()
CPU_START = sum(psutil.Process().cpu_times()[:2])
SOURCE_SHA = '0ee26e8aa6f815d8b202419aafb71ff5bc25093d193e95e972036f488c5040b8'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def budget():
    process = psutil.Process()
    require(time.monotonic()-START <= 180, 'Reviewer wall budget exceeded')
    require(sum(process.cpu_times()[:2])-CPU_START <= 120, 'Reviewer CPU budget exceeded')
    require(process.memory_info().rss <= 384*MIB, 'Reviewer resident budget exceeded')


def real(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        info = item.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 1024,
                'Symlink/reparse point not accepted')
    require(path.is_file(), 'Expected regular file')
    return path


def checksum(path, limit=MAX_BYTES):
    path = real(path); before = path.stat()
    require(before.st_size <= limit, 'File exceeds reader allocation')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(MIB):
            budget(); digest.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ino) ==
            (after.st_size, after.st_mtime_ns, after.st_ino), 'Input changed during review')
    return digest.hexdigest()


def read_json(path, limit=MIB):
    path = real(path)
    require(path.stat().st_size <= limit, 'JSON extent exceeds reader allocation')
    return strict(path.read_bytes())


def lines(path, maximum_bytes=MAX_BYTES, maximum_records=MAX_EVENTS):
    path = real(path); total = count = 0
    with path.open('rb') as stream:
        while raw := stream.readline(MIB+1):
            budget(); count += 1; total += len(raw)
            require(len(raw) <= MIB and raw.endswith(b'\n') and total <= maximum_bytes and count <= maximum_records,
                    'JSONL record/count/byte bound')
            yield strict(raw)


def only(paths, reason):
    require(len(paths) == 1, reason)
    return paths[0]


def verify_mirror(directory):
    directory = Path(directory).absolute()
    complete = read_json(directory/'MIRROR_COMPLETE.json')
    manifest = read_json(directory/'MIRROR_MANIFEST.json')
    closure = complete.get('closure', {}); exit_row = closure.get('job_exit', {})
    require(complete.get('kind') == 'COMPLETE' and complete.get('mirror_scope') == 'all_regular_output_files',
            'Complete regular-file mirror required')
    require(all(closure.get(key) is True for key in ('closed', 'cgroup_empty', 'exact_owner_gone')) and
            exit_row.get('natural_returncode') == 0 and exit_row.get('error') is None and
            exit_row.get('leases_released') is True and exit_row.get('output_budget_failure') is None,
            'Natural successful closure, empty cgroup and released leases required')
    require(checksum(directory/'MIRROR_MANIFEST.json') == complete['manifest_sha256'], 'Mirror manifest pin differs')
    require(type(manifest) is list and 0 < len(manifest) <= MAX_FILES and len(manifest) == complete['files'],
            'Mirror inventory extent differs')
    root = directory/'closed-output'; names = set(); total = 0
    for row in manifest:
        name = row['path']; parts = Path(name).parts
        require(type(name) is str and name and '\\' not in name and not Path(name).is_absolute() and
                '..' not in parts and ':' not in name and name not in names, 'Unsafe/duplicate mirror member')
        names.add(name); path = real(root/name); size = path.stat().st_size; total += size
        require(size == row['identity']['bytes'] and total <= MAX_BYTES, 'Mirror byte allocation differs')
        require(checksum(path) == row['sha256'], 'Mirror member hash differs')
    require(total == complete['bytes'], 'Full mirror byte total differs')
    observed = set()
    for folder, directories, files in os.walk(root, followlinks=False):
        budget()
        for name in directories:
            info = (Path(folder)/name).lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 1024,
                    'Mirror directory reparse point not accepted')
        for name in files:
            observed.add(real(Path(folder)/name).relative_to(root).as_posix())
            require(len(observed) <= MAX_FILES, 'Mirror file count exceeded')
    require(observed == names, 'Unlisted or missing regular mirror members')
    return root, names, dict(manifest_sha256=complete['manifest_sha256'],
        completion_sha256=checksum(directory/'MIRROR_COMPLETE.json'), files=len(names), bytes=total,
        all_listed_members_rehashed=True, closure=closure)


def interval_union(intervals):
    total = 0; previous = None
    for left, right in sorted(intervals):
        if previous is None: previous = [left, right]
        elif left <= previous[1]: previous[1] = max(previous[1], right)
        else: total += previous[1]-previous[0]; previous = [left, right]
    return total + (previous[1]-previous[0] if previous else 0)


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def aggregate(rows, fields):
    output = {}; count = 0
    for row in rows:
        budget(); count += 1
        for output_key, input_key, operation in fields:
            value = row.get(input_key)
            if finite(value):
                output[output_key] = value if output_key not in output else operation(output[output_key], value)
    return dict(samples=count, **output)


def final_asr(directory):
    path = directory/'latest_labelled_transcript.jsonl'
    if path.exists():
        rows = lines(path, maximum_bytes=16*MIB, maximum_records=MAX_ROWS)
        representation = 'retained_plain_final_rows'
    else:
        index = path.with_name(path.name+'.index.json')
        reference = read_json(index, 4096)
        reference['index_sha256'] = checksum(index, 4096)
        rows = iter_rows(directory, reference)
        representation = 'bounded_final_row_archive'
    words = hashlib.sha256(); utterances = hashlib.sha256(); count = tokens = 0
    for row in rows:
        budget(); require(row.get('is_final') is True, 'Nonfinal row in final ASR archive')
        text = row.get('text'); require(isinstance(text, str), 'Final ASR text missing')
        count += 1; require(count <= MAX_ROWS, 'Final utterance bound')
        word_list = text.split(); tokens += len(word_list)
        for token in word_list:
            raw = token.encode('utf-8'); words.update(len(raw).to_bytes(4, 'big')); words.update(raw)
        utterances.update(encoded(dict(start=row['source_start_sec'], end=row['source_end_sec'],
                                      words=word_list))+b'\n')
    return dict(utterances=count, words=tokens, word_sequence_sha256=words.hexdigest(),
                utterance_source_and_word_sha256=utterances.hexdigest(), representation=representation,
                definition='Exact case-sensitive whitespace tokens; utterance hash also binds ordered source windows; no transcript emitted')



def native_probability_summary(directory):
    """One exact matched-file D1 stream; no probabilities or identity labels emitted."""
    import math
    import struct
    values = hashlib.sha256(); private_values = bytearray(); cursor = 0; batches = 0; final = False
    step = None; columns = None
    for event in iter_events(directory/'events.jsonl', maximum_bytes=MAX_BYTES, maximum_records=MAX_EVENTS):
        budget()
        if event.get('event_type') != 'n2_diarization_frames':
            continue
        row = event.get('payload', {}); data = row.get('probabilities')
        require(not final and row.get('frame_start') == cursor and type(row.get('frame_start')) is int,
                'Native probability frame origin/gap/final boundary differs')
        require(isinstance(data, list) and 0 < len(data) <= 4470-cursor,
                'Native probability row extent differs')
        frame_step = row.get('frame_step_sec'); track_ids = row.get('track_ids')
        require(type(frame_step) in (int,float) and math.isfinite(frame_step) and abs(frame_step-.01)<1e-8,
                'Native probability sample clock differs')
        require(isinstance(track_ids,list) and len(track_ids)==8 and len(set(track_ids))==8,
                'Native probability column provenance differs')
        clock_bits = struct.pack('<d',frame_step).hex(); column_hash = hashlib.sha256(encoded(track_ids)).hexdigest()
        if step is None: step,columns=clock_bits,column_hash
        require((step,columns)==(clock_bits,column_hash), 'Native probability clock/column order changed within run')
        for probabilities in data:
            require(isinstance(probabilities,list) and len(probabilities)==8 and all(
                type(value) in (int,float) and math.isfinite(value) and 0 <= value <= 1 for value in probabilities),
                'Native probability value/dimension differs')
            raw = struct.pack('<8f',*probabilities);values.update(raw);private_values.extend(raw);cursor+=1
        require(type(row.get('is_final')) is bool, 'Native probability final flag missing')
        final=row['is_final'];batches+=1
        if final:
            require(abs(row.get('audio_received_sec',-1)-715127/16000)<1e-9,
                    'Native probability EOF input count differs')
    require(cursor==4470 and final, 'Complete matched D1 frame/EOF stream required')
    return dict(rows=cursor,columns=8,frames_contiguous=True,final_eof=True,
                source_samples=715127,frame_step_float64_le=step,column_order_sha256=columns,
                probabilities_float32_le_sha256=values.hexdigest(),publication_batches=batches,
                _private_float32_values=bytes(private_values),
                scope='All ordered native frame values reconstructed as little-endian float32; batch timing excluded; no accuracy inference')



def compare_probability_values(before, after):
    """Bounded matched-file arrays only; never serialize probability values."""
    import struct
    require(len(before)==len(after)==4470*8*4, 'Exact probability comparison byte extent required')
    maximum = 0.0; changed = above = 0
    for left,right in zip(struct.iter_unpack('<f',before),struct.iter_unpack('<f',after)):
        error=abs(left[0]-right[0]);maximum=max(maximum,error)
        changed += left[0]!=right[0];above += error>1e-5
    return dict(compared_values=4470*8,maximum_absolute_difference=maximum,
                changed_values=changed,values_above_absolute_tolerance=above,
                absolute_tolerance=1e-5,within_absolute_tolerance=above==0,
                scope='Float32 numerical consistency, not diarization quality or identity accuracy')


def event_summary(directory):
    counts = Counter(); spans = {}; captions = set(); origins = {}; issues = Counter()
    revisions = Counter(); final_display = {}
    for event in iter_events(directory/'events.jsonl', maximum_bytes=MAX_BYTES, maximum_records=MAX_EVENTS):
        budget(); kind = event.get('event_type'); counts[kind] += 1; row = event.get('payload', {})
        if kind == 's6d_display':
            key = row.get('caption_key'); require(isinstance(key, str), 'Stable native caption key missing')
            captions.add(key); require(len(captions) <= MAX_ROWS, 'Caption review capacity exceeded')
            origin = row.get('source_start_sec')
            if key in origins and origins[key] != origin: issues['caption_origin_changed'] += 1
            origins[key] = origin
            word_rows = row.get('word_spans', []); require(len(word_rows) <= 4096, 'Display span capacity exceeded')
            seen = set()
            for span in word_rows:
                identifier = span['id']; shape = (span['source_start_sec'], span['source_end_sec'], span.get('first_seen_monotonic_sec'))
                if identifier in seen: issues['duplicate_span_id_in_snapshot'] += 1
                seen.add(identifier)
                if identifier in spans and spans[identifier] != shape: issues['stable_span_origin_changed'] += 1
                spans[identifier] = shape
                require(len(spans) <= 65536, 'Historical span review capacity exceeded')
            final_display[key] = (row.get('text_revision_id'), len(word_rows))
        elif kind == 'transcript_label_revision':
            revisions['events'] += 1
            revisions['exact_text_revision_targets'] += isinstance(row.get('target_text_revision_id'), str)
            revisions['explicit_span_targets'] += bool(row.get('target_span_ids'))
            revisions['raw_words_explicitly_unchanged'] += row.get('changes_raw_words') is False
            revisions['coarse_observation_timing'] += row.get('timing_kind') == 'ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT'
            revisions['with_evidence_ids'] += bool(row.get('evidence_ids'))
            if row.get('changes_raw_words') is True: issues['label_revision_changes_raw_words'] += 1
    return dict(event_counts=dict(counts), unique_caption_keys=len(captions), unique_observed_span_ids=len(spans),
                final_span_count=sum(value[1] for value in final_display.values()),
                label_revision_provenance=dict(revisions), observed_invariant_issues=dict(issues),
                scope='Native event provenance; not proof that every upstream revision passed the bounded late-label view')


def open_database(path):
    require(not path.with_name(path.name+'-wal').exists() or path.with_name(path.name+'-wal').stat().st_size == 0,
            'Uncheckpointed SQLite WAL cannot be ignored')
    db = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True); db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    return db


def database_summary(path, session_id):
    db = open_database(path)
    try:
        def event_rows(kind):
            for number, row in enumerate(db.execute('SELECT * FROM events WHERE session_id=? AND event_type=? ORDER BY seq', (session_id, kind))):
                require(number < MAX_EVENTS, 'Indexed event review capacity exceeded')
                yield _unpack_event(dict(row))
        health = aggregate(event_rows('health'), [
            ('maximum_backlog_seconds','backlog_seconds',max), ('first_text_latency_seconds','first_caption_latency',min),
            ('first_supported_label_latency_seconds','first_speaker_latency',min), ('maximum_sampled_worker_rss_bytes','rss',max),
            ('maximum_sampled_worker_pss_bytes','pss_bytes',max), ('maximum_sampled_worker_vm_bytes','virtual_bytes',max),
            ('maximum_observed_worker_vm_peak_bytes','peak_virtual_bytes',max), ('minimum_system_available_ram_bytes','available_ram',min),
            ('maximum_sampled_worker_swap_bytes','swap_bytes',max), ('maximum_observed_dropped_audio','dropped_audio',max),
            ('maximum_observed_process_cpu_seconds','cpu_seconds',max), ('maximum_sampled_source_elapsed_seconds','elapsed',max)])
        health['scope'] = 'Worker health samples; maxima are sampled observations, not whole-unit peaks; first timings use recorded source origin'
        schedule = Counter(); counters = {}; invalid = 0
        for row in event_rows('embedding_schedule'):
            budget(); schedule[row.get('status','missing')] += 1
            counters = row.get('counters', counters)
            if not (type(row.get('source_start_sample')) is int and type(row.get('source_end_sample')) is int and
                    0 <= row['source_start_sample'] < row['source_end_sample'] <= 715127): invalid += 1
        all_intervals = []; unsupported = []; count = revisions = provisional = missing = 0
        for row in db.execute('SELECT * FROM captions WHERE session_id=? ORDER BY seq', (session_id,)):
            budget(); count += 1; require(count <= MAX_ROWS, 'Indexed caption bound')
            provenance = strict(row['provenance']); interval = (row['start_sample'], row['end_sample'])
            all_intervals.append(interval); revisions += row['revision']; provisional += bool(row['provisional'])
            missing += not isinstance(provenance.get('text_revision'), str)
            if provenance.get('speaker_supported') is False: unsupported.append(interval)
        return dict(health=health, embedding_schedule=dict(events=dict(schedule), final_counters=counters, invalid_source_intervals=invalid),
            indexed_captions=dict(count=count, accumulated_upsert_revisions=revisions, provisional_rows=provisional,
                missing_text_revision_provenance=missing, source_interval_union_samples=interval_union(all_intervals),
                unsupported_caption_interval_union_samples=interval_union(unsupported),
                coverage_definition='Final indexed captions with speaker_supported=false; coarse overlapping ASR observation windows, not acoustic speaker time or DER'))
    finally:
        db.close()


def attribution_summary(path):
    if path is None:
        return dict(available=False, scope='Retained presentation; no single-D1 view archive')
    latest = {}; records = 0; statuses = Counter(); invalid = Counter()
    for row in iter_events(path, maximum_bytes=MAX_BYTES, maximum_records=MAX_EVENTS):
        budget(); records += 1
        spans = row['attribution_spans']; key = row['caption_key']
        require(type(spans) is list and len(spans) <= 1024, 'Attribution span allocation exceeded')
        raw = json.dumps(spans, sort_keys=True, allow_nan=False).encode()
        require(hashlib.sha256(raw).hexdigest() == row['attribution_spans_sha256'], 'Attribution source proof differs')
        covered = []; unsupported = []; counts = Counter(); seen = set()
        for span in spans:
            identifier = span.get('span_id'); start = span.get('start_sample'); end = span.get('end_sample')
            require(type(start) is int and type(end) is int and 0 <= start <= end <= 715127,
                    'Attribution source interval differs')
            if identifier in seen: invalid['duplicate_span_id'] += 1
            seen.add(identifier); covered.append((start,end)); counts[span.get('status','missing')] += 1
            if not span.get('supported'): unsupported.append((start,end))
            if not finite(span.get('revision_deadline_monotonic')): invalid['missing_deadline'] += 1
            if span.get('supported'):
                evidence = span.get('evidence') or {}
                if not str(evidence.get('evidence_event_id','')).startswith('n2-caption:'):
                    invalid['supported_without_native_evidence'] += 1
        latest[key] = (covered, unsupported, counts)
        statuses[row.get('attribution_status','missing')] += 1
        require(len(latest) <= MAX_ROWS and sum(len(value[0]) for value in latest.values()) <= 65536,
                'Retained attribution review capacity exceeded')
    covered = [span for value in latest.values() for span in value[0]]
    unsupported = [span for value in latest.values() for span in value[1]]
    final_counts = Counter()
    for value in latest.values(): final_counts.update(value[2])
    return dict(available=True, records=records, caption_keys=len(latest), observed_status_counts=dict(statuses),
        final_span_status_counts=dict(final_counts), observed_provenance_issues=dict(invalid),
        final_observation_interval_union_samples=interval_union(covered),
        final_unsupported_observation_interval_union_samples=interval_union(unsupported),
        limits='Archive hashes/deadline fields/native evidence IDs verified. It lacks per-record publication time, so Unknown wall duration and actual deadline compliance cannot be reconstructed; intervals are coarse ASR windows.')


def summarize(directory):
    root, names, mirror = verify_mirror(directory)
    results = [root/name for name in names if name.endswith('/worker/RESULT.json')]
    result_path = only(results, 'Exactly one current worker result required'); worker = read_json(result_path)
    result = worker.get('result', {}); host_path = result_path.parent.parent/'HOST_CLOSURE.json'; host = read_json(host_path)
    require(worker.get('failure') is None and worker.get('logical_cleanup_complete') is True and
            result.get('status') == 'FUNCTIONAL_SESSION_COMPLETED' and host.get('direct_child_reaped') is True and
            host.get('returncode') == 0 and host.get('output_error') is None and not host.get('receipt_errors') and
            host.get('stdout_reader_joined') is True and host.get('result') == worker,
            'Successful current worker and authoritative host closure required')
    admission = read_json(root/'ADMISSION.json'); payload = admission['payload']
    require(payload.get('input_sha256') == SOURCE_SHA and result.get('source_samples') == 715127,
            'Exact matched 715127-sample input required')
    require(payload['selection'] == result['selection'] and payload['policy'] == result['source_policy'],
            'Requested and executed selection/policy differ')
    session_id = worker['session_id']
    session_file = only([root/name for name in names if name.endswith('/sessions/'+session_id+'/session.json')], 'One kept recording required')
    session = read_json(session_file); require(session['status'] == 'kept' and session['processed_samples'] == 715127, 'Kept complete source required')
    require(host.get('registered_owner') == read_json(result_path.parent/'REGISTERED_OWNER.json') and
            host['registered_owner']['boot_id'] == mirror['closure']['owner']['boot_id'], 'Worker ownership differs from actual host closure')
    db_path = only([root/name for name in names if name.endswith('/history.sqlite3')], 'One history database required')
    source_hash = hashlib.sha256(); cursor = 0
    db = open_database(db_path)
    try:
        for number, row in enumerate(db.execute("SELECT * FROM segments WHERE session_id=? AND kind='processed' ORDER BY idx", (session_id,))):
            require(number < MAX_ROWS and row['start_sample'] == cursor and row['samples'] > 0, 'Processed segment source gap/bound')
            require(Path(row['data_name']).name == row['data_name'], 'Processed segment must be local')
            data = real(session_file.parent/row['data_name'])
            require(data.stat().st_size == row['samples']*4, 'Processed float sample extent differs')
            with data.open('rb') as stream:
                while block := stream.read(MIB): budget(); source_hash.update(block)
            cursor += row['samples']
    finally:
        db.close()
    require(cursor == 715127, 'Incomplete processed source stream')
    native_dir = only([root/name for name in names if name.startswith(str(session_file.parent.relative_to(root)).replace('\\','/')+'/') and name.endswith('/session_summary.json')], 'One native session summary required').parent
    data = database_summary(db_path, session_id)
    attribution_paths = [root/name.removesuffix('.index.json') for name in names if name.endswith('/caption-attribution.jsonl.index.json')]
    require(len(attribution_paths) <= 1, 'One bounded late-label archive expected')
    unit_path = root/'WHOLE_UNIT_MEMORY.jsonl'
    unit = aggregate(lines(unit_path), [('maximum_sampled_unit_rss_bytes','combined_rss_bytes',max),
            ('maximum_sampled_unit_pss_bytes','combined_pss_bytes',max), ('minimum_available_ram_bytes','available_ram',min)]) if unit_path.exists() else None
    return dict(mirror=mirror, executed_package=payload['package'], manifest_sha256=payload['package_manifest_sha256'],
        worker_result_sha256=checksum(result_path), host_closure_sha256=checksum(host_path),
        selection=result['selection'], policy=result['source_policy'], source=dict(input_sha256=SOURCE_SHA, samples=cursor,
        processed_float32_sha256=source_hash.hexdigest()), costs=result.get('costs', {}), final_asr=final_asr(native_dir),
        native_events=event_summary(native_dir), native_probabilities=native_probability_summary(native_dir), late_label_view=attribution_summary(attribution_paths[0] if attribution_paths else None),
        whole_unit_samples=unit, **data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    require(args.baseline.resolve() != args.candidate.resolve(), 'Two distinct closed runs required')
    baseline = summarize(args.baseline); candidate = summarize(args.candidate)
    expected = dict(baseline['selection'], allow_experimental=True, embedding_schedule='sparse_clean_turn',
                    speaker_attribution='single_d1_late_labels')
    require(baseline['selection']['embedding_schedule'] == 'continuous' and
            baseline['selection']['speaker_attribution'] == 'retained' and
            baseline['selection']['diarizer'] == 'nemotron' and baseline['selection']['embedding'] == 'redimnet' and
            baseline['selection']['nemotron_profile'] == 'current_delayed' and
            baseline['selection']['input_source'] == 'saved' and not baseline['selection']['optional_d1_refiner'] and
            candidate['selection'] == expected and candidate['policy'] == baseline['policy'], 'Exact single comparison controls differ')
    require(candidate['source'] == baseline['source'], 'Matched input/processed-source agreement failed')
    probability_diff = compare_probability_values(
        baseline['native_probabilities'].pop('_private_float32_values'),
        candidate['native_probabilities'].pop('_private_float32_values'))
    old = baseline['costs'].get('embedding', {}); new = candidate['costs'].get('embedding', {})
    comparison = dict(same_input_and_processed_source=True, final_word_sequence_equal=baseline['final_asr']['word_sequence_sha256'] == candidate['final_asr']['word_sequence_sha256'],
        final_utterance_source_and_words_equal=baseline['final_asr']['utterance_source_and_word_sha256'] == candidate['final_asr']['utterance_source_and_word_sha256'],
        native_probability_difference=probability_diff,
        native_probability_frame_provenance_equal=all(baseline['native_probabilities'][key] == candidate['native_probabilities'][key]
            for key in ('rows','columns','frames_contiguous','final_eof','source_samples','frame_step_float64_le','column_order_sha256')),
        native_probability_float32_values_exactly_equal=baseline['native_probabilities']['probabilities_float32_le_sha256'] == candidate['native_probabilities']['probabilities_float32_le_sha256'],
        embedding_cost_delta={key:new[key]-old[key] for key in ('calls','samples','seconds') if key in old and key in new},
        quality_evaluated=False, der_evaluated=False, identity_accuracy_evaluated=False, sustained_realtime_qualified=False,
        limitations=['Agreement is output consistency, not recognition or speaker accuracy.',
            'Caption source windows are coarse ASR observation windows, not acoustic word alignment or speech-time coverage.',
            'Health sampling can miss peaks; absent whole-unit data is null, not zero.',
            'Runtime package differences and scheduling can affect timings; this is not causal isolation of the sparse schedule.',
            'Native upstream revision counts do not prove every revision was shown by the bounded late-label view.'])
    pins={name:checksum(Path(__file__).with_name(name), MIB) for name in
          ('review_research_comparison.py','runtime_support.py','storage.py','event_compaction.py','final_snapshot.py')}
    report=dict(schema='just-peachy.research-adaptation-comparison.v1',status='READ_ONLY_COMPARISON_COMPLETE',
                reviewer_source_sha256=pins,baseline=baseline,candidate=candidate,comparison=comparison)
    raw=encoded(report)+b'\n'; require(len(raw) <= 128*1024, 'Summary output allocation exceeded')
    with (OUTPUT/'COMPARISON.json').open('xb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(dict(status=report['status'], output=str(OUTPUT/'COMPARISON.json'),
                         final_word_sequence_equal=comparison['final_word_sequence_equal'],
                         embedding_cost_delta=comparison['embedding_cost_delta'], quality_evaluated=False)))


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        # Never print untrusted parser/data exceptions that could include text.
        (OUTPUT/'FAILED.json').write_text(json.dumps(dict(status='REVIEW_FAILED', error_type=type(exc).__name__,
            safe_reason='Reader failed; input content and parser details withheld'))+'\n', encoding='utf-8')
        print(json.dumps(dict(status='REVIEW_FAILED', output=str(OUTPUT/'FAILED.json'))))
        raise SystemExit(1)
