"""Named/anonymous causal mode integration tests. README_COMPONENT_MODES.md."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from common import bind,freeze,load
import test_mode_galleries as galleries
import test_d1_lane_components as fixtures
from test_component_s7_replay import advance,push,asr,embedding
from component_d1_replay import d1_plan
from component_mode_replay import replay_d0_mode,replay_d1_mode


class TestComponentModes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        galleries.TestModeGalleries.setUpClass();fixtures.TestD1ActualLoop.setUpClass()

    def setUp(self):
        g=galleries.TestModeGalleries();g.setUp();self.addCleanup(g.doCleanups)
        ip,rp=g.fixture();rows=galleries.verified_primary(bind(ip),bind(rp),'E0');conditions={}
        for mode,row in rows.items():
            conditions[mode]={k:row[k] for k in ('condition','namespace','source_gallery')}
            conditions[mode]['baseline_manifest']=galleries.materialize_baseline(row,g.root/'bridge'/mode)
        self.namespace=g.namespace
        path=g.root/'GALLERIES.json';freeze(path,dict(status='PREPARED_VERIFIED_RESEARCH_GALLERIES_ONLY',
            catalog=bind(g.source/'config/backends.json'),encoders={'E0':{'conditions':conditions}}))
        self.preparation=bind(path)

    def d0(self,backend='baseline',mode='enrolled_names',speaker=None,**kwargs):
        a=[push('asr',asr()),advance('asr',None,1.25)]
        speaker=[push('speaker',embedding()),advance('speaker',None,1.25)] if speaker is None else speaker
        return replay_d0_mode(a,speaker,duration=1.25,preparation=self.preparation,backend=backend,mode=mode,
            tap='O0',namespace=self.namespace,session_id='protocol-only',**kwargs)

    def fixture(self):
        f=fixtures.TestD1ActualLoop();capture=f.setup_capture();f.encoder.namespace=self.namespace
        summary=capture.run_capture(f.encoder);rows=[json.loads(line) for line in f.log.getvalue().splitlines()]
        return f,rows,summary

    def d1(self,f,rows,summary,mode,observations=None):
        observations=observations or [asr(ready=1.01,end=.6,text='kept original words')]
        a=[push('asr',r) for r in observations]+[advance('asr',None,max(len(f.wave)/16000,observations[-1]['available_at_sec']))]
        return replay_d1_mode(a,rows,wave=f.wave,summary=summary,namespace=self.namespace,preparation=self.preparation,
            backend='nemotron_hybrid',mode=mode,tap='O0',session_id='test-scene')

    def test_original_and_n2_d0_resolvers_are_catalog_specific(self):
        baseline=self.d0();n2=self.d0('compact_eou')
        self.assertEqual(baseline['contract']['resolver'],'PrototypeIdentityResolver')
        self.assertEqual(n2['contract']['resolver'],'N2NameMap')
        decisions=[r['decision'] for r in n2['policy_events'] if r['event_type']=='speaker_decision']
        self.assertTrue(decisions)
        self.assertTrue(all(r['identity']['calibration_status']=='UNCALIBRATED_REJECT_ALL' for r in decisions))
        self.assertTrue(all(r['known_profile_id'] is None for r in decisions))
        self.assertEqual(n2['presentation']['rows'][0]['text'],baseline['presentation']['rows'][0]['text'])

    def test_missing_voice_closed_fallback_is_published_without_mutating_state(self):
        lane=[advance('speaker',None,1.25)]
        baseline=self.d0(mode='selected_closed',speaker=lane)
        n2=self.d0('compact_eou','selected_closed',speaker=lane)
        self.assertTrue(baseline['display_events'])
        for row in baseline['display_events']:
            self.assertNotIn('closed_display_assignment',row['state_row'])
            self.assertIn('closed_display_assignment',row['published_row'])
            self.assertFalse(row['published_row']['closed_display_assignment']['voice_identity_verified'])
        self.assertTrue(all('closed_display_assignment' not in r['published_row'] for r in n2['display_events']))
        self.assertNotIn('closed_display_assignment',baseline['presentation']['rows'][0])

    def test_d1_closed_uses_actual_name_history_and_exact_queries(self):
        f,rows,summary=self.fixture()
        opened=self.d1(f,rows,summary,'selected_focus');closed=self.d1(f,rows,summary,'selected_closed')
        self.assertEqual(opened['embedding_calls'],closed['embedding_calls'])
        self.assertEqual(closed['embedding_calls'],3)
        decisions=[r['payload'] for r in closed['native_events'] if r['event_type']=='speaker_decision']
        self.assertTrue(all(p['naming_state']=='closed_assumption' and not p['identity']['verified'] for p in decisions))
        self.assertTrue(any(p['published_row'].get('closed_display_assignment') or
            any(s.get('closed_display_assignment') for s in p['published_row'].get('segments',[])) for p in closed['display_events']))
        self.assertTrue(all(r['payload']['known_profile_id'] is None for r in opened['native_events'] if r['event_type']=='speaker_decision'))
        self.assertEqual(opened['presentation']['rows'][0]['text'],closed['presentation']['rows'][0]['text'])
        self.assertFalse(closed['d1_worker_alive']);self.assertEqual(closed['integrated_N4_cells'],0)

    def test_d1_raw_text_during_locked_query_does_not_borrow_future_closed_name(self):
        f,rows,summary=self.fixture();plan=d1_plan(rows,f.wave,summary,self.namespace,'test-scene')
        group=next(g for g in plan['groups'] if g['queries']);ready=(group['dispatch']['modeled_available_at_sec']+group['queries'][0]['event']['available_at_sec'])/2
        result=self.d1(f,rows,summary,'selected_closed',[asr(ready=ready,end=.6,text='before query')])
        first=result['display_events'][0]
        self.assertNotIn('closed_display_assignment',first['published_row'])
        self.assertEqual(next(r for r in result['execution'] if r['lane']=='asr' and r['operation']=='push')['activity_phase'],'query_wait')
        supported=[r for r in result['display_events'] if any(s.get('known_profile_id') for s in r['published_row'].get('segments',[]))]
        self.assertTrue(supported);self.assertGreater(supported[0]['modeled_at_sec'],first['modeled_at_sec'])

    def test_d1_overlap_has_no_invented_closed_voice_match_or_d0_clustering(self):
        from edge_speech_pipeline.research_tracking_v3 import S6CTracker
        f,rows,summary=self.fixture();event=asr(ready=1.01,end=.85);event['source_start_sec']=.65
        with patch.object(S6CTracker,'update',side_effect=AssertionError('No D0 tracker in D1')):
            result=self.d1(f,rows,summary,'selected_closed',[event])
        self.assertTrue(all(s.get('known_profile_id') is None for s in result['presentation']['rows'][0]['segments']))
        self.assertTrue(all('closed_display_assignment' not in r['published_row'] for r in result['display_events']))

    def test_final_formatting_preserves_words_and_mode_scopes(self):
        fmt=dict(utterance_id='utterance:000000',input_event_id='asr:00000001',raw_text='one two',
            punctuation={'text':'One two.'},modeled_available_at_sec=1.3)
        result=self.d0('compact_eou','open_with_names',formatting=[fmt])
        self.assertEqual(result['presentation']['rows'][0]['text'],'one two')
        self.assertEqual(result['display_events'][-1]['published_row']['display_text'],'One two.')
        self.assertFalse(result['observed_Controller_parity']);self.assertFalse(result['physical_widget_observed'])

    def test_foreign_namespace_wrong_diarizer_and_gallery_mutation_rejected(self):
        from component_mode_replay import ModeReplay
        with self.assertRaisesRegex(ValueError,'namespaces'):
            ModeReplay(self.preparation,'compact_eou','selected_closed','O0',{'foreign':True},'s')
        with self.assertRaisesRegex(ValueError,'D0 commands'):self.d0('nemotron_hybrid')
        gallery=load(self.preparation['path'])['encoders']['E0']['conditions']['open']['condition']['gallery']
        Path(gallery['path']).write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Binding changed'):self.d0('compact_eou')

    def test_worker_failure_cleans_both_real_threads(self):
        from app.n2_pipeline import N2Engine
        f,rows,summary=self.fixture();names={'n4-cached-d1-activity','edge-s7-observed-policy'}
        before={t.ident for t in threading.enumerate() if t.name in names}
        with patch.object(N2Engine,'_accept_activity',side_effect=ValueError('mode failure')):
            with self.assertRaisesRegex(RuntimeError,'mode failure'):self.d1(f,rows,summary,'selected_closed')
        self.assertEqual(before,{t.ident for t in threading.enumerate() if t.name in names})


if __name__=='__main__':unittest.main()
