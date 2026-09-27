"""Restart guard, provenance and unchanged lifecycle tests; see the V3 README."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind
import restart_family_v3 as family
import restart_application_plan_v2 as old_plan
import restart_application_plan_v3 as plan
import restart_application_runner_v2 as old_runner
import restart_application_runner_v3 as runner
import review_restart_run_v2 as old_review
import review_restart_run_v3 as review
import review_restart_content_run_v2 as old_content
import review_restart_content_run_v3 as content
import review_restart_content_cell as old_cell
import review_restart_content_cell_v3 as cell
import review_restart_complete as old_complete
import review_restart_complete_v3 as complete
from restart_application_child import control
from paced_child_admission_v4 import write_lease
from paced_slot_guarded_v1 import ExclusiveApplicationSlot

ACTUAL = {}


def function(module, name):
    return next(n for n in ast.parse(Path(module.__file__).read_text(encoding='utf-8')).body
                if isinstance(n, ast.FunctionDef) and n.name == name)


def same_function(a, b, name):
    return ast.dump(function(a, name), include_attributes=False) == ast.dump(function(b, name), include_attributes=False)


class GuardedRestartTests(unittest.TestCase):
    def built(self):
        return plan.build_plan(ACTUAL['panel_binding'], deepcopy(ACTUAL['panel']), ACTUAL['lifecycle'])

    def envelope(self, role='run'):
        cap, seconds = family.LIMITS[role]; code = [{'synthetic': True}]; pb = {'synthetic_plan': True}
        qb = {'synthetic_qualification': True}; resource = {'synthetic_resource': True}
        a = dict(code=code, plan=pb, qualification=qb, allocation_bytes=cap, maximum_seconds=seconds)
        e = dict(schema=family.SCHEMA, role=role, entry_script=bind(family.HERE/family.ENTRIES[role]),
            code=code, plan=pb, family_qualification=qb, resource_qualification=resource,
            allocation_bytes=cap, maximum_seconds=seconds, application_permission_from_envelope=False)
        return a, e, dict(role=role, code=code, plan=pb, qualification=qb), resource

    def validate(self, a, e, expected, resource):
        with patch.object(family.resource, 'qualification', return_value=resource):
            family.validate_envelope(a, e, **expected)

    def test_actual_twelve_pairs_and_twenty_four_sessions(self):
        p = self.built()
        self.assertEqual((p['required'], p['required_sessions']), (12, 24))
        self.assertEqual(p['candidates'], ACTUAL['panel']['candidates'])
        for i, row in enumerate(p['rows']):
            payload = plan.execution_payload(p, i)
            self.assertEqual(len(payload), 13)
            self.assertEqual(control(payload)['stop_after_samples'], row['stop_after_samples'])
            self.assertFalse(payload['source_execution_authorized'])

    def test_old_panel_schema_rejected(self):
        panel = deepcopy(ACTUAL['panel']); panel['schema'] = old_plan.panels.SCHEMA
        with self.assertRaises(ValueError): plan.build_plan({}, panel, {})

    def test_changed_source_relationship_rejected(self):
        panel = deepcopy(ACTUAL['panel']); panel['source_relationship'] = {}
        with self.assertRaises(ValueError): plan.build_plan({}, panel, {})

    def test_changed_application_policy_rejected(self):
        panel = deepcopy(ACTUAL['panel']); panel['context']['application_policy'] = {}
        with self.assertRaises(ValueError): plan.build_plan({}, panel, {})

    def test_partial_panel_rejected(self):
        panel = deepcopy(ACTUAL['panel']); panel['rows'].pop()
        with self.assertRaises(ValueError): plan.build_plan({}, panel, {})

    def test_duplicate_panel_occurrence_rejected(self):
        panel = deepcopy(ACTUAL['panel']); panel['rows'][1] = deepcopy(panel['rows'][0])
        with self.assertRaises(ValueError): plan.build_plan({}, panel, {})

    def test_payload_rows_cannot_change_midpoint(self):
        p = self.built(); p['rows'][0]['stop_after_samples'] += 320
        with self.assertRaises(ValueError): plan.execution_payload(p, 0)

    def test_payload_rows_cannot_gain_acceptance(self):
        p = self.built(); p['N4_accepted'] = True
        with self.assertRaises(ValueError): plan.execution_payload(p, 0)

    def test_payload_and_midpoint_logic_unchanged(self):
        for name in ('row_key', 'execution_payload', 'lifecycle_qualification'):
            self.assertTrue(same_function(old_plan, plan, name), name)

    def test_collection_changes_only_slot_allocation_arguments(self):
        old = function(old_runner, 'collect_one'); new = function(runner, 'collect_one')
        self.assertEqual([x.arg for x in new.args.kwonlyargs], ['allocation_guard', 'allocation_receipt'])
        self.assertEqual(new.args.kw_defaults, [None, None])
        new.args.kwonlyargs = []; new.args.kw_defaults = []
        calls = [n for n in ast.walk(new) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'ExclusiveApplicationSlot']
        self.assertEqual(len(calls), 1)
        self.assertEqual([k.arg for k in calls[0].keywords], ['allocation_guard', 'allocation_receipt'])
        calls[0].keywords = []
        self.assertEqual(ast.dump(old, include_attributes=False), ast.dump(new, include_attributes=False))
        self.assertIs(runner.write_lease, write_lease)
        self.assertIs(runner.ExclusiveApplicationSlot, ExclusiveApplicationSlot)

    def test_child_manifest_and_exit_gates_unchanged(self):
        for name in ('qualified_manifests', 'check_after_exit', 'check_child_result'):
            self.assertTrue(same_function(old_runner, runner, name), name)
        parent, child, exe, script = runner.qualified_manifests()
        _, old_child, old_exe, old_script = old_runner.qualified_manifests()
        self.assertEqual((child, exe, script), (old_child, old_exe, old_script))
        self.assertEqual(len(child), 122)
        self.assertTrue(all(b in parent for b in child))

    def test_existing_native_roster_viewport_readers_unchanged(self):
        self.assertTrue(same_function(old_cell, cell, 'review_cell'))
        self.assertTrue(same_function(old_complete, complete, 'review_cell'))
        self.assertIs(complete.join_reviews, old_complete.join_reviews)
        self.assertIs(cell.review_complete, complete.review_cell)

    def test_population_and_bounded_content_logic_unchanged(self):
        self.assertTrue(same_function(old_review, review, 'validate_population'))
        for name in ('review_population', 'freeze_bounded'):
            self.assertTrue(same_function(old_content, content, name), name)
        self.assertIs(content.review_cell, cell.review_cell)
        self.assertIs(content.stopped_run, review.stopped_run)

    def test_every_role_accepts_exact_bounded_envelope(self):
        for role in family.ENTRIES: self.validate(*self.envelope(role))

    def test_changed_budget_rejected_even_when_both_records_agree(self):
        for key in ('allocation_bytes', 'maximum_seconds'):
            a, e, expected, resource = self.envelope(); a[key] += 1; e[key] = a[key]
            with self.assertRaises(ValueError): self.validate(a, e, expected, resource)

    def test_wrong_entry_script_rejected(self):
        a, e, expected, resource = self.envelope(); e['entry_script'] = {}
        with self.assertRaises(ValueError): self.validate(a, e, expected, resource)

    def test_mismatched_plan_rejected(self):
        a, e, expected, resource = self.envelope(); a['plan'] = {}
        with self.assertRaises(ValueError): self.validate(a, e, expected, resource)

    def test_mismatched_code_rejected(self):
        a, e, expected, resource = self.envelope(); a['code'] = []
        with self.assertRaises(ValueError): self.validate(a, e, expected, resource)

    def test_foreign_resource_qualification_rejected(self):
        a, e, expected, resource = self.envelope(); e['resource_qualification'] = {}
        with self.assertRaises(ValueError): self.validate(a, e, expected, resource)

    def test_envelope_cannot_authorize_application(self):
        a, e, expected, resource = self.envelope(); e['application_permission_from_envelope'] = True
        with self.assertRaises(ValueError): self.validate(a, e, expected, resource)
