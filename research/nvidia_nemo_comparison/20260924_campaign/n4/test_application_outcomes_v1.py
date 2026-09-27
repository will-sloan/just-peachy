"""Failure discrimination against preserved V8 evidence; README_APPLICATION_OUTCOMES_V1.md."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, load
import review_application_failure_v1 as failure
import paced_application_runner_v9 as runner

CONTEXT = {}


class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.root = CONTEXT['failed_cell']
        names = ('transport/CHILD_RESULT.json', 'application/RESULT.json', 'PARENT_CLOSURE.json',
                 'application/ENGINE_CLOSURE.json', 'application/delivery/OBSERVATION.json', 'transport/INPUT.json')
        self.values = [load(self.root/n) for n in names]

    def reject(self, index, mutate):
        mutate(self.values[index])
        with self.assertRaises((ValueError, KeyError)): failure.classify(*self.values)

    def test_observed_timeout_is_failure_with_zero_acceptance(self):
        r = failure.classify(*self.values)
        self.assertEqual(r['lane'], 'edge-speaker')
        self.assertEqual(r['source_frames_delivered'], 715127)
        self.assertFalse(r['success_credit']); self.assertFalse(r['N4_accepted'])

    def test_unknown_primary_is_rejected(self):
        self.reject(3, lambda d: d.update(finalization_error='out of memory'))

    def test_cleanup_failure_is_rejected(self):
        self.reject(2, lambda d: d.update(cleanup_error='unclosed child'))

    def test_resource_guard_error_is_rejected(self):
        self.reject(2, lambda d: d.update(error='ValueError: disk floor reached'))

    def test_live_lane_is_rejected(self):
        self.reject(3, lambda d: d['threads']['lane_1'].update(alive=True))

    def test_live_writer_is_rejected(self):
        self.reject(3, lambda d: d['text_writers'][0].update(closed=False))

    def test_callback_failure_is_rejected(self):
        self.reject(1, lambda d: d.update(callback_errors=['other Tk error']))

    def test_incomplete_source_is_rejected(self):
        self.reject(3, lambda d: d['source'].update(sent=1))

    def test_append_failure_is_rejected(self):
        self.reject(4, lambda d: d['summary'].update(failed_appends=1))

    def test_foreign_job_is_rejected(self):
        self.reject(3, lambda d: d['job'].update(job_id='foreign'))

    def test_additional_application_failure_is_rejected(self):
        self.reject(1, lambda d: d['errors'].append('lease expired'))

    def test_preserved_actual_transport_and_exact_closure(self):
        a = load(self.root.parents[1]/'ADMISSION.json')
        permit = load(self.root/'transport/PERMIT.json')
        lifetime = load(self.root/'transport/LIFETIME.json')
        argv = load(self.root.parents[1]/'worker.json')['argv']
        r = failure.review(self.root, payload=self.values[-1], plan_sha256=permit['plan_sha256'],
            coordinator=a['owner'], code=a['code'], executable=lifetime['executable'],
            script=lifetime['script'], coordinator_argv=argv, state=Path(permit['state']))
        self.assertEqual(r['status'], 'VERIFIED_FAILED_CELL_NO_ACCEPTANCE')
        self.assertFalse(r['N4_accepted'])
        CONTEXT['actual_review'] = r

    def test_forced_lifetime_cannot_continue(self):
        life = load(self.root/'transport/LIFETIME.json'); life['forced'] = True
        with self.assertRaises(ValueError):
            failure.validate_lifetime(life, owner=life['owner'], executable=life['executable'],
                script=life['script'], argv_sha256=life['argv_sha256'], desktop=life['desktop'], cpu=4, expected_exit=1)

    def test_all_existing_child_and_supervision_functions_unchanged(self):
        def functions(name):
            tree = ast.parse((runner.HERE/name).read_text())
            return {n.name: ast.dump(n, include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
        old, new = functions('paced_application_runner_v8.py'), functions('paced_application_runner_v9.py')
        for name in old.keys()-{'run', 'code_bindings'}: self.assertEqual(old[name],new[name],name)

    def test_other_exceptions_still_stop_the_run(self):
        with patch.object(runner,'collect_one',side_effect=ValueError('lease expired')):
            with self.assertRaisesRegex(ValueError,'lease expired'):
                runner.collect_outcome({},0,Path('unused'),Path('unused'),[],allocation_guard=None,allocation_receipt=None)

    def test_success_still_requires_original_collector(self):
        receipt = {'path':'original collection receipt'}
        with patch.object(runner,'collect_one',return_value=receipt) as collector:
            value = runner.collect_outcome({},0,Path('unused'),Path('unused'),[],allocation_guard=None,allocation_receipt=None)
        collector.assert_called_once()
        self.assertEqual(value,dict(outcome='collected_requires_review',receipt=receipt))


if __name__ == '__main__':
    raise SystemExit('Run the admitted probe; it binds the actual failed cell and complete source lineage.')
