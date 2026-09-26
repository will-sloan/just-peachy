"""Evaluator provenance rejection tests. README_SCORING_HISTORY_V3.md."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import bind, freeze
from integrated_prefix_reuse import reuse_cell
from scoring_bank_v3 import admit_reuse, validate_producer


class ScoringReuseTests(unittest.TestCase):
    def receipt(self):
        return dict(admission={'path':'fixture'}, plan='old-plan', terminal='old-terminal',
                    completed=2, prediction_digests=['first','second'],
                    all_full_artifacts_closures_and_conversion_verified=True)

    def admit(self, receipt, active=False, **changes):
        admission=dict(owner={'pid':1,'create_time':1.},plan='old-plan',terminal='old-terminal')
        admission.update(changes)
        with patch('integrated_prefix_reuse.load_reuse',return_value=receipt), \
                patch('scoring_bank_v3.verify'), patch('scoring_bank_v3.load',return_value=admission), \
                patch('scoring_bank_v3.exact_process',return_value=object() if active else None):
            return admit_reuse({'context':{}})

    def test_closed_review_required(self):
        self.assertEqual(self.admit(self.receipt()),self.receipt())
        with self.assertRaises(ValueError):self.admit(self.receipt(),active=True)

    def test_incomplete_digest_or_closure_proof_rejected(self):
        for key,value in [('prediction_digests',[]),('all_full_artifacts_closures_and_conversion_verified',False)]:
            receipt=self.receipt();receipt[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.admit(receipt)

    def test_review_producer_plan_and_terminal_are_exact(self):
        for key in ('plan','terminal'):
            with self.subTest(key=key),self.assertRaises(ValueError):self.admit(self.receipt(),**{key:'foreign'})

    def test_reused_receipt_retains_original_producer_and_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);freeze(root/'old-plan.json',{'old':True});freeze(root/'new-plan.json',{'new':True})
            old_plan,new_plan=bind(root/'old-plan.json'),bind(root/'new-plan.json')
            old=dict(plan=old_plan,cell_id='cell',job_id='audio',contract={'mode':'open'},parents=[],
                     outputs={'publication':'unchanged'},cache_key='old')
            freeze(root/'old-cell.json',old)
            receipt=dict(completed=1,plan=old_plan,cells=[bind(root/'old-cell.json')])
            row=dict(old,cache_key='new');cell=reuse_cell(row,new_plan,receipt,0)
            validate_producer(cell,row,new_plan,receipt,0)
            for key in ('reused_from','execution_source','outputs','plan','cache_key'):
                broken=deepcopy(cell);broken.pop(key)
                with self.subTest(key=key),self.assertRaises(ValueError):
                    validate_producer(broken,row,new_plan,receipt,0)

    def test_new_cells_cannot_claim_unqualified_reuse(self):
        for receipt,index in [(None,0),({'completed':2},2)]:
            validate_producer({}, {}, {}, receipt,index)
            for key in ('reused_from','execution_source'):
                with self.subTest(key=key,receipt=receipt),self.assertRaises(ValueError):
                    validate_producer({key:None},{},{},receipt,index)


if __name__=='__main__':unittest.main()
