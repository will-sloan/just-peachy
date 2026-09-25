"""Bounded native event-envelope census. See README_NATIVE_JOURNAL_REVIEW.md."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re

from common import audio_only, bind, fingerprint, verify
from paced_child_admission import assert_plain_path
from review_application_transport import finite, record, unique_pairs
from review_scoring_bank import require

MAX_BYTES = 256*1024**2
MAX_LINE = 1024**2
MAX_SEGMENTS = 256
MAX_RECORDS = 500000
EVENT_FIELDS = {'schema_version', 'event_type', 'source_time_sec', 'wall_time_utc',
                'payload', 'journal_write_monotonic_sec'}


def segments(session):
    """Bind existing rotations in oldest-to-newest order, without guessing gaps."""
    session = Path(session).absolute()
    session = assert_plain_path(session, session.parent)
    require(session.is_dir(), 'Session directory missing')
    entries = {}
    for path in session.iterdir():
        if path.name == 'events.jsonl':
            number = 0
        elif path.name.startswith('events.jsonl.'):
            suffix = path.name[len('events.jsonl.'):]
            require(re.fullmatch('[1-9][0-9]{0,2}', suffix) is not None, 'Ambiguous journal rotation name')
            number = int(suffix)
        else:
            continue
        require(number < MAX_SEGMENTS, 'Journal segment bound exceeded')
        path = assert_plain_path(path, session)
        require(path.is_file(), 'Journal segment is not a regular file')
        entries[number] = path
    require(0 in entries and len(entries) <= MAX_SEGMENTS, 'Native base journal missing')
    require(set(entries) == set(range(max(entries)+1)), 'Missing journal rotation')
    sizes = [path.stat().st_size for path in entries.values()]
    require(all(size > 0 for size in sizes) and sum(sizes) <= MAX_BYTES, 'Empty or oversized native journal')
    return [bind(entries[number]) for number in sorted(entries, reverse=True)]


def rows(bindings, checkpoint=None):
    """Yield strict JSON records privately; a final hash check detects changes."""
    count = total = 0
    for binding in bindings:
        if checkpoint: checkpoint()
        verify(binding)
        with Path(binding['path']).open('rb') as stream:
            consumed = 0
            while True:
                line = stream.readline(MAX_LINE+1)
                if not line: break
                consumed += len(line); total += len(line); count += 1
                require(len(line) <= MAX_LINE and line.endswith(b'\n'), 'Oversized or unterminated journal record')
                require(total <= MAX_BYTES and count <= MAX_RECORDS, 'Native journal read bound exceeded')
                value = json.loads(line.decode('utf-8'), object_pairs_hook=unique_pairs,
                    parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON constant')))
                require(type(value) is dict and set(value) == EVENT_FIELDS, 'Native event envelope differs')
                fingerprint(value)  # Also rejects exponent overflow anywhere in a nested payload.
                if checkpoint and count % 256 == 0: checkpoint()
                yield value
            require(consumed == binding['bytes'], 'Journal changed while reading')
        verify(binding)
    for binding in bindings: verify(binding)


def terminal_census(session, job):
    cb, consumer = record(session/'s6d_consumer_closure.json', session)
    fb, final = record(session/'session_finalization_v3.json', session)
    require(consumer['state'] == 'COMPLETED' and consumer['full_event_consumer_drained'] is True
            and finite(consumer['monotonic_sec']) and consumer['monotonic_sec'] > 0, 'Consumer closure is not complete')
    journal = consumer['queues']['journal']; inbox = consumer['queues']['event_consumer']
    for item in (journal['accepted'], journal['completed'], inbox['consumed'], inbox['coalesced_obsolete_ui_partials']):
        require(type(item) is int and item >= 0, 'Invalid terminal event census')
    require(journal['accepted'] == journal['completed'] > 0
            and journal['completed'] == inbox['consumed']+inbox['coalesced_obsolete_ui_partials']
            and journal['depth'] == inbox['depth'] == 0 and journal['error'] is None
            and journal['thread_alive'] is False and journal['closed'] is True, 'Terminal event census does not close')
    require(final['schema_version'] == 'edge-session-finalization.v3' and final['state'] == 'COMPLETED'
            and final['live_lanes_at_finalization'] == [] and final['finalization_error'] is None
            and final['resident_bundle_lease_retained'] is False and final['resident_bundle_reuse_allowed'] is True
            and final['event_and_transcript_handles_closed'] is True
            and final['source_samples'] == final['identity_samples'] == job['frames'], 'Native finalization differs')
    require(set(final['handle_close_results']) == {'_event_handle', '_transcript_handle', '_readable_transcript_handle'}
            and all(r == dict(closed=True, error=None, was_opened=True) for r in final['handle_close_results'].values()),
            'Native handles did not close normally')
    return journal['completed'], consumer['monotonic_sec'], [cb, fb]


def inspect(session, *, job, checkpoint=None):
    """Classify complete envelopes versus retained tails; never return transcript text.

    Caller must separately establish exact application ownership and complete
    production-plan population. Semantic payloads and accuracy are not scored.
    """
    audio_only(job)
    session = Path(session).absolute()
    session = assert_plain_path(session, session.parent)
    bindings = segments(session)
    expected, closed_at, terminal = terminal_census(session, job)
    duration = job['frames']/16000
    counts = Counter(); first = last = None
    previous_publication = previous_write = previous_cursor = -1.
    minimum_source = maximum_source = None
    overhang = 0; maximum_queue_age = 0.; start = None; completed_at = None
    for row in rows(bindings, checkpoint):
        require(row['schema_version'] == 'edge-speech-event.v1', 'Native event schema differs')
        kind = row['event_type']; payload = row['payload']
        require(type(kind) is str and re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,95}', kind) is not None
                and type(payload) is dict, 'Invalid native event kind or payload')
        wall = datetime.fromisoformat(row['wall_time_utc'])
        require(wall.utcoffset() is not None, 'Native event wall clock lacks timezone')
        serial = payload['publication_sequence']; publication = payload['publication_monotonic_sec']
        written = row['journal_write_monotonic_sec']; cursor = payload['publication_source_cursor_sec']
        require(type(serial) is int and 0 < serial <= expected and (last is None or serial == last+1),
                'Native journal sequence is duplicated, out of order or has an internal gap')
        require(payload['session_id'] == session.name, 'Native event belongs to another session')
        require(all(finite(v) for v in (publication, written, cursor, row['source_time_sec']))
                and 0 < publication <= written <= closed_at
                and publication >= previous_publication and written >= previous_write
                and 0 <= cursor <= duration and previous_cursor <= cursor, 'Native publication/write/cursor clock differs')
        if first is None: first = serial
        last = serial; counts[kind] += 1
        require(len(counts) <= 256, 'Native event type census exceeds bound')
        minimum_source = row['source_time_sec'] if minimum_source is None else min(minimum_source, row['source_time_sec'])
        maximum_source = row['source_time_sec'] if maximum_source is None else max(maximum_source, row['source_time_sec'])
        overhang += int(not 0 <= row['source_time_sec'] <= duration)
        maximum_queue_age = max(maximum_queue_age, written-publication)
        previous_publication, previous_write, previous_cursor = publication, written, cursor
        if kind == 'source_started':
            require(start is None and payload['mode'] == 'file' and payload['start_sample'] == 0
                    and payload['gain'] == 1. and payload['pacing'] == 'absolute'
                    and Path(payload['path']).absolute() == Path(job['audio_path']).absolute()
                    and finite(payload['source_epoch_monotonic_sec'])
                    and 0 < payload['source_epoch_monotonic_sec'] <= publication and cursor == 0,
                    'Source-start payload does not match the expected saved source')
            start = dict(sequence=serial, source_epoch_monotonic_sec=payload['source_epoch_monotonic_sec'],
                         publication_monotonic_sec=publication)
        if start is not None:
            require(publication >= start['source_epoch_monotonic_sec'], 'Publication precedes recorded source origin')
        if kind == 'session_completed':
            require(completed_at is None and serial == expected and cursor == duration,
                    'Native completion event is duplicated, premature or has a different source cursor')
            completed_at = publication
    require(first is not None, 'No native records retained')
    missing_prefix = first-1; missing_suffix = expected-last
    complete = not missing_prefix and not missing_suffix and start is not None and completed_at is not None
    reasons = []
    if missing_prefix: reasons.append('DISCARDED_OR_MISSING_PREFIX')
    if missing_suffix: reasons.append('MISSING_SUFFIX')
    if start is None: reasons.append('SOURCE_START_UNAVAILABLE')
    if completed_at is None: reasons.append('SESSION_COMPLETION_UNAVAILABLE')
    require(sum(counts.values()) == last-first+1, 'Retained event count differs from sequence interval')
    require(segments(session) == bindings, 'Native rotation set changed during review')
    for binding in terminal+bindings: verify(binding)
    return dict(status='PASS_COMPLETE_NATIVE_EVENT_ENVELOPE_ONLY' if complete else 'INCOMPLETE_NATIVE_EVENT_JOURNAL',
        complete_envelope=complete, reasons=reasons, journal=bindings, terminal=terminal,
        expected_events=expected, retained_events=sum(counts.values()), first_sequence=first, last_sequence=last,
        missing_prefix_events=missing_prefix, missing_suffix_events=missing_suffix, event_counts=dict(sorted(counts.items())),
        source_start=start, completion_publication_monotonic_sec=completed_at,
        source_audio_seconds=duration, retained_final_source_cursor_sec=previous_cursor,
        event_source_seconds_range=[minimum_source, maximum_source], event_source_outside_audio_count=overhang,
        max_recorded_publication_to_journal_seconds=maximum_queue_age,
        source_timestamp_policy='Unmodified diagnostic event source times; padding overhang counted, never clamped',
        scope='Native envelope/order/terminal census only; recorded timestamps, not independent physical delivery or latency proof',
        native_payload_semantics_reviewed=False, accuracy_qualified=False, source_to_widget_latency_qualified=False,
        production_panel_reviewed=False, integrated_N4_cells=0, N4_accepted=False)


def require_complete(review):
    require(review['status'] == 'PASS_COMPLETE_NATIVE_EVENT_ENVELOPE_ONLY' and review['complete_envelope'] is True,
            'Complete native event history is required; a retained tail cannot qualify')
    return review
