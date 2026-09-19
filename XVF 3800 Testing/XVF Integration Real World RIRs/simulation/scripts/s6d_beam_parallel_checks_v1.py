"""Tiny exact-membership checks; see README_S6D_BEAM_PARALLEL_PREPARE_V1.md."""
import argparse
from pathlib import Path
import unittest
import s6d_beam_parallel_prepare_v1 as P
class Checks(unittest.TestCase):
    def test_twelve_exactly_once_three_each(self):
        rows=[dict(job_id=str(i),fixed_payload={'value':i}) for i in range(12)];groups=P.partition(rows);self.assertEqual([len(g) for g in groups],[3]*4);self.assertEqual(groups[0],[rows[0],rows[4],rows[8]]);self.assertEqual({id(j) for g in groups for j in g},{id(j) for j in rows})
    def test_528_exactly_once_132_each(self):self.assertEqual([len(g) for g in P.partition([dict(job_id=str(i)) for i in range(528)])],[132]*4)
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):P.partition([dict(job_id='same'),dict(job_id='same')])
    def test_empty_rejected(self):
        with self.assertRaises(ValueError):P.partition([])
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();P.N.need(a.output.drive.upper()=='G:' and not a.output.exists(),'Fresh G output required');a.output.mkdir(parents=True)
    with (a.output/'TESTS.log').open('w',encoding='utf-8') as f:r=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    P.N.save(a.output/'RECEIPT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,source=P.N.bind(P.__file__),checks=P.N.bind(__file__),NN_calls=0));raise SystemExit(0 if r.wasSuccessful() else 1)
