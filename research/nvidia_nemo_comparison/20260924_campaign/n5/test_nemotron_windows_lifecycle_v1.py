"""Model-free refusal tests; see README_NEMOTRON_WINDOWS_LIFECYCLE_V1.md."""
from copy import deepcopy
import unittest
from nemotron_windows_lifecycle_v1 import acceptance


class ReceiptRefusals(unittest.TestCase):
    def setUp(self):
        self.r=dict(status='PASS_NEMOTRON_PHASE',phase='reopen',controller_closed=True,worker_alive=False,
            lock_released=True,errors=[],rendered_rows=2,stored_rows=2,saved_audio_only=True,
            sentinel_preserved=True,test_session_deleted=True,
            pages=[dict(requested=p,actual=p) for p in ('modes','backends','sessions','settings')])
        self.r.update(backend_id='sha256:fixture',mode='caption_only')
        self.l=dict(status='OWNED_PROCESS_LIFETIME_CLOSED',forced=False,job_empty_verified=True,
            root_exit_code=0,observed_members_exited=True)

    def test_full_samples_and_speaker_drain_required(self):
        r=deepcopy(self.r); r.update(phase='infer',expected_samples=16000,source_samples=16000,asr_samples=16000,writers_drained=True)
        acceptance(r,self.l)
        r['asr_samples']=15999
        with self.assertRaises(ValueError):acceptance(r,self.l)
        r.update(asr_samples=16000,mode='anonymous_conversation',identity_samples=15999,speaker_lag_sec=0)
        with self.assertRaises(ValueError):acceptance(r,self.l)
        r['identity_samples']=16000; acceptance(r,self.l)
        r['speaker_lag_sec']=1
        with self.assertRaises(ValueError):acceptance(r,self.l)

    def test_complete_receipt(self):acceptance(self.r,self.l)

    def test_partial_and_failed_phase_refused(self):
        for key,value in [('status','FAILED_NEMOTRON_PHASE'),('controller_closed',False),('worker_alive',True),
                          ('lock_released',False),('errors',['failure']),('rendered_rows',0),('stored_rows',0)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                r=deepcopy(self.r); r[key]=value; acceptance(r,self.l)

    def test_persistence_and_privacy_evidence_required(self):
        for key in ('sentinel_preserved','saved_audio_only','test_session_deleted'):
            with self.subTest(key=key),self.assertRaises(ValueError):
                r=deepcopy(self.r); r[key]=False; acceptance(r,self.l)

    def test_navigation_incomplete_refused(self):
        r=deepcopy(self.r); r['pages'].pop()
        with self.assertRaises(ValueError):acceptance(r,self.l)

    def test_forced_or_uncertain_lifetime_refused(self):
        for key,value in [('status','FAILED_LIFETIME_PRESERVED'),('forced',True),('job_empty_verified',False),
                          ('root_exit_code',1),('observed_members_exited',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                life=deepcopy(self.l); life[key]=value; acceptance(self.r,life)


if __name__=='__main__':unittest.main()
