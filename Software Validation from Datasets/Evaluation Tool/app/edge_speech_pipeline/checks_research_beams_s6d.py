"""Model-free accepted-input/native-hook fixtures. See README_RESEARCH_S6D_BEAMS.md."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
import unittest
from types import SimpleNamespace
from queue import Queue
import numpy as np
import soundfile as sf

from .research_beams_s6d import BeamSettings,CaptureAdmission,BeamSelector,BeamPipelineEngine,MultiJournal,binding,verify_cli_inputs
from .research_identity_v3 import ResearchGallery
from .research_profiles_v3 import ResearchProfileV3,IdentitySettingsV3
from .config import PipelineConfig


def save(path,row):path.write_text(json.dumps(row,indent=2)+'\n');return binding(path)


def fixture_capture(root,frames=48000,matching_focus=False):
    streams=[]
    for index,name in enumerate(('auto_asr','focus0_asr','focus1_asr')):
        frequency=220 if matching_focus and index==1 else 220+index*80
        wave=.1*np.sin(np.arange(frames)*2*np.pi*frequency/16000)
        path=root/(name+'.wav');sf.write(path,wave,16000,subtype='PCM_16')
        streams.append({'name':name,'category':7,'source':(3,0,1)[index],'audio':binding(path),'raw_gain':1.,'common_capture_start_native_frame':4})
    config=save(root/'configuration.json',{'fixture_only':True,'profile':'P_MAIN6'})
    result=save(root/'case_result.json',{'fixture_only':True,'status':'PASS','transport_integrity_status':'PASS','streams':streams,'configuration':config})
    proof=save(root/'qualification.json',{'fixture_only':True,'schema_version':'edge-s6d-route-qualification.v1','status':'PASS',
        'case_result':result,'configuration':config,'stream_identity_verified':True,'common_frame_origin_verified':True,
        'source_tail_validity_verified':True,'stream_names':[r['name'] for r in streams]})
    data={'fixture_only':True,'schema_version':'edge-s6d-capture-admission.v1','status':'ACCEPTED_FOR_NATIVE_ANALYSIS',
        'capture_source_id':'fixture_capture','route_id':'fixture_route','capture_epoch':'fixture_epoch','common_origin':'fixture_sample_zero',
        'case_result':result,'configuration':config,'qualification':proof,'sample_count':frames,'stream_names':[r['name'] for r in streams]}
    save(root/'admission.json',data);return root/'admission.json',data


def calibrated(settings):
    selector=BeamSelector(settings,None)
    selector.calibration={'minimum_selected_score':.7,'minimum_selected_margin':.1,'minimum_beam_margin':.1,
        'minimum_auto_correlation':.9,'minimum_auto_margin':.1,'duplicate_waveform_correlation':.95,'duplicate_voice_cosine':.9,'continuity_bonus':.05,'duplicate_resolution_enabled':True}
    return selector


def candidate(stream='focus0_asr',person='a',wave=None,start=.5,end=2.,available=2.):
    vector=np.zeros(192,np.float32);vector[0 if person=='a' else 1]=1
    return {'stream_id':stream,'capture_source_id':'capture','route_id':'route','event_id':stream+str(end),'speech':True,'overlap':False,
        'source_start_sec':start,'source_end_sec':end,'available_at_sec':available,'vector':vector,
        'waveform':np.sin(np.arange(24000)*.02).astype(np.float32) if wave is None else wave,
        'identity':{'naming_state':'confirmed','known_profile_id':person,'known_name':person,'current_query_name_cosine':.9,'margin':.2}}


class BeamChecks(unittest.TestCase):
    def test_active_restart_rejects_before_reading_or_mutating_beam_state(self):
        for state in ('RUNNING','PAUSED','LOADING','STOPPING'):
            engine=BeamPipelineEngine.__new__(BeamPipelineEngine);engine._state=state
            engine.capture=object();engine._beam_selector=object();engine._beam_source_origin=123.
            original=(engine.capture,engine._beam_selector,engine._beam_source_origin)
            with self.assertRaisesRegex(RuntimeError,'already '+state.lower()):engine.start_capture('missing-file-must-not-be-read.json')
            self.assertEqual((engine.capture,engine._beam_selector,engine._beam_source_origin),original)

    def test_inherited_restart_guards_preserve_previous_beam_provenance(self):
        with tempfile.TemporaryDirectory(prefix='s6d-beam-start-guards-') as tmp:
            root=Path(tmp);path,data=fixture_capture(root)
            gallery=save(root/'gallery.json',{'fixture_only':True})
            for reason in ('enrollment','finalizer','undrained','closure'):
                engine=BeamPipelineEngine.__new__(BeamPipelineEngine);engine._state='COMPLETED';engine.beam_settings=BeamSettings()
                engine.capture=object();engine._beam_selector=object();engine._beam_source_origin=123.;engine._beam_views=object()
                original=(engine.capture,engine._beam_selector,engine._beam_source_origin,engine._beam_views)
                engine._research_gallery=SimpleNamespace(receipt={'manifest':gallery});engine._research_profile=SimpleNamespace(digest=lambda:'fixture')
                engine._enrollment_recorder=object() if reason=='enrollment' else None
                engine._finalization_thread=SimpleNamespace(is_alive=lambda:reason=='finalizer')
                engine._s6d=object();engine._session_dir=root;engine.events=Queue()
                if reason=='undrained':engine.events.put('committed fixture event')
                inbox=engine.events
                with self.assertRaises(RuntimeError):engine.start_capture(path,realtime=False)
                self.assertEqual((engine.capture,engine._beam_selector,engine._beam_source_origin,engine._beam_views),original)
                self.assertIs(engine.events,inbox)
                self.assertEqual(engine.events.qsize(),int(reason=='undrained'))

    def test_cli_job_bindings_reject_changed_inputs_before_native_start(self):
        with tempfile.TemporaryDirectory(prefix='s6d-cli-fixture-') as tmp:
            root=Path(tmp);source=root/'profile.json';ref=save(source,{'fixture':1})
            receipt=root/'INPUTS.json';receipt_ref=save(receipt,{'schema_version':'edge-s6d-beam-job-inputs.v1','inputs':{'profile':ref}})
            verify_cli_inputs({'profile':source},receipt,receipt_ref['sha256'])
            save(source,{'fixture':2})
            with self.assertRaises(ValueError):verify_cli_inputs({'profile':source},receipt,receipt_ref['sha256'])

    def test_capture_requires_qualified_same_pass_routes_and_hashes(self):
        with tempfile.TemporaryDirectory(prefix='s6d-capture-fixture-') as tmp:
            root=Path(tmp);path,data=fixture_capture(root)
            self.assertEqual(CaptureAdmission(path,BeamSettings()).frames,48000)
            bad=dict(data,status='TRANSPORT_ONLY');save(path,bad)
            with self.assertRaises(ValueError):CaptureAdmission(path,BeamSettings())
            save(path,data);proof=json.loads((root/'qualification.json').read_text());proof['source_tail_validity_verified']=False
            data['qualification']=save(root/'qualification.json',proof);save(path,data)
            with self.assertRaises(ValueError):CaptureAdmission(path,BeamSettings())
            proof['source_tail_validity_verified']=True;data['qualification']=save(root/'qualification.json',proof);save(path,data)
            with (root/'focus0_asr.wav').open('ab') as handle:handle.write(b'changed')
            with self.assertRaises(ValueError):CaptureAdmission(path,BeamSettings())

    def test_multibeam_calibration_never_imputed_and_no_future_mixed_capture(self):
        settings=BeamSettings(mode='selected_beam_association',selected_profile_ids=('a','b'))
        row=candidate()
        self.assertEqual(BeamSelector(settings,None).choose([row],2.1)['reason'],'multiple_beam_C_calibration_unavailable')
        selector=calibrated(settings)
        self.assertEqual(selector.choose([row],1.9)['status'],'NO_MATCH')
        self.assertEqual(selector.choose([row],3.)['status'],'NO_MATCH')
        self.assertEqual(selector.choose([dict(row,available_at_sec=3.)],3.1)['status'],'NO_MATCH')
        self.assertEqual(selector.choose([row,dict(candidate('focus1_asr'),capture_source_id='other')],2.1)['reason'],'mixed_capture_or_route_evidence')
        self.assertEqual(selector.choose([dict(row,speech=False)],2.1)['status'],'NO_MATCH')
        self.assertEqual(selector.choose([dict(row,overlap=True)],2.1)['status'],'NO_MATCH')

    def test_duplicate_needs_same_span_waveform_and_voice(self):
        selector=calibrated(BeamSettings(mode='selected_beam_association',selected_profile_ids=('a','b')))
        a=candidate();b=candidate('focus1_asr')
        self.assertEqual(selector.choose([a,b],2.1)['status'],'ASSOCIATED')
        different_voice=candidate('focus1_asr','b',wave=a['waveform'])
        self.assertEqual(selector.choose([a,different_voice],2.1)['reason'],'competing_selected_beams')
        self.assertEqual(selector.choose([a,dict(b,source_start_sec=.4,source_end_sec=1.9)],2.1)['status'],'NO_MATCH')
        self.assertEqual(selector.choose([a,dict(b,waveform=np.cos(np.arange(24000)*.071))],2.1)['status'],'NO_MATCH')
        selector.calibration['duplicate_resolution_enabled']=False
        self.assertEqual(selector.choose([a,b],2.1)['status'],'NO_MATCH')

    def test_auto_focus_bridge_requires_exact_source_window_and_exclusive_auto(self):
        selector=calibrated(BeamSettings());a=candidate();b=candidate('focus1_asr',wave=np.cos(np.arange(24000)*.031))
        args={'auto_wave':a['waveform'],'auto_support':(.5,2.),'auto_speech':True}
        self.assertEqual(selector.choose([a,b],2.1,**args)['selected_stream'],'focus0_asr')
        self.assertEqual(selector.choose([a],2.1,**dict(args,auto_speech=False))['status'],'NO_MATCH')
        self.assertEqual(selector.choose([a],2.1,**dict(args,auto_support=(.4,1.9)))['status'],'NO_MATCH')
        self.assertEqual(selector.choose([a,candidate('focus1_asr')],2.1,**args)['reason'],'competing_auto_focus_associations')

    def test_mono_native_engine_uses_one_asr_and_shared_models_without_calibration(self,calibrated_case=False,auto_control=False,calibration_collection=False):
        class ASR:
            utterance_index=0;decode_ms=0.
            def __init__(self):self.blocks=[]
            def accept(self,audio):self.blocks.append(np.asarray(audio).copy());return ('fixture text',False)
            def finish(self):return 'fixture text'
            def punctuate(self,text):return {'text':text,'compute_ms':0.,'status':'fixture','model_id':'no_neural_model'}
        class Models:
            last_segment_ms=last_embed_ms=0.
            def __init__(self):self.segment_calls=self.embed_calls=0
            def segment(self,wave,include_posteriors=False):
                self.segment_calls+=1;ones=np.ones(592,np.float32);zeros=np.zeros(592,np.float32)
                return {'speech':ones,'overlap':zeros,'speech_probability':ones,'overlap_probability':zeros}
            def embed(self,wave):
                self.embed_calls+=1;v=np.zeros(192,np.float32)
                frequency=np.argmax(np.abs(np.fft.rfft(wave)))*16000/len(wave)
                v[0 if frequency<250 else 1]=1;return v
        class Bundle:
            def __init__(self):self.models=Models();self.asr=ASR();self.acquired=self.released=0
            def acquire(self,config):self.acquired+=1;return self.models,self.asr
            def release(self):self.released+=1
        with tempfile.TemporaryDirectory(prefix='s6d-native-beam-fixture-') as tmp:
            root=Path(tmp);path,data=fixture_capture(root,matching_focus=calibrated_case)
            config=replace(PipelineConfig(),session_root=root/'sessions')
            gallery=ResearchGallery.__new__(ResearchGallery);gallery.matrix=np.eye(1,192,dtype=np.float32);gallery.ids=['a'];gallery.names=['Alice'];gallery.gallery_id='fixture'
            manifest=save(root/'gallery.json',{'fixture_only':True})
            gallery.receipt={'manifest':manifest,'backend_sha256':config.asset('redimnet2_b2_fp32').sha256,'loaded_count':1}
            from .research_s6d import S6DSettings
            profile=replace(ResearchProfileV3(),identity=replace(IdentitySettingsV3(),mode='post_association',minimum_unique_sec=.5,minimum_disjoint_count=1))
            settings=BeamSettings()
            if calibrated_case:
                cproof=save(root/'C_fixture.json',{'fixture_only':True,'partition':'C','Q_used':False,'disjoint_from_E_Q_verified':True})
                cref=save(root/'calibration.json',{'fixture_only':True,'schema_version':'edge-s6d-beam-calibration.v1','status':'ACCEPTED_C_ONLY',
                    'gallery':manifest,'identity_streams':list(settings.identity_streams),'profile_sha256':profile.digest(),'capture_profile':'P_MAIN6',
                    'selected_profile_ids':['a'],'calibration_evidence':cproof,**calibrated(settings).calibration})
                settings=replace(settings,calibration=cref,mode='selected_beam_association',selected_profile_ids=('a',))
            if auto_control:settings=replace(settings,mode='same_pass_auto_control',identity_streams=('auto_asr',))
            if calibration_collection:
                settings=replace(settings,mode='calibration_collection')
                with self.assertRaises(ValueError):CaptureAdmission(path,settings)
                data['calibration_partition']=save(root/'partition.json',{'fixture_only':True,'schema_version':'edge-s6d-beam-calibration-partition.v1',
                    'partition':'C','Q_used':False,'disjoint_from_E_Q_verified':True,'accepted_case_results':[data['case_result']]})
                save(path,data)
            bundle=Bundle();engine=BeamPipelineEngine(config,research_profile=profile,research_gallery=gallery,model_bundle=bundle,
                s6d_settings=S6DSettings(),beam_settings=settings)
            session=engine.start_capture(path,realtime=False);deadline=time.perf_counter()+10;events=[]
            while time.perf_counter()<deadline:
                while not engine.events.empty():events.append(engine.events.get())
                if engine._finalization_thread is not None and not engine._finalization_thread.is_alive():break
                time.sleep(.002)
            engine.wait_for_completion(2)
            while not engine.events.empty():events.append(engine.events.get())
            engine.record_s6d_consumer_closure('synthetic native-hook fixture, no neural models')
            self.assertEqual(engine.state,'COMPLETED');self.assertEqual((bundle.acquired,bundle.released),(1,1))
            self.assertGreater(bundle.models.embed_calls,0);self.assertGreater(bundle.models.segment_calls,0)
            self.assertTrue(any(e.event_type==('research_embedding' if auto_control else 's6d_beam_identity') for e in events))
            if calibrated_case:
                self.assertTrue(any(e.event_type=='s6d_auto_beam_association' and e.payload['status']=='ASSOCIATED' for e in events))
                self.assertTrue(any(e.event_type=='s6d_selected_beam_association' and e.payload['status']=='ASSOCIATED' for e in events))
            elif not auto_control:self.assertTrue(all(e.payload['status']=='NO_MATCH' for e in events if e.event_type=='s6d_auto_beam_association'))
            originals=sf.read(root/'auto_asr.wav',dtype='float32')[0];actual=np.concatenate(bundle.asr.blocks)
            np.testing.assert_allclose(actual[:len(originals)],originals,atol=1/32768)
            self.assertEqual(engine.telemetry()['s6d_beams']['model_instance_counts']['sherpa_decoder_states'],1)
            self.assertEqual(len(list(session.glob('*audio_spool.pcm16'))),1 if auto_control else 3)
            latest=[json.loads(x) for x in (session/'latest_labelled_transcript.jsonl').read_text().splitlines()]
            self.assertEqual([r['text'] for r in latest],['fixture text'])

    def test_calibrated_native_hook_associates_matching_beam_without_switching_asr(self):
        self.test_mono_native_engine_uses_one_asr_and_shared_models_without_calibration(calibrated_case=True)

    def test_same_pass_auto_control_uses_existing_native_identity_lane(self):
        self.test_mono_native_engine_uses_one_asr_and_shared_models_without_calibration(auto_control=True)

    def test_C_collection_requires_bound_partition_and_keeps_selection_disabled(self):
        self.test_mono_native_engine_uses_one_asr_and_shared_models_without_calibration(calibration_collection=True)


if __name__=='__main__':unittest.main(verbosity=2)
