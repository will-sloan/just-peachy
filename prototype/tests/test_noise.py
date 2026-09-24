"""Noise branch failure, domain and archive contracts. See README_NOISE.md."""
from pathlib import Path
import sys,tempfile,unittest,time,threading,json,queue,hashlib
from types import SimpleNamespace
from unittest.mock import Mock,patch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT/'tests')]
from app.enhancement import EnhancementRouter,identity_binding,route_binding
from app.noise_coordination import NoiseCoordinator
from app.people import PersonalStore,route_compatible
from app.sessions import SessionStore,records
from app.controller import Controller
from app.enrollment_quality import EnrollmentQuality
from test_script_evidence import Models,fixture
from test_people import ROUTE,BACKEND


class DelayedHelper:
    def reset(self):self.pending=np.empty(0,np.float32);self.calls=0
    def run(self,x):
        self.calls+=1;self.pending=np.concatenate((self.pending,x));n=max(0,len(self.pending)-160)
        result=self.pending[:n]*np.float32(.5);self.pending=self.pending[n:];return result
    def flush(self):result=self.pending*.5;self.pending=np.empty(0,np.float32);return result


class NoiseTests(unittest.TestCase):
    def test_all_routes_alignment_and_exact_raw_branch(self):
        with tempfile.TemporaryDirectory() as td:
            x=np.linspace(-.7,.7,3207,dtype=np.float32)
            for route in ('asr','identity','both'):
                router=EnhancementRouter(Path(td)/route,2,route,DelayedHelper());router.start()
                for start in range(0,len(x),320):router.append(x[start:start+320])
                router.finish();router.join()
                self.assertTrue(router.active);self.assertEqual(router.enhanced.committed_samples,len(x))
                np.testing.assert_array_equal(router.raw.read(0,len(x)),x)
                np.testing.assert_array_equal(router.asr.read(0,len(x)),x*.5 if route!='identity' else x)
                np.testing.assert_array_equal(router.identity.read(0,len(x)),x*.5 if route!='asr' else x)

    def test_failure_keeps_source_without_duplication_and_stops_enhanced_identity(self):
        with tempfile.TemporaryDirectory() as td:
            helper=DelayedHelper();helper.run=Mock(side_effect=RuntimeError('injected helper failure'))
            router=EnhancementRouter(Path(td)/'failed',2,'both',helper);router.start()
            x=np.linspace(-.1,.1,911,dtype=np.float32);router.append(x);router.finish();router.join()
            np.testing.assert_array_equal(router.asr.read(0,9999),x)
            self.assertEqual(router.identity.committed_samples,0);self.assertEqual(len(router.identity.read(0,100)),0)
            self.assertIn('injected',router.snapshot()['fallback']['reason']);helper.run.assert_called_once()

    def test_backlog_yields_optional_work_without_dropping_raw_samples(self):
        with tempfile.TemporaryDirectory() as td:
            helper=DelayedHelper();router=EnhancementRouter(Path(td)/'backlog',2,'asr',helper)
            x=np.linspace(-.2,.2,9000,dtype=np.float32);router.append(x);router.start();router.finish();router.join()
            self.assertEqual(helper.calls,0);self.assertFalse(router.active)
            np.testing.assert_array_equal(router.asr.read(0,9999),x)
            self.assertIn('backlog',router.snapshot()['fallback']['reason'])

    def test_enhanced_profile_domain_is_required_for_matching_and_transfer(self):
        q,v,_,_=fixture();route=dict(ROUTE,**identity_binding('identity'))
        self.assertFalse(route_compatible(route,ROUTE));self.assertFalse(route_compatible(route,dict(route,tap='O1')))
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=PersonalStore(root/'a/people',BACKEND);row=store.save('Enhanced',v,q,route)
            with self.assertRaises(ValueError):store.gallery(ROUTE)
            self.assertEqual(store.gallery(route).ids,[row['id']])
            archive=root/'profiles.zip';store.export(archive,True);other=PersonalStore(root/'b/people',BACKEND);other.import_archive(archive,True)
            self.assertEqual(json.loads((root/'b/DATA_SCHEMA.json').read_text())['required_features'],['enhanced-reference-v1'])
            self.assertEqual(other.gallery(route).ids,[row['id']])

    def test_audio_archive_keeps_actual_two_streams_and_no_audio_without_consent(self):
        for audio in (False,True):
            with self.subTest(audio=audio),tempfile.TemporaryDirectory() as td:
                store=SessionStore(Path(td),dict(free_floor_mib=0));identifier=store.new(audio=audio,consent=audio)
                archive=store.begin(identifier,dict(enhancement=route_binding('both')))
                router=EnhancementRouter(Path(td)/'ring',2,'both',DelayedHelper(),archive=archive);router.start()
                x=np.linspace(-.1,.1,3207,dtype=np.float32);router.append(x);router.finish();router.join()
                store.ended(identifier,archive);self.assertIsNone(archive.error)
                rows=list(records(archive.path/'transforms.jsonl'));self.assertTrue(rows)
                self.assertEqual(rows[0]['source_start_sample'],0);self.assertEqual(rows[-1]['source_end_sample'],len(x))
                if audio:
                    np.testing.assert_array_equal(store.audio_slice(identifier,archive.path.name,0,len(x),stream='input'),x)
                    np.testing.assert_array_equal(store.audio_slice(identifier,archive.path.name,0,len(x),stream='asr'),x*.5)
                    meta=json.loads((archive.path/'epoch.json').read_text());self.assertEqual(meta['enhanced_recorded_samples'],len(x))
                else:
                    self.assertFalse((archive.path/'model_input.f32le').exists());self.assertFalse((archive.path/'enhanced.f32le').exists())

    def test_coordinator_retains_unknown_and_never_equates_quiet_missing_words_with_noise(self):
        c=NoiseCoordinator('asr');self.assertEqual(c.snapshot()['observations']['beam']['state'],'unknown')
        c.observe('waveform',0,1,dict(rms=.00001,clipped_fraction=0),'fixture')
        c.event('research_asr_observation',1,dict(source_start_sec=0,text=''))
        a=c.snapshot(16000);self.assertIsNone(a['noise_probability']);self.assertFalse(a['identity_authority'])
        self.assertEqual(a['actions'],['observe only; retain normal scheduler'])
        c.event('research_segmentation',1,dict(source_start_sec=0,speech=True,overlap=True))
        self.assertIn('overlap',c.snapshot(16000)['actions'][0])
        c.observe('beam',0,.1,dict(valid=True),'old fixture',available=time.perf_counter()-3)
        self.assertEqual(c.snapshot(16000)['observations']['beam']['state'],'stale_or_ahead_of_consumer')

    def test_route_selection_stops_and_requires_new_start(self):
        with tempfile.TemporaryDirectory() as td:
            c=Controller.__new__(Controller);c.settings={};c.data_root=Path(td);c._ensure_no_enrollment=Mock();c._stop_session=Mock()
            c.models=SimpleNamespace(enhancement_model=Mock());c.config=object();c.source_kind='live'
            c._do_noise_route('asr');c._stop_session.assert_called_once();self.assertIsNone(c.source_kind)
            self.assertEqual(c.state,'IDLE');self.assertEqual(c.settings['enhancement_route'],'asr')
            with self.assertRaises(ValueError):c._do_noise_route('unqualified_model')

    def test_inflight_late_output_is_discarded_after_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            entered=threading.Event();release=threading.Event();helper=DelayedHelper()
            original=helper.run
            def stalled(x):
                if helper.calls:
                    entered.set();assert release.wait(3)
                return original(x)
            helper.run=stalled
            router=EnhancementRouter(Path(td)/'late',2,'both',helper);router.start()
            x=np.linspace(-.2,.2,9700,dtype=np.float32)
            router.append(x[:320])
            deadline=time.monotonic()+2
            while router.enhanced.committed_samples!=160 and time.monotonic()<deadline:time.sleep(.001)
            self.assertEqual(router.enhanced.committed_samples,160)
            router.append(x[320:640]);self.assertTrue(entered.wait(2))
            router.append(x[640:]);self.assertEqual(router.identity_limit,160)
            router.finish();release.set();router.join()
            expected=x.copy();expected[:160]*=.5
            np.testing.assert_array_equal(router.asr.read(0,len(x)),expected)
            np.testing.assert_array_equal(router.identity.read(0,len(x)),x[:160]*.5)
            self.assertTrue(router.identity.finished)

    def test_enrollment_quality_hash_and_script_audio_follow_enhanced_stream(self):
        c=Controller.__new__(Controller);c._enroll_enhancer=DelayedHelper();c._enroll_enhancer.reset()
        c._enroll_script_enabled=True;c._enroll_audio=[];c.enrollment={};c._update_enrollment_read=Mock()
        c._quality_queue=queue.Queue();c._quality=EnrollmentQuality(Models(),SimpleNamespace(minimum_rms=.001),None)
        x=np.full(161601,.1,np.float32)
        c._quality_queue.put((0,x[:160000]));c._quality_queue.put((160000,x[160000:]));c._quality_queue.put(None)
        c._quality_loop();c._quality_queue.join();q,_=c._quality.result()
        expected=x*.5
        self.assertEqual(q['source_sha256'],hashlib.sha256(expected.astype('<f4').tobytes()).hexdigest())
        np.testing.assert_array_equal(np.concatenate(c._enroll_audio),expected)
        self.assertEqual(c._quality.samples,len(x));self.assertEqual(q['gaps'],0)

    def test_stalled_final_native_call_releases_asr_but_retains_worker_ownership(self):
        with tempfile.TemporaryDirectory() as td:
            entered=threading.Event();release=threading.Event();helper=DelayedHelper();original=helper.run
            def hang(x):entered.set();assert release.wait(3);return original(x)
            helper.run=hang;router=EnhancementRouter(Path(td)/'eof',2,'both',helper);router.start()
            x=np.full(320,.1,np.float32);router.append(x);self.assertTrue(entered.wait(1));router.finish()
            deadline=time.monotonic()+2
            while not router.enhanced.finished and time.monotonic()<deadline:time.sleep(.01)
            self.assertTrue(router.enhanced.finished);self.assertEqual(router.identity_limit,0)
            np.testing.assert_array_equal(router.asr.read(0,320),x)
            with self.assertRaises(RuntimeError):router.join(.001)
            release.set();router.join();self.assertFalse(router.thread.is_alive())

    def test_enrollment_failure_cannot_save_or_substitute_raw(self):
        c=Controller.__new__(Controller);helper=DelayedHelper();helper.reset();helper.run=Mock(side_effect=RuntimeError('failed'))
        c._enroll_enhancer=helper;c._enroll_script_enabled=True;c._enroll_audio=[];c.enrollment={};c._update_enrollment_read=Mock()
        c._quality_queue=queue.Queue();c._quality=EnrollmentQuality(Models(),SimpleNamespace(minimum_rms=.001),None)
        c._quality_queue.put((0,np.full(16000,.1,np.float32)));c._quality_queue.put(None);c._quality_loop()
        self.assertFalse(c._quality.result(gaps=c.enrollment['gaps'])[0]['can_save']);self.assertEqual(c._quality.samples,0)

    def test_fallback_clears_stale_identity_but_preserves_caption_text(self):
        from app.pipeline import PrototypeEngine,PipelineEngine
        engine=PrototypeEngine.__new__(PrototypeEngine);engine.coordinator=NoiseCoordinator();engine.prototype_identity=None
        engine.live_spatial=None;engine.enhancement_router=SimpleNamespace(identity_limit=16000)
        row=dict(text='Do not leave',source_end_sec=2,segments=[dict(text='Do not leave',source_end_sec=2,
            known_name='Old',known_profile_id='old',track_id=1,anonymous_label='Speaker 1',voice_available=True)])
        with patch.object(PipelineEngine,'_emit') as emit:engine._emit('s6d_display',2,row)
        result=emit.call_args.args[2];self.assertEqual(result['text'],row['text']);self.assertEqual(row['segments'][0]['known_name'],'Old')
        part=result['segments'][0];self.assertIsNone(part['known_profile_id']);self.assertIsNone(part['anonymous_label'])
        self.assertFalse(part['voice_available']);self.assertEqual(part['label'],'Unknown')


if __name__=='__main__':unittest.main()
