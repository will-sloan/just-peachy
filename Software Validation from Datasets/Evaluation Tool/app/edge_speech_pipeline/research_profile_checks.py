"""Focused executable checks for opt-in S6 profiles; see README_RESEARCH_PROFILES.md."""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import sys
import time
import unittest
import numpy as np

from .config import PipelineConfig
from .models import POWERSET_TO_MULTILABEL, SpeakerModels, powerset_posteriors, _ort_session
from .research_profiles import ResearchProfile, segmentation_gate, EndpointAdvisor, DeliveredSpatialObservation, spatial_is_fresh


class ProfileTests(unittest.TestCase):
    def test_explicit_default_config_equals_previous_default(self):
        self.assertEqual(ResearchProfile().apply(), PipelineConfig())

    def test_unknown_fields_and_types_rejected(self):
        for value in [{"asr": {"new_api_field": 1}}, {"embedding": {"window_sec": "1"}}, {"runtime": {"speaker_threads": True}}, {"input": {"gain": float("nan")}}, {"asr": {"max_active_paths": 3}}]:
            with self.assertRaises(ValueError):
                ResearchProfile.from_dict(value)

    def test_fixed_shape_and_cadence_and_double_gain_rejected(self):
        for value in [{"segmentation": {"window_sec": 5}}, {"segmentation": {"hop_sec": .75}, "embedding": {"hop_sec": .5}}, {"input": {"already_gained": True, "gain": 1.4125375446227544}}]:
            with self.assertRaises(ValueError):
                ResearchProfile.from_dict(value)

    def test_all_advertised_component_values_take_effect(self):
        p = ResearchProfile.from_dict({"asr": {"journal_read_ms": 50, "endpoint_rule1_silence_sec":1.6,"endpoint_rule2_silence_sec":.8,"decoding_method":"modified_beam_search","max_active_paths":2,"blank_penalty":.2}, "segmentation":{"hop_sec":.5,"post_policy":"posterior_hysteresis","onset":.55,"offset":.4}, "embedding":{"window_sec":1.0,"hop_sec":.5,"minimum_rms":.001}, "runtime":{"asr_threads":1,"speaker_threads":1}, "punctuation":{"partial_display_min_interval_sec":.2}})
        c = p.apply()
        expected = {"journal_read_ms":50,"endpoint_rule1_silence_sec":1.6,"endpoint_rule2_silence_sec":.8,"asr_decoding_method":"modified_beam_search","asr_max_active_paths":2,"asr_blank_penalty":.2,"segmentation_hop_sec":.5,"segmentation_onset":.55,"segmentation_offset":.4,"embedding_window_sec":1.0,"embedding_hop_sec":.5,"minimum_rms":.001,"asr_threads":1,"speaker_threads":1,"partial_display_min_interval_sec":.2}
        for key, value in expected.items():
            self.assertEqual(getattr(c,key), value)

    def test_powerset_semantics_and_hard_default(self):
        raw = np.full((1, 7, 7), -30, np.float32)
        raw[0, np.arange(7), np.arange(7)] = 0
        out = powerset_posteriors(raw)
        self.assertTrue(np.allclose(out["local_speaker_probability"],POWERSET_TO_MULTILABEL,atol=1e-5))
        self.assertTrue(np.allclose(out["speech_probability"],[0,1,1,1,1,1,1],atol=1e-5))
        self.assertTrue(np.allclose(out["overlap_probability"],[0,0,0,0,1,1,1],atol=1e-5))
        rng = np.random.default_rng(512)
        for n in [1,44,589]:
            views={"speech":rng.integers(0,2,n,dtype=np.int8),"overlap":rng.integers(0,2,n,dtype=np.int8)}
            actual=segmentation_gate(views,PipelineConfig(),False)
            self.assertEqual(actual["speech"],bool(np.mean(views["speech"][-44:])>=.20))
            self.assertEqual(actual["overlap"],bool(np.mean(views["overlap"][-44:])>=.20))

    def test_posterior_hysteresis_and_assistance_change_actual_gate(self):
        c=replace(PipelineConfig(),segmentation_post_policy="posterior_hysteresis")
        views={"speech":np.zeros(589),"overlap":np.zeros(589),"speech_probability":np.full(589,.455),"overlap_probability":np.zeros(589)}
        self.assertFalse(segmentation_gate(views,c,False)["speech"])
        self.assertTrue(segmentation_gate(views,c,True)["speech"])
        self.assertTrue(segmentation_gate(views,c,False,speech_assist_delta=.05)["speech"])

    def test_cue_assistance_requires_explicit_supported_policy(self):
        with self.assertRaises(ValueError):
            ResearchProfile.from_dict({"xvf":{"mode":"soft_energy"}})

    def test_conditional_noop_knobs_rejected(self):
        for value in [{"asr":{"max_active_paths":2}}, {"segmentation":{"onset":.6}}, {"tracker":{"mode":"voice_time","identity_score_threshold":.6}}, {"tracker":{"commit_evidence_sec":3}}, {"tracker":{"mode":"voice_time","revision_horizon_sec":0}}, {"tracker":{"mode":"voice_time"},"xvf":{"mode":"tracking_only"}}]:
            with self.assertRaises(ValueError):
                ResearchProfile.from_dict(value)

    def test_deterministic_roundtrip_digest(self):
        p=ResearchProfile.from_dict({"profile_id":"a","embedding":{"window_sec":1}})
        self.assertEqual(p.digest(),ResearchProfile.from_dict(json.loads(json.dumps(p.to_dict()))).digest())

    def test_advice_requires_persistence_silence_and_fresh_nonreordered_delivery(self):
        p=ResearchProfile.from_dict({"xvf":{"mode":"advisory"}})
        advisor=EndpointAdvisor(p)
        decisions=[]
        for i in range(31):
            t=i*.1
            angle=20.0 if i<10 else 90.0
            o=DeliveredSpatialObservation(angle,t,1.,1.,True,i,t,t)
            decisions.append(advisor.observe(o,t,.01 if i<20 else 0.0,.1,0))
        self.assertEqual(sum(decisions),1)
        self.assertFalse(any(decisions[:22]))
        for defect in ("stale_source","decreasing_sequence","missing"):
            a=EndpointAdvisor(p)
            results=[]
            for i in range(31):
                t=i*.1
                o=DeliveredSpatialObservation(20.0 if i<10 else 90.0,t,1.,1.,True,i,t,t)
                if i>=10:
                    if defect=="stale_source": o=replace(o,source_start_sec=0.,source_end_sec=0.)
                    elif defect=="decreasing_sequence": o=replace(o,sequence=0)
                    else: o=None
                results.append(a.observe(o,t,0.,.1,0))
            self.assertFalse(any(results),defect)

    def test_old_observation_cannot_be_refreshed_by_new_delivery(self):
        p=ResearchProfile()
        self.assertFalse(spatial_is_fresh(DeliveredSpatialObservation(90,10,1,1,True,3,0,1),10,p))
        self.assertTrue(spatial_is_fresh(DeliveredSpatialObservation(90,10,1,1,True,3,9.95,9.98),10,p))

    def test_overlap_uses_causal_segmentation_even_when_embeddings_are_blocked(self):
        from .runtime import PipelineEngine
        from .contracts import SpeakerDecision
        engine=PipelineEngine(research_profile=ResearchProfile.from_dict({"tracker":{"mode":"voice_time"}}))
        decision=SpeakerDecision("Speaker_1","Speaker_1","anonymous",None,None,None,1.0,1)
        engine._research_speaker_history.append((1.,decision,False,1.01))
        engine._research_segmentation_history.extend([(.75,False,.8),(1.5,True,1.6),(3.,False,3.1)])
        engine._research_asr_available_sec=2.1
        engine._transcript_event("hello",2.,final=False,utterance=0,decode_ms=1)
        event=engine.events.get()
        self.assertTrue(event.payload["overlap_detected"])
        self.assertEqual(event.payload["speaker_state"],"overlap_uncertain")
        engine._research_asr_available_sec=1.55
        engine._transcript_event("hello",2.,final=False,utterance=0,decode_ms=1)
        self.assertFalse(engine.events.get().payload["overlap_detected"])

    def test_baseline_overlap_display_remains_original_global_flag(self):
        from .runtime import PipelineEngine
        engine=PipelineEngine()
        engine._overlap_active=True
        engine._transcript_event("hello",2.,final=False,utterance=0,decode_ms=1)
        self.assertTrue(engine.events.get().payload["overlap_detected"])


def model_probe() -> dict:
    import importlib.metadata
    import sherpa_onnx
    import psutil
    p=psutil.Process()
    start=time.perf_counter()
    config=PipelineConfig()
    models=SpeakerModels(config)
    graph={}
    for name, session in [("pyannote",models._segmentation),("redim",models._redim)]:
        graph[name]={"input":[{"name":v.name,"shape":v.shape,"type":v.type} for v in session.get_inputs()],
                     "output":[{"name":v.name,"shape":v.shape,"type":v.type} for v in session.get_outputs()],
                     "metadata":session.get_modelmeta().custom_metadata_map,"providers":session.get_providers()}
    rng=np.random.default_rng(20260909)
    wave=rng.normal(0,.015,160000).astype(np.float32)
    raw=models._segmentation.run(None,{"waveform":wave[None,None,:]})[0]
    graph["pyannote"]["actual_output_shape"]=list(raw.shape)
    graph["pyannote"]["raw_min_max"]=[float(raw.min()),float(raw.max())]
    graph["pyannote"]["max_exp_sum_error"]=float(np.max(np.abs(np.exp(raw).sum(axis=-1)-1)))
    assert raw.shape == (1,589,7)
    assert graph["pyannote"]["max_exp_sum_error"] < 1e-4
    views=models.segment(wave,include_posteriors=True)
    graph["pyannote"]["returned_fields_shapes"]={k:list(v.shape) for k,v in views.items()}
    longer=[]
    for seconds in [.5,.75,1.,1.5,2.,3.]:
        vector=models.embed(wave[:round(seconds*16000)])
        assert vector.shape==(192,) and abs(float(np.linalg.norm(vector))-1)<1e-5
        longer.append({"duration_sec":seconds,"samples":round(seconds*16000),"compute_ms":models.last_embed_ms,"norm":float(np.linalg.norm(vector)),"vector_sha256":hashlib.sha256(vector.tobytes()).hexdigest()})
    graph["redim"]["actual_length_tests"]=longer
    for name, method, waveform in [("segmentation",models.segment,wave[:80000]),("redim",models.embed,wave[:7999])]:
        try: method(waveform)
        except ValueError as exc: graph[name if name=="redim" else "pyannote"]["invalid_short_input_rejected"]=str(exc)
        else: raise AssertionError("short shape unexpectedly accepted")
    encoder=_ort_session(str(config.asset("sherpa_giga_encoder_int8").path),1)
    graph["sherpa_encoder"]={"input":[{"name":v.name,"shape":v.shape,"type":v.type} for v in encoder.get_inputs()],"metadata":encoder.get_modelmeta().custom_metadata_map}
    return {"status":"PASS","graph":graph,"versions":{k:importlib.metadata.version(k) for k in ["numpy","onnxruntime","sherpa-onnx"]},
            "sherpa_signature":str(inspect.signature(sherpa_onnx.OnlineRecognizer.from_transducer)),
            "sherpa_source_path":inspect.getsourcefile(sherpa_onnx.OnlineRecognizer),
            "elapsed_sec":time.perf_counter()-start,"resident_point_memory":p.memory_full_info()._asdict(),
            "scope":"bounded graph/length/normalization checks only; not recognition or target-device qualification"}


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--models",action="store_true")
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ProfileTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    receipt={"schema_version":"edge-profile-checks.v1","created_utc":datetime.now(timezone.utc).isoformat(),"python":sys.executable,"tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"status":"PASS" if result.wasSuccessful() else "FAIL"}
    if result.wasSuccessful() and args.models: receipt["models"]=model_probe()
    receipt["code_sha256"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    temporary=args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt,indent=2,allow_nan=False),encoding="utf-8")
    temporary.replace(args.output)
    print(json.dumps({"output":str(args.output),"status":receipt["status"],"tests":result.testsRun}))
    return 0 if result.wasSuccessful() else 1


if __name__=="__main__":
    raise SystemExit(main())
