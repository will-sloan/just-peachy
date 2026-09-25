"""D1 full-bank gates and storage tests. See README_D1_FULL_BANK.md."""
from copy import deepcopy
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import d1_full_bank as runner
from common import load
import test_d1_lane_components as lane
import test_review_asr_full_bank as asr_fixture
import review_asr_full_bank as asr_review


class TestD1FullBank(unittest.TestCase):
    def test_expanded_utf8_limit_preserves_complete_prior_events(self):
        stream=io.StringIO();writer=runner.BoundedTextWriter(stream,4)
        writer.write('éé')
        with self.assertRaisesRegex(RuntimeError,'D1'):writer.write('x')
        self.assertEqual(stream.getvalue(),'éé');self.assertEqual(writer.written,4)

    def test_actual_d1_source_tail_and_queries_survive_writer(self):
        lane.TestD1ActualLoop.setUpClass();fixture=lane.TestD1ActualLoop();capture=fixture.setup_capture()
        capture.log=runner.BoundedTextWriter(fixture.log)
        result=capture.run_capture(fixture.encoder)
        self.assertEqual(result['input_samples'],40005)
        self.assertEqual(result['embeddings'],3)
        self.assertEqual(result['telemetry']['n2_exclusive_runs_below_embedding_minimum'],1)
        self.assertEqual(fixture.native.finishes,1)

    def test_failed_or_partial_smoke_is_not_admitted(self):
        original=dict(status='PASS_D1_COMPONENT_SMOKE',component_cells=4,paired_files=2,
            rows=[{}]*4,integrated_N4_cells=0,Controller_widget_parity=False)
        for key,value in [('status','READY_FOR_REVIEW'),('component_cells',3),('rows',[{}]*3),
                ('integrated_N4_cells',4),('Controller_widget_parity',True)]:
            bad=deepcopy(original);bad[key]=value
            with patch.object(runner,'load',return_value=bad):
                with self.assertRaises(ValueError):runner.verify_smoke_review(Path('unused'))

    def test_disk_allocation_and_packaging_cutoff_stop(self):
        policy={'target_utc':'2026-09-28T14:48:19+00:00'}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(runner,'load',return_value=policy),patch.object(runner.supervisor,'disk_reserves',return_value=({},[])),patch.object(runner,'datetime',wraps=datetime) as clock:
                clock.now.return_value=datetime(2026,9,25,tzinfo=timezone.utc)
                runner.resource_guard(root,root)
                with patch.object(runner,'ALLOCATION',1):
                    with self.assertRaisesRegex(RuntimeError,'allocation'):runner.resource_guard(root,root)
                with patch.object(runner.supervisor,'disk_reserves',return_value=({},['C:'])):
                    with self.assertRaisesRegex(RuntimeError,'reserve'):runner.resource_guard(root,root)
                clock.now.return_value=datetime(2026,9,28,3,tzinfo=timezone.utc)
                with self.assertRaises(TimeoutError):runner.resource_guard(root,root)

    def test_missing_predecessor_does_not_start_model(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'remains prepared'):
                runner.require_predecessor({'predecessor_review_path':str(Path(directory)/'absent.json')})


class TestRealPredecessorReceipt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        asr_fixture.TestFullReview.setUpClass()
        cls.fixture=asr_fixture.TestFullReview
        cls.parent=deepcopy(cls.fixture.contract);cls.parent['output']=str(cls.fixture.root)
        output=cls.fixture.root.parent/'predecessor-review'
        with patch.object(asr_review,'verify_admission',return_value=cls.parent):
            asr_review.review(cls.fixture.root,output)
        cls.contract=dict(predecessor_review_path=str(output/'REVIEW.json'),asr_full_admission=cls.fixture.final['admission'])

    @classmethod
    def tearDownClass(cls):cls.fixture.tearDownClass()

    def test_real_review_all_1920_files_and_hashes_satisfy_gate(self):
        with patch.object(runner,'verify_asr_full',return_value=self.parent):
            result=runner.require_predecessor(self.contract)
        self.assertEqual(result['path'],self.contract['predecessor_review_path'])

    def test_missing_review_cell_or_live_owner_rejected(self):
        def changed(path):
            doc=load(path)
            if str(path)==self.contract['predecessor_review_path']:doc['cells'].pop()
            return doc
        with patch.object(runner,'load',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'complete ASR'):runner.require_predecessor(self.contract)
        with patch.object(runner,'verify_asr_full',return_value=self.parent),patch.object(runner.supervisor,'same_process',return_value=True):
            with self.assertRaisesRegex(ValueError,'remains active'):runner.require_predecessor(self.contract)


if __name__=='__main__':unittest.main()
