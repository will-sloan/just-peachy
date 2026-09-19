"""Small offline reference-contract regressions; README_S45_REFERENCES.md."""
import unittest
import numpy as np
import s45_references as r

class ReferenceTests(unittest.TestCase):
    def test_only_unused_development_enrollment_source(self):
        source={'split':'development','usage':'enrollment_reference','whole_clip':True,'duration_sec':4}
        self.assertTrue(r.reference_eligible(source))
        self.assertFalse(r.reference_eligible({**source,'usage':'probe'}))
        self.assertFalse(r.reference_eligible({**source,'split':'downstream_reserve'}))
    def test_three_second_start_full_tail_and_duration_bound(self):
        duration,stop=r.required_duration(10*16000,32812)
        self.assertTrue(20<=duration<=25)
        self.assertGreaterEqual(duration-stop/16000,5)
        self.assertEqual(stop,3*16000+10*16000+32812-1)
    def test_source_scalar_applied_once_four_distinct_channels(self):
        dry=np.array([1.,2.,3.]);kernel=np.array([[1.,2.,3.,4.]])
        actual=r.convolution_samples(dry,kernel,.1)
        np.testing.assert_allclose(actual,dry[:,None]*kernel*.1,rtol=1e-12,atol=1e-12)
    def test_source_tail_not_truncated(self):
        dry=np.array([0.,1.]);kernel=np.column_stack([np.array([1.,.5,.25])]*4)
        actual=r.convolution_samples(dry,kernel,1)
        self.assertEqual(actual.shape,(4,4));np.testing.assert_allclose(actual[-1],.25)

if __name__=='__main__':unittest.main()
