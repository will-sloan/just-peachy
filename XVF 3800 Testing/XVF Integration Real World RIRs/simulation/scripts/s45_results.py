"""Read-only S4.5 results aggregation and four bounded plots. README_S45_RESULTS.md."""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import statistics
import string

from s45_common import BANK, REPORT, RUN_ID, SIM, bind, now, read, save
from s45_coverage import (CoverageError, compact_binding, json_snapshot, require, write_csv)

OUTPUTS = ('O0', 'O1')
INTENDED = {'canonical_scenes': 240, 'development_scenes': 180, 'reserve_scenes': 60,
            'sentinel_scenes': 24, 'output_H2_jobs': 48, 'maximum_dry_jobs': 24}
WORD_KEYS = ('substitutions', 'deletions', 'insertions', 'errors', 'reference_words', 'hypothesis_words')
CHAR_KEYS = ('substitutions', 'deletions', 'insertions', 'errors', 'reference_characters', 'hypothesis_characters')
LIMITS = [
    'No final O0/O1 accuracy winner, population confidence interval, age/accent causal effect, full DER, enrolled-name accuracy or fusion benefit is established.',
    'Reserve rows contain only coverage, raw levels and integrity. Reserve spatial, transcript, identity and H2 task results are never opened.',
    'Matched conditions, shared voices/utterances/prompts/books/noise parents/RIRs are dependent. Scene and embedding-window counts are not independent population observations.',
    'Spatial timing is causal host receipt/copy-completion availability on estimated activity, not calibrated acoustic or internal DSP latency. Identical values do not prove stale DSP.',
    'Whole mixed-output WER is pooled only with complete all-speaker references and no scheduled overlap. Overlap and uncertain ambient speech remain LIMITED.',
    'Dry source controls describe a source-domain ASR floor. Multi-turn processed scene WER is not a paired single-source treatment effect.',
    'Embedding decisions use overlapping windows; missing decisions do not identify rejected embed calls. Anonymous-label continuity is not diarization error rate or name recognition.',
]


def stable_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str).encode()).hexdigest()


def normalize(value):
    return ' '.join(str(value or '').lower().translate(str.maketrans('', '', string.punctuation)).split())


def edit_distance(left, right):
    row = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        next_row = [i]
        for j, b in enumerate(right, 1):
            next_row.append(min(row[j] + 1, next_row[-1] + 1, row[j - 1] + (a != b)))
        row = next_row
    return row[-1]


def verified_json(binding, consumed):
    actual = compact_binding(bind(binding['path'], binding['sha256']))
    consumed[(actual['path'], actual['sha256'])] = actual
    return read(actual['path'])


def snapshot(path, consumed):
    document, binding = json_snapshot(path)
    consumed[(binding['path'], binding['sha256'])] = binding
    return document, binding


def finite_ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def text_eligibility(scene):
    if scene['split'] != 'development':
        return 'PROHIBITED_RESERVE'
    if not scene.get('transcript_valid') or not scene.get('all_speaker_reference_complete'):
        return 'LIMITED_UNKNOWN_AMBIENT_REFERENCE'
    if scene.get('overlap_intervals') or scene.get('overlap_scoring_limited'):
        return 'LIMITED_SCHEDULED_OVERLAP'
    return 'NONOVERLAP_COMPLETE_REFERENCE' if any(s['kind'] == 'utterance' for s in scene['segments']) else 'STRICT_EMPTY_REFERENCE'


def validate_text(scene, metrics):
    eligibility = text_eligibility(scene)
    require(eligibility != 'PROHIBITED_RESERVE', 'Attempt to score reserve text')
    text = metrics['text']
    if eligibility.startswith('LIMITED'):
        require(text['status'] == 'LIMITED' and text.get('wer') is None and text.get('cer') is None, 'Limited text must not have ordinary WER/CER')
        return eligibility
    reference = normalize(' '.join(s['transcript'] for s in sorted(scene['segments'], key=lambda r: r['source_start_sample']) if s['kind'] == 'utterance'))
    require(text['reference_normalized'] == reference, 'Text reference does not match canonical whole utterances')
    hypothesis = text['hypothesis_normalized']
    require(normalize(hypothesis) == hypothesis, 'Hypothesis uses a different normalization')
    words = text['word_counts']
    require(words['reference_words'] == len(reference.split()) and words['hypothesis_words'] == len(hypothesis.split()), 'Word denominator differs')
    require(words['errors'] == sum(words[k] for k in ('substitutions', 'deletions', 'insertions')) == edit_distance(reference.split(), hypothesis.split()), 'Raw word edit counts differ')
    characters = text['character_counts']
    require(characters['reference_characters'] == len(reference.replace(' ', '')), 'Character denominator differs')
    require(characters['hypothesis_characters'] == len(hypothesis.replace(' ', '')), 'Hypothesis character count differs')
    require(characters['errors'] == sum(characters[k] for k in ('substitutions', 'deletions', 'insertions')) == edit_distance(reference.replace(' ', ''), hypothesis.replace(' ', '')), 'Character edit counts differ')
    if reference:
        require(text['status'] == 'SCORED' and math.isclose(text['wer'], words['errors'] / words['reference_words'], rel_tol=1e-12, abs_tol=1e-12), 'WER value differs')
        require(math.isclose(text['cer'], characters['errors'] / characters['reference_characters'], rel_tol=1e-12, abs_tol=1e-12), 'CER value differs')
    else:
        require(text['status'] == 'EMPTY_REFERENCE' and text['wer'] is None and text['cer'] is None, 'Empty reference has invented WER/CER')
    return eligibility


def pool_text(jobs):
    """Keep raw denominators; never average scene WER or pool LIMITED targets."""
    groups = collections.defaultdict(list)
    for job in jobs:
        if job['status'] != 'COMPLETE_NATIVE' or job['text_eligibility'] != 'NONOVERLAP_COMPLETE_REFERENCE':
            continue
        strata = job['metrics'].get('source_strata', [])
        require(strata and len({s['dataset'] for s in strata}) == 1, 'Ordinary corpus WER requires one source corpus per scene')
        qualities = sorted({str(s['quality_partition']) for s in strata})
        quality = qualities[0] if len(qualities) == 1 else 'MIXED: ' + ' + '.join(qualities)
        groups[(job['stream'], strata[0]['dataset'], quality)].append(job)
    result = []
    for (output, dataset, quality), rows in sorted(groups.items()):
        total = {k: sum(j['metrics']['text']['word_counts'].get(k, 0) for j in rows) for k in WORD_KEYS}
        char_total = {k: sum(j['metrics']['text']['character_counts'][k] for j in rows) for k in CHAR_KEYS}
        result.append({'output': output, 'dataset': dataset, 'quality_partition': quality, 'jobs': len(rows),
                       'case_ids': [j['case_id'] for j in rows], **total, 'wer': finite_ratio(total['errors'], total['reference_words']),
                       'character_counts': char_total, 'cer': finite_ratio(char_total['errors'], char_total['reference_characters'])})
    by_output = []
    for output in sorted({r['output'] for r in result}):
        rows = [r for r in result if r['output'] == output]
        total = {k: sum(r[k] for r in rows) for k in WORD_KEYS}
        char_total = {k: sum(r['character_counts'][k] for r in rows) for k in CHAR_KEYS}
        by_output.append({'output': output, 'jobs': sum(r['jobs'] for r in rows), **total, 'wer': finite_ratio(total['errors'], total['reference_words']),
                          'character_counts': char_total, 'cer': finite_ratio(char_total['errors'], char_total['reference_characters'])})
    return {'by_output_corpus_quality': result, 'by_output': by_output, 'denominator': 'Sum reference words in eligible COMPLETE native jobs; dependent descriptive evidence, not mean scene WER. Mixed-quality scenes form their own category and are counted once.'}


def transport_summary(receipts):
    result = {'accepted_cases': len(receipts), 'native_48k_stereo_frames': 0, 'native_scalar_samples': 0,
              'decoded_16k_six_channel_frames': 0, 'decoded_scalar_samples': 0, 'compared_diagnostic_mic_samples': 0,
              'exact_payload_mismatches': 0, 'marker_errors': 0, 'startup_native_frames_excluded': 0,
              'boundary_source_frames_omitted_nonsilent_only': 0, 'silent_alignment_unidentifiable_cases': 0,
              'all_active_payload_complete_nonsilent_cases': 0, 'per_mic_max_abs_error_counts_nonsilent': [None] * 4}
    for receipt in receipts:
        framing, payload = receipt['framing'], receipt['payload']
        require(payload['status'] == 'PASS' and framing['marker_error_count'] == 0, 'Accepted raw transport failed')
        result['native_48k_stereo_frames'] += framing['native_frames']
        result['decoded_16k_six_channel_frames'] += framing['decoded_frames']
        result['compared_diagnostic_mic_samples'] += payload['compared_mic_samples']
        result['exact_payload_mismatches'] += payload['payload_mismatches']
        result['marker_errors'] += framing['marker_error_count']
        result['startup_native_frames_excluded'] += framing['startup_frames_excluded']
        if payload.get('capture_minus_source_offset_samples') is None:
            require(payload.get('alignment_status') == 'UNIDENTIFIABLE_ALL_ZERO_INPUT', 'Unknown alignment lacks silent-input qualification')
            result['silent_alignment_unidentifiable_cases'] += 1
        else:
            require(payload['all_nonzero_source_payload_captured'], 'Incomplete active payload accepted')
            result['all_active_payload_complete_nonsilent_cases'] += 1
            result['boundary_source_frames_omitted_nonsilent_only'] += payload['boundary_source_frames_omitted']
            for index, error in enumerate(payload['per_mic_max_abs_error_counts']):
                prior = result['per_mic_max_abs_error_counts_nonsilent'][index]
                result['per_mic_max_abs_error_counts_nonsilent'][index] = error if prior is None else max(prior, error)
    result['native_scalar_samples'] = result['native_48k_stereo_frames'] * 2
    result['decoded_scalar_samples'] = result['decoded_16k_six_channel_frames'] * 6
    result['scope'] = 'Verified accepted receipt counts. Exact recaptured four-mic payload equality preserves channel relations; inactive boundary padding can be outside comparison. All-zero input cannot identify a unique delay.'
    return result


def level_summary(audio_rows):
    result = []
    for partition in ('all', 'development', 'reserve', 'optional_reference'):
        selected = [r for r in audio_rows if partition == 'all' and r['split'] != 'optional_reference' or r['split'] == partition]
        for output in OUTPUTS:
            rows = [r['audio']['streams'][output] for r in selected]
            samples, rails = sum(r['sample_count'] for r in rows), sum(r['rail_samples'] for r in rows)
            result.append({'split': partition, 'output': output, 'analyzed_cases': len(rows), 'sample_count': samples,
                           'rail_samples': rails, 'rail_fraction': finite_ratio(rails, samples), 'rail_runs': sum(r['rail_runs'] for r in rows),
                           'max_contiguous_rail_run_samples': max((r['maximum_contiguous_rail_run_samples'] for r in rows), default=None),
                           'max_peak_fs': max((r['peak_fs'] for r in rows), default=None),
                           'saved_vs_native_count_mismatches': sum(r['audio']['converter']['outputs'][output]['mismatched_saved_vs_native_counts'] for r in selected),
                           'task_use_gate_counts': dict(collections.Counter(r['gates'].get(output, 'REFERENCE_NOT_SCORED') for r in selected))})
    return result


def spatial_summary(rows):
    primary = collections.defaultdict(list)
    fields = collections.defaultdict(list)
    omitted = collections.Counter()
    total_turns = 0
    returns = collections.defaultdict(list)
    for case in rows:
        scene, spatial = case['scene'], case['spatial']
        require(scene['split'] == 'development', 'Reserve spatial metric read is prohibited')
        for name, field in spatial['raw_field_statistics'].items():
            fields[name].append(field)
        seen = set()
        segment_lookup = {s['utterance_label']: s for s in scene['segments'] if s['kind'] == 'utterance'}
        for label, turn in spatial['turns'].items():
            total_turns += 1
            require(label in segment_lookup, 'Spatial utterance label mismatch')
            if turn['status'] != 'DESCRIPTIVE_NOMINAL_GEOMETRY' or not scene.get('all_speaker_reference_complete'):
                omitted[turn['status'] if scene.get('all_speaker_reference_complete') else 'LIMITED_UNKNOWN_AMBIENT_REFERENCE'] += 1
                continue
            participant = segment_lookup[label]['speaker_key']
            returning = participant in seen
            seen.add(participant)
            for stream, row in turn['streams'].items():
                primary[stream].append(row)
                if returning:
                    returns[stream].append(row)
    result = []
    for stream, entries in sorted(primary.items()):
        support = sum(r['support_duration_s'] for r in entries)
        def weighted(key):
            valid = [r for r in entries if r.get(key) is not None]
            denominator = sum(r['support_duration_s'] for r in valid)
            return finite_ratio(sum(r[key] * r['support_duration_s'] for r in valid), denominator)
        acquire = [r['sustained_acquisition_s'] for r in entries if r.get('sustained_acquisition_s') is not None]
        return_rows = returns[stream]
        result.append({'stream': stream, 'turns': len(entries), 'support_duration_s': support,
                       'angle_only_coverage': weighted('angle_only_coverage'), 'speech_energy_gated_coverage': weighted('speech_energy_gated_coverage'),
                       'matching_sector_occupancy': weighted('matching_sector_occupancy'),
                       'wrong_sector_duration_s': sum(r['wrong_sector_duration_s'] or 0 for r in entries),
                       'held_wrong_sector_duration_s': sum(r['held_wrong_sector_duration_s'] or 0 for r in entries),
                       'already_matching_at_onset': sum(r['already_matching_at_onset'] for r in entries),
                       'sustained_acquired_turns': len(acquire), 'sustained_censored_turns': sum(r['sustained_acquisition_censored'] for r in entries),
                       'sustained_acquisition_median_s_acquired_only': statistics.median(acquire) if acquire else None,
                       'returning_turns': len(return_rows), 'returning_turns_sustained_acquired': sum(not r['sustained_acquisition_censored'] for r in return_rows),
                       'off_delay_censored_turns': sum(r['off_delay_censored'] for r in entries)})
    return {'development_cases_analyzed': len(rows), 'all_scheduled_turns_in_metrics': total_turns, 'limited_or_unavailable_turns_excluded_from_primary': dict(omitted),
            'primary_nonoverlap_complete_reference_by_stream': result,
            'raw_field_health': {name: {'transactions': sum(r['count'] for r in values),
                                       'invalid_transactions': sum(r['invalid_transactions'] for r in values),
                                       'nonfinite_or_invalid_values': sum(r['nonfinite_or_invalid_values'] for r in values),
                                       'receipt_gaps_above_250ms': sum(r['receipt_gaps_above_age_limit'] for r in values),
                                       'largest_receipt_gap_s': max((r['receipt_gap_max_s'] for r in values if r['receipt_gap_max_s'] is not None), default=None),
                                       'identical_adjacent_arrays': sum(r['identical_adjacent_arrays'] for r in values),
                                       'adjacent_comparisons': sum(r['adjacent_comparisons'] for r in values)} for name, values in fields.items()},
            'return_scope': 'Later scheduled turns by a previously present participant, evaluated as cue availability/acquisition. This is not beam-to-person identity tracking.',
            'timing_and_staleness_limits': LIMITS[3], 'censoring': 'Never-acquired and unobserved off transitions stay censored; acquired-only latency excludes censored turns explicitly.'}


def embedding_summary(jobs):
    result = []
    for stream in sorted({j['stream'] for j in jobs}):
        valid = [j for j in jobs if j['stream'] == stream and j['status'] == 'COMPLETE_NATIVE']
        gate = collections.Counter()
        turns, returning, supported_jobs = [], [], 0
        label_rows = []
        for job in valid:
            gate.update(job['metrics'].get('embedding_gate_evidence', {}).get('counts', {}))
            evidence = job['metrics']['speaker'].get('reference_turn_evidence')
            if evidence:
                supported_jobs += 1
                turns += evidence['turns']
                returning += evidence['returning_participants']
            speaker = job['metrics']['speaker']
            decisions = speaker.get('decision_label_counts')
            decision_switches = speaker.get('decision_label_switches')
            finals = speaker.get('emitted_final_labels')
            decision_available = decisions is not None and decision_switches is not None
            if decision_available:
                require(sum(decisions.values()) == speaker['embedding_calls_successful'], 'Decision-label count differs from successful embedding calls')
            if finals is not None and 'final_transcripts' in job['metrics']:
                require(finals == [row['speaker'] for row in job['metrics']['final_transcripts']], 'Emitted final-label list differs from final transcript records')
            label_rows.append({'case_id': job['case_id'],
                               'decision_label_counts': decisions if decision_available else None,
                               'decision_label_switches': decision_switches if decision_available else None,
                               'emitted_final_label_counts': dict(collections.Counter(finals)) if finals is not None else None,
                               'emitted_final_label_switches': sum(a != b for a, b in zip(finals, finals[1:])) if finals is not None else None,
                               'reconciliation_status': speaker.get('reconciliation_status', 'UNAVAILABLE_METRIC_FIELD'),
                               'reconciled_labels_available': speaker.get('reconciled_labels') is not None})
        def label_fragmentation(count_key, switch_key):
            supported = [r for r in label_rows if r[count_key] is not None]
            return {'jobs_with_label_evidence': len(supported), 'jobs_without_label_evidence': len(valid) - len(supported),
                    'observations_in_supported_jobs': sum(sum(r[count_key].values()) for r in supported),
                    'sum_within_job_distinct_labels': sum(len(r[count_key]) for r in supported),
                    'within_job_label_switches': sum(r[switch_key] for r in supported),
                    'jobs_with_multiple_labels': sum(len(r[count_key]) > 1 for r in supported)}
        result.append({'output': stream, 'native_jobs': len(valid),
                       'successful_embedding_calls': sum(j['metrics']['speaker']['embedding_calls_successful'] for j in valid),
                       'rejected_embedding_calls': None, 'gate_counts': dict(gate), 'reference_supported_turns': len(turns),
                       'reference_turn_evidence_jobs': supported_jobs, 'reference_turn_evidence_unavailable_jobs': len(valid) - supported_jobs,
                       'turns_missing_decision_evidence': sum(t['missing_evidence'] for t in turns),
                       'turns_with_multiple_anonymous_labels': sum(t['fragment_count'] > 1 for t in turns),
                       'within_turn_label_switches': sum(t['label_switches'] for t in turns),
                       'returning_participant_groups': len(returning), 'consistent_return_groups': sum(r['consistent'] is True for r in returning),
                       'inconsistent_return_groups': sum(r['consistent'] is False for r in returning),
                       'return_groups_without_complete_dominant_label_evidence': sum(r['consistent'] is None for r in returning),
                       'decision_label_fragmentation': label_fragmentation('decision_label_counts', 'decision_label_switches'),
                       'emitted_final_label_fragmentation': label_fragmentation('emitted_final_label_counts', 'emitted_final_label_switches'),
                       'label_evidence_by_job': label_rows,
                       'reconciled_cluster_lineage': {
                           'status_counts': dict(collections.Counter(r['reconciliation_status'] for r in label_rows)),
                           'reconciled_labels_available_jobs': sum(r['reconciled_labels_available'] for r in label_rows),
                           'underlying_cluster_fragmentation': None}})
    return {'by_output': result, 'scope': LIMITS[6], 'full_DER': None, 'enrolled_name_accuracy': None,
            'label_fragmentation_scope': 'Decision observations are successful anonymous embedding decisions across the whole native session. Emitted observations are final-transcript speaker snapshots in journal order. Counts and switches are computed within each fresh job; label strings are never identities shared across jobs, and switches can reflect actual speaker changes rather than errors.',
            'reference_return_scope': 'Existing reference-turn counts use fully contained single-source file-support embedding windows. Repeated participant groups require a dominant label for every scheduled turn; missing or tied evidence remains unknown. Eligible exclusive portions of overlap scenes can contribute; these are not all-speaker overlap scores.',
            'reconciled_lineage_scope': 'The unchanged edge baseline records UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE and no reconciled labels. Decision labels and emitted snapshots do not recover unlogged cluster merges, retrospective lineage or underlying-cluster fragmentation; that quantity remains null.'}


def load_capture_analysis(path, accepted, scenes, consumed, reference=False):
    if not path.exists():
        return [], []
    document, _ = snapshot(path, consumed)
    require(document.get('reserve_task_scored', False) is False, 'Capture analysis claims reserve task scoring')
    audio_rows, spatial_rows, seen = [], [], set()
    for row in document['cases']:
        cid = row['case_id']
        require(cid in accepted and cid in scenes and cid not in seen, 'Analysis case not authoritative/unique')
        seen.add(cid)
        selection = accepted[cid]
        require(row['case_result']['sha256'] == selection['case_result_binding']['sha256'], 'Analysis points to different capture')
        scene = scenes[cid]
        if scene['split'] == 'reserve' or reference:
            # Gate BEFORE opening any spatial/H2 artifacts or interpreting source truth.
            require(row.get('spatial_metrics') is None, 'Forbidden reserve/reference spatial analysis pointer')
        audio = verified_json(row['audio_metrics'], consumed)
        require(audio['case_id'] == cid, 'Audio metrics case mismatch')
        for output in OUTPUTS:
            require(audio['converter']['outputs'][output]['mismatched_saved_vs_native_counts'] == 0, 'Saved audio differs from native counts')
            require(audio['streams'][output]['sample_count'] == selection['receipt']['framing']['decoded_frames'], 'Level sample denominator differs')
        if scene['split'] == 'reserve':
            require(audio['task_scoring'] == 'PROHIBITED_RESERVE' and audio['output_alignment'] is None, 'Reserve task/alignments present')
        elif reference:
            require(audio['task_scoring'] == 'PROHIBITED_REFERENCE' and audio['output_alignment'] is None, 'Optional reference task/alignments present')
        elif not reference:
            require(audio['input_scene_sha256'] == scene['canonical_audio']['sha256'] and audio['input_payload'] == selection['receipt']['payload'], 'Development audio input join differs')
        audio_rows.append({'case_id': cid, 'split': 'optional_reference' if reference else scene['split'], 'audio': audio,
                           'gates': row.get('task_use_by_output', {}), 'binding': row['audio_metrics']})
        if not reference and scene['split'] == 'development' and row.get('spatial_metrics'):
            spatial = verified_json(row['spatial_metrics'], consumed)
            require(spatial['case_id'] == cid and spatial['hardware_status'] == 'PASS' and spatial['telemetry_status'] == 'PASS', 'Spatial capture join failed')
            require(any(b['sha256'] == selection['case_result_binding']['sha256'] for b in spatial['bindings']), 'Spatial analysis not bound to accepted case')
            spatial_rows.append({'scene': scene, 'spatial': spatial})
    require(document.get('count', len(seen)) == len(seen), 'Analysis index count mismatch')
    return audio_rows, spatial_rows


def load_accepted(path, manifest, manifest_binding, consumed, reference=False):
    if not path.exists():
        return {}
    document, _ = snapshot(path, consumed)
    source = document.get('reference_scene_manifest', document.get('scene_manifest'))
    require(source and source['sha256'] == manifest_binding['sha256'], 'Acceptance manifest source changed')
    scenes = {s['case_id']: s for s in manifest['scenes']}
    accepted = {}
    for row in document['accepted']:
        cid = row['case_id']
        require(cid in scenes and cid not in accepted, 'Unknown/duplicate accepted case')
        receipt = verified_json(row['case_result'], consumed)
        require(receipt['case_id'] == cid and receipt['status'] == 'PASS' and receipt['audio_integrity_status'] == 'PASS' and receipt['telemetry_status'] == 'PASS', 'Accepted capture gate failed')
        require(receipt['input_scene_sha256'] == row['input_scene_sha256'] == scenes[cid]['canonical_audio']['sha256'], 'Accepted canonical hash differs')
        require(receipt['final_recipe_capture'] and not receipt.get('reserve_task_scored'), 'Accepted recipe/reserve marker differs')
        if not reference:
            require(row['split'] == scenes[cid]['split'] and row['task_scoring_allowed'] == (scenes[cid]['split'] == 'development'), 'Accepted split differs')
        accepted[cid] = {'receipt': receipt, 'row': row, 'case_result_binding': row['case_result']}
    require(document['accepted_count'] == len(accepted), 'Accepted count differs')
    return accepted


def validate_native_job(receipt, metrics, scene, stream, contract, selected, policy, consumed, control=None):
    kind = 'dry' if control else 'outputs'
    require(receipt['case_id'] == scene['case_id'] and receipt['stream'] == stream and receipt['kind'] == kind, 'H2 job case/stream differs')
    require(receipt['identity']['contract_sha256'] == stable_hash(contract) and receipt['job_key'] == stable_hash(receipt['identity']), 'H2 execution identity differs')
    expected_gain = control['fixed_gain_scalar'] if control else policy['fixed_host_gain'][stream]
    require(receipt['identity']['gain_scalar'] == expected_gain == metrics['fixed_host_gain'], 'Frozen host/source gain differs')
    expected_raw = control['source']['decoded_16k_binding']['sha256'] if control else selected['receipt']['output_audio'][stream]['sha256']
    require(receipt['raw_audio']['sha256'] == receipt['identity']['raw_audio_sha256'] == expected_raw, 'H2 raw input hash differs')
    if not control:
        require(receipt['input_provenance']['case_result']['sha256'] == selected['case_result_binding']['sha256'], 'H2 did not consume accepted capture')
    require(receipt['exit_code'] == 0 and not receipt.get('error') and receipt.get('labels_or_transcripts_sent_to_model') is False, 'Native H2 completion/label isolation differs')
    summary = verified_json(receipt['session_summary_binding'], consumed)
    require(summary['state'] == 'COMPLETED' and 'reconstruction_provenance' not in summary, 'S4.5 requires native completed summary')
    require(receipt['completion_evidence']['native_summary'] and receipt['completion_evidence']['unique_completion_event'], 'Native completion evidence missing')
    require(receipt['completion_evidence']['exact_full_pcm16_samples'] == receipt['adapter']['samples'], 'Native completion journal sample count differs')
    require(receipt['adapter']['gain_scalar'] == expected_gain and receipt['adapter']['channels'] == 1 and receipt['adapter']['rate_hz'] == 16000, 'Adapter format/gain differs')
    # Hash the metadata journal, not audio/model payloads. Its contents were
    # already interpreted by the bound scorer and native completion verifier.
    events_binding = compact_binding(bind(receipt['events_binding']['path'], receipt['events_binding']['sha256']))
    consumed[(events_binding['path'], events_binding['sha256'])] = events_binding
    require(metrics['case_id'] == scene['case_id'] and metrics['stream'] == stream and metrics['state'] == 'COMPLETED' and not metrics['failure_events'], 'H2 metrics completion differs')
    require(metrics['telemetry'] == summary['telemetry'] and metrics['scientific_policy'] == summary['scientific_policy'], 'H2 summary/metrics differ')
    for key, value in summary['scientific_policy'].items():
        require(key in contract['baseline']['scientific_config'] and value == contract['baseline']['scientific_config'][key], 'Native scientific policy differs from baseline')
    require(metrics['reference_scope']['reserve_task_scored'] is False, 'H2 scored reserve')
    require(metrics['reference_scope']['all_speaker_reference_complete'] == scene['all_speaker_reference_complete'], 'H2 reference completeness differs')
    alignment_view = metrics['source_to_output_turn_scoring']
    alignment = {k: v for k, v in alignment_view.items() if k != 'status'} if alignment_view['status'] == 'DESCRIPTIVE_FILE_SUPPORT_ONLY' else None
    require(receipt['analysis_identity'] == stable_hash({'alignment': alignment, 'provenance': metrics['analysis_provenance'], 'code': contract['code']}), 'H2 analysis identity differs')
    if not control:
        provenance = metrics['analysis_provenance']
        verified_json(provenance['audio_metrics'], consumed)
        if provenance.get('alignment_mapping'):
            verified_json(provenance['alignment_mapping'], consumed)
    expected_strata = collections.Counter((s['dataset'], s.get('quality_partition')) for s in scene['segments'] if s['kind'] == 'utterance')
    observed_strata = {(s['dataset'], s['quality_partition']): s['scheduled_utterances'] for s in metrics['source_strata']}
    require(dict(expected_strata) == observed_strata, 'H2 source stratum accounting differs')
    return validate_text(scene, metrics)


def dry_scene(control):
    source = control['source']
    require(source['split'] == 'development' and source['usage'] == 'probe', 'Dry control source role differs')
    return {'case_id': control['control_id'], 'family_id': 'DRY', 'split': 'development', 'transcript_valid': True,
            'all_speaker_reference_complete': True, 'overlap_intervals': [],
            'segments': [{'kind': 'utterance', 'source_id': source['source_id'], 'source_start_sample': 0,
                          'source_stop_sample': source['samples'], 'transcript': source['transcript'],
                          'dataset': source['dataset'], 'quality_partition': source.get('quality_partition')}]}


def load_jobs(manifest, accepted, audio_rows, consumed):
    sentinel_path = REPORT / 'SENTINEL_PLAN.json'
    if not sentinel_path.exists():
        return [], [], {'output_intended': 48, 'output_pending': 48, 'dry_planned': None, 'status': 'PENDING_SENTINEL_PLAN'}, []
    plan, sentinel_binding = snapshot(sentinel_path, consumed)
    ids = plan['scene_ids']
    scenes = {s['case_id']: s for s in manifest['scenes']}
    require(len(ids) == len(set(ids)) == 24 and plan['reserve_jobs_allowed'] == 0 and plan['selection_before_hardware_or_H2'], 'Sentinel plan differs')
    require(all(scenes[cid]['split'] == 'development' for cid in ids), 'Reserve H2 sentinel prohibited')
    expected_output_paths = {REPORT / 'h2' / cid / stream / 'run_receipt.json' for cid in ids for stream in OUTPUTS}
    # Listing unexpected paths reads no reserve contents; fail before opening them.
    require(set((REPORT / 'h2').glob('*/*/run_receipt.json')) <= expected_output_paths, 'Unexpected/reserve H2 receipt path exists; not opened')
    dry_path = REPORT / 'DRY_CONTROL_PLAN.json'
    dry_plan, controls = None, []
    if dry_path.exists():
        dry_plan, dry_binding = snapshot(dry_path, consumed)
        require(dry_plan['selection_before_any_H2'], 'Dry controls not frozen before model use')
        controls = dry_plan['identity']['controls']
        require(len(controls) == dry_plan['count'] <= 24, 'Dry job plan exceeds bound')
    expected_dry_paths = {REPORT / 'h2_dry' / c['control_id'] / 'run_receipt.json' for c in controls}
    require(set((REPORT / 'h2_dry').glob('*/run_receipt.json')) <= expected_dry_paths, 'Unplanned dry job exists')
    contract_path = REPORT / 'h2/execution_contract.json'
    contract, policy = None, None
    if contract_path.exists():
        contract, _ = snapshot(contract_path, consumed)
        policy = verified_json(contract['output_policy'], consumed)
        require(contract['reserve_jobs'] == 0 and contract['scientific_policy_changed'] is False, 'H2 scientific/reserve contract differs')
        require(contract['scene_manifest']['sha256'] == bind(BANK / 'SCENE_MANIFEST.json')['sha256'], 'H2 scene contract differs')
        require(contract['sentinel_plan']['sha256'] == sentinel_binding['sha256'], 'H2 sentinel contract differs')
        require(dry_plan is not None and contract['dry_plan']['sha256'] == dry_binding['sha256'], 'H2 dry-plan contract differs')
        for binding in contract['code']:
            actual = compact_binding(bind(binding['path'], binding['sha256']))
            consumed[(actual['path'], actual['sha256'])] = actual
        fix = verified_json(contract['baseline']['durability_fix'], consumed)
        require(fix['status'] == 'PASS_MODEL_FREE_REGRESSIONS' and fix['scientific_methods_ast_unchanged'], 'H2 lifecycle fix provenance differs')
        for binding in contract['baseline']['source_identities']:
            actual = compact_binding(bind(binding['path'], binding['sha256']))
            consumed[(actual['path'], actual['sha256'])] = actual
    by_audio = {r['case_id']: r for r in audio_rows}
    outputs, dry_jobs = [], []
    schedules = [('outputs', cid, stream, scenes[cid], None) for cid in ids for stream in OUTPUTS]
    schedules += [('dry', c['control_id'], 'DRY', dry_scene(c), c) for c in controls]
    for kind, cid, stream, scene, control in schedules:
        path = REPORT / ('h2_dry' if control else 'h2') / cid
        if not control:
            path /= stream
        job = {'case_id': cid, 'stream': stream, 'kind': kind, 'status': 'PENDING', 'text_eligibility': 'NOT_ANALYZED', 'metrics': None}
        receipt_path = path / 'run_receipt.json'
        if receipt_path.exists():
            receipt, receipt_binding = snapshot(receipt_path, consumed)
            require(contract is not None, 'Started H2 job lacks execution contract')
            require(receipt['case_id'] == cid and receipt['stream'] == stream, 'H2 path/receipt identity differs')
            job['receipt_binding'] = receipt_binding
            job['status'] = receipt['status']
            if not control:
                require(cid in accepted and cid in by_audio, 'H2 job lacks accepted analyzed capture')
            if receipt['status'] == 'QUARANTINED':
                require(not control and receipt['model_invocations'] == 0 and by_audio[cid]['gates'][stream] == 'QUARANTINED_GROSS_SATURATION', 'Quarantine lacks raw-level evidence')
                require(receipt['job_key'] == stable_hash(receipt['identity']) and receipt['identity']['contract_sha256'] == stable_hash(contract), 'Quarantined job identity differs')
                require(receipt['identity']['gain_scalar'] == policy['fixed_host_gain'][stream], 'Quarantined frozen gain differs')
                require(receipt['raw_audio']['sha256'] == accepted[cid]['receipt']['output_audio'][stream]['sha256'], 'Quarantined raw input differs')
                require(receipt['input_provenance']['case_result']['sha256'] == accepted[cid]['case_result_binding']['sha256'], 'Quarantine points to different capture')
                metrics = verified_json(receipt['metrics_binding'], consumed)
                if not control:
                    require(metrics['analysis_provenance']['audio_metrics']['sha256'] == by_audio[cid]['binding']['sha256'], 'H2 analysis audio provenance differs')
                require(metrics['text']['status'] == 'QUARANTINED' and metrics['text']['wer'] is None and 'word_counts' not in metrics['text'], 'Quarantine has fabricated scores')
                job['text_eligibility'] = 'QUARANTINED'
            elif receipt['status'] == 'COMPLETE':
                metrics = verified_json(receipt['metrics_binding'], consumed)
                if not control:
                    require(metrics['analysis_provenance']['audio_metrics']['sha256'] == by_audio[cid]['binding']['sha256'], 'H2 analysis audio provenance differs')
                job['text_eligibility'] = validate_native_job(receipt, metrics, scene, stream, contract, accepted.get(cid), policy, consumed, control)
                if not control:
                    require(metrics['raw_output_rail_samples'] == by_audio[cid]['audio']['streams'][stream]['rail_samples'], 'H2 raw rail counts differ from capture analysis')
                job.update(status='COMPLETE_NATIVE', metrics=metrics)
            else:
                require(receipt['status'] in ('STARTED', 'MODEL_COMPLETED', 'FAILED_OR_INTERRUPTED'), 'Unknown H2 status')
                job['error'] = receipt.get('error')
        (dry_jobs if control else outputs).append(job)
    status_counts = lambda rows: dict(collections.Counter(j['status'] for j in rows))
    return outputs, dry_jobs, {'output_intended': 48, 'output_status_counts': status_counts(outputs),
                              'output_native_complete': sum(j['status'] == 'COMPLETE_NATIVE' for j in outputs),
                              'output_quarantined': sum(j['status'] == 'QUARANTINED' for j in outputs),
                              'output_failed': sum(j['status'] == 'FAILED_OR_INTERRUPTED' for j in outputs),
                              'output_pending': sum(j['status'] == 'PENDING' for j in outputs),
                              'dry_planned': len(controls) if dry_plan else None, 'dry_maximum': 24,
                              'dry_status_counts': status_counts(dry_jobs), 'native_summary_required': True, 'derived_summaries_allowed': False}, controls


def dry_comparison(controls, dry_jobs, output_jobs, scenes):
    results = []
    dlookup = {j['case_id']: j for j in dry_jobs}
    olookup = {(j['case_id'], j['stream']): j for j in output_jobs}
    for control in controls:
        dry = dlookup[control['control_id']]
        sid = control['source_id']
        contexts = []
        for cid in control['sentinel_case_ids']:
            scene = scenes[cid]
            require(scene['split'] == 'development', 'Dry comparison includes reserve')
            utterances = [s for s in scene['segments'] if s['kind'] == 'utterance']
            require(any(s['source_id'] == sid for s in utterances), 'Dry control is not present in declared context')
            for stream in OUTPUTS:
                job = olookup[(cid, stream)]
                exact_single_clip = len(utterances) == 1 and utterances[0]['source_id'] == sid and text_eligibility(scene) == 'NONOVERLAP_COMPLETE_REFERENCE'
                paired = exact_single_clip and dry['status'] == job['status'] == 'COMPLETE_NATIVE'
                contexts.append({'case_id': cid, 'output': stream, 'processed_job_status': job['status'],
                                 'source_occurrences_in_scene': sum(s['source_id'] == sid for s in utterances),
                                 'scene_total_utterances': len(utterances), 'exact_single_clip_reference_comparison': paired,
                                 'processed_wer_minus_dry_wer': job['metrics']['text']['wer'] - dry['metrics']['text']['wer'] if paired else None,
                                 'scope': 'Descriptive exact whole-clip text comparison; acoustic/level/processing chain remains composite' if paired else 'Shared source context only; scene WER and single-clip dry WER are not paired treatment effects'})
        results.append({'control_id': control['control_id'], 'source_id': sid, 'stratum': control['stratum'], 'dry_status': dry['status'],
                        'dry_word_counts': dry['metrics']['text'].get('word_counts') if dry['metrics'] else None,
                        'dry_wer': dry['metrics']['text'].get('wer') if dry['metrics'] else None, 'processed_contexts': contexts})
    return {'controls': results, 'scope': LIMITS[5]}


def build(validate_only=False, plots=True):
    required = [BANK / 'SCENE_MANIFEST.json', REPORT / 'COVERAGE_SUMMARY.json']
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        return {'status': 'PENDING_REQUIRED_INPUTS', 'missing': missing, 'outputs_written': False}, 2
    consumed = {}
    manifest, manifest_binding = snapshot(required[0], consumed)
    coverage, _ = snapshot(required[1], consumed)
    require(manifest['validation']['status'] == 'PASS' and len(manifest['scenes']) == 240, 'Bank not frozen and complete')
    require(coverage['input_bindings']['SCENE_MANIFEST.json']['sha256'] == manifest_binding['sha256'], 'Coverage refers to different bank')
    for binding in coverage.get('export_bindings', []):
        actual = compact_binding(bind(binding['path'], binding['sha256']))
        consumed[(actual['path'], actual['sha256'])] = actual
    scenes = {s['case_id']: s for s in manifest['scenes']}
    accepted = load_accepted(REPORT / 'ACCEPTED_CAPTURES.json', manifest, manifest_binding, consumed)
    require(coverage['counts']['canonical_accepted_captures'] == len(accepted), 'Coverage capture count is stale; rerun s45_coverage.py before results')
    audio, spatial = load_capture_analysis(REPORT / 'CAPTURE_ANALYSIS.json', accepted, scenes, consumed)
    reference_manifest_path = BANK / 'REFERENCE_SCENE_MANIFEST.json'
    refs, refaudio = {}, []
    if reference_manifest_path.exists():
        rm, rb = snapshot(reference_manifest_path, consumed)
        refs = load_accepted(REPORT / 'REFERENCE_CAPTURES.json', rm, rb, consumed, True)
        refaudio, _ = load_capture_analysis(REPORT / 'REFERENCE_CAPTURE_ANALYSIS.json', refs, {s['case_id']: s for s in rm['scenes']}, consumed, True)
    outputs, dry, job_counts, controls = load_jobs(manifest, accepted, audio, consumed)
    audio_lookup = {r['case_id']: r for r in audio}
    output_lookup = {(j['case_id'], j['stream']): j for j in outputs}
    rows = []
    for cid, scene in scenes.items():
        row = {'case_id': cid, 'family_id': scene['family_id'], 'split': scene['split'], 'reserve_stratum': scene['reserve_stratum'],
               'duration_s': scene['duration_s'], 'capture_status': 'ACCEPTED' if cid in accepted else 'PENDING',
               'level_analysis_status': 'ANALYZED' if cid in audio_lookup else 'PENDING',
               'task_scope': 'PROHIBITED_RESERVE' if scene['split'] == 'reserve' else 'PREDECLARED_SENTINEL_ONLY_FOR_H2'}
        if cid in accepted:
            payload = accepted[cid]['receipt']['payload']
            row.update(compared_mic_samples=payload['compared_mic_samples'], payload_mismatches=payload['payload_mismatches'],
                       capture_minus_source_offset_samples=payload['capture_minus_source_offset_samples'])
        for stream in OUTPUTS:
            if cid in audio_lookup:
                level = audio_lookup[cid]['audio']['streams'][stream]
                for key in ('sample_count', 'rail_samples', 'rail_runs', 'maximum_contiguous_rail_run_samples', 'peak_fs', 'rms_dbfs'):
                    row[stream + '_' + key] = level[key]
                row[stream + '_level_gate'] = audio_lookup[cid]['gates'].get(stream)
            job = output_lookup.get((cid, stream))
            row[stream + '_H2_status'] = 'PROHIBITED_RESERVE' if scene['split'] == 'reserve' else job['status'] if job else 'NOT_SELECTED_SENTINEL'
            if job and job['status'] == 'COMPLETE_NATIVE':
                row[stream + '_text_scope'] = job['text_eligibility']
                if job['text_eligibility'] in ('NONOVERLAP_COMPLETE_REFERENCE', 'STRICT_EMPTY_REFERENCE'):
                    for key in WORD_KEYS:
                        row[stream + '_' + key] = job['metrics']['text']['word_counts'][key]
                    row[stream + '_wer'] = job['metrics']['text']['wer']
                    for key in CHAR_KEYS:
                        row[stream + '_char_' + key] = job['metrics']['text']['character_counts'][key]
                    row[stream + '_cer'] = job['metrics']['text']['cer']
        rows.append(row)
    false_words = []
    for job in outputs:
        if job['status'] == 'COMPLETE_NATIVE' and job['text_eligibility'] == 'STRICT_EMPTY_REFERENCE':
            text = job['metrics']['text']
            scene = scenes[job['case_id']]
            require(not any(s['kind'] == 'utterance' for s in scene['segments']) and all(s.get('strict_nonspeech_eligible') for s in scene['segments']), 'False-word control is not strictly nonspeech')
            false_words.append({'case_id': job['case_id'], 'output': job['stream'], 'control': 'digital_silence' if not scene['segments'] else 'documented_nonspeech_noise',
                                'duration_s': text['duration_s'], 'duration_scope': 'Native decoded H2 input duration from completed session telemetry; raw native-frame totals and intended canonical duration are reported separately',
                                'insertions': text['empty_reference_insertions'], 'words_per_minute': text['empty_reference_words_per_minute']})
    complete = len(accepted) == 240 and len(audio) == 240 and len(spatial) == 180 and job_counts.get('output_native_complete', 0) + job_counts.get('output_quarantined', 0) == 48
    dry_complete = bool(controls) and all(j['status'] == 'COMPLETE_NATIVE' for j in dry)
    summary = {'schema': 'jp_s45_summary_v1', 'run_id': RUN_ID, 'aggregated_utc': now(),
               'status': 'COMPLETE_WITH_LIMITATIONS' if complete and dry_complete else 'PARTIAL_EVIDENCE', 'intended': INTENDED,
               'actual': {'canonical_prepared': len(scenes), 'canonical_accepted': len(accepted), 'development_accepted': sum(scenes[c]['split'] == 'development' for c in accepted),
                          'reserve_accepted': sum(scenes[c]['split'] == 'reserve' for c in accepted), 'audio_analyzed': len(audio), 'development_spatial_analyzed': len(spatial),
                          'optional_references_accepted': len(refs), 'optional_references_level_analyzed': len(refaudio), 'H2': job_counts},
               'coverage_counts': coverage['counts'], 'transport_canonical': transport_summary([r['receipt'] for r in accepted.values()]),
               'transport_optional_references': transport_summary([r['receipt'] for r in refs.values()]),
               'raw_levels': level_summary(audio + refaudio), 'development_spatial': spatial_summary(spatial),
               'H2_nonoverlap_text': pool_text(outputs), 'dry_nonoverlap_text': pool_text(dry),
               'H2_text_scope_counts': dict(collections.Counter(j['text_eligibility'] for j in outputs)),
               'strict_nonspeech_false_words': false_words, 'embedding_evidence': embedding_summary(outputs),
               'dry_source_context_comparisons': dry_comparison(controls, dry, outputs, scenes),
               'H2_job_status_rows': [{k: j[k] for k in ('case_id', 'stream', 'kind', 'status', 'text_eligibility')} for j in outputs + dry],
               'reserve_task_metrics_read': False, 'audio_or_models_opened_by_aggregation': False,
               'no_final_output_winner': True, 'limitations': LIMITS,
               'consumed_json_bindings': list(consumed.values()), 'aggregation_code': compact_binding(bind(Path(__file__)))}
    paired_ids = set.intersection(*[{j['case_id'] for j in outputs if j['stream'] == output and j['status'] == 'COMPLETE_NATIVE' and j['text_eligibility'] == 'NONOVERLAP_COMPLETE_REFERENCE'} for output in OUTPUTS])
    summary['H2_nonoverlap_text']['common_O0_O1_eligible_case_ids'] = sorted(paired_ids)
    summary['H2_nonoverlap_text']['common_case_pool'] = pool_text([j for j in outputs if j['case_id'] in paired_ids])
    summary['H2_nonoverlap_text']['comparison_limit'] = 'Primary per-output totals can have different eligibility after quarantine; common-case totals are separately disclosed. No output winner is declared.'
    if not validate_only:
        write_csv(REPORT / 'per_scene_metrics.csv', rows)
        summary['per_scene_metrics_binding'] = compact_binding(bind(REPORT / 'per_scene_metrics.csv'))
        save(REPORT / 'summary_metrics.json', summary)
        if plots:
            make_plots(summary, rows)
    return {'status': summary['status'], 'actual': summary['actual'], 'outputs_written': not validate_only, 'reserve_task_metrics_read': False}, 0


def make_plots(summary, rows):
    # Import plotting only after metadata validation. No model/audio imports.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    directory = REPORT / 'plots'
    directory.mkdir(exist_ok=True)
    data, figures = [], []
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'figure.dpi': 140})
    def datum(figure, panel, series, category, metric, value, denominator=None):
        data.append({'figure': figure, 'panel': panel, 'series': series, 'category': category, 'metric': metric, 'value': value, 'denominator': denominator})
    def finish(fig, filename, title):
        fig.suptitle(title, fontsize=14)
        fig.tight_layout(rect=(0, 0.025, 1, .95))
        fig.savefig(directory / filename, dpi=170)
        plt.close(fig)
        figures.append({'file': filename, 'title': title, 'binding': compact_binding(bind(directory / filename))})
    name = '01_capture_and_raw_rails.png'
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    families = sorted({r['family_id'] for r in rows})
    accepted = [sum(r['family_id'] == f and r['capture_status'] == 'ACCEPTED' for r in rows) for f in families]
    axes[0].bar(families, [20] * len(families), color='#e5e7eb', label='20 intended')
    axes[0].bar(families, accepted, color='#217a8c', label='Accepted')
    axes[0].set(ylabel='Canonical scenes', ylim=(0, 23)); axes[0].legend(loc='upper right', ncol=2)
    for f, value in zip(families, accepted):
        datum(name, 'capture', 'accepted', f, 'scene_count', value, 20)
    colors = {'O0': '#217a8c', 'O1': '#bd6339'}
    for stream in OUTPUTS:
        points = [(i + 1, r[stream + '_rail_samples'] / r[stream + '_sample_count']) for i, r in enumerate(rows) if stream + '_rail_samples' in r]
        if points:
            axes[1].scatter([p[0] for p in points], [100 * p[1] for p in points], label=stream, s=15, alpha=.7, color=colors[stream])
        for index, value in points:
            datum(name, 'rails', stream, rows[index - 1]['case_id'], 'rail_fraction', value, rows[index - 1][stream + '_sample_count'])
    axes[1].set(xlabel='Canonical scene order (families F01–F12)', ylabel='Raw output samples at rail (%)')
    axes[1].set_xlim(.5, len(rows) + .5)
    axes[1].set_ylim(bottom=0)
    if axes[1].collections:
        axes[1].legend()
    else:
        axes[1].set_yticks([])
        axes[1].text(.5, .5, 'Raw level analysis pending', transform=axes[1].transAxes, ha='center')
    fig.text(.01, .005, 'Coverage and raw integrity only; reserve task scores are not shown.', fontsize=9)
    finish(fig, name, 'S4.5 capture coverage and raw output rails')
    spatial = summary['development_spatial']['primary_nonoverlap_complete_reference_by_stream']
    if spatial:
        name = '02_development_spatial_support.png'
        fig, axis = plt.subplots(figsize=(11, 5))
        x = list(range(len(spatial)))
        for offset, key, label, color in [(-.2, 'speech_energy_gated_coverage', 'Usable gated cue', '#217a8c'), (.2, 'matching_sector_occupancy', 'Matching nominal sector', '#bd6339')]:
            vals = [r[key] for r in spatial]
            axis.bar([i + offset for i, v in zip(x, vals) if v is not None], [100 * v for v in vals if v is not None], width=.38, label=label, color=color)
            for row, value in zip(spatial, vals):
                datum(name, 'primary_support', label, row['stream'], key, value, row['support_duration_s'])
        axis.set_xticks(x, [r['stream'].replace('_', '\n') for r in spatial]); axis.set(ylabel='Estimated support time (%)', ylim=(0, 105))
        axis.legend(loc='upper left')
        fig.text(.01, .005, 'Development nonoverlap, complete-reference turns; causal host availability, not physical reaction latency.', fontsize=9)
        finish(fig, name, 'Development spatial cue support')
    text_rows = summary['H2_nonoverlap_text']['by_output_corpus_quality']
    if text_rows:
        name = '03_nonoverlap_asr_counts.png'
        fig, axis = plt.subplots(figsize=(12, 6))
        groups = sorted({(r['dataset'], r['quality_partition']) for r in text_rows})
        for stream, offset in [('O0', -.19), ('O1', .19)]:
            for index, group in enumerate(groups):
                row = next((r for r in text_rows if (r['dataset'], r['quality_partition']) == group and r['output'] == stream), None)
                if row:
                    axis.bar(index + offset, row['wer'] * 100, width=.36, color=colors[stream], label=stream if index == 0 else None)
                    axis.text(index + offset, row['wer'] * 100, str(row['errors']) + '/' + str(row['reference_words']), ha='center', va='bottom', fontsize=9)
                    datum(name, 'WER', stream, ' / '.join(group), 'wer', row['wer'], row['reference_words'])
                    datum(name, 'raw_counts', stream, ' / '.join(group), 'errors', row['errors'], row['reference_words'])
        labels = [corpus + '\n' + quality.replace('_', ' ') for corpus, quality in groups]
        import textwrap
        axis.set_xticks(range(len(groups)), ['\n'.join(textwrap.wrap(label, 24)) for label in labels])
        axis.set(ylabel='Word error rate (%)'); axis.legend(); axis.margins(y=.2)
        fig.text(.01, .005, 'Labels show raw errors/reference words. LIMITED overlap/ambient cases are excluded; descriptive dependent evidence.', fontsize=9)
        finish(fig, name, 'Native H2 nonoverlap ASR evidence by source stratum')
    name = '04_H2_job_and_embedding_evidence.png'
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    jobs = summary['H2_job_status_rows']
    status_order = ['COMPLETE_NATIVE', 'QUARANTINED', 'FAILED_OR_INTERRUPTED', 'MODEL_COMPLETED', 'STARTED', 'PENDING']
    legend_seen = set()
    for label, group in [('O0', [j for j in jobs if j['stream'] == 'O0']), ('O1', [j for j in jobs if j['stream'] == 'O1']), ('DRY', [j for j in jobs if j['stream'] == 'DRY'])]:
        left = 0
        for index, status in enumerate(status_order):
            number = sum(j['status'] == status for j in group)
            if number:
                axes[0].barh(label, number, left=left, color=plt.cm.Set2(index / 7), label=status if status not in legend_seen else None)
                legend_seen.add(status)
                axes[0].text(left + number / 2, label, str(number), ha='center', va='center', fontsize=9)
            datum(name, 'job_status', label, status, 'jobs', number, len(group))
            left += number
    axes[0].set(xlabel='Predeclared jobs', title='Native completion, quarantine and pending')
    handles, labels = axes[0].get_legend_handles_labels()
    if handles:
        axes[0].legend(handles, [s.replace('_', ' ').lower() for s in labels], fontsize=8, loc='upper center', bbox_to_anchor=(.5, -.15), ncol=2)
    embeddings = summary['embedding_evidence']['by_output']
    for i, row in enumerate(embeddings):
        axes[1].bar(i, row['successful_embedding_calls'], color=colors.get(row['output'], '#777'))
        datum(name, 'embedding', row['output'], 'native_completed_jobs', 'successful_embedding_calls', row['successful_embedding_calls'], row['native_jobs'])
    axes[1].set_xticks(range(len(embeddings)), [r['output'] for r in embeddings]); axes[1].set(ylabel='Successful embedding decisions', title='Overlapping windows; not independent speakers')
    axes[1].set_ylim(0, max(1, max((r['successful_embedding_calls'] for r in embeddings), default=0) * 1.15))
    if not any(r['native_jobs'] for r in embeddings):
        axes[1].set_yticks([])
        axes[1].text(.5, .5, 'No completed model evidence yet', transform=axes[1].transAxes, ha='center')
    finish(fig, name, 'Bounded H2 execution and embedding evidence')
    write_csv(directory / 'plotted_data.csv', data)
    save(directory / 'FIGURE_INDEX.json', {'schema': 'jp_s45_figures_v1', 'generated_utc': now(), 'figure_count': len(figures), 'maximum_figures': 4,
                                          'figures': figures, 'plotted_data': compact_binding(bind(directory / 'plotted_data.csv')),
                                          'summary_metrics': compact_binding(bind(REPORT / 'summary_metrics.json')), 'plot_code': compact_binding(bind(Path(__file__))),
                                          'visual_QA': 'PENDING_HUMAN_OR_TOOL_INSPECTION', 'no_reserve_task_plots': True})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--no-plots', action='store_true', help='Write metrics only; default makes at most four plots from available evidence.')
    args = parser.parse_args()
    try:
        result, code = build(args.validate_only, not args.no_plots)
    except (CoverageError, KeyError, ValueError, FileNotFoundError) as error:
        result, code = {'status': 'INVALID_INPUT_OR_BINDING', 'error': str(error), 'outputs_written': False}, 1
    print(json.dumps(result, indent=2))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
