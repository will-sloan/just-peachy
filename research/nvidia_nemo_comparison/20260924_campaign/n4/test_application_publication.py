"""Actual publication behavior checks. README_APPLICATION_PUBLICATION.md."""
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import time
import unittest

import test_component_modes as fixtures
from test_component_s7_replay import asr,embedding,push,advance
from application_publication import PublicationReplay,replay_d0_publication,replay_d1_publication
from component_d1_replay import d1_plan
from common import load,verify,bind,freeze


class TestPublication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.TestComponentModes.setUpClass()

    def setUp(self):
        from app.paths import pipeline_config
        from app.n2_models import redim_namespace
        g=fixtures.galleries.TestModeGalleries();g.setUp();self.addCleanup(g.doCleanups)
        g.namespace=redim_namespace(pipeline_config(Path('TEST_METADATA'),Path('NO_MODELS')))
        ip,rp=g.fixture();rows=fixtures.galleries.verified_primary(bind(ip),bind(rp),'E0');conditions={}
        for mode,row in rows.items():
            conditions[mode]={k:row[k] for k in ('condition','namespace','source_gallery')}
            conditions[mode]['baseline_manifest']=fixtures.galleries.materialize_baseline(row,g.root/'bridge'/mode)
        path=g.root/'GALLERIES.json';freeze(path,dict(status='PREPARED_VERIFIED_RESEARCH_GALLERIES_ONLY',
            catalog=bind(g.source/'config/backends.json'),encoders={'E0':{'conditions':conditions}}))
        self.fixture=fixtures.TestComponentModes();self.fixture.namespace=g.namespace;self.fixture.preparation=bind(path)
        self.kw=dict(preparation=self.fixture.preparation,backend='baseline',mode='anonymous_conversation',
            tap='O0',namespace=self.fixture.namespace,session_id='protocol-only')

    def raw(self,**kwargs):
        from edge_speech_pipeline.runtime import format_partial_display
        row=asr(**kwargs);row['display_text']=format_partial_display(row['text']);return row

    def d0(self,*,a=None,s=None,formatting=(),**changes):
        a=a or [push('asr',self.raw()),advance('asr',None,1.25)]
        s=s or [push('speaker',embedding()),advance('speaker',None,1.25)]
        return replay_d0_publication(a,s,duration=1.25,formatting=formatting,**(self.kw|changes))

    def test_actual_emit_serials_and_independent_raw_before_policy(self):
        result=self.d0();rows=result['publication_events'];kinds=[r['event_type'] for r in rows]
        self.assertEqual([r['payload']['publication_sequence'] for r in rows],list(range(1,len(rows)+1)))
        raw=kinds.index('research_asr_observation');ready=kinds.index('s6d_text_ready')
        self.assertLess(raw,ready);self.assertEqual(kinds[ready+1],'s6d_display')
        self.assertLess(ready,kinds.index('transcript_final'))
        self.assertGreater(len(rows),len(result['display_events']))
        self.assertEqual(result['presentation']['raw_observations'],1)
        self.assertFalse(result['worker_counts']['thread_alive'])

    def test_actual_scheduled_event_flattens_decision_preserving_availability(self):
        result=self.d0();p=next(r['payload'] for r in result['publication_events'] if r['event_type']=='speaker_decision')
        self.assertEqual(p['tracker_id'],p['decision']['tracker_id'])
        self.assertEqual(p['known_profile_id'],p['decision']['known_profile_id'])
        self.assertIn('input_available_at_sec',p);self.assertIn('modeled_available_at_sec',p)
        self.assertEqual(p['observed_publication_at_sec'],p['publication_monotonic_sec'])

    def test_clock_facade_is_local_restored_on_success_and_failure(self):
        from edge_speech_pipeline import runtime,research_s7_presentation
        before=time.perf_counter;runtime_before=runtime.time;presentation_before=research_s7_presentation.time
        self.d0();self.assertIs(time.perf_counter,before);self.assertIs(runtime.time,runtime_before)
        self.assertIs(research_s7_presentation.time,presentation_before)
        broken=self.raw();broken['display_text']='changed parent'
        with self.assertRaisesRegex(ValueError,'sealed ASR'):
            self.d0(a=[push('asr',broken),advance('asr',None,1.25)])
        self.assertIs(runtime.time,runtime_before);self.assertIs(research_s7_presentation.time,presentation_before)
        self.d0()

    def test_second_clock_owner_rejected_without_disturbing_first(self):
        context=PublicationReplay(duration=1.25,**self.kw)
        try:
            with self.assertRaisesRegex(RuntimeError,'One publication clock'):
                PublicationReplay(duration=1.25,**self.kw)
            context.clock.set(.5);self.assertEqual(context.engine._journal.duration_sec,.5)
        finally:context.close()

    def test_actual_publication_freshness_expires_delayed_policy(self):
        result=self.d0();parent=next(r for r in result['publication_events'] if r['event_type']=='transcript_final')
        context=PublicationReplay(duration=1.25,**self.kw)
        try:
            context.clock.set(10.)
            context.engine._emit(parent['event_type'],parent['source_time_sec'],deepcopy(parent['payload']))
            p=next(r['payload'] for r in context.inbox.rows if r['event_type']=='transcript_final')
            self.assertIs(p['live_evidence_fresh_at_publication'],False)
            self.assertEqual(p['publication_monotonic_sec'],10.)
        finally:context.close()

    def test_final_formatter_uses_exact_parent_and_preserves_words(self):
        raw=self.raw();component=dict(utterance_id=raw['utterance_id'],input_event_id=raw['event_id'],raw_text=raw['text'],
            modeled_available_at_sec=1.2,punctuation=dict(text='One, two!',compute_ms=2.,status='complete'))
        result=self.d0(formatting=[component]);rows=result['presentation']['rows']
        self.assertEqual(rows[0]['text'],raw['text']);self.assertEqual(rows[0]['display_text'],'One, two!')
        self.assertEqual(result['presentation']['formatting_revisions'],1)
        self.assertEqual(result['publication_counts']['s6d_punctuation_revision'],1)

    def test_d1_actual_emit_during_locked_query_keeps_raw_independent(self):
        f,rows,summary=self.fixture.fixture();plan=d1_plan(rows,f.wave,summary,self.fixture.namespace,'test-scene')
        group=next(g for g in plan['groups'] if g['queries'])
        ready=(group['dispatch']['modeled_available_at_sec']+group['queries'][0]['event']['available_at_sec'])/2
        raw=self.raw(ready=ready,end=.6,text='before query')
        a=[push('asr',raw),advance('asr',None,len(f.wave)/16000)]
        result=replay_d1_publication(a,rows,wave=f.wave,summary=summary,**(self.kw|dict(backend='nemotron_hybrid',mode='selected_closed',session_id='test-scene')))
        self.assertEqual(result['embedding_calls'],3);self.assertFalse(result['d1_worker_alive'])
        first=result['display_events'][0]['published_row']
        self.assertEqual(first['text'],raw['text']);self.assertNotIn('closed_display_assignment',first)
        self.assertTrue(any(x['published_row'].get('closed_display_assignment') or
            any(p.get('closed_display_assignment') for p in x['published_row'].get('segments',[])) for x in result['display_events']))
        revisions=[r['payload'] for r in result['publication_events'] if r['event_type']=='transcript_label_revision']
        targeted=[r for r in revisions if r.get('target_span_ids')]
        self.assertTrue(targeted)
        span_ids={p['id'] for r in result['presentation']['rows'] for p in r['word_spans']}
        self.assertTrue(all(r['target_text_revision_id']==raw['event_id'] and set(r['target_span_ids'])<=span_ids for r in targeted))

    def test_controller_consumes_new_actual_publication_displays(self):
        from controller_projection import project_mode_result,forbid_inference
        result=self.d0(mode='selected_closed')
        wiring=load(Path(__file__).with_name('ACCEPTED_SOURCE_CATALOG_CHECK.json'))
        runtimes={Path(b['path']).name:b for b in wiring['inputs']}
        with tempfile.TemporaryDirectory() as tmp,forbid_inference():
            projected=project_mode_result(result,tap='O0',preparation=self.fixture.preparation,
                n2_runtime=runtimes['n2_runtime.json'],n3_runtime=runtimes['n3_runtime.json'],data_root=Path(tmp)/'controller')
        self.assertEqual(projected['display_inputs'],len(result['display_events']))
        self.assertTrue(projected['controller_closed'])

    def test_namespace_and_worker_cleanup(self):
        names={'edge-s6d-policy','n4-cached-d1-activity'}
        before={t.ident for t in threading.enumerate() if t.name in names}
        namespace=deepcopy(self.kw['namespace']);namespace['model_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'namespace'):self.d0(namespace=namespace)
        self.d0();self.assertEqual(before,{t.ident for t in threading.enumerate() if t.name in names})


if __name__=='__main__':unittest.main()
