"""S6 all-bank metrics, exact S5 scoring definitions. See README_S6A.md."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from importlib.metadata import version
import json
import math
from pathlib import Path

from s4_h2_analysis import NORMALIZATION, binding, load_json, normalize, score_text, write_json

SCHEMA = 'jp_s6a_text_metrics_v1'
MEETEVAL_VERSION = '0.4.3'
SIM = Path(__file__).resolve().parents[1]
S45 = SIM / 'reports/S4_5/20260909T031300Z'
BANK = SIM / 'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json'
MIMO_SCOPE = ('Multiple ordered reference-speaker utterance streams and exactly ONE hypothesis stream. '
              'Original utterance boundaries and within-speaker order are preserved; cross-speaker '
              'utterance serialization can change. No word shuffling or time constraints. '
              'This is not time-resolved overlap recall or separated-stream accuracy.')
CP_SCOPE = ('One global minimum-cost assignment per scene between complete reference-speaker text '
            'streams and ACTUAL emitted final transcript label streams. No truth-based label merging. '
            'Final-snapshot attributed text quality, not reconciled identity, enrollment, or DER.')


def require_all_bank(scene, allowed_ids):
    """S6 allowlist, checked before accessing any task path; source metadata unchanged."""
    cid = scene.get('case_id')
    if cid not in frozenset(allowed_ids):
        raise PermissionError('Outside authorized S6 bank: '+str(cid))
    return cid


def reference_layout(scene):
    """Preserve original whole-clip utterances; never discard a missing talker's words."""
    utterances = sorted((s for s in scene['segments'] if s.get('kind') == 'utterance'),
                        key=lambda s: s['source_start_sample'])
    problems = []
    for i, segment in enumerate(utterances):
        if not isinstance(segment.get('transcript'), str) or not normalize(segment['transcript']):
            problems.append(f'Missing reference text for utterance {i}')
        if not segment.get('speaker_key'):
            problems.append(f'Missing reference speaker_key for utterance {i}')
        if segment['source_stop_sample'] <= segment['source_start_sample']:
            problems.append(f'Invalid source interval for utterance {i}')
        if segment.get('source_split', 'development') not in {'development', 'downstream_reserve'}:
            raise PermissionError('Unknown source partition in S6 scene')
    intervals = [(s['source_start_sample'], s['source_stop_sample']) for s in utterances]
    overlap = bool(scene.get('overlap_intervals')) or any(max(a, c) < min(b, d)
        for i, (a, b) in enumerate(intervals) for c, d in intervals[i + 1:])
    complete = scene.get('all_speaker_reference_complete') is True and scene.get('transcript_valid') is True and not problems
    streams = defaultdict(list)
    for s in utterances:
        if s.get('speaker_key') and isinstance(s.get('transcript'), str):
            streams[s['speaker_key']].append(normalize(s['transcript']))
    reference = ' '.join(normalize(s.get('transcript', '')) for s in utterances)
    group = ('INCOMPLETE_REFERENCE' if not complete else 'STRICT_EMPTY_REFERENCE' if not reference
             else 'COMPLETE_OVERLAP' if overlap else 'PRIMARY_NONOVERLAP')
    return {'utterances': utterances, 'streams': dict(streams), 'reference': reference,
            'complete': complete, 'overlap': overlap, 'problems': problems, 'population': group}


def _final_rows(native_metrics=None, events=None):
    if native_metrics is None and events is None:
        raise ValueError('Native completed metrics or native events are required; absence is not an empty decode')
    metric_rows = None
    if native_metrics is not None:
        if native_metrics.get('state') != 'COMPLETED' or native_metrics.get('failure_events'):
            raise ValueError('Unavailable/failed model input cannot be scored as empty output')
        metric_rows = native_metrics['final_transcripts']
    event_rows = None
    if events is not None:
        if any(e['event_type'] in ('failure', 'session_stopped') for e in events):
            raise ValueError('Failure/stopped events cannot be scored as successful completion')
        if sum(e['event_type'] == 'session_completed' for e in events) != 1:
            raise ValueError('Require exactly one native session completion')
        event_rows = [dict(source_cursor_s=e['source_time_sec'], **e['payload'])
                      for e in events if e['event_type'] == 'transcript_final']
    if metric_rows is not None and event_rows is not None and metric_rows != event_rows:
        raise ValueError('Native final events and supplied metrics disagree')
    rows = event_rows if event_rows is not None else metric_rows
    indices = [r['utterance_index'] for r in rows]
    if len(indices) != len(set(indices)):
        raise ValueError('Duplicate final utterance index: no reconciliation policy is exported')
    if any(not isinstance(r.get('text'), str) for r in rows):
        raise ValueError('Missing raw final ASR text; display_text is not a substitute')
    return rows


def _duration(native_metrics, events, explicit):
    values = []
    if explicit is not None: values.append(float(explicit))
    if native_metrics is not None:
        tele = native_metrics.get('telemetry', {})
        if 'source_duration_sec' in tele: values.append(float(tele['source_duration_sec']))
        elif 'duration_s' in native_metrics.get('text', {}): values.append(float(native_metrics['text']['duration_s']))
    if not values:
        raise ValueError('Provide measured decoded duration; nominal scene length is not substituted')
    if any(not math.isfinite(v) or v <= 0 for v in values) or max(values) - min(values) > 1e-6:
        raise ValueError('Invalid or inconsistent decoded duration')
    return values[0]


def _backend():
    import meeteval.wer.wer.mimo
    import meeteval.wer.wer.cp
    actual = version('meeteval')
    if actual != MEETEVAL_VERSION:
        raise RuntimeError(f'Pinned MeetEval {MEETEVAL_VERSION} required, found {actual}')
    return meeteval.wer.wer.mimo.mimo_word_error_rate, meeteval.wer.wer.cp.cp_word_error_rate


def _rate(result, hypothesis_words, metric, scope):
    row = asdict(result)
    length = int(row['length'])
    counts = {'errors': int(row['errors']), 'substitutions': int(row['substitutions']),
              'deletions': int(row['deletions']), 'insertions': int(row['insertions']),
              'reference_words': length, 'hypothesis_words': hypothesis_words}
    assert counts['errors'] == sum(counts[k] for k in ('substitutions', 'deletions', 'insertions'))
    assert hypothesis_words == length - counts['deletions'] + counts['insertions']
    output = {'status': 'SCORED_DIAGNOSTIC', 'metric': metric, 'implementation': 'meeteval',
              'implementation_version': MEETEVAL_VERSION, 'wer': counts['errors'] / length if length else None,
              'word_counts': counts, 'assignment': json.loads(json.dumps(row.get('assignment'))), 'scope': scope}
    for key in ('missed_speaker', 'falarm_speaker', 'scored_speaker'):
        if key in row: output[key] = int(row[key])
    return output


def score_scene(scene, native_metrics=None, events=None, *, allowed_ids, duration_s=None, include_multitalker=True):
    """Pure scoring API. Guard is first. No task files, audio or model assets opened."""
    cid = require_all_bank(scene, allowed_ids)
    layout = reference_layout(scene)
    finals = _final_rows(native_metrics, events)
    duration = _duration(native_metrics, events, duration_s)
    hypothesis = ' '.join(r['text'] for r in finals)
    text = score_text(layout['reference'], hypothesis, duration_s=duration,
                      overlap=layout['overlap'], transcript_valid=layout['complete'])
    if not layout['complete']:
        text['reason'] = 'Incomplete all-speaker reference or missing utterance/identity annotation'
    out = {'schema': SCHEMA, 'case_id': cid, 'population': layout['population'],
           'normalization': NORMALIZATION, 'text': text, 'decoded_duration_s': duration,
           'hypothesis_empty': not normalize(hypothesis), 'reference_complete': layout['complete'],
           'reference_problems': layout['problems'], 'scheduled_overlap': layout['overlap'],
           'reference_speakers': len(layout['streams']), 'reference_utterances': len(layout['utterances']),
           'final_utterances': len(finals), 'all240_s6_authorized': True,
           'raw_asr_field': 'text', 'punctuation_display_used': False}
    if not layout['complete']:
        targets = sorted(scene.get('target_references', []), key=lambda r: r['start_sample'])
        if targets and all(isinstance(t.get('transcript'), str) and normalize(t['transcript']) for t in targets):
            target = score_text(' '.join(t['transcript'] for t in targets), hypothesis,
                                duration_s=duration, overlap=layout['overlap'])
            target.update(status='LIMITED_TARGET_REFERENCE_ONLY',
                scope='Whole mixed-output hypothesis against annotated targets; unknown ambient words may be insertions. '
                      'No excerpt alignment or all-speaker false-word interpretation; never primary pooled WER.')
            out['target_only_text'] = target
    limited_reason = ('Disabled for historical raw-count regression' if not include_multitalker
                      else 'Incomplete reference' if not layout['complete']
                      else 'Strict empty reference: report insertions and decoded minutes separately' if not layout['reference'] else None)
    out['overlap_mimo'] = {'status': 'NOT_APPLICABLE', 'reason': 'Not a complete-reference overlap scene', 'wer': None}
    out['attributed_cpwer'] = {'status': 'LIMITED', 'reason': limited_reason, 'wer': None, 'scope': CP_SCOPE}
    if limited_reason:
        if layout['overlap']:
            out['overlap_mimo'] = {'status': 'LIMITED', 'reason': limited_reason, 'wer': None, 'scope': MIMO_SCOPE}
        return out
    try:
        mimo, cp = _backend()
    except ImportError as exc:
        reason = f'Pinned MeetEval unavailable in this analysis process: {type(exc).__name__}'
        out['attributed_cpwer'].update(reason=reason)
        if layout['overlap']: out['overlap_mimo'] = {'status': 'LIMITED', 'reason': reason, 'wer': None, 'scope': MIMO_SCOPE}
        return out
    hyp = normalize(hypothesis)
    if layout['overlap']:
        result = mimo(layout['streams'], {'ONE_OUTPUT': hyp}, reference_sort=False, hypothesis_sort=False)
        out['overlap_mimo'] = _rate(result, len(hyp.split()), 'MIMO_WER_MULTIPLE_REFERENCE_ONE_HYPOTHESIS', MIMO_SCOPE)
        out['overlap_mimo']['hypothesis_streams'] = 1
    if any(normalize(r['text']) and (not isinstance(r.get('speaker'), str) or not r['speaker']) for r in finals):
        out['attributed_cpwer']['reason'] = 'Nonempty final transcript without an actual emitted speaker label'
        return out
    hyp_streams = defaultdict(list)
    for r in finals:
        if normalize(r['text']): hyp_streams[r['speaker']].append(normalize(r['text']))
    refs = {k: ' '.join(v) for k, v in layout['streams'].items()}
    hyps = {k: ' '.join(v) for k, v in hyp_streams.items()}
    result = cp(refs, hyps, reference_sort=False, hypothesis_sort=False)
    out['attributed_cpwer'] = _rate(result, len(hyp.split()), 'CPWER_FINAL_LABEL_SNAPSHOT', CP_SCOPE)
    out['attributed_cpwer'].update(reference_streams=len(refs), hypothesis_streams=len(hyps),
                                    hypothesis_labels=list(hyps), reconciled_lineage_available=False)
    return out


def score_scene_files(scene, *, allowed_ids, metrics_path=None, events_path=None, **kwargs):
    """Guard before opening either task input. Caller binds input hashes/receipt identity."""
    require_all_bank(scene, allowed_ids)
    metrics = load_json(metrics_path) if metrics_path is not None else None
    events = ([json.loads(line) for line in Path(events_path).read_text(encoding='utf-8').splitlines() if line.strip()]
              if events_path is not None else None)
    return score_scene(scene, metrics, events, allowed_ids=allowed_ids, **kwargs)

