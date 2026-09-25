"""Planning and reference-firewall regressions. README_PACED_PANEL_PLAN.md."""
from copy import deepcopy
from itertools import product
from pathlib import Path
import tempfile
import unittest

from common import bind, freeze
from metric_process import identity, pin
from paced_panel_plan import (ANCHORS, BASELINE, COMPOSITIONS, build_plan, execution_payload,
                              read_review, validate_review_pair, validate_selection)


def selection(selected, reviews):
    return dict(schema='n4-paced-selection-v1', status='PROPOSED_PACED_EVALUATION_ONLY', reviews=deepcopy(reviews),
        selected=[dict(composition=c, objective='baseline' if c == BASELINE else 'independent_architecture',
                       rationale='Dictionary routing fixture, not a candidate selection.', limitations='No measured comparison or deployment claim.') for c in selected],
        excluded=[dict(composition=c, reason='Outside this dictionary routing fixture.') for c in sorted(COMPOSITIONS-set(selected))],
        limitations='Fixture only; actual selection requires both passed full-bank scoring reviews.')


def fixtures():
    catalog = {'backends': []}
    for a, d, e in product(('A0', 'A1', 'A2', 'A3'), ('D0', 'D1'), ('E0', 'E1')):
        c = '_'.join((a, d, e)); base = c == BASELINE
        comp = {} if base else dict(n2=dict(diarization=d, embedding=e, streaming_profile='low_latency'))
        if a != 'A0': comp['n3'] = dict(variant=a)
        catalog['backends'].append(dict(key='baseline' if base else c.lower(), implemented=True, composition=comp))
    jobs = [dict(job_id=f'N2_S45_{family:02d}_{case:02d}_{tap}', audio_path=f'X:/fixture/{family:02d}-{case:02d}-{tap}.wav',
                 audio_sha256='0'*64, frames=715127, sample_rate_hz=16000, gain=1., reset_between_scenes=True, tap=tap)
            for family in range(1, 13) for case in range(1, 21) for tap in ('O0', 'O1')]
    panel = [j for j in jobs if j['job_id'] in ANCHORS or (int(j['job_id'].split('_')[2]) not in (3, 6, 8, 12)
             and j['job_id'].split('_')[3] == '01')]
    regression = [j for j in jobs if j['job_id'] in ANCHORS]
    reviews = dict(main={'fixture': 'main'}, **{'modes-panel': {'fixture': 'modes'}})
    context = dict(source_receipt={'fixture': 'source'}, catalog={'fixture': 'catalog'},
                   runtimes={name: {'path': 'X:/fixture/'+name, 'sha256': '0'*64, 'bytes': 1} for name in ('n2_runtime.json', 'n3_runtime.json')},
                   gallery_preparation={'fixture': 'gallery'}, models_root='X:/fixture/models', assets=[], code=[])
    return jobs, panel, regression, catalog, context, reviews


def plan_fixture(candidates=None):
    jobs, panel, regression, catalog, context, reviews = fixtures()
    return build_plan(selection(candidates or [BASELINE, 'A3_D1_E1'], reviews), reviews, jobs, panel, regression, catalog, context)


class PacedPanelPlanTests(unittest.TestCase):
    def test_exact_paired_census_and_three_occurrences_of_each_anchor(self):
        plan = plan_fixture(); self.assertEqual(plan['required'], 80)
        for c in plan['candidates']:
            rows = [r for r in plan['rows'] if r['composition'] == c]
            self.assertEqual(sum(r['kind'] == 'panel' for r in rows), 24)
            self.assertEqual(sum(r['kind'] == 'timing_repeat' for r in rows), 16)
            for jid in ANCHORS: self.assertEqual(sum(r['job']['job_id'] == jid for r in rows), 3)
        self.assertFalse(plan['continuity_included']); self.assertFalse(plan['model_slot_admitted'])
        self.assertFalse(plan['N4_accepted']); self.assertEqual(plan['integrated_N4_cells'], 0)

    def test_baseline_required_unique_bounded_selection_and_exclusion_census(self):
        reviews = fixtures()[-1]; valid = selection([BASELINE, 'A1_D0_E0'], reviews); validate_selection(valid, reviews)
        changes = [lambda s: s['selected'].reverse(), lambda s: s['selected'].append(s['selected'][1]),
                   lambda s: s['excluded'].pop(), lambda s: s['selected'][1].update(rationale=''),
                   lambda s: s.update(status='RELEASE_ACCEPTED'), lambda s: s['selected'][1].update(objective='baseline')]
        for mutate in changes:
            changed = deepcopy(valid); mutate(changed)
            with self.assertRaises(ValueError): validate_selection(changed, reviews)
        with self.assertRaises(ValueError): validate_selection(selection(sorted(COMPOSITIONS)[:7], reviews), reviews)

    def test_main_and_mode_comparison_source_and_scope_must_match(self):
        main = dict(scope='main', required=7680, context={'source': 1}, jobs=[1])
        modes = dict(scope='modes-panel', required=1536, context={'source': 1}, jobs=[1])
        validate_review_pair(main, modes)
        for key, value in [('required', 24), ('context', {'source': 2}), ('jobs', [2]), ('scope', 'main')]:
            wrong = deepcopy(modes); wrong[key] = value
            with self.assertRaises(ValueError): validate_review_pair(main, wrong)

    def test_full_audio_panel_anchors_and_gain_cannot_change(self):
        for position, mutate in [(0, lambda v: v.pop()), (1, lambda v: v.pop()),
                                 (2, lambda v: v.__setitem__(0, v[1])), (1, lambda v: v[0].update(gain=2.))]:
            values = deepcopy(fixtures()); mutate(values[position]); jobs, panel, regression, catalog, context, reviews = values
            with self.assertRaises(ValueError): build_plan(selection([BASELINE], reviews), reviews, jobs, panel, regression, catalog, context)

    def test_inference_payload_is_an_allowlist_and_independent_copy(self):
        jobs, panel, regression, catalog, context, reviews = fixtures()
        context['evaluator_truth'] = {'transcript': 'DO_NOT_COPY'}
        plan = build_plan(selection([BASELINE], reviews), reviews, jobs, panel, regression, catalog, context)
        payload = execution_payload(plan, 0)
        self.assertEqual(set(payload), {'schema', 'cell_id', 'job', 'contract', 'execution', 'source_receipt', 'catalog',
            'runtimes', 'gallery_preparation', 'models_root', 'assets', 'source_execution_authorized', 'remaining_gate'})
        self.assertNotIn('DO_NOT_COPY', repr(payload)); self.assertNotIn('reviews', payload)
        self.assertFalse(payload['source_execution_authorized'])
        payload['job']['frames'] = 1; self.assertNotEqual(plan['rows'][0]['job']['frames'], 1)

    def test_changed_key_contract_execution_or_truth_in_job_is_rejected(self):
        changes = [lambda p: p['rows'][0]['job'].update(frames=1), lambda p: p['rows'][0]['contract'].update(adaptation=True),
                   lambda p: p['execution'].update(gpu=True), lambda p: p['context'].update(models_root='foreign'),
                   lambda p: p['rows'][0]['job'].update(transcript='forbidden')]
        for mutate in changes:
            plan = plan_fixture(); mutate(plan)
            with self.assertRaises(ValueError): execution_payload(plan, 0)

    def test_each_composition_has_a_distinct_fresh_source_key(self):
        keys = set()
        for candidate in sorted(COMPOSITIONS):
            plan = plan_fixture([BASELINE] if candidate == BASELINE else [BASELINE, candidate])
            row = next(r for r in plan['rows'] if r['composition'] == candidate)
            self.assertNotIn(row['cache_key'], keys); keys.add(row['cache_key'])
            self.assertFalse(row['contract']['adaptation'])
        self.assertEqual(len(keys), 16)

    def test_missing_or_partial_review_never_prepares_a_plan(self):
        with tempfile.TemporaryDirectory(prefix='n4-panel-review-fixture-') as tmp:
            path = Path(tmp)/'REVIEW.json'
            with self.assertRaises(FileNotFoundError): read_review(path)
            freeze(path, {'status': 'PARTIAL_MODELED_BANK_SCORING'})
            with self.assertRaises(ValueError): read_review(path)

    def test_live_exact_reviewer_is_rejected_without_loading_models(self):
        process = pin()
        with tempfile.TemporaryDirectory(prefix='n4-panel-owner-fixture-') as tmp:
            root = Path(tmp); freeze(root/'ADMISSION.json', {'owner': identity(process)}); freeze(root/'fixture.json', {})
            review = dict(status='PASS_REVIEWED_MODELED_SCORING_ONLY', all_metric_inputs_and_report_totals_verified=True,
                          N4_accepted=False, integrated_N4_cells=0, admission=bind(root/'ADMISSION.json'))
            for key in ('scoring_result', 'plan', 'method_review', 'report'): review[key] = bind(root/'fixture.json')
            freeze(root/'REVIEW.json', review)
            with self.assertRaisesRegex(ValueError, 'reviewer is still active'): read_review(root/'REVIEW.json')


if __name__ == '__main__':
    pin(); unittest.main()
