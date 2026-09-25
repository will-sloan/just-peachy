"""Total activity, causal history and support limits. README_D0_ACTIVITY.md."""
from copy import deepcopy
import unittest
from d0_activity_evidence import D0ActivityEvidence


def payload(speech=(1,1,1),overlap=(0,0,0),available=10.1):
    return dict(source_end_sec=10.,modeled_available_at_sec=available,receptive_start_sec=0.,
        receptive_end_sec=10.,left_padding_sec=0.,frame_step_sec=.016875,frame_duration_sec=.0619375,
        speech_frames=list(speech),overlap_frames=list(overlap))


class TestActivity(unittest.TestCase):
    def setUp(self):
        self.ledger=D0ActivityEvidence(160123,clock_kind='modeled_component_availability')
    def claim(self,key,track=1,start=.03,end=.045,available=10.2,committed=True):
        self.ledger.track(key,source_start_sec=0.,source_end_sec=10.,available_at_sec=available,
            track_id=track,clean_intervals=[[start,end]],observation_id='embedding:'+key,committed=committed)
    def check_total(self,snapshot):
        rows=snapshot['spans']
        self.assertEqual(rows[0]['start'],0.)
        self.assertEqual(rows[-1]['end'],160123/16000)
        for a,b in zip(rows,rows[1:]):self.assertEqual(a['end'],b['start'])
        self.assertAlmostEqual(sum(r['end']-r['start'] for r in rows),160123/16000)
    def test_initial_whole_source_unobserved_never_silence(self):
        value=self.ledger.snapshot();self.check_total(value)
        self.assertEqual(value['mask_seconds'],{'unobserved':160123/16000})
        self.assertFalse(value['global_diarization_or_DER_qualified'])
    def test_exact_half_sample_frame_support_and_unanalyzed_tail(self):
        self.ledger.segmentation('seg1',payload());value=self.ledger.snapshot();self.check_total(value)
        speech=[r for r in value['spans'] if r['state']=='speech']
        self.assertEqual(speech[0]['start'],721/32000)
        self.assertEqual(speech[-1]['end'],2341/32000)
        self.assertAlmostEqual(value['mask_seconds']['speech'],3*.016875)
        self.assertEqual(value['spans'][-1]['state'],'unobserved')
    def test_no_embedding_does_not_delete_detected_speech(self):
        self.ledger.segmentation('seg1',payload());value=self.ledger.snapshot()
        self.assertAlmostEqual(value['unassigned_single_speech_sec'],3*.016875)
        self.assertEqual(value['supported_single_speech_sec'],0.)
    def test_track_does_not_extend_outside_clean_support(self):
        self.ledger.segmentation('seg1',payload());self.claim('d1');value=self.ledger.snapshot();self.check_total(value)
        rows=[r for r in value['spans'] if r['track_id']==1]
        self.assertEqual([(r['start'],r['end']) for r in rows],[(.03,.045)])
        self.assertAlmostEqual(value['supported_single_speech_sec'],.015)
        self.assertAlmostEqual(value['unassigned_single_speech_sec'],3*.016875-.015)
    def test_conflicting_tracks_never_choose_by_latest_arrival(self):
        self.ledger.segmentation('seg1',payload());self.claim('d1');self.claim('d2',track=2,available=10.3)
        value=self.ledger.snapshot();self.check_total(value)
        rows=[r for r in value['spans'] if r['assignment']=='conflicting_tracks']
        self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['track_id'])
        self.assertEqual(rows[0]['candidate_track_ids'],[1,2])
    def test_overlap_not_relabelled_as_single_person(self):
        self.ledger.segmentation('seg1',payload(overlap=(1,1,1)));self.claim('d1')
        value=self.ledger.snapshot()
        self.assertEqual(value['supported_single_speech_sec'],0.)
        self.assertAlmostEqual(value['overlap_without_global_source_assignment_sec'],3*.016875)
        self.assertTrue(all(r['track_id'] is None for r in value['spans']))
    def test_later_mask_preserves_first_and_prior_snapshot(self):
        self.ledger.segmentation('seg1',payload());before=self.ledger.snapshot();saved=deepcopy(before)
        self.ledger.segmentation('seg2',payload(speech=(0,0,0),available=10.4));after=self.ledger.snapshot()
        self.assertEqual(before,saved)
        row=next(r for r in after['spans'] if r['state']=='silence')
        self.assertEqual(after['observations'][row['first_mask_observation']]['mask'],'speech')
        self.assertEqual(after['observations'][row['latest_mask_observation']]['mask'],'silence')
    def test_provisional_and_unresolved_claims_remain_explicit(self):
        self.ledger.segmentation('seg1',payload());self.claim('d1',committed=False);self.claim('d2',track=None,available=10.3)
        row=next(r for r in self.ledger.snapshot()['spans'] if r['track_id']==1)
        self.assertFalse(row['has_committed_track_support']);self.assertTrue(row['unresolved_claim_also_present'])
    def test_future_and_backward_events_rejected_without_mutation(self):
        self.ledger.segmentation('seg1',payload());before=self.ledger.snapshot()
        for now in (9.,10.05,float('nan')):
            with self.assertRaises(ValueError):self.ledger.segmentation('bad',payload(available=now))
            self.assertEqual(before,self.ledger.snapshot())
    def test_mask_and_support_rejection_without_mutation(self):
        before=self.ledger.snapshot()
        for changed in (payload(overlap=(1,0,0),speech=(0,0,0)),payload(speech=(float('nan'),1,1))):
            with self.assertRaises(ValueError):self.ledger.segmentation('bad',changed)
            self.assertEqual(before,self.ledger.snapshot())
        with self.assertRaises(ValueError):self.claim('bad',start=-.1)
        self.assertEqual(before,self.ledger.snapshot())
    def test_duplicate_event_and_resource_bounds(self):
        self.ledger.segmentation('seg1',payload())
        with self.assertRaises(ValueError):self.ledger.segmentation('seg1',payload())
        small=D0ActivityEvidence(160123,clock_kind='modeled_component_availability',max_events=1)
        small.segmentation('seg1',payload())
        with self.assertRaises(ValueError):small.segmentation('seg2',payload(available=10.2))
        small=D0ActivityEvidence(160123,clock_kind='modeled_component_availability',max_segments=1)
        with self.assertRaises(ValueError):small.segmentation('seg1',payload())
        self.assertEqual(len(small.snapshot()['spans']),1)
    def test_observed_clock_must_be_explicit_not_substituted(self):
        ledger=D0ActivityEvidence(160123,clock_kind='observed_policy_availability')
        with self.assertRaises(KeyError):ledger.segmentation('seg1',payload())
        value=payload();value['observed_available_at_sec']=10.3;ledger.segmentation('seg1',value)
        self.assertEqual(ledger.snapshot()['availability_through_sec'],10.3)


if __name__=='__main__':unittest.main()
