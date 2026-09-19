"""Offline S4 output and unchanged-H2 evidence analysis. Never opens hardware."""
from __future__ import annotations

import argparse
import collections
import dataclasses
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import string

SIM = Path(__file__).resolve().parents[1]
ROOT = SIM.parent
REPO = ROOT.parents[1]
H2 = REPO / 'Software Validation from Datasets/Evaluation Tool'
NORMALIZATION = {
    'id': 'lowercase_remove_ascii_punctuation_collapse_whitespace_v1',
    'case': 'lowercase', 'punctuation': 'remove ASCII string.punctuation',
    'whitespace': 'strip and collapse', 'characters': 'normalized text without spaces',
    'numbers': 'no number expansion', 'contractions': 'remove apostrophe, no expansion',
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def binding(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(part)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def normalize(text):
    return ' '.join(str(text or '').lower().translate(str.maketrans('', '', string.punctuation)).split())


def _existing_wer():
    # Import the local audited scorer without loading unrelated dataset libraries.
    import sys
    path = H2 / 'app/scoring/wer.py'
    spec = importlib.util.spec_from_file_location('_jp_s4_existing_wer', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.compute_wer


def score_text(reference, hypothesis, *, duration_s, overlap=False, transcript_valid=True):
    ref, hyp = normalize(reference), normalize(hypothesis)
    common = {'normalization': NORMALIZATION, 'reference_normalized': ref,
              'hypothesis_normalized': hyp, 'duration_s': duration_s}
    if overlap or not transcript_valid:
        return {**common, 'status': 'LIMITED', 'reason': 'No valid timed multi-speaker scorer' if overlap else 'Transcript invalid',
                'wer': None, 'cer': None}
    scorer = _existing_wer()
    words = dataclasses.asdict(scorer(ref, hyp))
    chars = dataclasses.asdict(scorer(' '.join(ref.replace(' ', '')), ' '.join(hyp.replace(' ', ''))))
    word_result = {k: v for k, v in words.items() if k != 'wer'}
    char_result = {k.replace('words', 'characters'): v for k, v in chars.items() if k != 'wer'}
    # The historical scorer returns 1 for empty-reference insertions. S4 explicitly
    # leaves the undefined denominator null and reports raw insertions per minute.
    return {**common, 'status': 'SCORED' if ref else 'EMPTY_REFERENCE',
            'wer': words['errors'] / words['reference_words'] if ref else None,
            'cer': chars['errors'] / chars['reference_words'] if ref.replace(' ', '') else None,
            'word_counts': word_result, 'character_counts': char_result,
            'empty_reference_insertions': words['insertions'] if not ref else None,
            'empty_reference_words_per_minute': len(hyp.split()) * 60 / duration_s if not ref and duration_s > 0 else None}


def _db(value):
    return 20 * math.log10(value) if value > 0 else None


def rail_metrics(counts, rate=16000, bits=24, support_intervals=None, onset_window_s=0.5):
    import numpy as np
    x = np.asarray(counts, dtype=np.int64).reshape(-1)
    full = 2 ** (bits - 1)
    rails = (x <= -full) | (x >= full - 2)
    padded = np.r_[False, rails, False].astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    runs = [(int(a), int(b)) for a, b in zip(edges[::2], edges[1::2])]
    peak = int(np.max(np.abs(x))) if len(x) else 0
    support = np.zeros(len(x), bool)
    onset = np.zeros(len(x), bool)
    for start, end in support_intervals or []:
        a, b = max(0, round(start * rate)), min(len(x), round(end * rate))
        support[a:b] = True
        onset[a:min(b, a + round(onset_window_s * rate))] = True
    return {'sample_count': len(x), 'peak_counts': peak, 'peak_fs': peak / full,
            'rms_dbfs': _db(float(np.sqrt(np.mean((x / full) ** 2)))) if len(x) else None,
            'headroom_db': -_db(peak / full) if peak else None,
            'rail_samples': int(rails.sum()), 'rail_runs': len(runs),
            'maximum_contiguous_rail_run_samples': max((b-a for a, b in runs), default=0),
            'maximum_contiguous_rail_run_ms': max((b-a for a, b in runs), default=0) / rate * 1000,
            'first_rail_sample': int(np.flatnonzero(rails)[0]) if rails.any() else None,
            'first_rail_s': float(np.flatnonzero(rails)[0] / rate) if rails.any() else None,
            'rail_run_excerpt': [{'start_sample': a, 'samples': b-a, 'sign': int(np.sign(x[a]))} for a, b in runs[:25]],
            'support_samples': int(support.sum()) if support_intervals is not None else None,
            'onset_definition_s': onset_window_s,
            'onset_rail_samples': int((rails & onset).sum()) if support_intervals is not None else None,
            'steady_support_rail_samples': int((rails & support & ~onset).sum()) if support_intervals is not None else None,
            'outside_support_rail_samples': int((rails & ~support).sum()) if support_intervals is not None else None,
            'support_rms_dbfs': _db(float(np.sqrt(np.mean((x[support] / full) ** 2)))) if support.any() else None}


def audit_converter(case_dir, *, support_intervals=None):
    """Independent decoder checks saved outputs against original signed PCM24 words."""
    import numpy as np
    import soundfile as sf
    folder = Path(case_dir)
    receipt = load_json(folder / 'case_result.json')
    framing = receipt['framing']
    raw, rate = sf.read(folder / 'native_packed.wav', dtype='int32', always_2d=True)
    assert rate == 48000 and raw.shape[1] == 2
    raw = raw >> 8
    start = framing['startup_frames_excluded']
    end = framing['common_end_native_frame']
    # Independent reproduction of documented row-major 0,1,1 framing.
    payload = (raw[start:end].reshape(-1, 6) & -2)
    rows = {}
    for name, channel in [('O0', 4), ('O1', 5)]:
        saved, out_rate = sf.read(folder / (name + '.wav'), dtype='int32')
        saved = saved >> 8
        assert out_rate == 16000 and saved.ndim == 1
        rows[name] = {'mismatched_saved_vs_native_counts': int(np.count_nonzero(saved != payload[:, channel])),
                      **rail_metrics(saved, support_intervals=support_intervals)}
    return {'case_dir': str(folder.resolve()), 'outputs': rows,
            'native_file': binding(folder / 'native_packed.wav'),
            'conversion_status': 'EXACT_NATIVE_COUNTS' if all(v['mismatched_saved_vs_native_counts'] == 0 for v in rows.values()) else 'CONVERSION_MISMATCH',
            'interpretation': 'Rail plateaus already present in device native packed payload; saved-WAV attenuation cannot repair them.'}


def journal_audio(path):
    """Reproduce unchanged H2 float32-to-PCM16 path for gate evidence only."""
    import numpy as np
    import soundfile as sf
    audio, rate = sf.read(path, dtype='float32', always_2d=True)
    if rate != 16000 or audio.shape[1] != 1:
        raise ValueError('Require explicit mono 16 kHz H2 input; never average diagnostic channels')
    mono = audio[:, 0]
    if not np.isfinite(mono).all():
        raise ValueError('Nonfinite H2 input')
    return np.round(np.clip(mono, -1.0, 0.999969) * 32768.0).astype('<i2').astype(np.float32) / 32768.0


def gate_evidence(audio_path, events, *, minimum_rms=0.002, hop_s=0.25, window_s=0.5):
    import numpy as np
    audio = journal_audio(audio_path)
    rate, hop = 16000, round(hop_s * 16000)
    segments = {round(float(e['source_time_sec']), 6): e['payload'] for e in events if e['event_type'] == 'segmentation'}
    decisions = {round(float(e['source_time_sec']), 6) for e in events if e['event_type'] == 'speaker_decision'}
    totals = collections.Counter()
    speech = overlap = False
    for end in range(hop, len(audio) + 1, hop):
        t = round(end / rate, 6)
        if t in segments:
            speech, overlap = bool(segments[t]['speech']), bool(segments[t]['overlap'])
        rms = float(np.sqrt(np.mean(np.square(audio[end-hop:end]), dtype=np.float64)))
        flags = {'no_speech': not speech, 'overlap': overlap, 'short_window': end / rate < window_s, 'below_minimum_rms': rms < minimum_rms}
        eligible = not any(flags.values())
        totals['total_hops'] += 1
        totals['eligible_hops_reconstructed'] += eligible
        totals['emitted_embedding_decisions'] += t in decisions
        totals['eligible_without_decision'] += eligible and t not in decisions
        totals['decision_despite_ineligible'] += (not eligible) and t in decisions
        totals['single_speech_hops'] += speech and not overlap
        totals['single_speech_hops_below_rms'] += speech and not overlap and rms < minimum_rms
        for name, value in flags.items():
            totals['blocked_' + name] += value
    return {'minimum_rms': minimum_rms, 'minimum_rms_dbfs': _db(minimum_rms),
            'hop_s': hop_s, 'embedding_window_s': window_s, 'counts': dict(totals),
            'embedded_window_unique_speech_seconds': None,
            'scope': 'Gate reconstruction from exact PCM16 samples and emitted segmentation; blocking reasons may overlap. Decisions equal successful embed calls. Rejected embed calls are not logged; absence is not a model rejection. Overlapping 0.5 s windows every 0.25 s are not independent evidence.'}


def _wall_seconds(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def speaker_turn_evidence(events, turns, *, alignment_offset_s=0.0, window_s=0.5):
    """Scoring only: require full embedding window within exactly one dry-file turn."""
    decisions = [e for e in events if e['event_type'] == 'speaker_decision']
    per_turn = []
    for index, turn in enumerate(turns):
        start, end = float(turn['start_s']) + alignment_offset_s, float(turn['end_s']) + alignment_offset_s
        selected = []
        for event in decisions:
            t = float(event['source_time_sec'])
            if t - window_s < start or t > end:
                continue
            overlaps = sum(t > float(other['start_s']) + alignment_offset_s and t-window_s < float(other['end_s']) + alignment_offset_s for other in turns)
            if overlaps == 1:
                selected.append(event)
        labels = [str(e['payload']['anonymous_label']) for e in selected]
        counts = collections.Counter(labels)
        ordered = counts.most_common()
        dominant = ordered[0][0] if ordered and (len(ordered) == 1 or ordered[0][1] > ordered[1][1]) else None
        per_turn.append({'turn_index': index, 'participant_id': turn['participant_id'], 'decision_count': len(labels),
                         'labels': dict(counts), 'dominant_label': dominant,
                         'label_switches': sum(a != b for a, b in zip(labels, labels[1:])),
                         'fragment_count': len(counts), 'missing_evidence': not labels})
    repeated = []
    for participant in dict.fromkeys(t['participant_id'] for t in turns):
        rows = [r for r in per_turn if r['participant_id'] == participant]
        if len(rows) > 1:
            labels = [r['dominant_label'] for r in rows]
            repeated.append({'participant_id': participant, 'turn_indices': [r['turn_index'] for r in rows],
                             'dominant_labels': labels, 'consistent': len(set(labels)) == 1 if all(labels) else None})
    return {'turns': per_turn, 'returning_participants': repeated,
            'alignment_offset_s': alignment_offset_s,
            'scope': 'Anonymous embedding-decision continuity on fully contained single-source file-support windows. File bounds are not phonetic ground truth; no DER and no enrollment naming accuracy. No truth supplied to H2.'}


def analyze_session(session_dir, *, reference='', duration_s=None, overlap=False, transcript_valid=True,
                    audio_path=None, turns=None, alignment_offset_s=0.0):
    folder = Path(session_dir)
    events = [json.loads(line) for line in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    summary = load_json(folder / 'session_summary.json')
    duration_s = float(duration_s if duration_s is not None else summary['telemetry']['source_duration_sec'])
    finals = [e for e in events if e['event_type'] == 'transcript_final']
    indices = [e['payload']['utterance_index'] for e in finals]
    if len(indices) != len(set(indices)):
        raise ValueError('Duplicate final utterance indices require explicit lineage handling')
    hypothesis = ' '.join(e['payload'].get('text', '') for e in finals)
    start = next((e for e in events if e['event_type'] == 'source_started'), None)
    availability = []
    last_decision = None
    for event in events:
        if event['event_type'] == 'speaker_decision':
            last_decision = event
        if event['event_type'] in {'transcript_partial', 'transcript_final'}:
            availability.append({'event_type': event['event_type'], 'utterance_index': event['payload']['utterance_index'],
                                 'source_cursor_s': event['source_time_sec'],
                                 'wall_after_source_started_s': _wall_seconds(event['wall_time_utc']) - _wall_seconds(start['wall_time_utc']) if start else None,
                                 'emitted_speaker': event['payload']['speaker'],
                                 'latest_preceding_decision_source_s': last_decision['source_time_sec'] if last_decision else None,
                                 'speaker_source_cursor_minus_asr_cursor_s': float(last_decision['source_time_sec']) - float(event['source_time_sec']) if last_decision else None})
    decisions = [e for e in events if e['event_type'] == 'speaker_decision']
    labels = [e['payload']['anonymous_label'] for e in decisions]
    result = {'schema_version': 'jp_s4_h2_analysis_v1', 'session_dir': str(folder.resolve()),
              'state': summary['state'], 'event_counts': dict(collections.Counter(e['event_type'] for e in events)),
              'text': score_text(reference, hypothesis, duration_s=duration_s, overlap=overlap, transcript_valid=transcript_valid),
              'final_transcripts': [{'source_cursor_s': e['source_time_sec'], **e['payload']} for e in finals],
              'speaker': {'emitted_final_labels': [e['payload']['speaker'] for e in finals],
                          'decision_label_counts': dict(collections.Counter(labels)),
                          'decision_label_switches': sum(a != b for a, b in zip(labels, labels[1:])),
                          'reconciled_labels': None, 'reconciliation_status': 'UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE',
                          'lineage': 'Final transcript labels snapshot latest available concurrent speaker state; no source interval/cluster-merge/reconciliation event exists in this mode.',
                          'naming_accuracy': None, 'embedding_calls_successful': len(decisions),
                          'embedding_calls_rejected': None},
              'availability': availability,
              'availability_scope': 'Host UTC event creation after offline file source start, not live caption latency. Source cursor is consumed audio, not recognized word onset. Speaker and ASR lanes are concurrent.',
              'offline_rtf': summary['telemetry']['elapsed_wall_sec'] / duration_s if duration_s else None,
              'telemetry': summary['telemetry'], 'scientific_policy': summary['scientific_policy'],
              'failure_events': [e for e in events if e['event_type'] == 'failure']}
    if audio_path:
        result['embedding_gate_evidence'] = gate_evidence(audio_path, events)
    if turns:
        result['speaker']['reference_turn_evidence'] = speaker_turn_evidence(events, turns, alignment_offset_s=alignment_offset_s)
    return result


def analyze_scene(session_dir, scene, *, audio_path=None, alignment_offset_s=0.0):
    """Convenience bridge for canonical scene segments. Offset is caller evidenced."""
    rate = int(scene.get('sample_rate_hz', 16000))
    segments = sorted((s for s in scene['segments'] if s.get('transcript')), key=lambda s: s['source_start_sample'])
    intervals = [(s['source_start_sample'] / rate, s['source_stop_sample'] / rate) for s in segments]
    detected_overlap = any(max(a[0], b[0]) < min(a[1], b[1]) for i, a in enumerate(intervals) for b in intervals[i+1:])
    return analyze_session(session_dir, reference=' '.join(s['transcript'] for s in segments),
                           overlap=bool(scene.get('overlap', False) or detected_overlap),
                           transcript_valid=scene.get('transcript_valid', True),
                           audio_path=audio_path,
                           turns=[{'participant_id': s['speaker_key'], 'start_s': a, 'end_s': b}
                                  for s, (a, b) in zip(segments, intervals)],
                           alignment_offset_s=alignment_offset_s)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    session = sub.add_parser('session')
    session.add_argument('--session', required=True)
    session.add_argument('--reference-json', required=True, help='reference, duration_s, overlap, transcript_valid, turns, alignment_offset_s')
    session.add_argument('--audio')
    session.add_argument('--output', required=True)
    converter = sub.add_parser('converter')
    converter.add_argument('--case', required=True)
    converter.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'session':
        result = analyze_session(args.session, audio_path=args.audio, **load_json(args.reference_json))
    else:
        result = audit_converter(args.case)
    write_json(args.output, result)
    print(json.dumps({'output': str(Path(args.output).resolve()), 'status': result.get('state', result.get('conversion_status'))}))


if __name__ == '__main__':
    main()
