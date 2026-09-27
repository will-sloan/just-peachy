"""Diagnostic reader boundary checks; baseline_asr_diagnostic_v2/README.md."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from run_baseline_asr_diagnostic_v2 import read_events


class Reader(unittest.TestCase):
    def rows(self):
        return [dict(kind='diagnostic_input',frames=2000,nonzero=100,peak=.2,sum_squares=1.,f32_le_fnv1a64='123abc'),
            dict(kind='case_start',case='fresh_full_source',frames=2000),
            dict(kind='case_closed',case='fresh_full_source',frames=2000,sent_frames=2000,padding_frames=10560,stream_closed=True,finals=[]),
            dict(kind='diagnostic_complete',recognizer_closed=True,nonempty=False,acceptance=False,CM5_tested=False)]
    def check(self,rows):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.jsonl';p.write_text(''.join(json.dumps(r)+'\n' for r in rows));return read_events(p,2000)
    def test_empty_output_is_diagnostic_only(self):
        self.assertFalse(self.check(self.rows())['complete']['acceptance'])
    def test_truncation_energy_and_source_loss_refused(self):
        for index,key,value in [(0,'peak',0),(0,'sum_squares',float('inf')),(0,'f32_le_fnv1a64','not-hash'),(2,'sent_frames',1999),(2,'stream_closed',False)]:
            rows=copy.deepcopy(self.rows());rows[index][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(rows)
        with self.assertRaises(ValueError):self.check(self.rows()[:-1])
    def test_acceptance_and_hardware_claim_refused(self):
        for key in ['acceptance','CM5_tested','nonempty']:
            rows=self.rows();rows[-1][key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(rows)


if __name__=='__main__':unittest.main()
