"""Model-free S6D regressions and actual Tk widget checks; see README_RESEARCH_S6D.md."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

import numpy as np

from .contracts import PipelineEvent
from .research_s6d import BoundedWorker, EventInbox, PresentationState, S6DSettings, build_s6d_scheduler
from .research_profiles_v3 import ResearchProfileV3, IdentitySettingsV3
from .research_identity_v3 import ResearchGallery, ResearchIdentityResolver


class S6DChecks(unittest.TestCase):
    def test_actual_engine_workers_journal_and_consumer_closure(self):
        import wave
        from .runtime import PipelineEngine
        from .config import PipelineConfig
        class FakeASR:
            def __init__(self):
                self.utterance_index=0;self.decode_ms=0.;self.calls=0
            def accept(self,audio):
                self.calls+=1
                return ("hello" if self.calls<=2 else "world",self.calls==2)
            def reset_endpoint(self):
                self.utterance_index+=1
                return "hello"
            def finish(self):
                return "world"
            def punctuate(self,text):
                time.sleep(.05)
                return {"text":text.capitalize()+".","compute_ms":50.,"status":"fixture","model_id":"model_free_fixture"}
        class Bundle:
            released=False
            def acquire(self,config):
                return None,FakeASR()
            def release(self):
                self.released=True
        class Engine(PipelineEngine):
            def _speaker_loop(self,models):
                while not self._journal.finished:
                    time.sleep(.005)
                self._scheduler_advance("speaker",float("inf"),self._source_time())
        with tempfile.TemporaryDirectory(prefix="s6d_fixture_") as temporary:
            root=Path(temporary)
            wav=root/"fixture.wav"
            with wave.open(str(wav),'wb') as handle:
                handle.setnchannels(1);handle.setsampwidth(2);handle.setframerate(16000)
                handle.writeframes(bytes(16000*2//2))
            bundle=Bundle()
            engine=Engine(replace(PipelineConfig(),session_root=root/'sessions'),research_profile=ResearchProfileV3(),
                model_bundle=bundle,s6d_settings=S6DSettings())
            session=engine.start_file(wav,realtime=False)
            collected=[];deadline=time.perf_counter()+10.
            while time.perf_counter()<deadline:
                while not engine.events.empty():
                    collected.append(engine.events.get())
                if engine._finalization_thread is not None and not engine._finalization_thread.is_alive():
                    break
                time.sleep(.005)
            engine.wait_for_completion(2.)
            while not engine.events.empty():
                collected.append(engine.events.get())
            self.assertEqual(engine.state,"COMPLETED")
            self.assertTrue(bundle.released)
            engine.record_s6d_consumer_closure("model_free_fixture")
            self.assertTrue((session/'s6d_consumer_closure.json').exists())
            events=[json.loads(line) for line in (session/'events.jsonl').read_text().splitlines()]
            published=[r['payload']['publication_sequence'] for r in events]
            self.assertEqual(published,sorted(set(published)))
            immediate=[r for r in events if r['event_type']=='s6d_text_ready' and r['payload']['final']]
            self.assertEqual([r['payload']['text'] for r in immediate],["hello","world"])
            for event in immediate:
                correction=next(r for r in events if r['event_type']=='s6d_punctuation_revision' and r['payload']['utterance_id']==event['payload']['utterance_id'])
                self.assertLess(event['payload']['publication_monotonic_sec'],correction['payload']['publication_monotonic_sec'])
            latest=[json.loads(line) for line in (session/'latest_labelled_transcript.jsonl').read_text().splitlines()]
            self.assertEqual([r['display_text'] for r in latest],["Hello.","World."])
            self.assertEqual(engine._s6d_writer.accepted,engine._s6d_writer.completed)

    def test_strict_settings(self):
        for data in ({"transcript_mode":"T1"}, {"transcript_mode":"T2"}, {"direction_mode":"V2"}, {"text_delivery":"false"}):
            with self.assertRaises(ValueError):
                S6DSettings(**data).validate()

    def test_bounded_worker_nonblocking_and_durable_drain(self):
        entered, release = threading.Event(), threading.Event()
        output=[]
        def work(value):
            entered.set()
            release.wait(2)
            output.append(value)
        worker=BoundedWorker("fixture", work, 2)
        worker.submit(0)
        self.assertTrue(entered.wait(1))
        worker.submit(1)
        worker.submit(2)
        with self.assertRaises(RuntimeError):
            worker.submit(3)
        release.set()
        worker.close(3)
        self.assertEqual(output,[0,1,2])
        self.assertEqual(worker.snapshot()["accepted"],worker.snapshot()["completed"])
        self.assertFalse(worker.thread.is_alive())

    def test_worker_failure_is_not_success(self):
        def fail(value):
            raise OSError("fixture disk error")
        worker=BoundedWorker("failure_fixture",fail,2)
        worker.submit(1)
        with self.assertRaises(RuntimeError):
            worker.close(2)
        self.assertIn("fixture disk error",worker.error)

    def test_only_same_utterance_partials_coalesce(self):
        inbox=EventInbox(3)
        def ev(kind,key,text):
            return PipelineEvent(kind,1.,{"utterance_id":key,"text":text})
        inbox.put(ev("transcript_partial","a","first"))
        inbox.put(ev("transcript_partial","a","second"))
        inbox.put(ev("transcript_final","a","second"))
        inbox.put(ev("transcript_partial","b","third"))
        self.assertEqual(inbox.coalesced,1)
        with self.assertRaises(RuntimeError):
            inbox.put(ev("transcript_final","b","third"))
        self.assertEqual([inbox.get().event_type for _ in range(3)], ["transcript_partial","transcript_final","transcript_partial"])
        self.assertTrue(inbox.empty())

    def test_selection_unknown_late_correct_span_and_punctuation(self):
        state=PresentationState(S6DSettings(transcript_mode="T1",selected_profile_ids=("a",)))
        state.consume("s6d_text_ready",{"utterance_id":"u1","text":"hello","final":True},1.)
        state.consume("s6d_text_ready",{"utterance_id":"u2","text":"stranger","final":True},1.1)
        self.assertEqual(state.lines(),[])
        state.consume("s6d_punctuation_revision",{"utterance_id":"u1","text":"hello","display_text":"Hello."},1.2)
        row=state.consume("transcript_final",{"utterance_id":"u1","text":"hello","latest_label":"Alice",
            "latest_known_profile_id":"a","latest_naming_state":"confirmed"},1.3)
        self.assertEqual(state.lines(),["Alice: Hello."])
        self.assertEqual(row["first_visible_monotonic_sec"],1.3)
        self.assertFalse(state.rows["u2"]["visible"])
        state.consume("transcript_label_revision",{"utterance_id":"u1","latest_label":"Bob","latest_known_profile_id":"b","latest_naming_state":"confirmed","target_source_end_sec":1.},1.4)
        self.assertEqual(state.lines(),[])
        self.assertEqual(len(state.lines(full_view=True)),2)
        state.consume("transcript_partial",{"utterance_id":"u1","text":"he"},1.5)
        self.assertEqual(state.rows["u1"]["text"],"hello")

    def test_stable_prefix_token_ids(self):
        state=PresentationState(S6DSettings())
        a=state.token_ids("u","one two",1)
        b=state.token_ids("u","one two three",2)
        c=state.token_ids("u","one too",3)
        self.assertEqual(a,b[:2])
        self.assertEqual(a[0],c[0])
        self.assertNotEqual(a[1],c[1])

    def test_new_words_do_not_inherit_prior_selected_identity(self):
        state=PresentationState(S6DSettings(transcript_mode="T1",selected_profile_ids=("a",)))
        first={"utterance_id":"u","text":"old words","source_start_sec":0.,"source_end_sec":1.}
        state.consume("s6d_text_ready",first,1.)
        state.consume("transcript_partial",{**first,"latest_label":"Alice","latest_known_profile_id":"a","latest_naming_state":"confirmed"},1.1)
        self.assertTrue(state.rows['u']['visible'])
        state.consume("s6d_text_ready",{**first,"text":"old words new voice","source_end_sec":2.},2.)
        self.assertFalse(state.rows['u']['visible'])
        state.consume("transcript_partial",{**first,"latest_label":"Alice","latest_known_profile_id":"a","latest_naming_state":"confirmed"},2.1)
        self.assertFalse(state.rows['u']['visible'])
        self.assertEqual(state.rows['u']['text'],"old words new voice")
        state.consume("transcript_label_revision",{"utterance_id":"u","latest_label":"Alice","latest_known_profile_id":"a",
            "latest_naming_state":"confirmed","target_source_end_sec":1.},2.2)
        self.assertFalse(state.rows['u']['visible'])

    def test_direction_never_uses_sticky_identity_or_duplicates(self):
        settings=S6DSettings(direction_mode="V3")
        state=PresentationState(settings)
        obs={"angle_deg":75.,"valid":True,"available_at_sec":2.,"source_start_sec":1.5,"source_end_sec":2.,
            "voice_evidence_id":"e","observation_id":"o","association_verified":True,"association_confidence":.9}
        voice={"evidence_id":"e","naming_state":"confirmed","known_profile_id":"a","available_at_sec":2.,"source_start_sec":1.5,"source_end_sec":2.}
        speech={"speech":True,"overlap":False,"available_at_sec":2.,"source_start_sec":1.5,"source_end_sec":2.}
        route={'capture_source_id':'capture','route_id':'route','stream_id':'beam0'}
        obs.update(route,speech_evidence_id='s');voice.update(route);speech.update(route,evidence_id='s')
        self.assertEqual(len(state.directions([obs,dict(obs,observation_id="o2")],[speech],[voice],2.1)["arrows"]),1)
        self.assertEqual(state.directions([obs],[],[voice],2.1)["arrows"],[])
        self.assertEqual(state.directions([dict(obs,association_verified=False)],[speech],[voice],2.1)["arrows"],[])
        self.assertEqual(state.directions([obs],[speech],[voice],3.0)["arrows"],[])
        self.assertEqual(state.directions([obs],[dict(speech,overlap=True)],[voice],2.1)["arrows"],[])
        self.assertEqual(state.directions([dict(obs,voice_evidence_id="other")],[speech],[voice],2.1)["arrows"],[])
        for bad in (float('nan'),float('inf'),-.1,True,".9"):
            self.assertEqual(state.directions([dict(obs,association_confidence=bad)],[speech],[voice],2.1)["arrows"],[])
        for field in ('available_at_sec','source_start_sec','source_end_sec'):
            self.assertEqual(state.directions([dict(obs,**{field:float('nan')})],[speech],[voice],2.1)["arrows"],[])
            self.assertEqual(state.directions([obs],[dict(speech,**{field:float('nan')})],[voice],2.1)["arrows"],[])
            self.assertEqual(state.directions([obs],[speech],[dict(voice,**{field:float('nan')})],2.1)["arrows"],[])

    def test_direction_speech_binds_route_and_two_independent_voices(self):
        state=PresentationState(S6DSettings(direction_mode='V3'))
        route={'capture_source_id':'capture','route_id':'route','stream_id':'beam0'}
        span={'source_start_sec':1.5,'source_end_sec':2.,'available_at_sec':2.}
        speech={**span,**route,'speech':True,'overlap':False,'evidence_id':'s0'}
        voice={**span,**route,'evidence_id':'v0','naming_state':'confirmed','known_profile_id':'a'}
        obs={**span,**route,'observation_id':'o0','voice_evidence_id':'v0','speech_evidence_id':'s0',
            'angle_deg':45.,'valid':True,'association_verified':True,'association_confidence':.9}
        other_speech=dict(speech,stream_id='beam1',evidence_id='s1',speech=False)
        other_voice=dict(voice,stream_id='beam1',evidence_id='v1',known_profile_id='b')
        other_obs=dict(obs,stream_id='beam1',observation_id='o1',voice_evidence_id='v1',speech_evidence_id='s1',angle_deg=120.)
        result=state.directions([obs,other_obs],[speech,other_speech],[voice,other_voice],2.1)
        self.assertEqual([r['known_profile_id'] for r in result['arrows']],['a'])
        other_speech['speech']=True
        self.assertEqual(len(state.directions([obs,other_obs],[speech,other_speech],[voice,other_voice],2.1)['arrows']),2)
        for field in ('capture_source_id','route_id','stream_id','speech_evidence_id'):
            self.assertEqual(state.directions([dict(obs,**{field:'other'})],[speech],[voice],2.1)['arrows'],[])
        self.assertEqual(state.directions([obs],[speech],[dict(voice,stream_id='beam1')],2.1)['arrows'],[])

    def test_confirmed_name_revocation_hides_selected_row_and_export(self):
        settings=S6DSettings(text_delivery=False,transcript_mode='T1',selected_profile_ids=('a',))
        policy=build_s6d_scheduler(ResearchProfileV3(),None,None,None,settings)
        row={'utterance_id':'u','source_start_sec':0.,'source_end_sec':1.,'text':'hello','display_text':'Hello.',
            'first_display_label':'Alice','first_display_time':1.,'first_final_label':'Alice','first_final_time':1.1,
            'last_text_available_at_sec':1.1,'revision_count':0,'latest_label':'Alice','latest_state':'committed',
            'tracker_id':1,'is_final':True,'latest_known_profile_id':'a','latest_known_name':'Alice','latest_naming_state':'confirmed'}
        policy._utterances['u']=row
        event={'event_id':'e','source_start_sec':.5,'source_end_sec':1.,'available_at_sec':1.2,'speech':True,'overlap':False}
        decision={'tracker_id':1,'anonymous_label':'Speaker_1','display_label':'Speaker_1','state':'committed','committed':True,
            'identity':{'naming_state':'unresolved','known_name':None,'known_profile_id':None,'display_label':'Speaker_1'},
            'name_revision':{'track_id':1,'replacement_label':'Speaker_1','replacement_known_name':None,
                'replacement_known_profile_id':None,'replacement_naming_state':'unresolved','reason':'actual_voice_rejected'}}
        policy._decisions.append((event,decision))
        state=PresentationState(settings)
        state.consume('transcript_final',dict(row),1.1)
        self.assertTrue(state.rows['u']['visible'])
        revisions=policy._revise(event,decision)
        self.assertEqual(len(revisions),1)
        state.consume('transcript_label_revision',revisions[0],1.2)
        self.assertFalse(state.rows['u']['visible'])
        export=policy.snapshot()['utterances'][0]
        self.assertIsNone(export['latest_known_name'])
        self.assertIsNone(export['latest_known_profile_id'])
        self.assertEqual(export['latest_label'],'Speaker_1')
        self.assertEqual(export['first_final_label'],'Alice')

    def test_real_gallery_query_and_rejection_with_single_candidate(self):
        gallery=ResearchGallery.__new__(ResearchGallery)
        gallery.matrix=np.eye(2,192,dtype=np.float32)
        gallery.ids=["a","b"]
        gallery.names=["Alice","Bob"]
        gallery.gallery_id="fixture_only"
        resolver=ResearchIdentityResolver(replace(IdentitySettingsV3(),mode="post_association",minimum_unique_sec=.5,minimum_disjoint_count=1),gallery)
        event={"source_start_sec":0.,"source_end_sec":1.,"available_at_sec":1.1,"event_id":"e","evidence_kind":"mature",
            "clean_intervals":[[0.,1.]],"vector":gallery.matrix[0],"speech":True,"overlap":False}
        decision={"tracker_id":1,"anonymous_label":"Speaker_1","state":"committed"}
        result=resolver.resolve(decision,event)
        self.assertEqual(result["known_profile_id"],"a")
        self.assertTrue(result["identity"]["query_executed"])
        self.assertEqual(resolver.comparisons,4)
        gallery.matrix=gallery.matrix[:1]
        gallery.ids=gallery.ids[:1]
        gallery.names=gallery.names[:1]
        vector=np.zeros(192,dtype=np.float32); vector[4]=1.
        rejected=resolver.resolve(dict(decision,tracker_id=2),dict(event,event_id="e2",vector=vector))
        self.assertIsNone(rejected["known_profile_id"])

    def test_active_text_boundary_expiry_adjacent_and_revision_bound(self):
        def fixture(settings):
            policy=build_s6d_scheduler(ResearchProfileV3(),None,None,None,settings)
            row={"utterance_id":"u","source_start_sec":0.,"source_end_sec":5.,"text":"same raw words","display_text":"Same raw words",
                "first_display_label":"Speaker_?","first_display_time":1.,"first_final_label":None,"first_final_time":None,
                "last_text_available_at_sec":5.1,"revision_count":0,"latest_label":"Speaker_?","latest_state":"pending", "tracker_id":None}
            policy._utterances["u"]=row
            return policy,row
        settings=S6DSettings(text_delivery=False)
        event={"event_id":"e","source_start_sec":4.5,"source_end_sec":5.,"available_at_sec":5.10114,"speech":True,"overlap":False}
        decision={"tracker_id":1,"anonymous_label":"Speaker_1","display_label":"Speaker_1","state":"committed","committed":True,"identity":{}}
        policy,row=fixture(settings)
        self.assertEqual(len(policy._revise(event,decision)),1)
        self.assertEqual(row["latest_label"],"Speaker_1")
        self.assertEqual(row["first_display_time"],1.)
        self.assertEqual(row["text"],"same raw words")
        old,oldrow=fixture(replace(settings,boundary_repair=False))
        self.assertEqual(old._revise(event,decision),[])
        for bad in (dict(event,source_start_sec=5.,source_end_sec=5.1),dict(event,available_at_sec=6.),dict(event,available_at_sec=5.099),dict(event,overlap=True)):
            policy,row=fixture(settings)
            self.assertEqual(policy._revise(bad,decision),[])
        policy,row=fixture(settings); row["revision_count"]=policy.max_revisions_per_utterance
        self.assertEqual(policy._revise(event,decision),[])
        policy,row=fixture(settings); row.update(tracker_id=2,latest_state="committed")
        self.assertEqual(policy._revise(event,decision),[])

    def test_actual_tk_filter_widget_and_full_view(self):
        import tkinter as tk
        from types import SimpleNamespace
        from .gui import EdgeSpeechWindow
        root=tk.Tk(); root.withdraw()
        try:
            window=EdgeSpeechWindow.__new__(EdgeSpeechWindow)
            window.engine=SimpleNamespace(_s6d=S6DSettings(transcript_mode="T1",selected_profile_ids=("a",)))
            window.s6d_rows={};window.s6d_full_view=tk.BooleanVar(root,value=False)
            window.s6d_status=tk.StringVar(root);window.transcript=tk.Text(root)
            window._consume_s6d_display({"utterance_id":"u1","label":"Unknown","display_text":"hidden stranger","visible":False,"final":True,"visibility_state":"pending_identity"})
            self.assertNotIn("stranger",window.transcript.get("1.0","end"))
            window._consume_s6d_display({"utterance_id":"u2","label":"Alice","display_text":"visible target","visible":True,"final":True})
            self.assertIn("visible target",window.transcript.get("1.0","end"))
            window.s6d_full_view.set(True);window._render_transcript()
            self.assertIn("hidden stranger",window.transcript.get("1.0","end"))
        finally:
            root.destroy()

    def test_actual_tk_two_arrows_expire_without_new_direction_event(self):
        import tkinter as tk
        from types import SimpleNamespace
        from .gui import EdgeSpeechWindow
        root=tk.Tk();root.withdraw()
        try:
            window=EdgeSpeechWindow.__new__(EdgeSpeechWindow)
            window.engine=SimpleNamespace(_s6d=S6DSettings(direction_mode='V3'),session_dir=None)
            window._s6d_direction_rows=[];window._s6d_direction_evaluated=-1.
            window._s6d_gui_session_id='fixture_session'
            window.s6d_direction_canvas=tk.Canvas(root);window.s6d_direction_label=tk.StringVar(root)
            now=time.perf_counter()
            payload={'session_id':'fixture_session','publication_monotonic_sec':now,'evaluated_at_sec':2.,'arrows':[
                {'angle_deg':45.,'valid_for_sec':.04,'indicator':'active_speech'},
                {'angle_deg':120.,'valid_for_sec':.04,'indicator':'active_speech'}]}
            window._consume_s6d_direction(payload)
            self.assertEqual(len(window.s6d_direction_canvas.find_withtag('direction_arrow')),2)
            window._consume_s6d_direction(dict(payload,evaluated_at_sec=1.,arrows=[]))
            self.assertEqual(len(window.s6d_direction_canvas.find_withtag('direction_arrow')),2)
            root.after(75,window._expire_s6d_directions);root.after(100,root.quit);root.mainloop()
            self.assertEqual(window.s6d_direction_canvas.find_withtag('direction_arrow'),())
            self.assertIn('unavailable',window.s6d_direction_label.get())
            window._consume_s6d_direction(payload)
            self.assertEqual(window.s6d_direction_canvas.find_withtag('direction_arrow'),())
        finally:root.destroy()

    def test_gui_close_waits_for_event_consumer_and_finalizer(self):
        import queue
        from types import SimpleNamespace
        from .gui import EdgeSpeechWindow
        window=EdgeSpeechWindow.__new__(EdgeSpeechWindow);closed=[]
        window.root=SimpleNamespace(destroy=lambda:closed.append(True));window._s6d_render_handle=None
        window._s6d_stop_thread=None
        engine=SimpleNamespace(state='COMPLETED',events=queue.Queue(),_finalization_thread=SimpleNamespace(is_alive=lambda:True))
        window.engine=engine
        self.assertFalse(window._finish_s6d_close())
        engine._finalization_thread=SimpleNamespace(is_alive=lambda:False);engine.events.put('committed text')
        self.assertFalse(window._finish_s6d_close());self.assertEqual(closed,[])
        engine.events.get();self.assertTrue(window._finish_s6d_close());self.assertEqual(closed,[True])

    def test_actual_tk_direction_clock_resets_only_on_new_session(self):
        import tkinter as tk
        from types import SimpleNamespace
        from .gui import EdgeSpeechWindow
        root=tk.Tk();root.withdraw()
        try:
            window=EdgeSpeechWindow.__new__(EdgeSpeechWindow)
            window.engine=SimpleNamespace(_s6d=S6DSettings(direction_mode='V3'),session_dir=Path('session_A'))
            window._record_s6d_gui=lambda row:None
            window._s6d_gui_session_id=None;window._s6d_direction_rows=[];window._s6d_direction_evaluated=-1.
            window.s6d_rows={};window.s6d_full_view=tk.BooleanVar(root,value=False)
            window.s6d_direction_canvas=tk.Canvas(root);window.s6d_direction_label=tk.StringVar(root)
            window.transcript=tk.Text(root);window.research=tk.Text(root);window.transcript_lines=[];window.last_partial=''
            arrow={'angle_deg':75.,'valid_for_sec':.7,'indicator':'active_speech'}
            def packet(session,t):return {'session_id':session,'publication_monotonic_sec':time.perf_counter(),'evaluated_at_sec':t,'arrows':[arrow]}
            self.assertTrue(window._begin_s6d_gui_session({'session_id':'session_A'}))
            window._consume_s6d_direction(packet('session_A',100.))
            self.assertEqual(len(window.s6d_direction_canvas.find_withtag('direction_arrow')),1)
            window._clear_display();self.assertEqual(window._s6d_direction_evaluated,100.)
            window.engine.session_dir=Path('session_B')
            self.assertTrue(window._begin_s6d_gui_session({'session_id':'session_B'}))
            window._consume_s6d_direction(packet('session_B',1.))
            self.assertEqual(len(window.s6d_direction_canvas.find_withtag('direction_arrow')),1)
            self.assertFalse(window._begin_s6d_gui_session({'session_id':'session_A'}))
            window._consume_s6d_direction(packet('session_A',101.))
            self.assertEqual(window._s6d_direction_evaluated,1.)
        finally:root.destroy()

    def test_gui_idle_close_waits_for_pending_startup_and_ui_message(self):
        import queue
        from types import SimpleNamespace
        from .gui import EdgeSpeechWindow
        window=EdgeSpeechWindow.__new__(EdgeSpeechWindow);closed=[]
        window.root=SimpleNamespace(destroy=lambda:closed.append(True));window._s6d_render_handle=None;window._s6d_stop_thread=None
        window.engine=SimpleNamespace(state='IDLE',events=queue.Queue(),_finalization_thread=None)
        window._s6d_background_jobs=[SimpleNamespace(is_alive=lambda:True)];window.ui_messages=queue.Queue()
        self.assertFalse(window._finish_s6d_close());self.assertEqual(closed,[])
        window._s6d_background_jobs=[];window.ui_messages.put(('startup_error','fixture'))
        self.assertFalse(window._finish_s6d_close());self.assertEqual(closed,[])
        window.ui_messages.get();self.assertTrue(window._finish_s6d_close())


if __name__ == "__main__":
    unittest.main(verbosity=2)
