"""Bounded offline aggregation fixtures; README_S45_RESULTS.md."""
import copy
import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import s45_results as r


def scene():
    return {'case_id': 'T1', 'split': 'development', 'transcript_valid': True, 'all_speaker_reference_complete': True,
            'overlap_intervals': [], 'segments': [{'kind': 'utterance', 'source_start_sample': 0, 'transcript': 'One two.'}]}


def text_metrics():
    return {'text': {'status': 'SCORED', 'reference_normalized': 'one two', 'hypothesis_normalized': 'one',
                     'word_counts': {'errors': 1, 'substitutions': 0, 'deletions': 1, 'insertions': 0, 'reference_words': 2, 'hypothesis_words': 1},
                     'character_counts': {'errors': 3, 'substitutions': 0, 'deletions': 3, 'insertions': 0, 'reference_characters': 6, 'hypothesis_characters': 3}, 'wer': .5, 'cer': .5},
            'source_strata': [{'dataset': 'HiFiTTS', 'quality_partition': 'clean'}]}


def job(output='O0'):
    return {'case_id': 'T1', 'stream': output, 'kind': 'outputs', 'status': 'COMPLETE_NATIVE',
            'text_eligibility': 'NONOVERLAP_COMPLETE_REFERENCE', 'metrics': text_metrics()}


class ResultsTests(unittest.TestCase):
    def test_raw_edit_denominator_and_normalization(self):
        self.assertEqual(r.validate_text(scene(), text_metrics()), 'NONOVERLAP_COMPLETE_REFERENCE')
        metrics = text_metrics()
        metrics['text']['word_counts']['errors'] = 0
        with self.assertRaisesRegex(r.CoverageError, 'edit counts'):
            r.validate_text(scene(), metrics)
        metrics = text_metrics()
        metrics['text']['cer'] = 0
        with self.assertRaisesRegex(r.CoverageError, 'CER value'):
            r.validate_text(scene(), metrics)

    def test_limited_ambient_and_overlap_do_not_get_WER(self):
        for key, value in [('all_speaker_reference_complete', False), ('overlap_intervals', [{'start': 0, 'stop': 1}])]:
            s = {**scene(), key: value}
            with self.assertRaisesRegex(r.CoverageError, 'ordinary WER'):
                r.validate_text(s, text_metrics())
            self.assertTrue(r.validate_text(s, {'text': {'status': 'LIMITED', 'wer': None, 'cer': None}}).startswith('LIMITED'))

    def test_reserve_text_gate_precedes_reference_access(self):
        with self.assertRaisesRegex(r.CoverageError, 'reserve text'):
            r.validate_text({'split': 'reserve'}, {})

    def test_pool_uses_counts_not_mean_WER_and_excludes_limited(self):
        first, second = job(), job()
        second['metrics']['text']['word_counts'].update(errors=1, reference_words=8, hypothesis_words=8)
        second['case_id'] = 'T2'
        limited = {**job(), 'text_eligibility': 'LIMITED_UNKNOWN_AMBIENT_REFERENCE'}
        quarantine = {**job(), 'status': 'QUARANTINED', 'metrics': None}
        result = r.pool_text([first, second, limited, quarantine])['by_output'][0]
        self.assertEqual((result['errors'], result['reference_words'], result['wer']), (2, 10, .2))

    def test_mixed_quality_is_one_separate_denominator(self):
        j = job()
        j['metrics']['source_strata'].append({'dataset': 'HiFiTTS', 'quality_partition': 'other'})
        result = r.pool_text([j])
        self.assertEqual(result['by_output'][0]['reference_words'], 2)
        self.assertEqual(len(result['by_output_corpus_quality']), 1)
        self.assertIn('MIXED', result['by_output_corpus_quality'][0]['quality_partition'])

    def test_empty_reference_has_insertions_no_WER(self):
        s = {**scene(), 'segments': []}
        metrics = {'text': {'status': 'EMPTY_REFERENCE', 'reference_normalized': '', 'hypothesis_normalized': 'hello',
                            'word_counts': {'errors': 1, 'substitutions': 0, 'deletions': 0, 'insertions': 1, 'reference_words': 0, 'hypothesis_words': 1},
                            'character_counts': {'errors': 5, 'substitutions': 0, 'deletions': 0, 'insertions': 5, 'reference_characters': 0, 'hypothesis_characters': 5}, 'wer': None, 'cer': None}}
        self.assertEqual(r.validate_text(s, metrics), 'STRICT_EMPTY_REFERENCE')

    def test_zero_input_transport_does_not_invent_offset_or_per_mic_error(self):
        receipt = {'framing': {'native_frames': 300, 'decoded_frames': 100, 'marker_error_count': 0, 'startup_frames_excluded': 0},
                   'payload': {'status': 'PASS', 'capture_minus_source_offset_samples': None, 'alignment_status': 'UNIDENTIFIABLE_ALL_ZERO_INPUT',
                               'compared_mic_samples': 400, 'payload_mismatches': 0}}
        result = r.transport_summary([receipt])
        self.assertEqual(result['native_scalar_samples'], 600)
        self.assertEqual(result['decoded_scalar_samples'], 600)
        self.assertEqual(result['silent_alignment_unidentifiable_cases'], 1)
        self.assertEqual(result['per_mic_max_abs_error_counts_nonsilent'], [None] * 4)

    def test_reserve_spatial_pointer_rejected_before_metrics_read(self):
        document = {'cases': [{'case_id': 'R1', 'case_result': {'sha256': 'same'}, 'spatial_metrics': {'path': 'NEVER_OPEN'}}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'analysis.json'
            r.save(path, document)
            with patch.object(r, 'verified_json') as reader:
                with self.assertRaisesRegex(r.CoverageError, 'Forbidden reserve'):
                    r.load_capture_analysis(path, {'R1': {'case_result_binding': {'sha256': 'same'}}}, {'R1': {'split': 'reserve'}}, {})
                reader.assert_not_called()

    def test_spatial_weighting_and_censoring(self):
        a = {'support_duration_s': 1, 'angle_only_coverage': 1, 'speech_energy_gated_coverage': 1, 'matching_sector_occupancy': 1,
             'wrong_sector_duration_s': 0, 'held_wrong_sector_duration_s': 0, 'already_matching_at_onset': True,
             'sustained_acquisition_s': 1, 'sustained_acquisition_censored': False, 'off_delay_censored': True}
        b = {**a, 'support_duration_s': 3, 'speech_energy_gated_coverage': 0, 'matching_sector_occupancy': 0,
             'already_matching_at_onset': False, 'sustained_acquisition_s': None, 'sustained_acquisition_censored': True}
        s = {'split': 'development', 'all_speaker_reference_complete': True,
             'segments': [{'kind': 'utterance', 'utterance_label': 'A1', 'speaker_key': 'A'}, {'kind': 'utterance', 'utterance_label': 'A2', 'speaker_key': 'A'}]}
        spatial = {'raw_field_statistics': {}, 'turns': {'A1': {'status': 'DESCRIPTIVE_NOMINAL_GEOMETRY', 'streams': {'cue': a}},
                                                       'A2': {'status': 'DESCRIPTIVE_NOMINAL_GEOMETRY', 'streams': {'cue': b}}}}
        row = r.spatial_summary([{'scene': s, 'spatial': spatial}])['primary_nonoverlap_complete_reference_by_stream'][0]
        self.assertEqual(row['speech_energy_gated_coverage'], .25)
        self.assertEqual(row['sustained_censored_turns'], 1)
        self.assertEqual(row['returning_turns'], 1)

    def test_missing_embedding_support_is_unavailable_not_perfect(self):
        j = job()
        j['metrics']['speaker'] = {'embedding_calls_successful': 0}
        result = r.embedding_summary([j])['by_output'][0]
        self.assertEqual(result['reference_turn_evidence_unavailable_jobs'], 1)
        self.assertEqual(result['reference_supported_turns'], 0)
        self.assertIsNone(result['rejected_embedding_calls'])
        self.assertEqual(result['decision_label_fragmentation']['jobs_without_label_evidence'], 1)
        self.assertEqual(result['emitted_final_label_fragmentation']['jobs_without_label_evidence'], 1)
        self.assertIsNone(result['label_evidence_by_job'][0]['decision_label_counts'])

    def test_decision_and_emitted_label_fragmentation_stay_separate_per_job(self):
        first, second = job(), job()
        first['metrics']['speaker'] = {'embedding_calls_successful': 4,
            'decision_label_counts': {'Speaker 1': 3, 'Speaker 2': 1}, 'decision_label_switches': 2,
            'emitted_final_labels': ['Speaker 1', 'Speaker 1'], 'reconciled_labels': None,
            'reconciliation_status': 'UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE'}
        second['case_id'] = 'T2'
        second['metrics']['speaker'] = {'embedding_calls_successful': 2,
            'decision_label_counts': {'Speaker 1': 2}, 'decision_label_switches': 0,
            'emitted_final_labels': ['Speaker 1', 'Speaker 2', 'Speaker 1'], 'reconciled_labels': None,
            'reconciliation_status': 'UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE'}
        quarantine = {**job(), 'status': 'QUARANTINED', 'metrics': None}
        result = r.embedding_summary([first, second, quarantine])['by_output'][0]
        decisions, emitted = result['decision_label_fragmentation'], result['emitted_final_label_fragmentation']
        self.assertEqual((decisions['observations_in_supported_jobs'], emitted['observations_in_supported_jobs']), (6, 5))
        self.assertEqual(decisions['within_job_label_switches'], 2)
        self.assertEqual(emitted['within_job_label_switches'], 2)
        # Speaker 1 in T1 is not Speaker 1 in T2. Do not union label strings.
        self.assertEqual(decisions['sum_within_job_distinct_labels'], 3)
        self.assertEqual(emitted['sum_within_job_distinct_labels'], 3)
        per_job = result['label_evidence_by_job']
        self.assertEqual([r['decision_label_switches'] for r in per_job], [2, 0])
        self.assertEqual([r['emitted_final_label_switches'] for r in per_job], [0, 2])
        self.assertEqual(result['native_jobs'], 2)
        self.assertEqual(result['reference_turn_evidence_unavailable_jobs'], 2)
        self.assertIsNone(result['reconciled_cluster_lineage']['underlying_cluster_fragmentation'])
        self.assertEqual(result['reconciled_cluster_lineage']['status_counts'], {'UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE': 2})

    def test_empty_label_evidence_is_observed_zero_not_missing_or_return_success(self):
        j = job()
        j['metrics']['speaker'] = {'embedding_calls_successful': 0, 'decision_label_counts': {},
            'decision_label_switches': 0, 'emitted_final_labels': [], 'reconciled_labels': None,
            'reconciliation_status': 'UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE'}
        result = r.embedding_summary([j])['by_output'][0]
        self.assertEqual(result['decision_label_fragmentation']['jobs_with_label_evidence'], 1)
        self.assertEqual(result['emitted_final_label_fragmentation']['observations_in_supported_jobs'], 0)
        self.assertEqual(result['consistent_return_groups'], 0)
        self.assertEqual(result['reference_turn_evidence_unavailable_jobs'], 1)

    def test_label_evidence_must_agree_with_recorded_decisions_and_finals(self):
        j = job()
        j['metrics']['speaker'] = {'embedding_calls_successful': 1, 'decision_label_counts': {'S1': 2},
            'decision_label_switches': 0, 'emitted_final_labels': ['S1']}
        with self.assertRaisesRegex(r.CoverageError, 'Decision-label count'):
            r.embedding_summary([j])
        j['metrics']['speaker']['decision_label_counts'] = {'S1': 1}
        j['metrics']['final_transcripts'] = [{'speaker': 'S2'}]
        with self.assertRaisesRegex(r.CoverageError, 'final-label list'):
            r.embedding_summary([j])

    def test_dry_vs_multiturn_has_no_derived_treatment_delta(self):
        control = {'control_id': 'DRY_01', 'source_id': 'source', 'stratum': {}, 'sentinel_case_ids': ['T1']}
        s = scene()
        s['segments'] = [{'kind': 'utterance', 'source_id': 'source'}, {'kind': 'utterance', 'source_id': 'another'}]
        dry = {**job('DRY'), 'case_id': 'DRY_01'}
        result = r.dry_comparison([control], [dry], [job('O0'), job('O1')], {'T1': s})
        self.assertTrue(all(x['processed_wer_minus_dry_wer'] is None for x in result['controls'][0]['processed_contexts']))

    def test_derived_native_summary_is_rejected(self):
        contract = {}
        identity = {'contract_sha256': r.stable_hash(contract), 'gain_scalar': 1, 'raw_audio_sha256': 'raw'}
        receipt = {'case_id': 'T1', 'stream': 'O0', 'kind': 'outputs', 'identity': identity, 'job_key': r.stable_hash(identity),
                   'raw_audio': {'sha256': 'raw'}, 'input_provenance': {'case_result': {'sha256': 'capture'}},
                   'exit_code': 0, 'labels_or_transcripts_sent_to_model': False, 'session_summary_binding': {}}
        selected = {'receipt': {'output_audio': {'O0': {'sha256': 'raw'}}}, 'case_result_binding': {'sha256': 'capture'}}
        with patch.object(r, 'verified_json', return_value={'state': 'COMPLETED', 'reconstruction_provenance': {'status': 'DERIVED'}}):
            with self.assertRaisesRegex(r.CoverageError, 'native completed summary'):
                r.validate_native_job(receipt, {'fixed_host_gain': 1}, scene(), 'O0', contract, selected, {'fixed_host_gain': {'O0': 1}}, {})

    def test_four_plot_export_and_single_numeric_csv_use_temporary_fixture(self):
        summary = {'development_spatial': {'primary_nonoverlap_complete_reference_by_stream': [
                       {'stream': 'selected_auto', 'speech_energy_gated_coverage': .5, 'matching_sector_occupancy': .25, 'support_duration_s': 4}]},
                   'H2_nonoverlap_text': r.pool_text([job('O0'), job('O1')]),
                   'H2_job_status_rows': [{'stream': 'O0', 'status': 'COMPLETE_NATIVE'}, {'stream': 'O1', 'status': 'QUARANTINED'}],
                   'embedding_evidence': {'by_output': [{'output': 'O0', 'successful_embedding_calls': 2, 'native_jobs': 1},
                                                        {'output': 'O1', 'successful_embedding_calls': 0, 'native_jobs': 0}]}}
        rows = [{'family_id': 'F01', 'capture_status': 'ACCEPTED', 'case_id': 'FIXTURE',
                 'O0_rail_samples': 0, 'O0_sample_count': 100, 'O1_rail_samples': 20, 'O1_sample_count': 100}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            r.save(path / 'summary_metrics.json', {'test_fixture': True})
            with patch.object(r, 'REPORT', path), patch.dict(os.environ, {'MPLCONFIGDIR': str(path / 'mplcache')}):
                r.make_plots(summary, rows)
            index = r.read(path / 'plots/FIGURE_INDEX.json')
            self.assertEqual(index['figure_count'], 4)
            self.assertEqual(len(list((path / 'plots').glob('*.png'))), 4)
            with (path / 'plots/plotted_data.csv').open(encoding='utf-8-sig', newline='') as stream:
                numeric = list(csv.DictReader(stream))
            rails = next(row for row in numeric if row['panel'] == 'rails' and row['series'] == 'O1')
            self.assertEqual(float(rails['value']), .2)
            self.assertEqual(float(rails['denominator']), 100)

    def test_native_job_contract_analysis_and_scientific_policy_joins(self):
        s = scene()
        s['segments'][0].update(dataset='HiFiTTS', quality_partition='clean')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'events.jsonl').write_text('{"fixture":true}\n', encoding='utf8')
            r.save(path / 'audio.json', {'fixture': True})
            summary = {'state': 'COMPLETED', 'telemetry': {'source_duration_sec': 1}, 'scientific_policy': {'threshold': .5}}
            r.save(path / 'summary.json', summary)
            contract = {'baseline': {'scientific_config': {'threshold': .5}}, 'code': []}
            provenance = {'audio_metrics': r.bind(path / 'audio.json'), 'alignment_mapping': None}
            identity = {'contract_sha256': r.stable_hash(contract), 'gain_scalar': 1, 'raw_audio_sha256': 'raw'}
            receipt = {'case_id': 'T1', 'stream': 'O0', 'kind': 'outputs', 'identity': identity, 'job_key': r.stable_hash(identity),
                       'raw_audio': {'sha256': 'raw'}, 'input_provenance': {'case_result': {'sha256': 'capture'}},
                       'exit_code': 0, 'labels_or_transcripts_sent_to_model': False, 'session_summary_binding': r.bind(path / 'summary.json'),
                       'events_binding': r.bind(path / 'events.jsonl'), 'completion_evidence': {'native_summary': True, 'unique_completion_event': True, 'exact_full_pcm16_samples': 16000},
                       'adapter': {'samples': 16000, 'channels': 1, 'rate_hz': 16000, 'gain_scalar': 1},
                       'analysis_identity': r.stable_hash({'alignment': None, 'provenance': provenance, 'code': []})}
            selected = {'receipt': {'output_audio': {'O0': {'sha256': 'raw'}}}, 'case_result_binding': {'sha256': 'capture'}}
            metrics = {**text_metrics(), 'fixed_host_gain': 1, 'case_id': 'T1', 'stream': 'O0', 'state': 'COMPLETED', 'failure_events': [],
                       'telemetry': summary['telemetry'], 'scientific_policy': summary['scientific_policy'],
                       'reference_scope': {'reserve_task_scored': False, 'all_speaker_reference_complete': True},
                       'source_to_output_turn_scoring': {'status': 'LIMITED'}, 'analysis_provenance': provenance,
                       'source_strata': [{'dataset': 'HiFiTTS', 'quality_partition': 'clean', 'scheduled_utterances': 1}]}
            self.assertEqual(r.validate_native_job(receipt, metrics, s, 'O0', contract, selected, {'fixed_host_gain': {'O0': 1}}, {}), 'NONOVERLAP_COMPLETE_REFERENCE')
            receipt['analysis_identity'] = 'wrong'
            with self.assertRaisesRegex(r.CoverageError, 'analysis identity'):
                r.validate_native_job(receipt, metrics, s, 'O0', contract, selected, {'fixed_host_gain': {'O0': 1}}, {})


if __name__ == '__main__':
    unittest.main()
