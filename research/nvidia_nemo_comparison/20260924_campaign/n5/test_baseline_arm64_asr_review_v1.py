"""Model-free component-output refusal checks; README_BASELINE_ARM64_ASR_V1.md."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from baseline_arm64_asr_review_v1 import CONFIG,CASES,review,compare


class Refusals(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)/'events.jsonl'
        self.rows=[deepcopy(CONFIG)]
        for name,n in zip(CASES,(0,1281,4000,4000)):
            finals=[dict(text='SYNTHETIC READER FIXTURE',sent_frames=n,phase='finish')] if n else []
            self.rows.extend([dict(kind='case_start',case=name,frames=n),dict(kind='case_closed',case=name,frames=n,sent_frames=n,
                padding_frames=10560,endpoint_resets=0,stream_closed=True,finals=finals)])
        self.rows.append(dict(kind='complete',recognizer_closed=True,state_parity=True,CM5_tested=False,GUI_validated=False))

    def read(self,rows=None):
        self.path.write_text(''.join(json.dumps(r)+'\n' for r in (self.rows if rows is None else rows)),encoding='utf-8')
        return review(self.path,4000)

    def test_complete_and_equal(self):self.assertEqual(compare(self.read(),self.read())['cases'],4)
    def test_truncated_extra_and_wrong_config(self):
        bad=deepcopy(self.rows);bad[0]['threads']=2
        for rows in [self.rows[:-1],self.rows+[self.rows[-1]],bad]:
            with self.assertRaises(ValueError):self.read(rows)
    def test_order_source_flush_and_closure(self):
        for key,value in [('case','wrong'),('sent_frames',3999),('padding_frames',0),('stream_closed',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                r=deepcopy(self.rows);r[6][key]=value;self.read(r)
    def test_resident_state_mismatch(self):
        r=deepcopy(self.rows);r[8]['finals'][0]['text']='DIFFERENT'
        with self.assertRaises(ValueError):self.read(r)
    def test_cross_platform_mismatch(self):
        r=self.read();other=deepcopy(r);other['cases'][1]['finals'][0]['text']='DIFFERENT'
        with self.assertRaises(ValueError):compare(r,other)
    def test_duplicate_nonfinite_and_hardware_claim(self):
        for suffix in ['{"kind":"complete","kind":"complete"}\n','{"value":NaN}\n']:
            self.path.write_text(suffix,encoding='utf-8')
            with self.assertRaises(ValueError):review(self.path,4000)
        r=deepcopy(self.rows);r[-1]['CM5_tested']=True
        with self.assertRaises(ValueError):self.read(r)


if __name__=='__main__':unittest.main()
