"""Raw-word, activity and denominator regressions. README_INTEGRATED_SCORING.md."""
from copy import deepcopy
from pathlib import Path
import unittest

from common import load,verify
from integrated_scoring_adapter import convert,raw_projection,native_activity,score_prediction,read_artifact,read_component_events
from metrics import aggregate,require_versions

HERE=Path(__file__).resolve().parent


def fixture():
    contract={'diarization':'D0'}
    state=dict(caption_key='scene/u1',utterance_id='u1',text='alpha beta',display_text='Alpha, beta!',
        final=True,word_spans=[{},{}])
    publication=dict(status='PASS_MODELED_MODE_APPLICATION_METHODS_ONLY',
        publication_method_qualification='ACTUAL_METHODS_WITH_MODELED_MODULE_CLOCKS',contract=contract,
        presentation={'rows':[state]})
    rows=[dict(caption_key='scene/u1',utterance_id='u1',raw_asr_text='alpha ',token_range=[0,1],visible=True,final=True,track_id=0),
          dict(caption_key='scene/u1',utterance_id='u1',raw_asr_text='beta',token_range=[1,2],visible=True,final=True,track_id=None)]
    projection=dict(status='PASS_ACTUAL_CONSUMER_AND_LABEL_PROJECTION_ONLY',contract=contract,controller_closed=True,
        consumer_thread_alive=False,physical_widget_observed=False,controller_raw_rows=[deepcopy(state)],final_rows=rows)
    return publication,projection


def truth(kind='complete_nonoverlap'):
    return dict(job_id='scene',reference_class=kind,frames=32000,complete_reference=True,
        turns=[dict(identity='r1',transcript='alpha beta',activity_ranges_samples_estimated=[[0,16000]])])


class ScoringAdapterTests(unittest.TestCase):
    def test_pinned_versions(self):
        self.assertEqual(require_versions(),{'meeteval':'0.4.3','pyannote.metrics':'4.1'})

    def test_raw_fragments_rejoin_exactly_and_zero_tracker_is_not_unknown(self):
        pub,proj=fixture();raw,segments,formatting=raw_projection(pub,proj)
        self.assertEqual(raw,'alpha beta');self.assertEqual([r['track'] for r in segments],['0','Unknown'])
        self.assertEqual(formatting[0]['display_text'],'Alpha, beta!')
        proj['final_rows'].reverse()
        self.assertEqual(raw_projection(pub,proj)[0],raw)

    def test_dropped_duplicated_mutated_hidden_and_overlapping_fragments_rejected(self):
        for change in (lambda p:p['final_rows'].pop(),lambda p:p['final_rows'].append(p['final_rows'][0]),
                lambda p:p['final_rows'][0].update(raw_asr_text='wrong '),lambda p:p['final_rows'][0].update(visible=False),
                lambda p:p['final_rows'][1].update(token_range=[0,2])):
            pub,proj=fixture();change(proj)
            with self.assertRaises(ValueError):raw_projection(pub,proj)

    def test_d0_masks_cannot_be_promoted_to_global_speaker_activity(self):
        pub,proj=fixture();pred=convert(pub,proj,[],dict(job_id='scene',frames=32000),'D0')
        result=score_prediction(truth(),pred)
        self.assertIsNone(pred['activity']);self.assertIsNone(result['activity']['DER'])
        self.assertIn('UNAVAILABLE_D0',result['activity_support']['global_activity_status'])
        self.assertEqual(result['primary_wer']['errors'],0)
        self.assertIn('UNAVAILABLE',result['naming_metrics_status'])
        self.assertEqual(result['constant_speaker_controls']['all_unknown'],result['constant_speaker_controls']['all_one_name'])

    def test_formatting_lexical_loss_is_reported_without_overwriting_raw(self):
        pub,proj=fixture();pub['presentation']['rows'][0]['display_text']='Alpha!'
        pred=convert(pub,proj,[],dict(job_id='scene',frames=32000),'D0');result=score_prediction(truth(),pred)
        self.assertEqual(pred['raw_text'],'alpha beta');self.assertEqual(result['primary_wer']['errors'],0)
        self.assertEqual(result['formatting_lexical_preservation']['totals']['deletions'],1)

    def test_empty_success_failed_and_not_tested_have_distinct_denominators(self):
        pub,proj=fixture();pub['presentation']['rows']=[];proj['controller_raw_rows']=[];proj['final_rows']=[]
        empty=score_prediction(truth(),convert(pub,proj,[],dict(job_id='scene',frames=32000),'D0'))
        self.assertEqual(empty['primary_wer']['deletions'],2)
        failed=score_prediction(truth(),dict(job_id='scene',status='FAILED'))
        absent=score_prediction(truth(),dict(job_id='scene',status='NOT_TESTED'))
        self.assertIsNone(failed['primary_wer']);self.assertIsNone(absent['primary_wer'])
        total=aggregate([empty,failed,absent]);self.assertEqual(total['required_cells'],3)
        self.assertEqual(total['unscored_execution_reference_words'],4)
        self.assertEqual(total['primary_nonoverlap_words'],2)

    def test_overlap_and_incomplete_reference_do_not_get_ordinary_primary_wer(self):
        pub,proj=fixture();pred=convert(pub,proj,[],dict(job_id='scene',frames=32000),'D0')
        t=truth('complete_overlap');t['turns'].append(dict(identity='r2',transcript='gamma delta',activity_ranges_samples_estimated=[[0,16000]]))
        result=score_prediction(t,pred)
        self.assertIsNone(result['primary_wer']);self.assertEqual(result['cpwer']['words'],4)
        t=truth('incomplete_ambient_reference');t['complete_reference']=False;result=score_prediction(t,pred)
        self.assertIsNone(result['primary_wer']);self.assertIn('TARGET_ONLY',result['scoring_status'])

    def packet(self):
        return dict(event_type='n2_diarization_frames',payload=dict(frame_start=0,frame_step_sec=.1,audio_received_sec=.15,
            track_ids=[f'scene:nemotron-slot-{i}' for i in range(8)],probabilities=[[.8,.7,0,0,0,0,0,0],[0,.9,0,0,0,0,0,0]]))

    def test_native_overlap_and_overhang_retain_actual_delivered_support(self):
        activity,support=native_activity([self.packet()],'scene',1.)
        self.assertEqual(len(activity),3);self.assertEqual(support['native_frames'],2)
        self.assertAlmostEqual(support['overhang_seconds'],.05)
        self.assertEqual(activity[-1]['end'],.15)
        self.assertEqual(activity[0]['start'],activity[1]['start'])

    def test_native_foreign_duplicate_nonfinite_or_future_frames_rejected(self):
        for change in (lambda r:r['payload'].update(frame_start=1),lambda r:r['payload'].update(audio_received_sec=2.),
                lambda r:r['payload']['track_ids'].__setitem__(0,'foreign'),
                lambda r:r['payload']['probabilities'][0].__setitem__(0,float('nan'))):
            row=self.packet();change(row)
            with self.assertRaises(ValueError):native_activity([row],'scene',1.)
        with self.assertRaises(ValueError):native_activity([self.packet(),self.packet()],'scene',1.)

    def test_real_baseline_and_d1_method_evidence_preserves_all_words(self):
        public=load(HERE/'APPLICATION_PUBLICATION_CHECK_V1.json');verify(public['private_receipt'])
        checks=load(public['private_receipt']['path'])['checks']
        for backend in ('baseline','n4_a3_d1_e1'):
            row=next(r for r in checks if r['backend']==backend and r['mode']=='open_with_names' and r['tap']=='O0')
            for b in row['inputs']:verify(b)
            a,s=[load(b['path']) for b in row['inputs']]
            pub=read_artifact(row['publication']);proj=read_artifact(row['projection'])
            pred=convert(pub,proj,read_component_events(s),a['job'],pub['contract']['diarization'])
            self.assertEqual(pred['raw_text'],' '.join(r['text'] for r in pub['presentation']['rows']))
            self.assertEqual(pred['activity'] is None,backend=='baseline')


if __name__=='__main__':unittest.main()
