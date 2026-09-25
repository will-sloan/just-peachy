"""Protected-split and actual D0 lane contract tests. README_D0_CALIBRATION.md."""
from copy import deepcopy
import io
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
import numpy as np
import d0_calibration_windows as d0

SOURCE=d0.LOCAL/'releases/n4-catalog-v3/prototype'
sys.path[:0]=[str(SOURCE),str(SOURCE/'vendor')]
from app.pipeline import effective_profile
from edge_speech_pipeline.research_evidence_v3 import run_speaker_lane_v3


def row(role, identity):
    return dict(role=role,window_id=role+'_'+identity,source_id=role+'source'+identity,
        unique_source_pcm_sha256=role+'pcm'+identity,identity=identity,domain='clean_source',
        sample_rate_hz=16000,gain=1,whole_clip=True,start_sample=0,end_sample=24000,
        audio=dict(path='not-opened.wav',sha256='0'*64,bytes=1))


class FakeModels:
    last_segment_ms=last_embed_ms=0.
    def __init__(self, encoder): self.encoder=encoder; self.spans=[]
    def segment(self,audio,include_posteriors=False):
        assert audio.shape==(160000,) and include_posteriors
        return dict(speech=np.ones(589),overlap=np.zeros(589),
            speech_probability=np.ones(589),overlap_probability=np.zeros(589))
    def embed(self,audio):
        self.spans.append(audio.copy()); vector=np.zeros(192,np.float32)
        vector[self.encoder]=1.; return vector


class TestCalibrationCollection(unittest.TestCase):
    def manifest(self):
        return dict(windows=[row('E','x'),row('C','x')],diagnostic_Q_windows=[row('Q','x')])
    def test_labels_are_separate(self):
        jobs,labels=d0.select_c(self.manifest())
        d0.validate_job(jobs[0]); self.assertEqual(labels[0]['identity'],'x')
        self.assertNotIn('identity',jobs[0]); self.assertNotIn('role',jobs[0])
    def test_C_protected_from_E_and_Q(self):
        for role in ('E','Q'):
            for key in ('source_id','unique_source_pcm_sha256'):
                with self.subTest(role=role,key=key):
                    m=self.manifest(); c=m['windows'][1]
                    other=m['windows'][0] if role=='E' else m['diagnostic_Q_windows'][0]
                    c[key]=other[key]
                    with self.assertRaisesRegex(ValueError,'overlaps'): d0.select_c(m)
    def test_processed_windows_require_bound_protection(self):
        m=self.manifest(); m['diagnostic_Q_windows'][0]['domain']='XVF_query'
        del m['diagnostic_Q_windows'][0]['source_id']
        with self.assertRaisesRegex(ValueError,'Missing protected'):d0.select_c(m)
        c=m['windows'][1]
        p=dict(material=dict(leakage_audit=dict(known_parent_path_prompt_and_exact_bytes_checked=True,
            exact_intersections={'C_Q_source_ids':[]}), accepted_sources=[dict(source_id=c['source_id'],
                s6c_role='C',identity=c['identity'],decoded_pcm_sha256=c['unique_source_pcm_sha256'])]))
        self.assertEqual(len(d0.select_c(m,p)[0]),1)
        p['material']['leakage_audit']['exact_intersections']['C_Q_source_ids']=['x']
        with self.assertRaisesRegex(ValueError,'audit failed'):d0.select_c(m,p)
    def test_reject_nonwhole_C_or_changed_gain(self):
        for key,value in [('whole_clip',False),('start_sample',100),('gain',2),('domain','XVF_query')]:
            m=self.manifest(); m['windows'][1][key]=value
            with self.assertRaises(ValueError):d0.select_c(m)
    def test_lane_rejects_truth_or_large_clip(self):
        job=d0.select_c(self.manifest())[0][0]
        for change in [dict(identity='x'),dict(frames=120*16000+1),dict(reset=False)]:
            with self.assertRaises(ValueError):d0.validate_job(dict(job,**change))
    def test_unchanged_native_lane_selects_identical_actual_spans(self):
        profile=effective_profile('balanced','anonymous_conversation','O0')
        config=profile.apply(); audio=np.linspace(.1,.2,40001,dtype=np.float32)
        outputs=[]
        for encoder in (0,1):
            stream=io.StringIO(); capture=d0.LaneCapture(profile,config,audio,stream)
            models=FakeModels(encoder); run_speaker_lane_v3(capture,models)
            self.assertIsNone(capture.error); self.assertGreater(len(capture.vectors),0)
            self.assertEqual(capture._telemetry['identity_audio_samples'],len(audio))
            self.assertAlmostEqual(capture._telemetry['speaker_unanalyzed_short_tail_sec'],1/16000)
            self.assertEqual(capture.segmentation_calls,5)
            self.assertIn('speech_probability_frames',stream.getvalue())
            self.assertEqual({r['end_sample']-r['start_sample'] for r in capture.vectors},{8000,24000})
            for vector,wave in zip(capture.vectors,models.spans):
                np.testing.assert_array_equal(wave,audio[vector['start_sample']:vector['end_sample']])
            outputs.append([{k:v for k,v in r.items() if k!='normalized_embedding'} for r in capture.vectors])
        self.assertEqual(*outputs)
    def test_reject_tracker_dependent_cadence(self):
        profile=effective_profile('balanced','anonymous_conversation','O0')
        fake=SimpleNamespace(embedding=SimpleNamespace(cadence_policy='uncertainty',cadence_cues_enabled=False))
        with self.assertRaisesRegex(ValueError,'fixed cadence'):
            d0.LaneCapture(fake,profile.apply(),np.zeros(16000),io.StringIO())
    def test_lane_failure_retained(self):
        profile=effective_profile('balanced','anonymous_conversation','O0')
        class Bad(FakeModels):
            def embed(self,audio): raise RuntimeError('intentional fixture failure')
        capture=d0.LaneCapture(profile,profile.apply(),np.ones(24000,np.float32),io.StringIO())
        run_speaker_lane_v3(capture,Bad(0))
        self.assertEqual(capture._state,'FAILED'); self.assertIn('intentional fixture failure',capture.error)


if __name__=='__main__': unittest.main()
