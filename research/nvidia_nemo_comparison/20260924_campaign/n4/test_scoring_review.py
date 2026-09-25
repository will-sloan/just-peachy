"""Dictionary-only rejection tests. See README_SCORING_REVIEW.md."""
from copy import deepcopy
import unittest

from common import fingerprint
from metric_process import pin
from review_scoring_bank import (edit_counts, owners_closed, validate_activity, validate_row,
                                validate_score, validate_terminal, verify_report)
from scoring_report import report


def fixture(kind='complete_nonoverlap'):
    counts = dict(errors=0, words=1, substitutions=0, deletions=0, insertions=0, rate=0.)
    truth = dict(job_id='scene_O0', case_id='scene', tap='O0', frames=32000,
                 reference_class=kind, complete_reference=kind != 'incomplete_ambient_reference',
                 turns=[dict(identity='speaker', transcript='alpha', activity_ranges_samples_estimated=[[0, 16000]])])
    pred = dict(job_id=truth['job_id'], status='COMPLETE', raw_text='alpha',
                segments=[dict(track='Unknown', text='alpha')], activity=None,
                activity_support={'status': 'fixture'}, formatting=[])
    score = dict(job_id=truth['job_id'], reference_class=kind, execution_status='COMPLETE', reference_words=1,
                 audio_seconds=2., hypothesis_words=1, integrated_N4_cells=0, metric_status='SCORED', scoring_status='SCORED',
                 tcpwer_status='UNAVAILABLE_NO_EXACT_REFERENCE_WORD_TIMES',
                 naming_metrics_status='UNAVAILABLE_ACTUAL_WIDGET_VISIBILITY_NOT_RECORDED',
                 first_widget_visibility='UNAVAILABLE_MODELED_METHOD_REPLAY_ONLY', primary_wer=None, raw_wer=None,
                 cpwer=None, mimo=None, activity=dict(status='UNAVAILABLE_FULL_TRACK_ACTIVITY_NOT_RECORDED', DER=None, JER=None),
                 activity_support=deepcopy(pred['activity_support']), formatting_lexical_preservation=dict(
                     status='ASR_WORD_PRESERVATION_DIAGNOSTIC_NOT_PUNCTUATION_ACCURACY',
                     totals=dict(utterances=0, errors=0, words=0, substitutions=0, deletions=0, insertions=0), changed_utterances=[]))
    if kind == 'complete_nonoverlap': score.update(primary_wer=deepcopy(counts), raw_wer=deepcopy(counts))
    if kind.startswith('complete_'):
        speaker = dict(cpwer=deepcopy(counts), mimo=dict(status='SCORED', value=deepcopy(counts)))
        score.update(deepcopy(speaker)); score['constant_speaker_controls'] = dict(all_unknown=deepcopy(speaker),
            all_one_name=deepcopy(speaker), interpretation='Identical permutation-invariant scores; neither control supplies evidence of correctly recognized names')
    if kind == 'empty_control':
        truth['turns'] = []; score.update(reference_words=0, inserted_words=1, inserted_words_per_minute=30.)
    if kind == 'incomplete_ambient_reference':
        score.update(target_only_diagnostic=deepcopy(counts), scoring_status='TARGET_ONLY_NOT_ALL_SPEAKER_ACCURACY')
    return truth, pred, score


class ScoringReviewTests(unittest.TestCase):
    def test_reference_classes_do_not_acquire_unsupported_metrics(self):
        for kind in ('complete_nonoverlap', 'complete_overlap', 'empty_control', 'incomplete_ambient_reference'):
            truth, pred, score = fixture(kind); validate_score(score, truth, pred)
            changed = deepcopy(score); changed['integrated_N4_cells'] = 1
            with self.assertRaises(ValueError): validate_score(changed, truth, pred)
            if kind != 'complete_nonoverlap':
                changed = deepcopy(score); changed['primary_wer'] = fixture()[2]['primary_wer']
                with self.assertRaises(ValueError): validate_score(changed, truth, pred)

    def test_bad_edit_sums_denominators_rates_nan_and_boolean_counts(self):
        valid = fixture()[2]['primary_wer']; edit_counts(valid, 1, 1)
        for key, value in (('errors', 1), ('words', 2), ('rate', .5), ('deletions', 2), ('insertions', True), ('rate', float('nan'))):
            changed = dict(valid); changed[key] = value
            with self.assertRaises(ValueError): edit_counts(changed, 1, 1)
        with self.assertRaises(ValueError): edit_counts(valid, 1, 0)

    def test_empty_and_incomplete_denominators_are_not_zero_accuracy(self):
        truth, pred, score = fixture('empty_control'); score['inserted_words_per_minute'] = 0
        with self.assertRaises(ValueError): validate_score(score, truth, pred)
        truth, pred, score = fixture('incomplete_ambient_reference'); score['scoring_status'] = 'SCORED'
        with self.assertRaises(ValueError): validate_score(score, truth, pred)

    def test_metric_workers_require_exact_exit_pipe_closure_and_request_census(self):
        closed = dict(owners=[dict(pid=123, create_time=100.)], requests=2, all_exact_owners_exited=True,
                      pipe_threads_closed=True, stderr_bytes=0, stderr_retained_bytes=0)
        owners_closed([closed], 2, lookup=lambda owner: None)
        for key, value in (('requests', 1), ('pipe_threads_closed', False), ('all_exact_owners_exited', False), ('stderr_retained_bytes', 1)):
            changed = deepcopy(closed); changed[key] = value
            with self.assertRaises(ValueError): owners_closed([changed], 2, lookup=lambda owner: None)
        with self.assertRaises(ValueError): owners_closed([closed], 2, lookup=lambda owner: object())
        with self.assertRaises(ValueError): owners_closed([closed, closed], 4, lookup=lambda owner: None)
        def denied(owner): raise PermissionError('fixture')
        with self.assertRaises(PermissionError): owners_closed([closed], 2, lookup=denied)

    def test_partial_status_duplicate_cells_and_false_complete_are_rejected(self):
        result = dict(status='SCORED_MODELED_BANK_REQUIRES_REVIEW', stop_reason=None, required=2,
                      prediction_completed=2, prediction_failed=0, prediction_not_tested=0,
                      metrics_unavailable_for_complete_predictions=0, integrated_N4_cells=0, scores=[{'path': 'a'}, {'path': 'b'}])
        validate_terminal(result, {'required': 2})
        for key, value in (('status', 'PARTIAL_MODELED_BANK_SCORING'), ('stop_reason', 'TIMEOUT'), ('prediction_not_tested', 1),
                           ('prediction_completed', 1), ('scores', [{'path': 'a'}, {'path': 'a'}])):
            changed = deepcopy(result); changed[key] = value
            with self.assertRaises(ValueError): validate_terminal(changed, {'required': 2})

    def test_plan_truth_input_and_method_provenance_are_joined(self):
        truth, pred, score = fixture(); row = dict(cell_id='cell', composition='A0_D0_E0', contract={'mode': 'open_with_names'})
        job = {k: truth[k] for k in ('job_id', 'tap', 'frames')}; binding = {'fixture': 1}
        value = dict(cell_id='cell', job_id=truth['job_id'], case_id=truth['case_id'], tap='O0', composition='A0_D0_E0',
                     mode='open_with_names', score=score, method_result=binding, integrated_N4_cells=0,
                     metric_input_sha256=fingerprint(dict(truth=truth, prediction=pred)), metric_seconds=.1)
        validate_row(value, row, job, truth, pred, binding)
        for key, datum in (('metric_input_sha256', 'foreign'), ('method_result', None), ('tap', 'O1'), ('metric_seconds', float('inf'))):
            changed = deepcopy(value); changed[key] = datum
            with self.assertRaises(ValueError): validate_row(changed, row, job, truth, pred, binding)

    def test_aggregate_and_paired_report_is_recomputed(self):
        truth, pred, score = fixture(); rows = []
        strata = {'scene': dict(case_id='scene', dependency_cluster='cluster', room='room', family_id='family', actor_cluster='actor')}
        for composition in ('A0_D0_E0', 'A1_D0_E0'):
            for tap in ('O0', 'O1'):
                rows.append(dict(composition=composition, mode='open_with_names', tap=tap, job_id='scene_'+tap, case_id='scene', score=deepcopy(score)))
        actual = report(rows, strata, scope='fixture'); verify_report(actual, rows, strata, 'fixture')
        for mutate in (lambda r: r['cohorts'][0]['counts']['word_metrics']['cpwer'].update(words=0),
                       lambda r: r['paired'][0]['result'].update(clusters=2), lambda r: r.update(required_cells=3)):
            changed = deepcopy(actual); mutate(changed)
            with self.assertRaises(ValueError): verify_report(changed, rows, strata, 'fixture')

    def test_activity_scope_and_components_are_not_hardware_or_exact_timing(self):
        truth, pred, _ = fixture(); pred['activity'] = []
        value = dict(status='APPROXIMATE_ACTIVITY_ONLY', DER=1., JER=1.,
            DER_components={'total': 1., 'correct': 0., 'confusion': 0., 'missed detection': 1., 'false alarm': 0.},
            JER_components={'speaker count': 1., 'speaker error': 1.}, collar_parameter_seconds=.25,
            collar_halfwidth_seconds=.125, overlap='include', mapping='per-scene Hungarian', uem_seconds=[0, 2.],
            timing='existing mapped estimated activity, not phonetic gold')
        validate_activity(value, truth, pred)
        for key, datum in (('DER', 0), ('uem_seconds', [0, 20]), ('timing', 'exact')):
            changed = deepcopy(value); changed[key] = datum
            with self.assertRaises(ValueError): validate_activity(changed, truth, pred)

    def test_formatting_loss_and_omitted_changed_rows_are_checked(self):
        truth, pred, score = fixture(); pred['formatting'] = [dict(utterance_id='u1', raw_text='alpha', display_text='')]
        counts = dict(errors=1, words=1, deletions=1, substitutions=0, insertions=0, rate=1.)
        formatting = score['formatting_lexical_preservation']; formatting.update(totals=dict(utterances=1, **{k: v for k, v in counts.items() if k != 'rate'}),
            changed_utterances=[dict(utterance_id='u1', counts=counts)])
        validate_score(score, truth, pred)
        formatting['changed_utterances'] = []
        with self.assertRaises(ValueError): validate_score(score, truth, pred)


if __name__ == '__main__':
    pin(); unittest.main()
