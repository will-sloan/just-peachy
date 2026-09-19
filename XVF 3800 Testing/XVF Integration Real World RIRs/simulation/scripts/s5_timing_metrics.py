"""S5 pure native timing and transcript-snapshot observability. No models or files."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import math

from s5_text_metrics import normalize, require_development

TIMING_SCOPE = ('Offline accelerated execution. UTC intervals and monotonic child wall measure different '
                'recorded boundaries; no claim of live word/name latency or CM5 resource fit. '
                'Historical reused and fresh S5 timings must be reported separately.')


def _timestamp(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('UTC timing requires timezone-aware timestamps')
    return parsed.timestamp()


def _prefix_length(a, b):
    count = 0
    for left, right in zip(a, b):
        if left != right:
            break
        count += 1
    return count


def transcript_revisions(events):
    """Changes between emitted snapshots, never corrections against reference truth."""
    utterances = defaultdict(list)
    for order, event in enumerate(events):
        if event['event_type'] not in ('transcript_partial', 'transcript_final'):
            continue
        payload = event['payload']
        if not isinstance(payload.get('text'), str):
            raise ValueError('Raw ASR text missing; display punctuation is not a substitute')
        utterances[payload['utterance_index']].append((order, event))
    totals = Counter()
    rows = []
    for index, observations in utterances.items():
        finals = [(order, e) for order, e in observations if e['event_type'] == 'transcript_final']
        if len(finals) > 1:
            raise ValueError('Duplicate native final index requires explicit unimplemented reconciliation semantics')
        if finals and finals[0][0] != observations[-1][0]:
            raise ValueError('Transcript event after final snapshot for same utterance')
        counts = Counter()
        transitions = []
        for (old_order, old), (new_order, new) in zip(observations, observations[1:]):
            a, b = normalize(old['payload']['text']).split(), normalize(new['payload']['text']).split()
            prefix = _prefix_length(a, b)
            content_change = a != b
            append = content_change and prefix == len(a)
            rewrite = content_change and not append
            before_label, after_label = old['payload'].get('speaker'), new['payload'].get('speaker')
            label_comparable = before_label is not None and after_label is not None
            label_change = label_comparable and before_label != after_label
            counts.update({'adjacent_snapshot_transitions': 1, 'raw_text_changed_transitions': int(old['payload']['text'] != new['payload']['text']),
                           'normalized_text_changed_transitions': int(content_change), 'prefix_append_transitions': int(append),
                           'lexical_rewrite_transitions': int(rewrite), 'removed_suffix_tokens': len(a)-prefix if rewrite else 0,
                           'added_suffix_tokens': len(b)-prefix if content_change else 0,
                           'label_comparable_transitions': int(label_comparable), 'emitted_label_changed_transitions': int(label_change),
                           'missing_label_transitions': int(not label_comparable)})
            if rewrite or label_change:
                transitions.append({'from_event_order': old_order, 'to_event_order': new_order,
                                    'from_event_type': old['event_type'], 'to_event_type': new['event_type'],
                                    'normalized_text_rewrite': rewrite, 'common_prefix_tokens': prefix,
                                    'removed_suffix_tokens': len(a)-prefix if rewrite else 0,
                                    'added_suffix_tokens': len(b)-prefix if content_change else 0,
                                    'emitted_label_changed': bool(label_change),
                                    'before_label': before_label, 'after_label': after_label,
                                    'from_source_cursor_s': old['source_time_sec'], 'to_source_cursor_s': new['source_time_sec']})
        first = observations[0][1]
        final = finals[0][1] if finals else None
        first_partial = next((e for _, e in observations if e['event_type'] == 'transcript_partial'), None)
        first_label = first_partial['payload'].get('speaker') if first_partial else None
        final_label = final['payload'].get('speaker') if final else None
        label_diff = final_label != first_label if first_label is not None and final_label is not None else None
        # UTC interval remains descriptive if the host clock moved backward.
        first_time = _timestamp(first.get('wall_time_utc'))
        final_time = _timestamp(final.get('wall_time_utc')) if final else None
        span = final_time-first_time if first_time is not None and final_time is not None else None
        if span is not None and span < 0:
            span = None
        counts.update({'partial_events': sum(e['event_type'] == 'transcript_partial' for _, e in observations),
                       'final_events': len(finals), 'utterances_with_lexical_rewrite': int(counts['lexical_rewrite_transitions'] > 0),
                       'utterances_with_emitted_label_change': int(counts['emitted_label_changed_transitions'] > 0)})
        totals.update(counts)
        rows.append({'utterance_index': index, 'counts': dict(counts), 'first_event_order': observations[0][0],
                     'final_event_order': finals[0][0] if finals else None, 'final_observed': final is not None,
                     'first_snapshot_to_final_host_s': span, 'first_partial_label': first_label,
                     'final_label': final_label, 'final_label_differs_from_first_partial': label_diff,
                     'rewrite_or_label_transition_evidence': transitions})
    return {'status': 'OBSERVED_NATIVE_SNAPSHOT_CHANGES', 'utterances': rows, 'counts': dict(totals),
            'utterance_count': len(rows), 'utterances_without_final': sum(not r['final_observed'] for r in rows),
            'normalization': 'Existing S4 lowercase/ASCII-punctuation deletion/whitespace collapse; raw text also counted separately',
            'raw_asr_field': 'text', 'display_text_used': False,
            'scope': 'Adjacent native partial/final snapshots within each utterance. Prefix appends are separated from rewrites; '
                     'an evolving incomplete word may be a rewrite. Suffix counts are not edit-distance errors or corrected ground-truth words. '
                     'Emitted label changes are snapshots, not cluster reconciliation or live latency.',
            'post_merge_reconciliation': None, 'post_merge_reason': 'Baseline exports no supported transcript reconciliation lineage'}


def analyze_timing(native_receipt, events, *, scene, development_ids, origin):
    """Pure API; caller provides verified resolved native receipt/events after allowlist gate."""
    cid = require_development(scene, development_ids)
    if origin not in ('reused_s45', 'fresh_s5'):
        raise ValueError('Keep historical reused and fresh S5 observations distinct')
    if native_receipt.get('case_id') != cid or native_receipt.get('stream') not in ('O0', 'O1'):
        raise ValueError('Native receipt case/stream mismatch')
    if native_receipt.get('status') != 'COMPLETE' or native_receipt.get('exit_code') != 0:
        raise ValueError('A failed/missing model run has no successful timing decomposition')
    expected_schema = 'jp_s5_native_attempt_v1' if origin == 'fresh_s5' else 'jp_s45_h2_job_v1'
    if native_receipt.get('schema') != expected_schema:
        raise ValueError('Resolve the original native receipt and declare its actual execution origin')
    by_type = defaultdict(list)
    for event in events:
        by_type[event['event_type']].append(event)
    for key in ('session_created', 'session_started', 'source_started', 'session_completed'):
        if len(by_type[key]) != 1:
            raise ValueError('Require exactly one native '+key)
    if any(by_type[key] for key in ('failure', 'session_stopped')) or events[-1]['event_type'] != 'session_completed':
        raise ValueError('Require terminal native completion and no failure/stopped events')
    tele = by_type['session_completed'][0]['payload']['telemetry']
    duration = float(native_receipt['adapter']['duration_s'])
    wall = float(native_receipt['model_wall_s'])
    if not math.isfinite(duration) or duration <= 0 or not math.isfinite(wall) or wall < 0:
        raise ValueError('Invalid duration or recorded child wall')
    if abs(duration-float(tele['source_duration_sec'])) > 1e-6:
        raise ValueError('Native source duration and adapter disagree')
    timestamps = {key: by_type[key][0].get('wall_time_utc') for key in
                  ('session_created', 'session_started', 'source_started', 'session_completed')}
    timestamps.update(receipt_created=native_receipt.get('created_utc'),
                      child_exit_observed=native_receipt.get('model_exited_utc'),
                      receipt_complete=native_receipt.get('completed_utc'))
    process_epoch = native_receipt.get('owned_process_creation_time')
    timestamps['process_created'] = (datetime.fromtimestamp(float(process_epoch), timezone.utc).isoformat()
                                     if process_epoch is not None else None)
    pairs = {
        'receipt_created_to_process_created': ('receipt_created', 'process_created'),
        'process_created_to_session_created': ('process_created', 'session_created'),
        'receipt_created_to_session_created': ('receipt_created', 'session_created'),
        'session_created_to_session_started': ('session_created', 'session_started'),
        'session_started_to_source_started': ('session_started', 'source_started'),
        'source_started_to_session_completed': ('source_started', 'session_completed'),
        'session_created_to_session_completed': ('session_created', 'session_completed'),
        'session_completed_to_child_exit': ('session_completed', 'child_exit_observed'),
        'child_exit_to_receipt_complete': ('child_exit_observed', 'receipt_complete'),
        'process_created_to_child_exit': ('process_created', 'child_exit_observed'),
        'receipt_created_to_receipt_complete': ('receipt_created', 'receipt_complete'),
    }
    intervals, unavailable, anomalies = {}, {}, []
    for key, (start, end) in pairs.items():
        a, b = _timestamp(timestamps[start]), _timestamp(timestamps[end])
        if a is None or b is None:
            intervals[key] = None
            unavailable[key] = 'Required timestamp not exported; no boundary inferred from model_wall_s'
        elif b < a:
            intervals[key] = None
            unavailable[key] = 'Negative host UTC interval; possible clock discontinuity or inconsistent receipt'
            anomalies.append({'interval': key, 'observed_signed_difference_s': b-a})
        else:
            intervals[key] = b-a
    tail = {key: tele.get(key) for key in ('asr_cursor_sec', 'speaker_cursor_sec', 'speaker_analyzed_through_sec',
                                         'speaker_unanalyzed_short_tail_sec')}
    elapsed = tele.get('elapsed_wall_sec')
    return {'schema': 'jp_s5_timing_metrics_v1', 'case_id': cid, 'stream': native_receipt['stream'], 'origin': origin,
            'status': 'LIMITED_HOST_CLOCK_ANOMALY' if anomalies else 'OBSERVED_NATIVE_TIMING',
            'model_child_wall_s': wall, 'decoded_audio_s': duration, 'child_wall_per_audio_s': wall/duration,
            'native_completion_elapsed_wall_s': elapsed,
            'native_completion_elapsed_per_audio_s': float(elapsed)/duration if elapsed is not None else None,
            'timestamps_utc': timestamps, 'intervals_s': intervals, 'unavailable_intervals': unavailable,
            'host_clock_anomalies': anomalies, 'native_source_tail': tail,
            'queue_wait_since_s5_start_s': native_receipt.get('queue_wait_since_s5_start_s') if origin == 'fresh_s5' else None,
            'queue_wait_scope': native_receipt.get('queue_wait_scope') if origin == 'fresh_s5' else 'Historical execution queue time unavailable',
            'owned_process_pid': native_receipt.get('owned_process_pid'), 'owned_process_creation_time': process_epoch,
            'process_closure': 'Caller must independently verify; this pure helper does not query or control processes',
            'duration_scope': {'source_started_to_session_completed': 'Accelerated processing and lane drain combined, not source playback duration',
                               'session_completed_to_child_exit': 'Combined remaining summary export, CLI and process finalization; no isolated write duration exported',
                               'child_exit_to_receipt_complete': 'Host native verification and legacy analysis after child exit, not model inference',
                               'process_created_to_session_created': 'Recorded process startup prefix; do not attribute entirely to model loading'},
            'unsupported': {'live_word_latency': None, 'live_name_latency': None, 'isolated_summary_write_s': None,
                            'isolated_model_loading_s': None, 'post_merge_label_correction_latency': None},
            'transcript_revisions': transcript_revisions(events), 'reserve_task_scored': False, 'scope': TIMING_SCOPE}
