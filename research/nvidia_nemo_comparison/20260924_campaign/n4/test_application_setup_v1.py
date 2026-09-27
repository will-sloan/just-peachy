"""Lease-open and failure-diagnostic checks. README_APPLICATION_SETUP_V1.md."""
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import freeze
import paced_child_admission_v7 as gate
import paced_application_runner_v10 as runner
from probe_lease_open_race_v1 import exercise

CONTEXT = {}


class SetupTests(unittest.TestCase):
    def test_concurrent_open_and_rename_has_no_error(self):
        root = CONTEXT['fixture_root']/'concurrent-open'
        result = exercise(root, reader=gate.bounded_json)
        CONTEXT['concurrent_open'] = result
        self.assertEqual(result['errors'],[])
        self.assertGreaterEqual(result['writes'],1000)
        self.assertGreaterEqual(result['reads'],1000)
        self.assertTrue(result['writer_closed'])

    def test_open_does_not_resolve_a_mutating_directory_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'LEASE.json'; path.write_bytes(b'{"sequence":1}')
            with patch.object(Path,'resolve',side_effect=AssertionError('must open the admitted pathname')):
                self.assertEqual(gate.bounded_json(path,4096),{'sequence':1})

    def test_missing_open_has_filename_and_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'LEASE.json'
            with self.assertRaises(FileNotFoundError) as caught: gate.bounded_json(path,4096)
            self.assertEqual(caught.exception.winerror,2)
            self.assertEqual(caught.exception.filename,str(path))
            self.assertFalse(path.exists())

    def test_all_other_gate_functions_unchanged(self):
        def nodes(name):
            return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse((runner.HERE/name).read_text()).body
                if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        old,new=nodes('paced_child_admission_v6.py'),nodes('paced_child_admission_v7.py')
        for name in old.keys()-{'shared_reader'}: self.assertEqual(old[name],new[name],name)

    def test_collector_supervision_unchanged(self):
        def nodes(name):
            return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse((runner.HERE/name).read_text()).body
                if isinstance(n,ast.FunctionDef)}
        old,new=nodes('paced_application_runner_v9.py'),nodes('paced_application_runner_v10.py')
        for name in old.keys()-{'code_bindings','run','child_main','collect_outcome'}:
            self.assertEqual(old[name],new[name],name)

    def test_missing_application_result_stops_without_hiding_child_error(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            freeze(folder/'transport/CHILD_RESULT.json',dict(cell_result=None,error='FileNotFoundError: fixture WinError 2'))
            with patch.object(runner,'collect_one',side_effect=ValueError('Application child did not exit normally')):
                with self.assertRaisesRegex(ValueError,'Application setup failed before RESULT: FileNotFoundError'):
                    runner.collect_outcome({},0,folder,Path('unused'),[],allocation_guard=None,allocation_receipt=None)
            self.assertFalse((folder/'FAILED_CELL.json').exists())

    def test_private_traceback_has_callsite_without_locals(self):
        try: raise FileNotFoundError('fixture')
        except FileNotFoundError as exc: detail=runner.child_failure_detail(exc,'prime')
        self.assertEqual(detail['phase'],'prime')
        self.assertEqual(detail['exception_type'],'FileNotFoundError')
        self.assertEqual(detail['frames'][-1]['function'],'test_private_traceback_has_callsite_without_locals')
        self.assertTrue(all(set(frame)=={'file','line','function'} for frame in detail['frames']))


if __name__ == '__main__': raise SystemExit('Use the admitted probe and its fresh private fixture output.')
