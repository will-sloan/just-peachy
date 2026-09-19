"""Aggregate existing S4 evidence only; never render, capture, or run H2. README_S4_RESULTS.md."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import unittest

from s4_common import BANK, REPORT, RUN_ID, bind, now, read, save
from s4_h2_analysis import normalize
from s4_capture_selection import accepted_cases, SELECTION_PATH

CASE_IDS = [f'S4_{i:02}' for i in range(1, 25)]
OUTPUTS = ('O0', 'O1')
SPATIAL_STREAMS = ('selected_processed', 'selected_auto', 'raw_auto', 'focused_1', 'focused_2', 'scanning')
REPEAT_BATCHES = ('repeat1', 'repeat2')


def write_csv(path, rows, fieldnames=None):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fields = fieldnames or list(dict.fromkeys(k for row in rows for k in row))
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fields, extrasaction='raise'); writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, separators=(',', ':'), ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    temporary.replace(path)


def present(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def maximum(values):
    values = [v for v in values if present(v)]
    return max(values) if values else None


def median(values):
    values = [v for v in values if present(v)]
    return statistics.median(values) if values else None


def weighted_rate(rows, numerator, denominator):
    n = sum(r[numerator] for r in rows)
    d = sum(r[denominator] for r in rows)
    return n / d if d else None


def text_pool(metrics):
    valid = [m for m in metrics if m['text']['status'] == 'SCORED']
    empty = [m for m in metrics if m['text']['status'] == 'EMPTY_REFERENCE']
    limited = [m for m in metrics if m['text']['status'] == 'LIMITED']
    word = {key: sum(m['text']['word_counts'][key] for m in valid) for key in
            ('errors', 'substitutions', 'deletions', 'insertions', 'reference_words', 'hypothesis_words')}
    character = {key: sum(m['text']['character_counts'][key] for m in valid) for key in
                 ('errors', 'substitutions', 'deletions', 'insertions', 'reference_characters', 'hypothesis_characters')}
    for result in (word, character):
        if result['errors'] != result['substitutions'] + result['deletions'] + result['insertions']:
            raise ValueError('Edit operation counts do not sum to errors')
    seconds = sum(m['text']['duration_s'] for m in empty)
    insertions = sum(m['text']['empty_reference_insertions'] for m in empty)
    return {'nonoverlap_scored_scene_ids': [m['case_id'] for m in valid], 'nonoverlap_scene_count': len(valid),
            'word_counts': word, 'character_counts': character,
            'pooled_wer': word['errors'] / word['reference_words'] if word['reference_words'] else None,
            'pooled_cer': character['errors'] / character['reference_characters'] if character['reference_characters'] else None,
            'empty_reference_scene_ids': [m['case_id'] for m in empty], 'empty_reference_duration_s': seconds,
            'empty_reference_insertions': insertions, 'empty_reference_words_per_minute': insertions * 60 / seconds if seconds else None,
            'overlap_or_invalid_transcript_limited_scene_ids': [m['case_id'] for m in limited],
            'aggregation': 'Sum edit counts / sum reference denominators. Empty references and overlap LIMITED excluded from WER/CER. No mean of per-scene WER and no population confidence interval.'}


def rms_pool(rows, *, support=False):
    nkey, rmskey = ('support_samples', 'support_rms_dbfs') if support else ('sample_count', 'rms_dbfs')
    pairs = [(r[nkey], r[rmskey]) for r in rows if present(r.get(nkey)) and r[nkey] > 0 and present(r.get(rmskey))]
    count = sum(n for n, _ in pairs)
    power = sum(n * 10 ** (db / 10) for n, db in pairs)
    return 10 * math.log10(power / count) if count and power else None


def audio_pool(rows):
    samples = sum(r['sample_count'] for r in rows)
    rails = sum(r['rail_samples'] for r in rows)
    return {'capture_count': len(rows), 'samples': samples, 'rail_samples': rails,
            'rail_samples_per_million': rails * 1e6 / samples if samples else None,
            'captures_with_rails': sum(r['rail_samples'] > 0 for r in rows),
            'max_peak_fs': maximum(r['peak_fs'] for r in rows),
            'max_contiguous_rail_run_samples': maximum(r['maximum_contiguous_rail_run_samples'] for r in rows),
            'pooled_whole_capture_rms_dbfs': rms_pool(rows), 'pooled_estimated_support_rms_dbfs': rms_pool(rows, support=True),
            'support_defined_captures': sum(present(r.get('support_samples')) and r['support_samples'] > 0 for r in rows),
            'onset_rail_samples_defined_cases_only': sum(r.get('onset_rail_samples') or 0 for r in rows),
            'steady_support_rail_samples_defined_cases_only': sum(r.get('steady_support_rail_samples') or 0 for r in rows),
            'rms_scope': 'Numerical sample-weighted energy over the stated dependent development captures; not calibrated acoustic SPL.'}


def spatial_pool(cases):
    result = {}
    for stream in SPATIAL_STREAMS:
        turns = [turn['streams'][stream] for case in cases for turn in case.get('turns', {}).values() if stream in turn.get('streams', {})]
        whole = [case['whole_capture_availability'][stream] for case in cases]
        seconds = sum(t['support_duration_s'] for t in turns)
        available = sum(t['support_duration_s'] * (t['speech_energy_gated_coverage'] or 0) for t in turns)
        occupancy = sum(t['support_duration_s'] * (t['matching_sector_occupancy'] or 0) for t in turns)
        all_seconds = sum(t['support_duration_s'] for t in whole)
        all_available = sum(t['support_duration_s'] * (t['speech_energy_gated_coverage'] or 0) for t in whole)
        nonspeech = [case['nonspeech_controls']['whole_nonspeech_capture'][stream] for case in cases
                     if 'whole_nonspeech_capture' in case.get('nonspeech_controls', {})]
        control_seconds = sum(t['support_duration_s'] for t in nonspeech)
        control_indicated = sum(t['support_duration_s'] * (t['speech_energy_gated_coverage'] or 0) for t in nonspeech)
        result[stream] = {
            'scored_turns': len(turns), 'summed_turn_support_s': seconds,
            'speech_energy_gated_coverage': available / seconds if seconds else None,
            'matching_sector_occupancy': occupancy / seconds if seconds else None,
            'wrong_sector_duration_s': sum(t.get('wrong_sector_duration_s') or 0 for t in turns),
            'held_wrong_sector_duration_s': sum(t.get('held_wrong_sector_duration_s') or 0 for t in turns),
            'first_hit_censored_turns': sum(t['first_hit_censored'] for t in turns),
            'already_matching_at_onset_turns': sum(t['already_matching_at_onset'] for t in turns),
            'sustained_acquisition_censored_turns': sum(t['sustained_acquisition_censored'] for t in turns),
            'sustained_acquisition_observed_turns': sum(not t['sustained_acquisition_censored'] for t in turns),
            'sustained_acquisition_median_s_observed_only': median(t['sustained_acquisition_s'] for t in turns),
            'off_delay_censored_turns': sum(t['off_delay_censored'] for t in turns),
            'off_delay_median_s_observed_only': median(t['off_delay_s'] for t in turns),
            'whole_capture_spatial_unavailable_s': all_seconds - all_available,
            'whole_capture_spatial_unavailable_fraction': 1 - all_available / all_seconds if all_seconds else None,
            'nonspeech_control_duration_s': control_seconds, 'nonspeech_positive_indication_s': control_indicated,
            'nonspeech_positive_indication_fraction': control_indicated / control_seconds if control_seconds else None,
            'limitation': 'Turn durations sum over dependent and overlapping supports, not unique audio time. Observed-only latency medians retain explicit censored denominators. Host availability is not device reaction latency.'}
    fields = {}
    for name in ('AEC_AZIMUTH_VALUES', 'AEC_SPENERGY_VALUES', 'AUDIO_MGR_SELECTED_AZIMUTHS'):
        values = [case['raw_field_statistics'][name] for case in cases]
        fields[name] = {'received_arrays': sum(v['count'] for v in values),
                        'median_case_receipt_rate_hz': median(v['receipt_rate_hz'] for v in values),
                        'max_receipt_gap_s': maximum(v['receipt_gap_max_s'] for v in values),
                        'gaps_over_age_limit': sum(v['receipt_gaps_above_age_limit'] for v in values),
                        'invalid_transactions': sum(v['invalid_transactions'] for v in values),
                        'nonfinite_or_invalid_values': sum(v['nonfinite_or_invalid_values'] for v in values),
                        'identical_adjacent_arrays': sum(v['identical_adjacent_arrays'] for v in values),
                        'adjacent_comparisons': sum(v['adjacent_comparisons'] for v in values),
                        'nonfinite_note': 'Selected no-speech NaN is a documented missing direction, not automatically a failed transaction. Repeated numeric values do not establish DSP freshness.'}
    return {'streams': result, 'raw_fields': fields,
            'max_callback_availability_gap_s': maximum(c['callback_availability']['max_availability_gap_s'] for c in cases),
            'max_callback_block_span_s': maximum(c['callback_availability']['max_block_span_s'] for c in cases),
            'device_internal_observation_time': 'unknown', 'ground_truth_used_by_live_adapter': False}


def h2_pool(metrics, receipts):
    counters = collections.Counter()
    returns = []; fragments = []; timing_limited = []
    for m in metrics:
        counters.update(m.get('embedding_gate_evidence', {}).get('counts', {}))
        evidence = m['speaker'].get('reference_turn_evidence')
        if evidence:
            returns += [{'case_id': m['case_id'], **row} for row in evidence['returning_participants']]
            fragments += [{'case_id': m['case_id'], **row} for row in evidence['turns']]
        else:
            timing_limited.append(m['case_id'])
    elapsed = sum(r.get('model_wall_s', 0) for r in receipts)
    source_seconds = sum(m['telemetry']['source_duration_sec'] for m in metrics)
    return {'successful_embedding_calls': sum(m['speaker']['embedding_calls_successful'] for m in metrics),
            'embedding_calls_rejected': None, 'gate_counts': dict(counters),
            'gate_scope': 'Reconstructed pre-embedding gates; reasons can overlap. Successful calls are observed decisions, rejected attempted calls are not logged. No unique speaker evidence duration claimed.',
            'returning_participant_cases': returns,
            'returning_cases_consistent_dominant_label': sum(r['consistent'] is True for r in returns),
            'returning_cases_inconsistent_dominant_label': sum(r['consistent'] is False for r in returns),
            'returning_cases_unknown': sum(r['consistent'] is None for r in returns),
            'reference_turns_with_multiple_clusters': sum(r['fragment_count'] > 1 for r in fragments),
            'reference_turns_with_no_embedding_evidence': sum(r['missing_evidence'] for r in fragments),
            'reference_turn_count': len(fragments), 'reference_turn_timing_limited_scene_ids': timing_limited,
            'emitted_final_labels_by_scene': {m['case_id']: m['speaker']['emitted_final_labels'] for m in metrics},
            'reconciliation_status': 'UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE',
            'model_process_wall_s': elapsed, 'audio_duration_s': source_seconds,
            'pooled_offline_process_rtf': elapsed / source_seconds if source_seconds else None,
            'audio_frames_dropped': sum(m['telemetry'].get('audio_frames_dropped', 0) for m in metrics),
            'full_der': None, 'enrolled_name_accuracy': None, 'live_caption_latency': None}


def build_summary(*, partial=False):
    consumed = []; omissions = []
    selection = accepted_cases(partial=partial)
    def consume(path, required=True):
        path = Path(path)
        if not path.is_file():
            if required: omissions.append({'path': str(path), 'reason': 'MISSING'})
            return None
        value = read(path); consumed.append(bind(path)); return value
    manifest = consume(BANK / 'SCENE_MANIFEST.json')
    source_manifest = consume(BANK / 'SOURCE_AND_SPLIT_MANIFEST.json')
    policy = consume(REPORT / 'OUTPUT_LEVEL_POLICY.json')
    spatial_policy = consume(REPORT / 'SPATIAL_SCORING_POLICY.json')
    selection_manifest = consume(SELECTION_PATH, required=not partial)
    contract = consume(REPORT / 'h2/execution_contract.json', required=not partial)
    contract_sha = None
    if contract:
        contract_sha = hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str).encode()).hexdigest()
        try:
            for path, key in ((BANK / 'SCENE_MANIFEST.json', 'scene_manifest_sha256'),
                              (REPORT / 'OUTPUT_LEVEL_POLICY.json', 'output_policy_sha256'),
                              (SELECTION_PATH, 'accepted_capture_selection_sha256')):
                bind(path, contract[key])
            if contract['fixed_host_gain'] != policy['fixed_host_gain']:
                raise ValueError('H2 execution contract fixed gains changed')
            for binding in contract['runner_code']:
                bind(binding['path'], binding['sha256'])
        except (KeyError, ValueError, OSError) as exc:
            omissions.append({'reason': 'H2_EXECUTION_CONTRACT_MISMATCH', 'detail': str(exc)})
    if not manifest or not policy: raise ValueError('Frozen scene manifest and output policy required even for partial aggregation')
    scenes = {s['case_id']: s for s in manifest['scenes']}
    if list(scenes) != CASE_IDS or manifest['canonical_scene_count'] != 24: raise ValueError('Expected exactly canonical S4_01 through S4_24')
    rendered = sum(Path(s['canonical_audio']['path']).is_file() and Path(s['canonical_audio']['path']).stat().st_size == s['canonical_audio']['bytes'] for s in scenes.values())
    if rendered != 24: omissions.append({'reason': 'CANONICAL_RENDER_FILE_COUNT_OR_SIZE', 'observed': rendered, 'expected': 24})
    audio = {}; spatial = {}; captures = {}; metrics = {s: [] for s in OUTPUTS}; receipts = {s: [] for s in OUTPUTS}; rows = []; summary_recoveries = []
    for cid, scene in scenes.items():
        folder = selection[cid]['folder'] if cid in selection else REPORT / 'hardware/final' / cid
        capture_batch = selection[cid]['batch'] if cid in selection else 'final'
        capture = consume(folder / 'case_result.json')
        am = consume(folder / 'audio_metrics.json'); sm = consume(folder / 'spatial_metrics.json')
        valid_capture = bool(capture and capture.get('status') == 'PASS' and capture.get('audio_integrity_status') == 'PASS'
                             and capture.get('final_recipe_capture') is True and capture.get('recipe') == policy['hardware_recipe']
                             and capture.get('input_scene_sha256') == scene['canonical_audio']['sha256']
                             and capture.get('payload', {}).get('status') == 'PASS' and capture.get('framing', {}).get('marker_error_count') == 0)
        if capture and not valid_capture: omissions.append({'case_id': cid, 'reason': 'INVALID_FINAL_CAPTURE'})
        if valid_capture: captures[cid] = capture
        if am and (not valid_capture or am.get('case_id') != cid or am.get('batch') != capture_batch or am.get('input_scene_sha256') != scene['canonical_audio']['sha256']
                   or am.get('converter', {}).get('conversion_status') != 'EXACT_NATIVE_COUNTS'):
            omissions.append({'case_id': cid, 'reason': 'AUDIO_METRICS_IDENTITY_MISMATCH'}); am = None
        if sm and (not valid_capture or sm.get('case_id') != cid or sm.get('batch') != capture_batch or sm.get('hardware_status') != 'PASS'
                   or sm.get('scoring_policy') != spatial_policy):
            omissions.append({'case_id': cid, 'reason': 'SPATIAL_METRICS_IDENTITY_MISMATCH'}); sm = None
        if am: audio[cid] = am
        if sm: spatial[cid] = sm
        speech = [seg for seg in scene['segments'] if seg['kind'] == 'utterance']
        for output in OUTPUTS:
            folder_h2 = REPORT / 'h2' / cid / output
            receipt = consume(folder_h2 / 'run_receipt.json'); hm = consume(folder_h2 / 'metrics.json')
            recovery_row = None
            h2_valid = bool(receipt and hm and valid_capture and receipt.get('status') == 'COMPLETE' and hm.get('state') == 'COMPLETED'
                            and receipt.get('case_id') == cid and receipt.get('stream') == output
                            and hm.get('case_id') == cid and hm.get('stream') == output and not hm.get('failure_events')
                            and contract_sha is not None and receipt.get('identity', {}).get('contract_sha256') == contract_sha
                            and receipt.get('raw_audio', {}).get('sha256') == capture['output_audio'][output]['sha256']
                            and receipt.get('adapter', {}).get('gain_scalar') == policy['fixed_host_gain'][output])
            if h2_valid:
                try:
                    bind(folder_h2 / 'metrics.json', receipt['metrics_binding']['sha256'])
                    reference = ' '.join(s['transcript'] for s in sorted(speech, key=lambda s: s['source_start_sample']))
                    if hm['text']['reference_normalized'] != normalize(reference):
                        raise ValueError('Whole-scene transcript reference changed')
                    recovery_binding = receipt.get('summary_recovery_receipt')
                    if recovery_binding:
                        recovered = consume(recovery_binding['path'])
                        bind(recovery_binding['path'], recovery_binding['sha256'])
                        if not recovered or recovered.get('status') != 'RECOVERED_FROM_COMPLETION_EVIDENCE' or recovered.get('case_id') != cid or recovered.get('stream') != output:
                            raise ValueError('Summary recovery case/status mismatch')
                        if recovered.get('no_model_rerun') is not True or recovered.get('frozen_execution_code_unchanged') is not True:
                            raise ValueError('Summary recovery changed the ordinary-job contract')
                        derived = recovered['derived_summary']
                        if derived['sha256'] != receipt['session_summary_binding']['sha256'] or Path(derived['path']).resolve() != Path(receipt['session_summary_binding']['path']).resolve():
                            raise ValueError('Active session summary is not the bound derived summary')
                        session_summary = consume(derived['path']); bind(derived['path'], derived['sha256'])
                        if session_summary.get('reconstruction_provenance', {}).get('status') != 'DERIVED_FROM_PRIMARY_COMPLETION_EVIDENCE':
                            raise ValueError('Derived summary lacks its explicit provenance marker')
                        if hm['telemetry'] != session_summary['telemetry'] or hm['scientific_policy'] != session_summary['scientific_policy']:
                            raise ValueError('Recovered metrics do not preserve primary telemetry and policy')
                        if receipt.get('error') or receipt.get('ended_utc'):
                            raise ValueError('Recovered active receipt retains a stale failure state')
                        recovery_row = {'case_id': cid, 'stream': output, 'recovery_receipt': bind(recovery_binding['path']),
                                        'derived_summary': derived, 'original_empty_summary': recovered['source_bindings']['original_empty_summary'],
                                        'model_rerun': False}
                except (KeyError, ValueError) as exc:
                    omissions.append({'case_id': cid, 'stream': output, 'reason': 'H2_METRICS_OR_REFERENCE_BINDING_MISMATCH', 'detail': str(exc)}); h2_valid = False
            if h2_valid and scene.get('overlap_scoring_limited') and hm['text']['status'] != 'LIMITED':
                omissions.append({'case_id': cid, 'stream': output, 'reason': 'OVERLAP_MUST_NOT_HAVE_ORDINARY_WER'}); h2_valid = False
            if receipt and hm and not h2_valid: omissions.append({'case_id': cid, 'stream': output, 'reason': 'INVALID_OR_INCOMPATIBLE_H2_EVIDENCE'})
            if h2_valid:
                hm = dict(hm, case_id=cid, stream=output)
                metrics[output].append(hm); receipts[output].append(receipt)
                if recovery_row: summary_recoveries.append(recovery_row)
            else: hm = None
            ar = am['streams'][output] if am else {}
            text = hm['text'] if hm else {}; wc = text.get('word_counts', {}); cc = text.get('character_counts', {})
            gate = hm.get('embedding_gate_evidence', {}).get('counts', {}) if hm else {}
            evidence = hm['speaker'].get('reference_turn_evidence', {}) if hm else {}
            returns = evidence.get('returning_participants', [])
            availability = hm.get('availability', []) if hm else []
            final_times = [r['wall_after_source_started_s'] for r in availability if r['event_type'] == 'transcript_final']
            row = {'case_id': cid, 'title': scene['title'], 'family_id': scene['family_id'], 'stream': output,
                   'accepted_capture_batch': capture_batch,
                   'room': scene['receiver_configuration']['room_table'], 'scheduled_duration_s': scene['duration_s'],
                   'speech_participants': len(scene['cast']), 'scheduled_speech_utterances': len(speech),
                   'overlap_scoring_limited': bool(scene.get('overlap_scoring_limited')), 'capture_valid': valid_capture,
                   'audio_analysis_present': bool(am), 'spatial_analysis_present': bool(sm), 'H2_complete_valid': h2_valid,
                   'fixed_host_gain': policy['fixed_host_gain'][output], 'raw_peak_fs': ar.get('peak_fs'),
                   'raw_rms_dbfs': ar.get('rms_dbfs'), 'raw_support_rms_dbfs': ar.get('support_rms_dbfs'),
                   'raw_samples': ar.get('sample_count'), 'raw_rail_samples': ar.get('rail_samples'),
                   'raw_longest_rail_run_samples': ar.get('maximum_contiguous_rail_run_samples'),
                   'raw_onset_rails': ar.get('onset_rail_samples'), 'raw_steady_support_rails': ar.get('steady_support_rail_samples'),
                   'output_delay_median_samples': ar.get('relative_delay_median_samples'),
                   'adapter_peak_fs': receipt.get('adapter', {}).get('peak_fs') if receipt else None,
                   'text_status': text.get('status'), 'wer': text.get('wer'), 'cer': text.get('cer'),
                   'word_substitutions': wc.get('substitutions'), 'word_deletions': wc.get('deletions'), 'word_insertions': wc.get('insertions'),
                   'reference_words': wc.get('reference_words'), 'hypothesis_words': wc.get('hypothesis_words'),
                   'character_substitutions': cc.get('substitutions'), 'character_deletions': cc.get('deletions'), 'character_insertions': cc.get('insertions'),
                   'reference_characters': cc.get('reference_characters'), 'empty_reference_insertions': text.get('empty_reference_insertions'),
                   'empty_reference_words_per_minute': text.get('empty_reference_words_per_minute'),
                   'first_text_wall_after_offline_source_s': min((r['wall_after_source_started_s'] for r in availability if present(r['wall_after_source_started_s'])), default=None),
                   'last_final_text_wall_after_offline_source_s': maximum(final_times),
                   'model_process_wall_s': receipt.get('model_wall_s') if receipt else None, 'offline_session_rtf': hm.get('offline_rtf') if hm else None,
                   'emitted_final_speaker_labels': hm['speaker']['emitted_final_labels'] if hm else None,
                   'reconciled_speaker_labels': None, 'returning_dominant_label_consistency': [r['consistent'] for r in returns] if hm else None,
                   'turns_with_multiple_clusters': sum(r['fragment_count'] > 1 for r in evidence.get('turns', [])) if hm else None,
                   'successful_embedding_calls': hm['speaker']['embedding_calls_successful'] if hm else None,
                   'embedding_rejected_calls': None, 'eligible_embedding_hops': gate.get('eligible_hops_reconstructed'),
                   'single_speech_hops': gate.get('single_speech_hops'), 'single_speech_hops_below_rms': gate.get('single_speech_hops_below_rms')}
            for stream in ('selected_processed', 'raw_auto'):
                whole = sm['whole_capture_availability'][stream] if sm else {}
                turns = [t['streams'][stream] for t in sm.get('turns', {}).values() if stream in t.get('streams', {})] if sm else []
                row.update({stream + '_whole_capture_unavailable_fraction': whole.get('spatial_unavailable_fraction'),
                            stream + '_scored_turns': len(turns) if sm else None,
                            stream + '_sustained_censored_turns': sum(t['sustained_acquisition_censored'] for t in turns) if sm else None})
            rows.append(row)
    repeats = []
    for batch in REPEAT_BATCHES:
        folder = REPORT / 'hardware' / batch / 'S4_01'
        capture = consume(folder / 'case_result.json'); am = consume(folder / 'audio_metrics.json'); sm = consume(folder / 'spatial_metrics.json')
        valid = bool(capture and capture.get('status') == 'PASS' and capture.get('final_recipe_capture') is True
                     and capture.get('audio_integrity_status') == 'PASS' and capture.get('payload', {}).get('status') == 'PASS'
                     and capture.get('framing', {}).get('marker_error_count') == 0
                     and capture.get('recipe') == policy['hardware_recipe'] and capture.get('input_scene_sha256') == scenes['S4_01']['canonical_audio']['sha256'])
        if capture and not valid: omissions.append({'batch': batch, 'reason': 'INVALID_REPEAT_CAPTURE'})
        if am and (am.get('case_id') != 'S4_01' or am.get('batch') != batch or am.get('input_scene_sha256') != scenes['S4_01']['canonical_audio']['sha256']):
            omissions.append({'batch': batch, 'reason': 'INVALID_REPEAT_AUDIO_METRICS'}); am = None
        if sm and (sm.get('case_id') != 'S4_01' or sm.get('batch') != batch or sm.get('scoring_policy') != spatial_policy):
            omissions.append({'batch': batch, 'reason': 'INVALID_REPEAT_SPATIAL_METRICS'}); sm = None
        repeats.append({'batch': batch, 'case_id': 'S4_01', 'valid_capture': valid, 'analyzed': bool(valid and am and sm),
                        'audio': am.get('streams') if am else None, 'spatial': spatial_pool([sm]) if sm else None})
    text_summary = {o: text_pool(metrics[o]) for o in OUTPUTS}
    common = sorted(set(text_summary['O0']['nonoverlap_scored_scene_ids']) & set(text_summary['O1']['nonoverlap_scored_scene_ids']))
    audio_summary = {}
    for output in OUTPUTS:
        audio_summary[output] = {'all_final_captures': audio_pool([r['streams'][output] for r in audio.values()]),
                                'speech_captures': audio_pool([r['streams'][output] for cid, r in audio.items() if scenes[cid]['cast']]),
                                'nonspeech_controls': audio_pool([r['streams'][output] for cid, r in audio.items() if not scenes[cid]['cast']]),
                                'fixed_host_gain': policy['fixed_host_gain'][output],
                                'max_adapted_peak_fs': maximum(r['adapter']['peak_fs'] for r in receipts[output])}
    paired = [cid for cid in CASE_IDS if all(any(m['case_id'] == cid for m in metrics[o]) for o in OUTPUTS)]
    counts = {'planned_scenes': 24, 'rendered_scenes': rendered, 'valid_final_captures': len(captures),
              'audio_analyzed_final_scenes': len(audio), 'spatial_analyzed_final_scenes': len(spatial),
              'planned_ordinary_H2_jobs': 48, 'complete_valid_H2_jobs': sum(map(len, metrics.values())),
              'complete_H2_pairs': len(paired), 'fully_analyzed_final_scenes': sum(cid in audio and cid in spatial for cid in paired),
              'planned_nominal_repeat_attempts': 2, 'valid_nominal_repeats': sum(r['valid_capture'] for r in repeats),
              'analyzed_nominal_repeats': sum(r['analyzed'] for r in repeats)}
    complete = not omissions and counts['fully_analyzed_final_scenes'] == 24 and counts['analyzed_nominal_repeats'] == 2
    summary = {'schema': 'jp_s4_summary_v1', 'run_id': RUN_ID, 'aggregated_utc': now(),
               'status': 'PARTIAL' if partial else 'COMPLETE_EVIDENCE_COUNTS' if complete else 'INCOMPLETE',
               'counts': counts, 'omissions': omissions, 'text_by_output': text_summary,
               'accepted_capture_batches': {cid: row['batch'] for cid, row in selection.items()},
               'excluded_attempts': selection_manifest.get('excluded_attempts', []) if selection_manifest else [],
               'paired_nonoverlap_scene_ids': common,
               'paired_weighted_text': {o: text_pool([m for m in metrics[o] if m['case_id'] in common]) for o in OUTPUTS},
               'audio_by_output': audio_summary, 'H2_by_output': {o: h2_pool(metrics[o], receipts[o]) for o in OUTPUTS},
               'spatial_final_bank': spatial_pool(list(spatial.values())), 'nominal_repeats_excluded_from_bank_totals': repeats,
               'output_level_policy': policy, 'source_cohort': source_manifest.get('actual_S4_contribution') if source_manifest else None,
               'summary_export_evidence': {'native_runtime_summary_count': counts['complete_valid_H2_jobs'] - len(summary_recoveries),
                                           'derived_completion_evidence_summary_count': len(summary_recoveries),
                                           'derived_summaries': summary_recoveries,
                                           'scope': 'Explicitly derived summaries preserve original empty files and completed-job primary evidence. No model rerun or original H2 export-race fix.'},
               'no_output_accuracy_winner': True, 'no_full_DER': True, 'no_enrolled_name_accuracy': True,
               'population_confidence_intervals': None, 'S6_fusion_benefit_established': False,
               'limitations': ['Dependent development scenes and matched variants do not form independent population samples.',
                              'WER/CER use complete normalized transcripts only for nonoverlap; overlap scenes including 20 are LIMITED.',
                              'Empty-reference controls report insertions and words per minute, with undefined WER/CER.',
                              'Manual source-angle +/-5 degrees is label uncertainty, never a device acceptance threshold.',
                              'Spatial timing uses measured host receipt and callback availability; internal DSP observation time remains unknown.',
                              'Missing spatial observations permit audio/text to continue; beam IDs are not participant IDs.',
                              'Rejected embedding-call counts and final label reconciliation are unavailable in the unchanged baseline.',
                              'Process RTF and event wall availability from accelerated files are not live caption latency.',
                              'Raw O1 saturation remains a limited output condition; no saved-WAV attenuation repair is claimed.'],
               'consumed_json_bindings': consumed, 'analysis_code': bind(Path(__file__))}
    write_csv(REPORT / 'per_case_metrics.csv', rows)
    save(REPORT / 'summary_metrics.json', summary)
    if not partial and not complete:
        raise RuntimeError('Mandatory S4 aggregation evidence incomplete; summary_metrics.json lists omissions. Use --partial only for explicitly partial inspection.')
    return summary


class SummaryTests(unittest.TestCase):
    def test_weighted_edits_not_average_case_wer(self):
        def row(cid, errors, words):
            counts = {'errors': errors, 'substitutions': errors, 'deletions': 0, 'insertions': 0, 'reference_words': words, 'hypothesis_words': words}
            chars = {k.replace('words', 'characters'): v for k, v in counts.items()}
            return {'case_id': cid, 'text': {'status': 'SCORED', 'word_counts': counts, 'character_counts': chars}}
        result = text_pool([row('a', 1, 1), row('b', 0, 9)])
        self.assertEqual(result['pooled_wer'], .1)
        self.assertEqual(result['word_counts']['reference_words'], 10)

    def test_empty_reference_is_separate_and_duration_weighted(self):
        rows = [{'case_id': 'a', 'text': {'status': 'EMPTY_REFERENCE', 'duration_s': 10, 'empty_reference_insertions': 2}},
                {'case_id': 'b', 'text': {'status': 'EMPTY_REFERENCE', 'duration_s': 50, 'empty_reference_insertions': 1}},
                {'case_id': 'c', 'text': {'status': 'LIMITED'}}]
        result = text_pool(rows)
        self.assertIsNone(result['pooled_wer']); self.assertEqual(result['empty_reference_words_per_minute'], 3)
        self.assertEqual(result['overlap_or_invalid_transcript_limited_scene_ids'], ['c'])

    def test_rms_is_energy_weighted_not_db_mean(self):
        result = rms_pool([{'sample_count': 1, 'rms_dbfs': 0}, {'sample_count': 1, 'rms_dbfs': -20}])
        self.assertAlmostEqual(result, 10 * math.log10(.505))

    def test_empty_spatial_keeps_unknown_denominators(self):
        result = spatial_pool([])
        self.assertIsNone(result['streams']['raw_auto']['matching_sector_occupancy'])
        self.assertIsNone(result['streams']['selected_processed']['sustained_acquisition_median_s_observed_only'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SummaryTests))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    summary = build_summary(partial=args.partial)
    print(json.dumps({'status': summary['status'], 'counts': summary['counts'], 'omissions': len(summary['omissions'])}, indent=2))
