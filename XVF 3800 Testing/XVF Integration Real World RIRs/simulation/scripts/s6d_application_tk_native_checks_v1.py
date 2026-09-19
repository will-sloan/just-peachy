"""Model-free causal-view harness checks; see README_S6D_APPLICATION_TK_NATIVE_V1.md."""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


class Tests(unittest.TestCase):
    def views(self):
        rows=[]
        for mode,ids in [('T0',()),('T1',('a',)),('T2',('a','b'))]:
            setting=S.S6DSettings(transcript_mode=mode,selected_profile_ids=ids)
            rows.append(dict(name=mode,settings=setting,presentation=S.PresentationState(setting),inbox=S.EventInbox(64),input_digest=hashlib.sha256(),input_count=0,forwarded=0,consumer_closed=False))
        return rows
    def setup_stream(self):
        views=self.views();fan=H.LiveFanout(views,C.PipelineEvent,clock=lambda:10.);producer=S.PresentationState(S.S6DSettings());serial=[0]
        def send(kind,p):
            serial[0]+=1;p=dict(p,publication_sequence=serial[0],publication_monotonic_sec=1.+serial[0]/100,pilot_publication_monotonic_sec=1.+serial[0]/100,session_id='session')
            event=C.PipelineEvent(kind,1.,p);fan.accept(event)
            shown=producer.consume(kind,p,now=2.)
            if shown is not None:send('s6d_display',shown)
        send('source_started',{})
        return views,fan,send
    def drain(self,views):
        for v in views:
            while not v['inbox'].empty():v['inbox'].get()
            v['consumer_closed']=True
    def test_live_visibility_confirm_demote_keeps_full_words(self):
        views,fan,send=self.setup_stream()
        send('s6d_text_ready',dict(utterance_id='u',text='full words',source_start_sec=0.,source_end_sec=1.,final=True))
        self.assertFalse(views[1]['presentation'].rows['u']['visible'])
        send('transcript_final',dict(utterance_id='u',text='full words',source_start_sec=0.,source_end_sec=1.,latest_known_profile_id='a',latest_naming_state='confirmed',speaker='A'))
        self.assertTrue(views[1]['presentation'].rows['u']['visible'])
        send('transcript_label_revision',dict(utterance_id='u',text='full words',target_source_end_sec=1.,latest_known_profile_id=None,latest_naming_state='unresolved',latest_label='Speaker_1'))
        self.assertFalse(views[1]['presentation'].rows['u']['visible'])
        self.assertEqual({v['presentation'].rows['u']['text'] for v in views},{'full words'})
        self.drain(views);self.assertEqual(fan.complete(),[]);self.assertEqual(fan.t0_comparisons,3)
    def test_selected_set_and_unselected_voice_are_separate(self):
        views,fan,send=self.setup_stream()
        send('transcript_final',dict(utterance_id='u',text='reply',source_start_sec=0.,source_end_sec=1.,latest_known_profile_id='b',latest_naming_state='confirmed',speaker='B'))
        self.assertFalse(views[1]['presentation'].rows['u']['visible']);self.assertTrue(views[2]['presentation'].rows['u']['visible'])
    def test_duplicate_publication_rejected(self):
        views,fan,send=self.setup_stream()
        with self.assertRaisesRegex(ValueError,'strictly increasing'):fan.accept(C.PipelineEvent('x',1.,dict(publication_sequence=1)))
    def test_t0_semantic_mismatch_rejected(self):
        views=self.views();fan=H.LiveFanout(views,C.PipelineEvent,clock=lambda:10.)
        fan.accept(C.PipelineEvent('s6d_text_ready',1.,dict(utterance_id='u',text='a',publication_sequence=1,pilot_publication_monotonic_sec=1.,session_id='s')))
        with self.assertRaisesRegex(ValueError,'differs'):fan.accept(C.PipelineEvent('s6d_display',1.,dict(utterance_id='u',text='wrong',publication_sequence=2)))
    def test_event_order_digest_tampering_is_adverse(self):
        views,fan,send=self.setup_stream();self.drain(views);views[1]['input_digest'].update(b'x')
        self.assertTrue(any('order' in e for e in fan.complete()))
    def test_pending_view_or_comparator_prevents_close(self):
        views,fan,send=self.setup_stream();self.assertTrue(fan.complete());self.drain(views);self.assertEqual(fan.complete(),[])
        fan.pending_t0.append({});self.assertTrue(fan.complete())
    def test_causal_inbox_does_not_coalesce_and_fails_full(self):
        box=H.CausalInbox(2,clock=lambda:1.)
        for n in range(2):box.put(C.PipelineEvent('transcript_partial',1.,dict(utterance_id='u',text=str(n))))
        with self.assertRaisesRegex(RuntimeError,'full'):box.put(C.PipelineEvent('transcript_final',1.,{}))
        self.assertEqual([box.get().payload['text'] for _ in range(2)],['0','1']);self.assertEqual(box.snapshot()['accepted'],2)
    def test_gui_cannot_close_before_dispatcher_terminal(self):
        view=self.views()[0];fan=SimpleNamespace(terminal=False);writer=SimpleNamespace(is_alive=lambda:False);engine=SimpleNamespace(_finalization_thread=writer)
        facade=H.ViewFacade(engine,view,fan);facade.record_s6d_consumer_closure('Tk')
        self.assertFalse(view['consumer_closed']);self.assertTrue(facade._finalization_thread.is_alive())
        fan.terminal=True;facade.record_s6d_consumer_closure('Tk');self.assertTrue(view['consumer_closed']);self.assertFalse(facade._finalization_thread.is_alive())
    def test_gallery_spy_executes_original_once_and_preserves_rows(self):
        class Vector:
            def tobytes(self):return b'exact-vector'
        class Gallery:
            def __init__(self):self.calls=0
            def score(self,v):self.calls+=1;return [dict(profile_id='a',cosine=.5)]
        gallery=Gallery();spy=H.GalleryScoreSpy(gallery,capacity=1);spy.install();scores=gallery.score(Vector())
        self.assertEqual(gallery.calls,1);self.assertEqual(scores,spy.rows[0]['scores']);scores[0]['cosine']=0.;self.assertEqual(spy.rows[0]['scores'][0]['cosine'],.5)
        spy.restore();self.assertEqual(gallery.score(Vector())[0]['cosine'],.5);self.assertEqual(gallery.calls,2)
    def test_full_journal_publication_hash_matches_all_views(self):
        views,fan,send=self.setup_stream();send('transcript_final',dict(utterance_id='u',text='final',source_start_sec=0.,source_end_sec=1.))
        self.assertTrue(all(v['input_digest'].hexdigest()==fan.digest.hexdigest() for v in views));self.assertEqual(len({v['input_count'] for v in views}),1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--app-source',type=Path,required=True);p.add_argument('--helper',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    H=load(a.helper,'s6d_tk_fixture_helper');S=load(a.app_source/'research_s6d.py','s6d_tk_fixture_policy');C=load(a.app_source/'contracts.py','s6d_tk_fixture_contracts')
    with (a.output/'FIXTURES.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    receipt=dict(status='PASS_MODEL_FREE_NO_TK_OR_MODELS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),helper=H.binding(a.helper),app_policy=H.binding(a.app_source/'research_s6d.py'),contracts=H.binding(a.app_source/'contracts.py'),fixture=H.binding(__file__),log=H.binding(a.output/'FIXTURES.log'),tk_created=False,model_calls=0,hardware_calls=0)
    H.write_new(a.output/'RESULT.json',receipt);print(json.dumps(receipt));sys.exit(0 if result.wasSuccessful() else 1)
