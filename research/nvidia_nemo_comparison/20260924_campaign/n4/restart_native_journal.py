"""Native envelope for explicit released prefixes; README_RESTART_NATIVE.md.

A separate derivative of the qualified full-file census. The planned audio job
is never copied with a shorter frames value. All terminal counts and event
cursors use an explicit independently supplied delivered length. Source path,
full-job fingerprint and intent stay bound. Caller must join delivery/engine
receipts and process ownership; this reader alone establishes none of those.
"""
from collections import Counter
from datetime import datetime
from pathlib import Path
import re

from common import audio_only, fingerprint, verify
from paced_child_admission import assert_plain_path
from review_application_transport import finite, record
from review_scoring_bank import require
from review_native_journal import segments, rows


def terminal_census(session, expected_frames):
    require(type(expected_frames) is int and expected_frames > 0, 'Positive delivered terminal sample count required')
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
            and type(final['source_samples']) is int and type(final['identity_samples']) is int
            and final['source_samples'] == final['identity_samples'] == expected_frames, 'Native finalization differs')
    require(set(final['handle_close_results']) == {'_event_handle', '_transcript_handle', '_readable_transcript_handle'}
            and all(r == dict(closed=True, error=None, was_opened=True) for r in final['handle_close_results'].values()),
            'Native handles did not close normally')
    return journal['completed'], consumer['monotonic_sec'], [cb, fb]


def inspect(session, *, job, delivered_frames, intent, checkpoint=None):
    """Classify complete envelopes versus retained tails; never return transcript text.

    Caller must separately establish exact application ownership and complete
    production-plan population. Semantic payloads and accuracy are not scored.
    """
    audio_only(job)
    require(type(delivered_frames) is int and 0 < delivered_frames <= job['frames'], 'Explicit positive delivered length required')
    require(intent in ('mid_file_stop', 'completed_release'), 'Explicit release intent required')
    require((intent == 'mid_file_stop' and delivered_frames < job['frames'] and delivered_frames % 320 == 0)
        or (intent == 'completed_release' and delivered_frames == job['frames']), 'Release intent and delivered length differ')
    session = Path(session).absolute()
    session = assert_plain_path(session, session.parent)
    bindings = segments(session)
    expected, closed_at, terminal = terminal_census(session, delivered_frames)
    duration = delivered_frames/16000
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
    return dict(schema='n4-released-native-envelope-v1',
        status='PASS_COMPLETE_RELEASED_NATIVE_EVENT_ENVELOPE_ONLY' if complete else 'INCOMPLETE_RELEASED_NATIVE_EVENT_JOURNAL',
        job_fingerprint=fingerprint(job), planned_audio_frames=job['frames'], delivered_audio_frames=delivered_frames, intent=intent,
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
        production_panel_reviewed=False, delivered_length_independently_joined=False,
        same_controller_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False)


def require_complete(review):
    require(review['schema'] == 'n4-released-native-envelope-v1'
        and review['status'] == 'PASS_COMPLETE_RELEASED_NATIVE_EVENT_ENVELOPE_ONLY'
        and review['complete_envelope'] is True,
        'Complete released native event history required; a retained tail cannot qualify')
    require(review['delivered_length_independently_joined'] is False
        and review['same_controller_restart_qualified'] is False and review['N4_accepted'] is False
        and review['integrated_N4_cells'] == 0, 'Native census cannot manufacture a joined restart acceptance')
    return review
