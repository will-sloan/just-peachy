"""No-model checks for the bounded CPU contrast; README_GUI_TWOCORE.md."""
import copy
from contextlib import ExitStack, nullcontext
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from prepare_gui_twocore import make_job, transformed, validate_failure, verify_derivatives
import supervise_n3_twocore as queue


class TwoCoreTests(unittest.TestCase):
    def test_exact_derivatives_preserve_all_nonresource_logic(self):
        verify_derivatives()

    def test_changed_or_duplicate_source_anchors_fail_closed(self):
        for original in ['', 'anchor anchor']:
            with self.assertRaises(ValueError):
                transformed(original, {'anchor':'replacement'})

    def test_diagnosis_requires_actual_cleanup_error_and_same_failed_receipt(self):
        binding = dict(path='failed/RESULT.json', sha256='fixture', bytes=1)
        failure = dict(status='FAILED', traceback='ERROR != STOPPED',
            cleanup_error='session lane edge-asr did not finish within 60 seconds')
        diagnosis = dict(status='DIAGNOSED_NOT_REPAIRED',
            equal_application_runtime_audio_and_cpu_contract=True,
            failed=dict(lane_drain_timeout_seconds=60.0, evidence=[binding]))
        validate_failure(failure, diagnosis, binding)
        for wrong in [dict(failure,status='COMPLETE'), dict(failure,cleanup_error='another failure')]:
            with self.assertRaises(ValueError):
                validate_failure(wrong, diagnosis, binding)
        with self.assertRaises(ValueError):
            validate_failure(failure, diagnosis, dict(binding,sha256='different'))

    def test_same_cells_model_flags_and_timeouts(self):
        old = dict(id='actual-gui-A3', gpu=False, depends_on=[], timeout_seconds=7500,
            argv=['python','-B','gui_finalaudit.py','--source','frozen','--output','old',
                  '--timeout-seconds','7200','--cell','A3_boundary','--cell','A3_short','--cell','A3_returning'])
        original = copy.deepcopy(old)
        revised = make_job(old, Path('new-output'))
        self.assertEqual(old, original)
        self.assertEqual(revised['cpu_affinity'], [4,14])
        self.assertEqual(revised['timeout_seconds'], old['timeout_seconds'])
        for i, value in enumerate(old['argv']):
            if i not in (2,6):
                self.assertEqual(revised['argv'][i], value)
        for mutation in [dict(old,id='actual-gui-A2'), dict(old,gpu=True),
                         dict(old,argv=old['argv'][:-2])]:
            with self.assertRaises(ValueError):
                make_job(mutation, Path('new-output'))

    def queue_context(self, stack, occupied):
        directory = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        document = dict(output=str(directory/'queue'), state=str(directory/'state'),
            worker_spec=str(directory/'worker.json'),
            n2=dict(numerical_result='numerical.json', chain_result='chain.json'))
        values = {'numerical.json':dict(completed=422),
            'chain.json':dict(owner={}, final_checks=dict(path='final.json', sha256='verified')),
            str(directory/'state'/'worker.json'):dict(status='RUNNING' if occupied else 'COMPLETE'),
            'final.json':dict(status='PASS')}
        stack.enter_context(patch.object(queue, 'load', side_effect=lambda p:values[str(p)]))
        stack.enter_context(patch.object(queue, 'before_cutoff'))
        stack.enter_context(patch.object(queue, 'prerequisite', return_value='READY'))
        stack.enter_context(patch.object(queue, 'owner_gone', return_value=True))
        stack.enter_context(patch.object(queue, 'sha', return_value='verified'))
        stack.enter_context(patch.object(queue, 'atomic'))
        stack.enter_context(patch.object(queue.supervisor, 'lock', side_effect=lambda *a,**k:nullcontext()))
        stack.enter_context(patch('psutil.Process', return_value=Mock(pid=1, create_time=lambda:2.0)))
        stack.enter_context(patch.object(queue.supervisor, 'require_no_active_worker',
            side_effect=RuntimeError('occupied') if occupied else None))
        return SimpleNamespace(plan=directory/'plan.json'), document

    def test_waiter_does_not_hash_bindings_while_candidate_is_active(self):
        with ExitStack() as stack:
            args, document = self.queue_context(stack, occupied=True)
            verify = stack.enter_context(patch.object(queue, 'verify'))
            launch = stack.enter_context(patch.object(queue.supervisor, 'start'))
            stack.enter_context(patch.object(queue.time, 'sleep', side_effect=KeyboardInterrupt))
            with self.assertRaises(KeyboardInterrupt):
                queue.wait_for_n2(args, document)
            verify.assert_not_called()
            launch.assert_not_called()

    def test_waiter_reverifies_before_dispatch_after_owner_release(self):
        with ExitStack() as stack:
            args, document = self.queue_context(stack, occupied=False)
            order = []
            stack.enter_context(patch.object(queue, 'verify', side_effect=lambda d:order.append('verify')))
            stack.enter_context(patch.object(queue.supervisor, 'phase', side_effect=lambda *a:order.append('phase')))
            stack.enter_context(patch.object(queue.supervisor, 'start', side_effect=lambda *a:order.append('start')))
            self.assertEqual(queue.wait_for_n2(args, document), 0)
            self.assertEqual(order, ['verify','phase','start'])


if __name__ == '__main__':
    unittest.main()
