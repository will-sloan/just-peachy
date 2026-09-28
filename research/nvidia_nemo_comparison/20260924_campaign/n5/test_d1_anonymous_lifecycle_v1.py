"""Model-free qualification refusals; README_D1_ANONYMOUS_LIFECYCLE_V1.md."""
from copy import deepcopy
import unittest
from d1_anonymous_lifecycle_v1 import bypass_acceptance
from test_nemotron_windows_lifecycle_v1 import ReceiptRefusals


class BypassRefusals(unittest.TestCase):
    def setUp(self):
        self.parent=dict(model_cache=dict(asr_loads=1,speaker_loads=1),
            telemetry=dict(n2_embedding_calls=20,n2_seen_slots=[0,1]),
            expected_samples=100,source_samples=100,asr_samples=100,identity_samples=100,
            speaker_lag_sec=0,activity_frame_count=10,activity_fingerprint='activity',
            caption_fingerprint='captions',stored_caption_fingerprint='stored')
        self.candidate=deepcopy(self.parent)
        self.candidate['model_cache']['speaker_loads']=0
        self.candidate['telemetry'].update(n2_embedding_calls=0,n2_embedding_policy='BYPASSED_ANONYMOUS_NATIVE_SLOTS')

    def test_valid_pair(self):
        bypass_acceptance(self.parent,'parent')
        bypass_acceptance(self.candidate,'candidate',self.parent)

    def test_encoder_activity_refused(self):
        for where,key in [('model_cache','speaker_loads'),('telemetry','n2_embedding_calls')]:
            bad=deepcopy(self.candidate);bad[where][key]=1
            with self.subTest(key=key),self.assertRaises(ValueError):bypass_acceptance(bad,'candidate',self.parent)

    def test_parity_changes_refused(self):
        for key in ('expected_samples','source_samples','asr_samples','identity_samples','speaker_lag_sec',
                    'activity_frame_count','activity_fingerprint','caption_fingerprint','stored_caption_fingerprint'):
            bad=deepcopy(self.candidate);bad[key]='changed'
            with self.subTest(key=key),self.assertRaises(ValueError):bypass_acceptance(bad,'candidate',self.parent)

    def test_missing_policy_or_reference_refused(self):
        with self.assertRaises(ValueError):bypass_acceptance(self.candidate,'candidate')
        bad=deepcopy(self.candidate);bad['telemetry'].pop('n2_embedding_policy')
        with self.assertRaises(ValueError):bypass_acceptance(bad,'candidate',self.parent)

    def test_absent_native_activity_refused(self):
        for key,value in [('activity_frame_count',0)]:
            bad=deepcopy(self.parent);bad[key]=value
            with self.assertRaises(ValueError):bypass_acceptance(bad,'parent')
        bad=deepcopy(self.parent);bad['telemetry']['n2_seen_slots']=[]
        with self.assertRaises(ValueError):bypass_acceptance(bad,'parent')


if __name__=='__main__':unittest.main()
