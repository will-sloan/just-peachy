"""Focused host-only readiness/fencing checks. README_XVF_READINESS.md."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def main():
    import psutil
    me = psutil.Process(); me.cpu_affinity([14]); sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--owner-receipt', type=Path, required=True)
    args = parser.parse_args()
    with args.owner_receipt.open('x', encoding='utf-8') as stream:
        json.dump(dict(pid=me.pid, create_time=me.create_time(), affinity=[14], purpose='focused XVF readiness fencing checks'), stream)
    runtime = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(runtime))
    from ui_restore_20261004.xvf_readiness import qualifying_fault, recover_previous_source
    from runtime_support import publish

    owner = dict(pid=21, start_ticks=4, boot_id='00000000-0000-0000-0000-000000000000')
    fault = dict(kind='CLOSED', stream_closed=True, lease_released=True, sent_samples=0,
        processed_acknowledgements=0, integrity=dict(route=None, restoration_ok=True), owner=owner,
        receipt=dict(metadata=dict(stream_start_return_perf_counter_ns=3), commands=[
            dict(command='VERSION', exit_code=0, stdout='VERSION 3 2 1'),
            dict(command='BLD_MSG', exit_code=0, stdout='BLD_MSG intdev-lr48-lin-i2c'),
            dict(command='AEC_MIC_ARRAY_TYPE', exit_code=255, stderr='Resource could not respond')]),
        status=dict(converted_samples=0))

    class Store:
        def __init__(self, directory): self.directory = directory
        def _artifact_path(self, session, suffix): return self.directory/session/suffix

    class Checks(unittest.TestCase):
        def fixture(self, root, physical=None):
            launch = root/'launches'/('a'*32); (launch/'worker').mkdir(parents=True)
            source = root/'recordings/sessions'/('b'*32)/'work/source'; source.mkdir(parents=True)
            physical = copy.deepcopy(fault) if physical is None else physical
            publish(source/'SOURCE_CLOSE.json', physical)
            publish(launch/'worker/SESSION.json', dict(session_id='b'*32))
            publish(root/'CURRENT_LAUNCH.json', dict(launch_id='a'*32))
            closed = dict(direct_child_reaped=True, stdout_reader_joined=True, registered_owner=owner,
                receipt_errors=[], nested_source=dict(closed=True, owner=owner, physical_receipt=physical))
            publish(launch/'HOST_CLOSURE.json', closed)
            manager = SimpleNamespace(process=None, closed=False, export_task=None, data_root=root,
                launches=root/'launches', store=Store(root/'recordings/sessions'), unit_ownership=None)
            raw = (source/'SOURCE_CLOSE.json').read_bytes(); sha = hashlib.sha256(raw).hexdigest()
            return manager, source, root/'recovery'/sha

        def test_exact_fault_trigger_and_changed_receipts(self):
            self.assertTrue(qualifying_fault(fault))
            for key, value in (('sent_samples', True), ('sent_samples', 1), ('processed_acknowledgements', False),
                               ('lease_released', False), ('stream_closed', False)):
                self.assertFalse(qualifying_fault(dict(fault, **{key: value})))
            changed = copy.deepcopy(fault); changed['receipt']['commands'][2]['exit_code'] = 1
            self.assertFalse(qualifying_fault(changed))

        def test_no_fault_no_device_action(self):
            with tempfile.TemporaryDirectory() as directory:
                manager, _, _ = self.fixture(Path(directory), dict(fault, sent_samples=160))
                with patch('subprocess.Popen', side_effect=AssertionError('No helper permitted')):
                    self.assertIsNone(recover_previous_source(manager))

        def test_incomplete_consumed_attempt_never_retries(self):
            with tempfile.TemporaryDirectory() as directory:
                manager, _, out = self.fixture(Path(directory)); out.mkdir(parents=True)
                publish(out/'RESTART_INTENT.json', dict(fault_sha256=out.name, maximum_sends=1))
                with patch('runtime_support.owner_status', return_value=dict(closed=True)), patch('subprocess.Popen', side_effect=AssertionError('No retry permitted')):
                    with self.assertRaisesRegex(RuntimeError, 'one-use evidence'):
                        recover_previous_source(manager)

        def test_successful_closed_readiness_reused_without_commands(self):
            with tempfile.TemporaryDirectory() as directory:
                manager, _, out = self.fixture(Path(directory)); out.mkdir(parents=True)
                publish(out/'RECOVERY.json', dict(fault_sha256=out.name, readiness_verified=True, owner=owner))
                publish(out/'HOST_CLOSURE.json', dict(owner=owner, natural_returncode=0, timeout=False,
                    direct_child_reaped=True, exact_owner_gone=True))
                with patch('runtime_support.owner_status', return_value=dict(closed=True)), patch('subprocess.Popen', side_effect=AssertionError('No repeated commands')):
                    self.assertEqual(recover_previous_source(manager)['status'], 'PREVIOUS_READINESS_REUSED')

        def test_missing_helper_owner_or_original_fault_drift_refused(self):
            with tempfile.TemporaryDirectory() as directory:
                manager, source, _ = self.fixture(Path(directory))
                with patch('runtime_support.owner_status', return_value=dict(closed=False)):
                    with self.assertRaisesRegex(RuntimeError, 'live or unverifiable'):
                        recover_previous_source(manager)
                changed = dict(fault, sent_samples=1)
                (source/'SOURCE_CLOSE.json').write_text(json.dumps(changed))
                with patch('runtime_support.owner_status', return_value=dict(closed=True)):
                    with self.assertRaisesRegex(RuntimeError, 'differs'):
                        recover_previous_source(manager)

        def test_readiness_from_other_helper_boot_not_reused(self):
            with tempfile.TemporaryDirectory() as directory:
                manager, _, out = self.fixture(Path(directory)); out.mkdir(parents=True)
                changed_owner = dict(owner, boot_id='11111111-1111-1111-1111-111111111111')
                publish(out/'RECOVERY.json', dict(fault_sha256=out.name, readiness_verified=True, owner=changed_owner))
                publish(out/'HOST_CLOSURE.json', dict(owner=changed_owner, natural_returncode=0, timeout=False,
                    direct_child_reaped=True, exact_owner_gone=True))
                with patch('runtime_support.owner_status', return_value=dict(closed=True)), patch('subprocess.Popen', side_effect=AssertionError('No historical retry')):
                    with self.assertRaisesRegex(RuntimeError, 'one-use evidence'):
                        recover_previous_source(manager)

        def test_retained_command_sequence_ast_and_helper_compilation(self):
            retained = ast.parse((runtime/'launch_xvf_recovery_action_v2.py').read_text())
            sequence = next(node.value.value for node in retained.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'SEQUENCE_SOURCE' for target in node.targets))
            expected = ast.parse(sequence).body[0]
            actual_tree = ast.parse((runtime/'ui_restore_20261004/xvf_readiness.py').read_text())
            actual = next(node for node in actual_tree.body if isinstance(node, ast.FunctionDef) and node.name == 'recovery_sequence')
            expected.body.pop(0); actual.body.pop(0)
            self.assertEqual(ast.dump(actual, include_attributes=False), ast.dump(expected, include_attributes=False))
            compile((runtime/'ui_restore_20261004/xvf_readiness_helper.py').read_bytes(), '<prepared-native-helper>', 'exec')

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__': sys.exit(main())
