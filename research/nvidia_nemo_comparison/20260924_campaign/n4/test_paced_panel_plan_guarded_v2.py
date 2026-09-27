"""Metadata-only regressions; README_PACED_PANEL_PLAN_GUARDED_V2.md."""
from copy import deepcopy
from pathlib import Path
import unittest

import paced_panel_plan_guarded_v2 as subject
from test_paced_panel_plan import selection
from test_paced_panel_plan_guarded_v1 import context_fixture


def plan_fixture():
    jobs, panel, anchors, catalog, reviews, context, *_ = context_fixture()
    context['preparation_policy'] = deepcopy(subject.PREPARATION_POLICY)
    return subject.build_plan(selection([subject.original.BASELINE, 'A3_D1_E0'], reviews),
        reviews, jobs, panel, anchors, catalog, context)


def assets_fixture():
    root = str(Path(__file__).resolve().parent/'metadata-fixture-models')
    source = {'fixture': 'source'}
    b = dict(path=str(Path(root)/'asset.bin'), sha256='0'*64, bytes=1)
    a = dict(models_root=root, component_contract=dict(source_receipt=source, assets=[b]))
    return dict(source_receipt=source), {'ASR': deepcopy(a), 'D1': deepcopy(a)}


def provenance_fixture():
    ab, eb, pb = [{'fixture': n} for n in ('admission', 'execution', 'plan')]
    code = [{'fixture': 'complete-code'}]; e = dict(fixture='expected-envelope')
    a = dict(execution_plan=eb, code=code, allocation_bytes=subject.CAP, maximum_seconds=subject.SECONDS)
    r = dict(status=subject.STATUS, admission=ab, execution_plan=eb, plan=pb, tests_passed=subject.TESTS,
        tests_skipped=0, model_assets_verified=True, actual_application_or_model_started=False,
        source_execution_authorized=False, N4_accepted=False, N5_complete=False, integrated_N4_cells=0)
    return [r, a, e, ab, eb, pb, code, deepcopy(e)]


class ProductionPlanTests(unittest.TestCase):
    def test_assets_join_is_deterministic_and_does_not_alias_inputs(self):
        scored, a = assets_fixture(); before = deepcopy(a)
        root, assets = subject.component_assets(scored, a)
        self.assertEqual(root, a['ASR']['models_root']); self.assertEqual(len(assets), 1)
        assets[0]['bytes'] = 2; self.assertEqual(a, before)

    def test_component_source_parent_and_required_roles_are_enforced(self):
        for change in ('source', 'missing', 'extra'):
            scored, a = assets_fixture()
            if change == 'source': a['D1']['component_contract']['source_receipt'] = {}
            if change == 'missing': del a['D1']
            if change == 'extra': a['E0'] = a['D1']
            with self.subTest(change=change), self.assertRaises(ValueError): subject.component_assets(scored, a)

    def test_mixed_roots_empty_conflicting_and_malformed_assets_are_refused(self):
        for change in ('root', 'relative', 'empty', 'conflict', 'size', 'path'):
            scored, a = assets_fixture()
            if change == 'root': a['D1']['models_root'] += '-other'
            if change == 'relative': a['ASR']['models_root'] = 'relative'
            if change == 'empty': a['D1']['component_contract']['assets'] = []
            if change == 'conflict': a['D1']['component_contract']['assets'][0]['sha256'] = '1'*64
            if change == 'size': a['D1']['component_contract']['assets'][0]['bytes'] = True
            if change == 'path': a['D1']['component_contract']['assets'][0]['path'] = 'relative'
            with self.subTest(change=change), self.assertRaises(ValueError): subject.component_assets(scored, a)

    def test_actual_policy_preserves_population_and_inference_allowlist(self):
        p = plan_fixture(); self.assertEqual(p['required'], 80)
        self.assertEqual(p['schema'], subject.SCHEMA)
        for i, row in enumerate(p['rows']):
            child = subject.execution_payload(p, i)
            self.assertEqual(len(child), 13); self.assertEqual(child['job'], row['job'])
            self.assertIs(child['source_execution_authorized'], False)
            self.assertNotIn('preparation_policy', child); self.assertNotIn('reviews', child)

    def test_wrong_schema_and_preparation_policy_cannot_authorize_payload(self):
        for change in ('schema', 'missing', 'permission'):
            p = plan_fixture()
            if change == 'schema': p['schema'] = subject.adapter.SCHEMA
            if change == 'missing': del p['context']['preparation_policy']
            if change == 'permission': p['context']['preparation_policy']['application_execution_authorized'] = True
            with self.subTest(change=change), self.assertRaises(ValueError): subject.execution_payload(p, 0)

    def test_changed_source_row_and_manifest_invalidate_child_cache(self):
        for change in ('source', 'job', 'code'):
            p = plan_fixture()
            if change == 'source': p['context']['source_receipt'] = {'foreign': True}
            if change == 'job': p['rows'][0]['job']['frames'] += 1
            if change == 'code': p['context']['code'] = [{'omitted': True}]
            with self.subTest(change=change), self.assertRaises(ValueError): subject.execution_payload(p, 0)

    def test_complete_closed_provenance_is_admitted_without_execution(self):
        v = provenance_fixture(); before = deepcopy(v)
        subject.validate_provenance(*v, owner_closed=True); self.assertEqual(v, before)

    def test_cross_receipt_substitution_is_refused(self):
        for index, field in ((0, 'admission'), (0, 'execution_plan'), (0, 'plan'), (1, 'execution_plan')):
            v = provenance_fixture(); v[index][field] = {'foreign': True}
            with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                subject.validate_provenance(*v, owner_closed=True)

    def test_budget_manifest_and_execution_envelope_changes_are_refused(self):
        for change in ('cap', 'seconds', 'code', 'envelope'):
            v = provenance_fixture()
            if change == 'cap': v[1]['allocation_bytes'] += 1
            if change == 'seconds': v[1]['maximum_seconds'] += 1
            if change == 'code': v[1]['code'] = []
            if change == 'envelope': v[2]['permission'] = True
            with self.subTest(change=change), self.assertRaises(ValueError): subject.validate_provenance(*v, owner_closed=True)

    def test_live_owner_or_ambiguous_closure_is_refused(self):
        for closed in (False, None, 1):
            with self.subTest(closed=closed), self.assertRaises(ValueError):
                subject.validate_provenance(*provenance_fixture(), owner_closed=closed)

    def test_partial_tests_skips_and_unverified_assets_are_refused(self):
        for field, value in (('tests_passed', 0), ('tests_passed', True), ('tests_skipped', 1), ('model_assets_verified', False)):
            v = provenance_fixture(); v[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): subject.validate_provenance(*v, owner_closed=True)

    def test_plan_preparation_cannot_claim_inference_or_acceptance(self):
        for field, value in (('status', 'COMPLETE'), ('actual_application_or_model_started', True),
            ('source_execution_authorized', True), ('N4_accepted', True), ('N5_complete', True), ('integrated_N4_cells', 1)):
            v = provenance_fixture(); v[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): subject.validate_provenance(*v, owner_closed=True)
