"""Matched collection rejection tests. README_D0_REVIEW.md."""
from copy import deepcopy
import unittest
from review_d0_collection import validate_pair


def cells():
    vector=[1.]+[0.]*191
    row=dict(start_sample=0,end_sample=8000,evidence_kind='short',waveform_sha256='1'*64,
        clean_intervals=[[0,.5]],normalized_embedding=vector)
    left=dict(status='COMPLETE',encoder='E0',job=dict(frames=16000),admission_sha256='a',
        profile_sha256='b',segmentation_calls=2,error=None,telemetry=dict(identity_audio_samples=16000),vectors=[row])
    right=deepcopy(left);right['encoder']='E1'
    return left,right


class TestReview(unittest.TestCase):
    def test_equal_geometry_different_values_allowed(self):
        a,b=cells();b['vectors'][0]['normalized_embedding']=[0.,1.]+[0.]*190
        self.assertEqual(len(validate_pair(a,b)),1)
    def test_changed_waveform_hash_or_clean_support_rejected(self):
        for key,value in [('waveform_sha256','2'*64),('clean_intervals',[[.1,.5]])]:
            a,b=cells();b['vectors'][0][key]=value
            with self.assertRaises(ValueError):validate_pair(a,b)
    def test_missing_or_duplicate_vectors_rejected(self):
        a,b=cells();b['vectors']=[]
        with self.assertRaises(ValueError):validate_pair(a,b)
        a,b=cells();a['vectors']*=2;b['vectors']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate'):validate_pair(a,b)
    def test_nonfinite_or_nonunit_vectors_rejected(self):
        for value in (float('nan'),2.):
            a,b=cells();b['vectors'][0]['normalized_embedding'][0]=value
            with self.assertRaisesRegex(ValueError,'normalized'):validate_pair(a,b)
    def test_all_failed_and_missing_source_rejected(self):
        for change in [dict(status='FAILED'),dict(error='failed'),dict(profile_sha256='changed'),
                       dict(telemetry=dict(identity_audio_samples=100))]:
            a,b=cells();b.update(change)
            with self.assertRaises(ValueError):validate_pair(a,b)
    def test_no_speech_is_valid_empty_observation_not_missing_cell(self):
        a,b=cells();a['vectors']=[];b['vectors']=[]
        self.assertEqual(validate_pair(a,b),[])


if __name__=='__main__':unittest.main()
