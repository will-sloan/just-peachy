"""In-memory panel/allowlist tests; README_PACED_PANEL_PLAN_GUARDED_V1.md."""
from copy import deepcopy
from pathlib import Path
import unittest

import paced_panel_plan as original
import paced_panel_plan_v4 as legacy
import paced_panel_plan_guarded_v1 as subject
from test_paced_panel_plan import fixtures, selection


def context_fixture():
    jobs, panel, anchors, catalog, base, reviews = fixtures()
    source = dict(component_source_receipt=base['source_receipt'],
        component_catalog=base['catalog'], component_gallery_preparation=base['gallery_preparation'],
        source_receipt={'fixture': 'application-source'}, catalog={'fixture': 'application-catalog'},
        gallery_preparation={'fixture': 'application-gallery'}, runtimes=list(base['runtimes'].values()))
    scored = dict(source_receipt=source['component_source_receipt'], catalog=source['component_catalog'],
        gallery_preparation=source['component_gallery_preparation'], runtimes=base['runtimes'],
        manifest={'fixture': 'manifest'}, panel={'fixture': 'panel'})
    common = dict(manifest=scored['manifest'], panel=scored['panel'], regression={'fixture': 'anchors'},
        models_root='NO_MODEL_PAYLOAD', assets=[], planner_qualification={'fixture': 'pending'}, code=[])
    context = subject.application_context(scored, source, {'fixture': 'source-context'}, {'fixture': 'prestart'}, common)
    return jobs, panel, anchors, catalog, reviews, context, scored, source, common


def plan_fixture(candidates=None):
    jobs, panel, anchors, catalog, reviews, context, *_ = context_fixture()
    return subject.build_plan(selection(candidates or [original.BASELINE, 'A3_D1_E1'], reviews),
        reviews, jobs, panel, anchors, catalog, context)


class GuardedPanelTests(unittest.TestCase):
    def test_counts_baseline_pairing_and_no_execution_credit(self):
        p = plan_fixture()
        self.assertEqual(p['required'], 80)
        self.assertEqual(p['schema'], subject.SCHEMA)
        for c in p['candidates']:
            rows = [r for r in p['rows'] if r['composition'] == c]
            self.assertEqual(sum(r['kind'] == 'panel' for r in rows), 24)
            self.assertEqual(sum(r['kind'] == 'timing_repeat' for r in rows), 16)
            for anchor in original.ANCHORS:
                self.assertEqual(sum(r['job']['job_id'] == anchor for r in rows), 3)
        for k in ('N4_accepted', 'model_slot_admitted', 'inference_started', 'continuity_included'):
            self.assertIs(p[k], False)
        self.assertEqual(p['integrated_N4_cells'], 0)

    def test_payload_preserves_allowlist_and_parent_behavior(self):
        p = plan_fixture()
        for i, row in enumerate(p['rows']):
            out = subject.execution_payload(p, i)
            self.assertEqual(out, subject.previous.execution_payload(dict(p, schema=subject.previous.SCHEMA), i))
            self.assertEqual(out['job'], row['job'])
            self.assertEqual(len(out), 13)
            self.assertIs(out['source_execution_authorized'], False)
            for k in ('reviews', 'selection', 'scoring_review_policy', 'truth', 'reference', 'application_source_context'):
                self.assertNotIn(k, out)

    def test_builder_requires_exact_guarded_policy(self):
        jobs, panel, anchors, catalog, reviews, context, *_ = context_fixture()
        for policy in (None, {}, legacy.scores.POLICY, dict(subject.scores.POLICY, required_modes_panel=1)):
            c = deepcopy(context)
            if policy is None: del c['scoring_review_policy']
            else: c['scoring_review_policy'] = policy
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                subject.build_plan(selection([original.BASELINE], reviews), reviews, jobs, panel, anchors, catalog, c)

    def test_guarded_policy_changes_cache_not_inference_payload(self):
        jobs, panel, anchors, catalog, reviews, context, *_ = context_fixture()
        chosen = selection([original.BASELINE], reviews)
        new = subject.build_plan(chosen, reviews, jobs, panel, anchors, catalog, context)
        old_context = deepcopy(context); old_context['scoring_review_policy'] = deepcopy(legacy.scores.POLICY)
        old = legacy.build_plan(chosen, reviews, jobs, panel, anchors, catalog, old_context)
        self.assertNotEqual(new['rows'][0]['cache_key'], old['rows'][0]['cache_key'])
        self.assertEqual(subject.execution_payload(new, 0), legacy.execution_payload(old, 0))

    def test_changed_headers_or_policy_refused(self):
        for change in ('schema', 'relationship', 'policy', 'missing'):
            p = plan_fixture()
            if change == 'schema': p['schema'] = legacy.SCHEMA
            if change == 'relationship': p['scoring_relationship'] = legacy.SCORING_RELATIONSHIP
            if change == 'policy': p['context']['scoring_review_policy']['required_main'] = 1
            if change == 'missing': del p['context']['scoring_review_policy']
            with self.subTest(change=change), self.assertRaises(ValueError): subject.execution_payload(p, 0)

    def test_context_and_row_mutations_refused(self):
        for change in ('source', 'application_policy', 'job', 'contract', 'repeat'):
            p = plan_fixture()
            if change == 'source': p['context']['source_receipt'] = {'foreign': True}
            if change == 'application_policy': p['context']['application_policy'] = {}
            if change == 'job': p['rows'][0]['job']['frames'] += 1
            if change == 'contract': p['rows'][0]['contract']['mode'] = 'selected_closed'
            if change == 'repeat': p['rows'][0]['repeat'] = 99
            with self.subTest(change=change), self.assertRaises(ValueError): subject.execution_payload(p, 0)

    def test_caller_objects_and_child_copies_are_independent(self):
        values = context_fixture(); before = deepcopy(values)
        jobs, panel, anchors, catalog, reviews, context, *_ = values
        p = subject.build_plan(selection([original.BASELINE], reviews), reviews, jobs, panel, anchors, catalog, context)
        self.assertEqual(values, before)
        out = subject.execution_payload(p, 0); out['job']['frames'] = 1
        self.assertNotEqual(p['rows'][0]['job']['frames'], 1)
        for index in (-1, p['required'], True, 0.0):
            with self.subTest(index=index), self.assertRaises(ValueError): subject.execution_payload(p, index)

    def test_component_source_runtime_and_common_joins_refused(self):
        *_, scored, source, common = context_fixture()
        for field in ('source_receipt', 'catalog', 'gallery_preparation', 'runtimes', 'manifest', 'panel'):
            bad = deepcopy(scored); bad[field] = {'foreign': True}
            with self.subTest(field=field), self.assertRaises(ValueError):
                subject.application_context(bad, source, {}, {}, common)
        bad = deepcopy(common); bad['evaluator_truth'] = 'MUST_NOT_COPY'
        with self.assertRaises(ValueError): subject.application_context(scored, source, {}, {}, bad)

    def test_selection_ceiling_baseline_and_full_exclusions_preserved(self):
        candidates = [original.BASELINE, *sorted(original.COMPOSITIONS-{original.BASELINE})[:5]]
        self.assertEqual(plan_fixture(candidates)['required'], 240)
        for candidates in (["A3_D1_E1"], sorted(original.COMPOSITIONS)):
            with self.subTest(candidates=candidates), self.assertRaises(ValueError): plan_fixture(candidates)
        jobs, panel, anchors, catalog, reviews, context, *_ = context_fixture()
        chosen = selection([original.BASELINE], reviews); chosen['excluded'].pop()
        with self.assertRaises(ValueError):
            subject.build_plan(chosen, reviews, jobs, panel, anchors, catalog, context)

    def test_evaluator_fields_never_enter_child(self):
        jobs, panel, anchors, catalog, reviews, context, *_ = context_fixture()
        context['evaluator_truth'] = {'text': 'FORBIDDEN_EVALUATOR_SENTINEL'}
        p = subject.build_plan(selection([original.BASELINE], reviews), reviews, jobs, panel, anchors, catalog, context)
        for i in range(p['required']):
            out = subject.execution_payload(p, i)
            self.assertNotIn('FORBIDDEN_EVALUATOR_SENTINEL', repr(out))
            self.assertNotIn('evaluator_truth', out)


if __name__ == '__main__':
    from metric_process import pin
    pin(); unittest.main()
