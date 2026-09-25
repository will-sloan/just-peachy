"""Actual frozen ASR-loop protocol tests, no models. README_ASR_BANK.md."""
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from asr_lane_components import capture_type,SequentialJournal
from asr_bank_components import component_key,require_owner,resource_guard


class BaselineStub:
    def __init__(self):
        self.utterance_index=0;self.decode_ms=.01;self.blocks=[];self.punctuation=[];self.finished=False
    def accept(self,block):
        self.blocks.append(block.copy());return 'test words',len(self.blocks)==2
    def reset_endpoint(self):self.utterance_index+=1;return 'test words'
    def finish(self):self.finished=True;return 'tail word'
    def punctuate(self,text):
        if not self.finished:raise AssertionError('Component punctuation must remain separate from raw ASR')
        self.punctuation.append(text);return dict(text=text+'.',compute_ms=.1,status='stub')


class NativeStub:
    padding_seconds=0.
    def __init__(self):
        self.input_samples=0;self.blocks=[];self.decode_ms=.01;self.closed=False;self.finished=False;self.punctuation=[]
    def row(self,text,final,utterance):
        return dict(raw_text=text,final=final,utterance=utterance,input_end_sec=self.input_samples/16000,
            input_samples=self.input_samples,words=[],word_time_kind='stub')
    def feed(self,block):
        self.blocks.append(block.copy());self.input_samples+=len(block)
        if len(self.blocks)==1:return [self.row('first',False,0),self.row('first',True,0),self.row('second',True,1)]
        return [self.row('tail',False,2)]
    def finish_events(self):
        self.finished=True;return [self.row('tail',True,2)]
    def close(self):self.closed=True
    def punctuate(self,text):
        if not self.closed:raise AssertionError('Actual native loop must close its stream')
        self.punctuation.append(text);return dict(text=text,compute_ms=0.,status='native_stub')


class TestRealASRLoops(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np=np
        source=Path(os.environ.get('JP_N4_SOURCE',r'G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-catalog-v3\prototype'))
        sys.path[:0]=[str(source),str(source/'vendor')]
        from app.pipeline import effective_profile
        from app.paths import pipeline_config
        from edge_speech_pipeline.runtime import PipelineEngine
        from app.n3_pipeline import StreamingASRLane
        cls.base=PipelineEngine;cls.native=StreamingASRLane;cls.Capture=capture_type(PipelineEngine)
        cls.profile=effective_profile('balanced','anonymous_conversation','O0')
        cls.config=cls.profile.apply(pipeline_config(Path('not-created'),Path('models-not-opened')))
    def capture(self,frames=3205):
        self.log=io.StringIO();self.wave=self.np.arange(frames,dtype='float32')/10000
        return self.Capture(self.profile,self.config,self.wave,self.log,{'variant':'stub'})
    def events(self):return [json.loads(line) for line in self.log.getvalue().splitlines()]
    def test_frozen_baseline_endpoint_and_exact_tail(self):
        c=self.capture();stream=BaselineStub();self.base._asr_loop(c,stream);summary=c.finish_capture()
        self.assertEqual([len(b) for b in stream.blocks],[1600,1600,5])
        self.np.testing.assert_array_equal(self.np.concatenate(stream.blocks),self.wave)
        self.assertEqual(summary['input_samples'],3205)
        self.assertEqual(summary['final_utterances'],['test words','tail word'])
        self.assertEqual(stream.punctuation,['test words','tail word'])
        self.assertEqual(summary['event_counts']['research_asr_tail_dispatch'],1)
        self.assertEqual(summary['event_counts']['research_asr_reset'],1)
    def test_native_multiple_finals_and_same_source_boundary_preserved(self):
        c=self.capture();stream=NativeStub();self.native._asr_loop(c,stream);summary=c.finish_capture()
        self.assertTrue(stream.closed)
        self.assertEqual(summary['final_utterances'],['first','second','tail'])
        self.assertEqual(stream.input_samples,3205)
        finals=[e['payload'] for e in self.events() if e['event_type']=='research_asr_observation' and e['payload']['final']]
        self.assertEqual(finals[1]['source_start_sec'],.1)
        self.assertEqual(finals[1]['source_end_sec'],.1)
        self.assertEqual(finals[-1]['source_end_sec'],3205/16000)
        self.assertEqual([len(b) for b in stream.blocks],[1600,1600,5])
    def test_formatting_does_not_change_raw_observations(self):
        c=self.capture();stream=BaselineStub();self.base._asr_loop(c,stream)
        before=list(c._scheduler.events);c.finish_capture()
        self.assertEqual(before,c._scheduler.events)
        rows=[e['payload'] for e in self.events() if e['event_type']=='component_final_punctuation']
        self.assertEqual(rows[0]['raw_text'],'test words')
        self.assertEqual(rows[0]['punctuation']['text'],'test words.')
        self.assertGreaterEqual(rows[0]['modeled_available_at_sec'],rows[0]['modeled_asr_submission_at_sec'])
    def test_native_failure_preserved_and_closed(self):
        c=self.capture();stream=NativeStub()
        with patch.object(stream,'feed',side_effect=RuntimeError('injected decoder failure')):
            self.native._asr_loop(c,stream)
        self.assertTrue(stream.closed)
        with self.assertRaisesRegex(RuntimeError,'injected'):c.finish_capture()
    def test_forward_journal_rejects_seek_without_losing_samples(self):
        j=SequentialJournal(self.np.zeros(200,dtype='float32'));j.read(0,100)
        with self.assertRaises(ValueError):j.read(0,100)
        self.assertEqual(j.delivered_samples,100)
        self.assertEqual(len(j.read(100,100)),100)
    def test_gain_or_model_thread_drift_rejected(self):
        for config in (replace(self.config,input_gain=2.),replace(self.config,asr_threads=2)):
            with self.assertRaises(ValueError):self.Capture(self.profile,config,self.np.zeros(1),io.StringIO())
    def test_each_independent_scene_has_fresh_utterance_state(self):
        for _ in range(2):
            c=self.capture();stream=BaselineStub();self.base._asr_loop(c,stream);c.finish_capture()
            self.assertEqual(c._scheduler.events[0]['utterance_id'],'utterance:000000')
            self.assertEqual(c._scheduler.events[0]['source_start_sec'],0.)


class TestASRAdmission(unittest.TestCase):
    def test_cache_invalidates_audio_profile_model_and_state_contract(self):
        job=dict(job_id='synthetic_O0',audio_path='not_read.wav',audio_sha256='a'*64,frames=16000,
            sample_rate_hz=16000,gain=1,reset_between_scenes=True,tap='O0')
        base=component_key({'component_contract':{'code':'v1'}},job,'A0',{'read_ms':100})
        for contract,j,v,p in [({'component_contract':{'code':'v2'}},job,'A0',{'read_ms':100}),
            ({'component_contract':{'code':'v1'}},dict(job,audio_sha256='b'*64),'A0',{'read_ms':100}),
            ({'component_contract':{'code':'v1'}},job,'A1',{'read_ms':100}),
            ({'component_contract':{'code':'v1'}},job,'A0',{'read_ms':80})]:
            self.assertNotEqual(base,component_key(contract,j,v,p))
        with self.assertRaises(ValueError):component_key({'component_contract':{}},dict(job,reference='forbidden'),'A0',{})
    def test_exact_supervisor_child_identity_required(self):
        from types import SimpleNamespace
        process=SimpleNamespace(pid=42,create_time=lambda:123.)
        with patch('asr_bank_components.load',return_value={'child_pid':42,'child_create_time':123.}),patch('asr_bank_components.supervisor.same_process',return_value=True):
            require_owner(Path('unused'),process)
        with patch('asr_bank_components.load',return_value={'child_pid':42,'child_create_time':124.}):
            with self.assertRaises(RuntimeError):require_owner(Path('unused'),process)
    def test_storage_reserve_and_deadline_fail_before_model_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch('asr_bank_components.load',return_value={'target_utc':'2099-01-01T00:00:00+00:00'}),patch('asr_bank_components.supervisor.disk_reserves',return_value=({},[])):
                resource_guard(root,root)
                with patch('asr_bank_components.ALLOCATION',1):
                    with self.assertRaisesRegex(RuntimeError,'allocation'):resource_guard(root,root)
            with patch('asr_bank_components.load',return_value={'target_utc':'2000-01-01T00:00:00+00:00'}):
                with self.assertRaises(TimeoutError):resource_guard(root,root)


if __name__=='__main__':unittest.main()
