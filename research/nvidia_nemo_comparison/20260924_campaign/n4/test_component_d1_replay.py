"""Actual D1 activity/name/span replay tests. README_COMPONENT_D1_REPLAY.md."""
from copy import deepcopy
import json
import threading
import unittest
from unittest.mock import patch

import test_d1_lane_components as fixtures
from test_component_s7_replay import advance, push, asr
from component_d1_replay import d1_plan, replay_d1_anonymous


class TestD1Replay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.TestD1ActualLoop.setUpClass()
        from app.pipeline import effective_profile
        cls.profile = effective_profile('balanced','anonymous_conversation','O0')

    def fixture(self):
        fixture = fixtures.TestD1ActualLoop()
        capture = fixture.setup_capture()
        summary = capture.run_capture(fixture.encoder)
        rows = [json.loads(line) for line in fixture.log.getvalue().splitlines()]
        return fixture, rows, summary

    def replay(self, fixture, rows, summary, observations=None, **options):
        duration = len(fixture.wave)/16000
        if observations is None:
            observations = [asr(ready=1.01,end=.6,text='actual first words')]
        commands = [push('asr',r) for r in observations]+[advance('asr',None,max(duration,observations[-1]['available_at_sec']))]
        return replay_d1_anonymous(commands,rows,wave=fixture.wave,summary=summary,
            namespace=fixture.encoder.namespace,profile=self.profile,session_id='test-scene',**options)

    def test_actual_query_frame_short_turn_and_close_census(self):
        f, rows, summary = self.fixture()
        result = self.replay(f,rows,summary)
        self.assertEqual(result['embedding_calls'],3)
        self.assertEqual(result['scan']['native_frames'],251)
        self.assertEqual(result['scan']['short_runs'],1)
        self.assertEqual(result['native_event_counts']['research_embedding'],3)
        self.assertFalse(result['d1_worker_alive'])
        self.assertFalse(result['worker_counts']['thread_alive'])
        self.assertEqual(result['worker_counts']['accepted'],result['worker_counts']['completed'])
        self.assertEqual(result['integrated_N4_cells'],0)

    def test_text_arrives_during_actual_embedding_lock_then_gets_exact_span_revision(self):
        f, rows, summary = self.fixture()
        plan = d1_plan(rows,f.wave,summary,f.encoder.namespace,'test-scene')
        group = next(g for g in plan['groups'] if g['queries'])
        ready = (group['dispatch']['modeled_available_at_sec']+group['queries'][0]['event']['available_at_sec'])/2
        result = self.replay(f,rows,summary,[asr(ready=ready,end=.6,text='kept all words')])
        step = next(r for r in result['execution'] if r['lane']=='asr' and r['operation']=='push')
        self.assertEqual(step['activity_phase'],'query_wait')
        raw = next(r for r in result['presentation_events'] if r['kind']=='s6d_text_ready')
        revision = next(r for r in result['native_events'] if r['event_type']=='transcript_label_revision')
        self.assertGreater(revision['modeled_publication_at_sec'],raw['modeled_available_at_sec'])
        self.assertEqual(revision['payload']['target_text_revision_id'],'asr:00000001')
        row = result['presentation']['rows'][0]
        self.assertEqual(row['text'],'kept all words')
        self.assertTrue(all(s['track_id']=='test-scene:nemotron-slot-0' for s in row['segments']))
        self.assertEqual(set(revision['payload']['target_span_ids']),{s['id'] for s in row['word_spans']})

    def test_overlap_stays_unassigned_and_no_majority_speaker_is_invented(self):
        f, rows, summary = self.fixture()
        event = asr(ready=1.01,end=.85,text='overlap words');event['source_start_sec']=.65
        result = self.replay(f,rows,summary,[event])
        revisions = [r['payload'] for r in result['native_events'] if r['event_type']=='transcript_label_revision']
        self.assertTrue(revisions)
        self.assertTrue(all(p['replacement_tracker_id'] is None for p in revisions))
        self.assertTrue(all(p['association']['overlap'] for p in revisions))
        self.assertEqual(result['presentation']['rows'][0]['text'],'overlap words')

    def test_short_turn_without_embedding_still_has_native_anonymous_activity(self):
        f,rows,summary = self.fixture()
        event = asr(ready=2.01,end=1.4,text='short actual words');event['source_start_sec']=1.
        result = self.replay(f,rows,summary,[event])
        row = result['presentation']['rows'][0]
        self.assertEqual(row['segments'][0]['track_id'],'test-scene:nemotron-slot-1')
        queries = [r['payload']['model_slot'] for r in result['native_events'] if r['event_type']=='research_embedding']
        self.assertNotIn(1,queries)
        self.assertEqual(result['scan']['short_runs'],1)

    def test_delayed_asr_and_formatting_keep_raw_final_and_endpoint_overhang(self):
        f,rows,summary = self.fixture()
        event=asr(ready=3.,end=2.5003125,text='last words')
        event['source_start_sec']=2.4
        fmt=dict(utterance_id=event['utterance_id'],input_event_id=event['event_id'],raw_text=event['text'],
            punctuation={'text':'Last words.'},modeled_available_at_sec=3.1)
        result = self.replay(f,rows,summary,[event],formatting=[fmt])
        row=result['presentation']['rows'][0]
        self.assertEqual(row['text'],'last words')
        self.assertEqual(row['display_text'],'Last words.')
        frames=[r['payload'] for r in result['native_events'] if r['event_type']=='n2_diarization_frames']
        self.assertAlmostEqual(frames[-1]['endpoint_overhang_sec'],2.51-2.5003125)
        self.assertLessEqual(max(p['source_end_sec'] for r in result['native_events']
            if r['event_type']=='research_embedding' for p in [r['payload']]),len(f.wave)/16000)

    def test_changed_query_waveform_namespace_and_native_slot_identity_are_rejected(self):
        f,rows,summary = self.fixture()
        f.wave[0] += .1
        with self.assertRaisesRegex(ValueError,'waveform'): self.replay(f,rows,summary)
        f,rows,summary = self.fixture()
        changed=deepcopy(rows)
        next(r for r in changed if r['event_type']=='research_embedding')['payload']['model_namespace']={'wrong':True}
        with self.assertRaisesRegex(ValueError,'namespace'):self.replay(f,changed,summary)
        with self.assertRaisesRegex(ValueError,'slot namespace'):
            d1_plan(rows,f.wave,summary,f.encoder.namespace,'other-scene')

    def test_missing_final_query_and_clock_regression_are_rejected_before_threads(self):
        f,rows,summary = self.fixture()
        for kind in ('component_d1_embedding_call','component_d1_dispatch'):
            changed=deepcopy(rows)
            del changed[max(i for i,r in enumerate(changed) if r['event_type']==kind)]
            with self.assertRaises(ValueError):self.replay(f,changed,summary)
        changed=deepcopy(rows)
        next(r for r in changed if r['event_type']=='research_embedding')['payload']['available_at_sec']=0.
        with self.assertRaises(ValueError):self.replay(f,changed,summary)

    def test_no_d0_tracker_update_and_no_known_name_without_gallery(self):
        from edge_speech_pipeline.research_tracking_v3 import S6CTracker
        f,rows,summary=self.fixture()
        with patch.object(S6CTracker,'update',side_effect=AssertionError('D1 must not use D0 clustering')):
            result=self.replay(f,rows,summary)
        decisions=[r['payload'] for r in result['native_events'] if r['event_type']=='speaker_decision']
        self.assertEqual(len(decisions),3)
        self.assertTrue(all(p['known_profile_id'] is None for p in decisions))
        self.assertEqual(result['name_map']['calls'],3)

    def test_real_worker_exception_releases_both_threads(self):
        from app.n2_pipeline import N2Engine
        f,rows,summary=self.fixture()
        names={'n4-cached-d1-activity','edge-s7-observed-policy'}
        before={t.ident for t in threading.enumerate() if t.name in names}
        with patch.object(N2Engine,'_accept_activity',side_effect=ValueError('deliberate activity failure')):
            with self.assertRaisesRegex(RuntimeError,'deliberate activity failure'):self.replay(f,rows,summary)
        self.assertEqual(before,{t.ident for t in threading.enumerate() if t.name in names})


if __name__=='__main__':unittest.main()
