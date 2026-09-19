"""Model-free S4.5 runner gates; commands in README_S45_H2_RUN.md."""
import copy
import contextlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
import soundfile as sf
import s45_h2_run as r


def source(sid, dataset='CMU ARCTIC', samples=16000, pcm=None):
    return {'source_id': sid, 'dataset': dataset, 'samples': samples, 'split': 'development',
            'usage': 'probe', 'whole_clip': True, 'decoded_pcm_sha256': pcm or sid,
            'decoded_16k_binding': {'path': sid+'.wav', 'sha256': sid},
            'preparation_gain': .5, 'quality_partition': 'studio', 'identity': sid,
            'transcript': 'An exact whole sentence.'}


class RunnerTests(unittest.TestCase):
    def test_baseline_allows_exact_two_file_durability_fix(self):
        c = r.baseline_contract()
        self.assertEqual(len(c['source_identities']), 18)
        self.assertEqual(c['scientific_config']['sample_rate'], 16000)

    def test_baseline_rejects_scientific_change(self):
        config = r._config_without_models(); config['sample_rate'] = 8000
        with mock.patch.object(r, '_config_without_models', return_value=config):
            with self.assertRaises(AssertionError): r.baseline_contract()

    def test_dry_selection_is_unique_balanced_and_bounded(self):
        sources = {str(i): source(str(i), ['CMU ARCTIC', 'HiFiTTS', 'Common Voice'][i%3], 8000+(i%4)*10000) for i in range(90)}
        scenes = {'S': {'segments': [{'kind': 'utterance', 'source_id': s} for s in sources]}}
        a = r.dry_candidates({'selected_sources': sources}, scenes, ['S'])
        b = r.dry_candidates({'selected_sources': sources}, scenes, ['S'])
        self.assertEqual(a, b); self.assertEqual(len(a), 24)
        self.assertEqual(len({x['source_id'] for x in a}), 24)
        self.assertEqual({x['stratum']['dataset'] for x in a}, {'CMU ARCTIC', 'HiFiTTS', 'Common Voice'})
        self.assertEqual({x['stratum']['duration_bin'] for x in a}, {'under_1s', '1_to_2s', 'over_2s'})

    def test_duplicate_pcm_is_one_dry_invocation(self):
        sources = {'a': source('a', pcm='same'), 'b': source('b', pcm='same')}
        scenes = {'S': {'segments': [{'kind':'utterance', 'source_id':sid} for sid in sources]}}
        self.assertEqual(len(r.dry_candidates({'selected_sources':sources}, scenes, ['S'])), 1)

    def test_dry_rejects_reserve_or_enrollment_or_L2(self):
        for key, value in [('split', 'downstream_reserve'), ('usage', 'enrollment_reference'), ('dataset', 'L2 ARCTIC')]:
            src = source('a'); src[key] = value
            with self.assertRaises(AssertionError):
                r.dry_candidates({'selected_sources': {'a':src}}, {'S':{'segments':[{'kind':'utterance','source_id':'a'}]}}, ['S'])

    def test_sentinel_family_split_gates(self):
        scenes = [{'case_id':f'S{i:02}_{j}', 'family_id':f'F{i:02}', 'split':'development','task_scoring_allowed':True} for i in range(1,13) for j in [1,2]]
        manifest = {'validation': {'status':'PASS'}, 'scenes': scenes}
        plan = {'scene_ids':[s['case_id'] for s in scenes], 'selection_before_hardware_or_H2':True,'reserve_jobs_allowed':0}
        def read(path): return manifest if Path(path).name == 'SCENE_MANIFEST.json' else plan
        with mock.patch.object(r, 'read', side_effect=read):
            self.assertEqual(len(r.scene_context()[2]), 24)
            scenes[0]['split']='reserve'
            with self.assertRaises(AssertionError):r.scene_context()

    def test_no_dry_plan_after_model_start(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(r, 'DRY_PLAN', Path(tmp)/'plan.json'), \
             mock.patch.object(r, 'scene_context', return_value=({'selected_sources':{}}, {}, [])), \
             mock.patch.object(r, 'identity_binding', return_value={}), mock.patch.object(r, 'jobs_started', return_value=['prior']):
            with self.assertRaises(AssertionError):r.prepare_plans()

    def test_ambient_speech_keeps_all_speaker_scoring_limited(self):
        scene = {'family_id':'F10','segments':[{'kind':'utterance','dataset':'CV','quality_partition':'ambient'}],
                 'transcript_valid':True,'all_speaker_reference_complete':False,'overlap_intervals':[],
                 'target_references':[{'start_sample':0,'transcript':'hello'}]}
        metrics = {'text': {'status':'LIMITED','hypothesis_normalized':'hello ambient words','duration_s':5,'wer':None,'cer':None},
                   'speaker':{'reference_turn_evidence':{'unsafe':1}}}
        with mock.patch.object(r, 'analyze_scene', return_value=metrics) as scorer:
            output=r.analyze_s45(None, scene, None, {'alignment_offset_s':.05}, kind='outputs')
            self.assertFalse(scorer.call_args.args[1]['transcript_valid'])
            self.assertEqual(output['text']['status'],'LIMITED')
            self.assertEqual(output['target_only_text']['status'],'LIMITED_TARGET_REFERENCE_ONLY')
            self.assertNotIn('reference_turn_evidence',output['speaker'])

    def test_output_without_measured_lag_has_no_turn_truth(self):
        scene={'family_id':'F12','segments':[], 'transcript_valid':True,'all_speaker_reference_complete':True,'overlap_intervals':[]}
        metrics={'speaker':{'reference_turn_evidence':{}},'text':{}}
        with mock.patch.object(r,'analyze_scene',return_value=metrics):
            output=r.analyze_s45(None,scene,None,None,kind='outputs')
            self.assertEqual(output['source_to_output_turn_scoring']['status'],'LIMITED')
            self.assertNotIn('reference_turn_evidence',output['speaker'])

    def test_native_summary_requires_complete_exact_spool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); audio=root/'input.wav'; session=root/'session'; session.mkdir()
            x=np.array([-.5,0,.1234,.999999]*20,dtype=np.float32); sf.write(audio,x,16000,subtype='FLOAT')
            summary={'state':'COMPLETED','telemetry':{'audio_frames_dropped':0}}
            (session/'session_summary.json').write_text(json.dumps(summary))
            (session/'events.jsonl').write_text(json.dumps({'event_type':'session_completed'})+'\n')
            exact=(r.journal_audio(audio)*32768).astype('<i2').tobytes()
            spool=session/'audio_spool.pcm16'; spool.write_bytes(exact)
            self.assertEqual(r.verify_native_completion(session,audio)['exact_full_pcm16_samples'],80)
            spool.write_bytes(exact[:-2])
            with self.assertRaises(AssertionError):r.verify_native_completion(session,audio)
            spool.write_bytes(exact); summary['reconstruction_provenance']={}
            (session/'session_summary.json').write_text(json.dumps(summary))
            with self.assertRaises(AssertionError):r.verify_native_completion(session,audio)

    def test_fixed_gain_preserves_float_samples_and_rejects_clipping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); src=root/'source.wav'; dest=root/'adapter.wav'
            x=np.linspace(-.4,.4,200,dtype=np.float32); sf.write(src,x,16000,subtype='FLOAT')
            r.fixed_gain_copy(src,dest,1.4125375446227544)
            np.testing.assert_array_equal(sf.read(dest,dtype='float32')[0],(x.astype(np.float64)*1.4125375446227544).astype(np.float32))
            with self.assertRaises(ValueError):r.fixed_gain_copy(src,root/'clip.wav',4)

    def test_job_count_caps_both_kinds(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(r,'REPORT',Path(tmp)):
            for n in range(49):
                folder=Path(tmp)/'h2'/str(n)/'O0'; folder.mkdir(parents=True)
                (folder/'run_receipt.json').write_text('{"status":"COMPLETE"}')
            with self.assertRaises(AssertionError):r.counts()

    def test_one_gross_stream_keeps_other_output_and_resume_without_extra_job(self):
        """Execute the actual runner loop with a fake child; never imports a model."""
        class Progress:
            done = 0
            def __init__(self, *args): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def emit(self, *args): pass
        class Child:
            pid = 12345
            def wait(self, **kwargs): return 0
            def poll(self): return 0
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            report = Path(tmp)/'report'; report.mkdir(); payload = Path(tmp)/'payload'
            scene = {'case_id':'CASE','family_id':'F01','segments':[]}
            selected = {'CASE':{'folder':Path(tmp)/'capture','capture':{'output_audio':{'O0':{'sha256':'zero'},'O1':{'sha256':'one'}}},
                                'case_result_binding':{'sha256':'capture'},'selection_record':{'case_id':'CASE'}}}
            original_read = r.read
            def read(path):
                if Path(path).name == 'OUTPUT_LEVEL_POLICY.json':
                    return {'frozen':True,'fixed_host_gain':{'O0':1.4125375446227544,'O1':1.0}}
                if Path(path).name == 'INITIALIZATION_POLICY.json':return {'frozen':True}
                return original_read(path)
            patches = {'REPORT': report,'PAYLOAD':payload,'Progress':Progress,'read':read,
                       'scene_context':lambda:({}, {'CASE':scene}, ['CASE']),
                       'prepare_plans':lambda:{'identity':{'controls':[]}},
                       'baseline_contract':lambda:{'durability_fix':{}},
                       'identity_binding':lambda path, expected=None:{'path':str(path),'sha256':expected or 'fixture','bytes':0},
                       'accepted_for':lambda *args:selected,'execution_release':lambda:{},
                       'load_alignment':lambda explicit,cid,stream,row:(None,{},None,'QUARANTINED_GROSS_SATURATION' if stream=='O1' else 'LEVEL_GATE_NO_RAILS'),
                       'check_storage':lambda:0,'launch_allowed':lambda *args:True,
                       'fixed_gain_copy':lambda *args:{'output_binding':{'sha256':'adapter'},'source_rail_samples':0},
                       'completed_session':lambda root:root/'fixture_session',
                       'verify_native_completion':lambda *args:{'native_summary':True},
                       'analyze_s45':lambda *args,**kwargs:{'state':'COMPLETED','failure_events':[]}}
            for key, value in patches.items():stack.enter_context(mock.patch.object(r,key,value))
            child = stack.enter_context(mock.patch.object(r.subprocess,'Popen',return_value=Child()))
            r.run(kind='outputs',cases=['CASE'])
            r.run(kind='outputs',cases=['CASE'])
            self.assertEqual(child.call_count,1)
            self.assertEqual(original_read(report/'h2/CASE/O0/run_receipt.json')['status'],'COMPLETE')
            self.assertEqual(original_read(report/'h2/CASE/O1/run_receipt.json')['status'],'QUARANTINED')
            self.assertFalse((payload/'h2/CASE/O1').exists())
            count=r.counts()
            self.assertEqual(count['intended_output_jobs'],48)
            self.assertEqual(count['output_jobs_complete'],1)
            self.assertEqual(count['output_jobs_quarantined'],1)
            self.assertEqual(count['output_jobs_started'],1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
