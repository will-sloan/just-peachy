"""File-only builder fixtures; see README_S6D_ENROLLMENT_INPUTS_BUILD.md."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
from s6d_enrollment_inputs_build_v1 import render_enrollment,headroom,write_enrollment,write_continuous,PAYLOAD
from s6d_capture_transport import quantize


class BuildChecks(unittest.TestCase):
    def test_full_convolution_tail_and_common_channel_origin(self):
        dry=np.array([.1,.2,0.,0.,-.15]);rir=np.array([[.2,.1,0.,0.],[0.,-.05,.3,0.],[.1,0.,0.,.2]])
        got=render_enrollment(dry,rir,9)
        expected=np.pad(np.column_stack([np.convolve(dry,rir[:,i],mode='full') for i in range(4)]),((0,2),(0,0)))
        np.testing.assert_allclose(got,expected,atol=1e-16,rtol=0)
        with self.assertRaisesRegex(ValueError,'tail would be clipped'):render_enrollment(dry,rir,6)

    def test_headroom_matches_frozen_packer_including_round_to_rail(self):
        for value in (0.,.5,-.5,.9999997,-.9999997,.99999999,-.99999999,1.,-1.,float('nan')):
            x=np.full((4,4),value);out=[]
            for operation in (headroom,quantize):
                try:operation(x);out.append(True)
                except ValueError:out.append(False)
            self.assertEqual(out[0],out[1],value)

    def test_float_write_preserves_all_samples_and_refuses_overwrite(self):
        root=PAYLOAD/'review_fixtures';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='E-builder-',dir=root) as tmp:
            path=Path(tmp)/'fixture.wav';x=np.random.default_rng(62).uniform(-.05,.05,(137,4))
            receipt=write_enrollment(path,x);self.assertEqual(receipt['frames'],137)
            with self.assertRaisesRegex(ValueError,'Preserve prior'):write_enrollment(path,x)

    def test_continuous_rejects_schedule_change_without_silent_padding(self):
        root=PAYLOAD/'review_fixtures';root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='long-builder-',dir=root) as tmp:
            with self.assertRaisesRegex(ValueError,'exact45s block schedule'):
                write_continuous(Path(tmp)/'fixture.wav',{'blocks':[{'source_start_sample':1,'source_stop_sample':720001}]})


if __name__=='__main__':unittest.main(verbosity=2)
