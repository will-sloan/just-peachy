"""Tiny model-free beam execution checks; see README_S6D_BEAM_EXECUTION_V1.md."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import s6d_beam_native_run_v1 as N
import s6d_beam_execution_prepare_v1 as P

class Checks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Checks.root);self.d=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def good(self):
        proof=dict(frames=16000,bytes=32000,sha256='a'*64)
        job=dict(job_id='T',mode='mono_asr_beam_identity',expected_frames=16000,stream_proofs={s:proof for s in ('auto_asr_raw','focus0_asr_raw','focus1_asr_raw')})
        worker=dict(closed=True,thread_alive=False,error=None,depth=0,accepted=1,completed=1)
        queues={k:worker for k in ('journal','punctuation','policy')};queues['event_consumer']=dict(depth=0)
        telemetry=dict(state='COMPLETED',source_duration_sec=1.,asr_cursor_sec=1.,speaker_cursor_sec=1.,paired_audio_samples=16000,identity_audio_samples=16000,audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0,live_lanes_at_finalization=[],bundle_retained_due_live_lanes=False,scheduler=dict(closed=True,pending_events=0,watermarks=dict(asr='closed',speaker='closed')),s6d=queues,s6d_beams=dict(waveform_switches=0,serial_model_owner=True,model_instance_counts=dict(sherpa_recognizer=1,sherpa_decoder_states=1,pyannote=1,redimnet=1)))
        result=dict(job=job,status='COMPLETE',failure=None,native_tested=True,resource_observer_closed=True,event_consumer_drained=True,observer_errors=[],completion_errors=[],telemetry=telemetry)
        final=dict(state='COMPLETED',finalization_error=None,event_and_transcript_handles_closed=True,live_lanes_at_finalization=[],resident_bundle_lease_retained=False,source_samples=16000,identity_samples=16000)
        closure=dict(full_event_consumer_drained=True,queues=queues)
        return result,job,final,closure,deepcopy(job['stream_proofs']),dict(frames=16000)
    def test_three_journal_full_source_positive(self):self.assertEqual(N.validate_multistream(*self.good()),[])
    def test_missing_second_focus_rejects(self):
        x=list(self.good());del x[4]['focus1_asr_raw'];self.assertTrue(N.validate_multistream(*x))
    def test_focus_hash_mismatch_rejects(self):
        x=list(self.good());x[4]['focus1_asr_raw']['sha256']='b'*64;self.assertTrue(N.validate_multistream(*x))
    def test_clean_stopped_prefix_is_not_complete(self):
        x=list(self.good());x[0]['telemetry']['source_duration_sec']=.5;x[2]['source_samples']=8000;self.assertTrue(N.validate_multistream(*x))
    def test_dispatch_prefix_rejects(self):
        x=list(self.good());x[5]['frames']=8000;self.assertTrue(N.validate_multistream(*x))
    def test_observer_error_rejects(self):
        x=list(self.good());x[0]['observer_errors']=['late I/O'];self.assertTrue(N.validate_multistream(*x))
    def test_worker_not_drained_rejects(self):
        x=list(self.good());x[0]['telemetry']['s6d']['journal']['closed']=False;self.assertTrue(N.validate_multistream(*x))
    def test_multiple_decoder_states_reject(self):
        x=list(self.good());x[0]['telemetry']['s6d_beams']['model_instance_counts']['sherpa_decoder_states']=2;self.assertTrue(N.validate_multistream(*x))
    def test_actual_journal_conversion_matches_frozen_audiojournal(self):
        import numpy as np
        import soundfile as sf
        import importlib.util
        audio_file=self.d/'source.wav';samples=np.array([-1,-.1,0,.1,.999969,1],np.float32);sf.write(audio_file,samples,16000,subtype='FLOAT')
        b=N.bind(audio_file);proof=N.journal_representation(b)
        path=P.R/'application/beam_native_interface_v3/source/edge_speech_pipeline/audio.py'
        spec=importlib.util.spec_from_file_location('frozen_audiojournal',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        journal=m.AudioJournal(self.d/'actual.pcm16');journal.append(samples);journal.finish()
        self.assertEqual(N.bind(journal.path)['sha256'],proof['sha256']);self.assertEqual(proof['frames'],6)
    def fixture_case(self,status='PASS'):
        import numpy as np
        import soundfile as sf
        wav=self.d/'s.wav';sf.write(wav,np.zeros(1600,np.float32),16000,subtype='PCM_24');audio=N.bind(wav)
        cfg=self.d/'configuration.json';N.save(cfg,dict(profile='P_MAIN6',source_input=dict(source=audio)));config=N.bind(cfg)
        case=dict(status='PASS',transport_integrity_status='PASS',configuration=config,attempt=dict(case_id='C',profile='P_MAIN6',source_audio=audio),source_input=dict(source=audio),streams=[dict(name=n,category=N.ROUTES[n][0],source=N.ROUTES[n][1],raw_gain=1.,audio=audio,common_capture_start_native_frame=0) for n in P.MAIN])
        cp=self.d/'case.json';N.save(cp,case);case_b=N.bind(cp)
        qp=self.d/'qualification.json';N.save(qp,dict(schema_version='edge-s6d-route-qualification.v1',status=status,case_result=case_b,configuration=config,stream_identity_verified=True,common_frame_origin_verified=True,source_tail_validity_verified=True,stream_names=P.MAIN))
        return dict(case_id='C',capture_profile='P_MAIN6',case_result=case_b,qualification=N.bind(qp))
    def test_alias_only_projection_keeps_raw_hashes(self):
        row=self.fixture_case();admission,original=P.project(row,self.d/'view');a=N.verified(admission);v=N.verified(a['case_result'])
        self.assertEqual([x['audio'] for x in original['streams']],[x['audio'] for x in v['streams']]);self.assertEqual(v['streams'][0]['name'],'auto_asr')
    def test_unaccepted_route_cannot_project(self):
        row=self.fixture_case('PENDING')
        with self.assertRaises(ValueError):P.project(row,self.d/'view')
    def test_wrong_physical_case_rejected(self):
        row=self.fixture_case();q=N.verified(row['qualification']);q['case_result']['sha256']='f'*64
        path=self.d/'wrong.json';N.save(path,q);row['qualification']=N.bind(path)
        with self.assertRaises(ValueError):P.project(row,self.d/'view')
    def test_uncaptured_C_partition_rejected(self):
        row=self.fixture_case();path=self.d/'C.json';N.save(path,dict(partition='C',Q_used=False,disjoint_from_E_Q_verified=True,accepted_case_results=[]));row['calibration_partition']=N.bind(path)
        with self.assertRaises(ValueError):P.project(row,self.d/'view')
    def test_Q_partition_rejected(self):
        row=self.fixture_case();path=self.d/'Q.json';N.save(path,dict(partition='C',Q_used=True,disjoint_from_E_Q_verified=True,accepted_case_results=[row['case_result']]));row['calibration_partition']=N.bind(path)
        with self.assertRaises(ValueError):P.project(row,self.d/'view')
    def test_C_probe_preserves_delegate_and_actual_window(self):
        seen=[];answer=dict(status='NO_MATCH',calibrated=False)
        class Delegate:
            def choose(self,candidates,now,**kw):seen.append((candidates,now,kw));return answer
        candidate=dict(event_id='a',stream_id='focus0_asr',source_start_sec=0.,source_end_sec=1.5,waveform=[1,2],identity={})
        candidates=[candidate];events=[];probe=N.CalibrationProbe(Delegate(),lambda *x:events.append(x),lambda a,b:.9)
        result=probe.choose(candidates,1.6,auto_wave=[1,2],auto_support=(0.,1.5),auto_speech=True)
        self.assertIs(result,answer);self.assertIs(seen[0][0],candidates);self.assertEqual(events[0][2]['candidates'][0]['auto_waveform_correlation'],.9)
        self.assertNotIn('waveform',events[0][2]['candidates'][0]);self.assertFalse(events[0][2]['thresholds_applied'])
    def test_C_probe_never_correlates_mismatched_window(self):
        class Delegate:
            def choose(self,*a,**k):return dict(status='NO_MATCH')
        events=[];probe=N.CalibrationProbe(Delegate(),lambda *x:events.append(x),lambda *x:(_ for _ in ()).throw(AssertionError('must not align')))
        probe.choose([dict(source_start_sec=0.,source_end_sec=1.5,waveform=[])],2.,auto_wave=[],auto_support=(.5,2.),auto_speech=True)
        self.assertIsNone(events[0][2]['candidates'][0]['auto_waveform_correlation'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();N.need(a.output.drive.upper()=='G:' and not a.output.exists(),'Fresh G fixture directory required');a.output.mkdir(parents=True);Checks.root=a.output
    with (a.output/'TESTS.log').open('x',encoding='utf-8') as log:result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    N.save(a.output/'RECEIPT.json',dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),source=[N.bind(Path(__file__)),N.bind(Path(N.__file__)),N.bind(Path(P.__file__))],models=0,hardware=0,native_sessions=0,process_launches=0))
    print(json.dumps(N.bind(a.output/'RECEIPT.json')));raise SystemExit(0 if result.wasSuccessful() else 1)
