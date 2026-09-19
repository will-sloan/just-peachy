"""Model-free actual-entrypoint checks; see README_RESEARCH_S6C.md."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
import soundfile as sf

from .config import PipelineConfig
from .research_profiles import ResearchProfile
from .research_profiles_v3 import IdentitySettingsV3
from .research_identity_v3 import ResearchGallery, ResearchIdentityResolver
from .research_scheduler_v3 import build_s6c_policy
from .research_evidence_v3 import EvidenceAdmissionV3
from .research_audio_v3 import PairedJournal, PairedWavSource
from .audio import AudioJournal


def unit(index=0):
    v = np.zeros(192, np.float32)
    v[index] = 1.
    return v


def profile(**sections):
    return ResearchProfile.from_dict({"schema_version": "edge-research-profile.v3", "profile_id": "fixture", **sections})


def event(index, start, end, vector=None, role="mature"):
    return {"kind": "embedding", "event_id": f"e{index}", "observation_id": f"e{index}",
        "vector": (unit() if vector is None else vector).tolist(), "source_start_sec": start,
        "source_end_sec": end, "available_at_sec": end+.01, "speech": True, "overlap": False,
        "evidence_kind": role, "clean_intervals": [[start, end]]}


def decision(track=1):
    return {"anonymous_label": f"Speaker_{track}", "display_label": f"Speaker_{track}",
        "tracker_id": track, "cluster_id": track, "state": "committed", "committed": True}


def create_gallery(root, indexes=(0, 1)):
    root.mkdir()
    config = PipelineConfig()
    backend = config.asset("redimnet2_b2_fp32").sha256
    rows = []
    def binding(p):
        return {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    for index in indexes:
        stem, name = f"fixture_{index}", f"ResearchPerson_{index:03d}"
        v = root/(stem+".npy")
        m = root/(stem+".json")
        np.save(v, unit(index), allow_pickle=False)
        m.write_text(json.dumps({"profile_id": stem, "display_name": name, "backend_id": "redimnet2_b2_fp32",
            "backend_sha256": backend, "schema_version": "edge-speaker-profile.v1"}), encoding="utf-8")
        rows.append({"profile_id": stem, "display_name": name, "metadata": binding(m), "vector": binding(v)})
    path = root.parent/(root.name+"_gallery.json")
    path.write_text(json.dumps({"schema_version": "edge-research-gallery.v1", "gallery_id": "constructed_fixture",
        "profile_root": str(root), "backend_sha256": backend, "profiles": rows}), encoding="utf-8")
    return path, ResearchGallery(path, backend)


class ComponentChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="s6c_model_free_")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_profile_roundtrip_and_defaults(self):
        p = profile()
        self.assertEqual(p.digest(), ResearchProfile.from_dict(p.to_dict()).digest())
        self.assertEqual(p.segmentation.hop_sec, .5)
        self.assertEqual(p.embedding.window_sec, 1.5)
        self.assertEqual(p.apply().input_gain, 1.)

    def test_profile_unknown_double_gain_and_noop_reject(self):
        for values in ({"input": {"gain": 2.}}, {"truth": "person"},
            {"identity": {"score_threshold": .6}}, {"embedding": {"cadence_policy": "fixed", "uncertainty_cosine": .4}}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                profile(**values)

    def test_historical_single_role_recipe_is_explicit(self):
        p = profile(embedding={"evidence_policy": "mature_only", "window_sec": .5, "mature_hop_sec": .25,
            "rms_policy": "dispatch", "purity_policy": "gate_only"}, segmentation={"post_policy": "hard_argmax_fraction", "hop_sec": .75})
        self.assertEqual(p.embedding.window_sec, .5)

    def test_gallery_actual_store_load_and_hash_guard(self):
        path, g = create_gallery(self.root/"g")
        self.assertEqual(g.receipt["loaded_count"], 2)
        self.assertEqual(g.score(unit())[0]["name"], "ResearchPerson_000")
        vector = self.root/"g"/"fixture_0.npy"
        vector.write_bytes(vector.read_bytes()+b"changed")
        with self.assertRaises(ValueError):
            ResearchGallery(path, PipelineConfig().asset("redimnet2_b2_fp32").sha256)

    def test_empty_control_cannot_load_gallery(self):
        _, g = create_gallery(self.root/"g")
        with self.assertRaises(ValueError):
            ResearchIdentityResolver(IdentitySettingsV3(), g)
        with self.assertRaises(ValueError):
            ResearchIdentityResolver(IdentitySettingsV3(mode="post_association"))

    def test_explicit_unavailable_gallery_uses_actual_empty_store(self):
        from unittest.mock import patch
        from .speakers import ProfileStore
        original=ProfileStore.load
        calls=[]
        def observed(store):
            calls.append(store)
            return original(store)
        with patch.object(ProfileStore,'load',observed):
            _,g=create_gallery(self.root/'empty',indexes=())
        self.assertEqual(len(calls),1)
        self.assertEqual(g.matrix.shape,(0,192))
        self.assertEqual(g.receipt['loaded_count'],0)
        self.assertEqual(g.receipt['template_availability'],'NO_AVAILABLE_TEMPLATES')
        self.assertEqual(g.score(unit()),[])
        r=ResearchIdentityResolver(IdentitySettingsV3(mode='post_association'),g)
        for role in ('short','mature'):
            row=r.resolve(decision(),event(1,0.,.5,role=role))
            self.assertIsNone(row['known_name'])
            self.assertEqual(row['naming_state'],'unknown')
            self.assertEqual(row['identity']['reason'],'NO_AVAILABLE_TEMPLATES')
            self.assertEqual(row['anonymous_label'],'Speaker_1')
        self.assertEqual(r.query_calls,0)
        self.assertEqual(r.comparisons,0)
        self.assertEqual(r.states,{})

    def test_resident_gallery_respects_lower_profile_bound(self):
        from .runtime import PipelineEngine
        _, gallery = create_gallery(self.root/"g")
        p = profile(identity={"mode":"post_association","max_gallery_profiles":1})
        with self.assertRaises(ValueError):
            PipelineEngine(research_profile=p,research_gallery=gallery)

    def test_retired_name_state_frees_capacity_requires_reidentification(self):
        _, gallery = create_gallery(self.root/"g")
        r = ResearchIdentityResolver(IdentitySettingsV3(mode="post_association",max_track_states=1,
            minimum_unique_sec=.5,minimum_disjoint_count=1),gallery)
        r.resolve(decision(1),event(1,0.,.5))
        r.sync_tracks({2},1.)
        self.assertNotIn(1,r.states)
        result=r.resolve(decision(2),event(2,.5,1.,unit(1)))
        self.assertEqual(result['known_name'],'ResearchPerson_001')
        self.assertEqual(r.snapshot()['retired_name_states'],1)

    def test_correct_absent_distractor_and_conflicting_voice(self):
        _, g = create_gallery(self.root/"g")
        resolver = ResearchIdentityResolver(IdentitySettingsV3(mode="post_association", minimum_unique_sec=.5,
            minimum_disjoint_count=1), g)
        correct = resolver.resolve(decision(), event(1, 0., .5))
        self.assertEqual(correct["known_name"], "ResearchPerson_000")
        self.assertEqual(correct["naming_state"], "confirmed")
        absent = resolver.resolve(decision(2), event(2, .5, 1., unit(2)))
        self.assertIsNone(absent["known_name"])
        conflict = resolver.resolve(decision(), event(3, 1., 1.5, unit(1)))
        self.assertIsNone(conflict["known_name"])
        self.assertEqual(conflict["anonymous_label"], "Speaker_1")

    def test_unique_disjoint_not_repeated_overlap(self):
        _, g = create_gallery(self.root/"g")
        r = ResearchIdentityResolver(IdentitySettingsV3(mode="post_association"), g)
        for index in range(1, 5):
            result = r.resolve(decision(), event(index, .1*index, .1*index+1.))
        self.assertAlmostEqual(result["identity"]["unique_clean_sec"], 1.3)
        self.assertEqual(result["identity"]["disjoint_count"], 1)
        self.assertEqual(result["naming_state"], "tentative")

    def test_short_keeps_bounded_prior_name_without_query(self):
        _, g = create_gallery(self.root/"g")
        r = ResearchIdentityResolver(IdentitySettingsV3(mode="post_association", minimum_unique_sec=.5,
            minimum_disjoint_count=1), g)
        r.resolve(decision(), event(1, 0., .5))
        short = r.resolve(decision(), event(2, .25, .75, role="short"))
        self.assertEqual(short["known_name"], "ResearchPerson_000")
        self.assertFalse(short["identity"]["query_executed"])
        self.assertEqual(r.query_calls, 1)

    def test_hidden_tentative_candidate_is_not_exported_as_known_name(self):
        _,g=create_gallery(self.root/'g')
        r=ResearchIdentityResolver(IdentitySettingsV3(mode='post_association',display_tentative=False),g)
        result=r.resolve(decision(),event(1,0.,.5))
        self.assertEqual(result['identity']['candidate_name'],'ResearchPerson_000')
        self.assertIsNone(result['known_name'])
        self.assertEqual(result['display_label'],'Speaker_1')

    def test_pair_commit_fault_never_publishes_one_lane(self):
        a, b = AudioJournal(self.root/"a.pcm"), AudioJournal(self.root/"b.pcm")
        pair = PairedJournal(a, b)
        def fail(_):
            raise OSError("injected second journal failure")
        b.append = fail
        with self.assertRaises(OSError):
            pair.append(np.ones(100, np.float32)*.1, np.ones(100, np.float32)*.2)
        self.assertEqual(pair.committed_samples, 0)
        self.assertTrue(pair.finished)
        self.assertEqual(pair.view(0).read(0, 100).size, 0)

    def test_pair_exact_tail_and_mismatched_lengths(self):
        a = np.arange(1707, dtype=np.float32)/10000
        b = -a
        for name, data in (("a.wav", a), ("b.wav", b)):
            sf.write(self.root/name, data, 16000, subtype="FLOAT")
        pair = PairedJournal(AudioJournal(self.root/"a.pcm"), AudioJournal(self.root/"b.pcm"))
        src = PairedWavSource(pair, self.root/"a.wav", self.root/"b.wav", realtime=False, accelerated_factor=0)
        src.start(); src.thread.join(5)
        self.assertEqual(pair.committed_samples, 1707)
        self.assertTrue(pair.finished)
        self.assertEqual((self.root/"a.pcm").stat().st_size, 3414)
        np.testing.assert_array_equal(pair.view(1).read(0, 2000), np.round(np.clip(b, -1., .999969)*32768).astype('<i2').astype(np.float32)/32768)
        sf.write(self.root/"short.wav", b[:100], 16000)
        with self.assertRaises(ValueError):
            PairedWavSource(pair, self.root/"a.wav", self.root/"short.wav")

    def test_dual_roles_and_clipping_admission(self):
        p = profile(embedding={"purity_policy": "gate_only", "clipping_fraction_max": .01})
        a = EvidenceAdmissionV3(p)
        rows = a.candidates(np.ones(32000, np.float32)*.1, np.ones(4000, np.float32)*.1, 2., True, False)
        self.assertEqual([r["samples"] for r in rows], [8000, 24000])
        self.assertTrue(all(r["admitted"] for r in rows))
        rows = a.candidates(np.ones(32000, np.float32), np.ones(4000, np.float32), 2., True, False)
        self.assertTrue(all(r["reason"] == "clipped_window" for r in rows))

    def test_track_debt_affects_opportunity_not_evidence(self):
        p = profile(embedding={"purity_policy": "gate_only", "cadence_policy": "uncertainty"})
        a = EvidenceAdmissionV3(p)
        context = [{"track_id": 7, "state": "provisional", "unique_clean_sec": .5, "disjoint_count": 1}]
        rows = a.candidates(np.ones(32000, np.float32)*.1, np.ones(4000, np.float32)*.1, 2., True, False, tracking_context=context)
        self.assertEqual(rows[0]["track_debts"][0]["unique_sec_deficit"], 1.5)
        a.admitted("short", unit(), 2., rows[0])
        self.assertEqual(context[0]["unique_clean_sec"], .5)
        self.assertFalse(rows[0]["naming_used_for_schedule"])

    def test_scheduler_forbids_truth_and_future_support(self):
        s = build_s6c_policy(profile())
        bad = event(1, 0., .5); bad["reference_person"] = "x"
        with self.assertRaises(ValueError):
            s.push(bad, "speaker")
        bad = event(2, 0., .5); bad["clean_intervals"] = [[0., .75]]
        with self.assertRaises(ValueError):
            s.push(bad, "speaker")

    def test_incremental_prefix_and_source_safe_scheduling(self):
        p = profile(tracker={"mode": "old_voice_gate", "lifecycle_policy": "none"})
        left, right = build_s6c_policy(p), build_s6c_policy(p)
        def feed(s, e):
            s.push(e, "speaker"); s.advance({"speaker": e["available_at_sec"]+.001, "asr": e["available_at_sec"]+.001})
        feed(left, event(1, 0., .5)); feed(right, event(1, 0., .5))
        before = deepcopy(left.snapshot()["utterances"])
        self.assertEqual(left.tracking_context(.5), [])
        self.assertEqual(left.tracking_context(.6), right.tracking_context(.6))
        feed(right, event(2, .5, 1., unit(1)))
        self.assertEqual(left.snapshot()["utterances"], before)
        self.assertEqual(left.tracking_context(.6), right.tracking_context(.6))

    def test_committed_anonymous_gets_forward_name_and_retraction(self):
        _, gallery = create_gallery(self.root/"g")
        p = profile(tracker={"mode":"old_voice_gate","lifecycle_policy":"none"},
            identity={"mode":"post_association","minimum_unique_sec":.5,"minimum_disjoint_count":1})
        output=[]
        scheduler=build_s6c_policy(p,gallery,emit=output.append)
        def feed(row,lane):
            scheduler.push(row,lane)
            scheduler.advance({"speaker":row['available_at_sec']+.001,"asr":row['available_at_sec']+.001})
        feed(event(1,0.,.5,role="short"),"speaker")
        feed(event(2,.5,1.,role="short"),"speaker")
        feed({"kind":"asr","event_id":"a1","utterance_id":"u1","text":"hello",
            "final":True,"source_start_sec":0.,"source_end_sec":1.2,"available_at_sec":1.21},"asr")
        original=deepcopy(scheduler.snapshot()['utterances'][0])
        feed(event(3,.5,1.5),"speaker")
        named=scheduler.snapshot()['utterances'][0]
        self.assertEqual(named['latest_known_name'],'ResearchPerson_000')
        self.assertEqual(named['first_final_label'],original['first_final_label'])
        self.assertEqual(named['text'],'hello')
        conflicting=.4*unit()+np.float32(math.sqrt(1-.4**2))*unit(1)
        feed(event(4,1.,2.,conflicting),"speaker")
        revised=scheduler.snapshot()['utterances'][0]
        self.assertIsNone(revised['latest_known_name'])
        self.assertEqual(revised['first_known_name'],'ResearchPerson_000')
        revisions=[r for r in output if r['event_type']=='transcript_label_revision']
        self.assertGreaterEqual(len(revisions),2)
        self.assertTrue(all(not r['changes_words'] for r in revisions))

    def test_pending_final_name_revision_is_decorated_before_sink(self):
        _,gallery=create_gallery(self.root/'g')
        p=profile(tracker={"mode":"old_voice_gate","lifecycle_policy":"none","commit_disjoint_count":1,"commit_evidence_sec":.5},
            identity={"mode":"post_association","minimum_unique_sec":.5,"minimum_disjoint_count":1})
        emitted=[]
        s=build_s6c_policy(p,gallery,emit=emitted.append)
        s.push({"kind":"asr","event_id":"a","utterance_id":"u","text":"hello","final":True,
            "source_start_sec":0.,"source_end_sec":.5,"available_at_sec":.51},'asr')
        s.advance({'speaker':.52,'asr':.52})
        s.push(event(1,0.,1.5),'speaker')
        s.advance({'speaker':1.52,'asr':1.52})
        row=s.snapshot()['utterances'][0]
        self.assertEqual(row['latest_known_name'],'ResearchPerson_000')
        self.assertEqual(row['first_known_name'],'ResearchPerson_000')
        revision=[r for r in emitted if r['event_type']=='transcript_label_revision'][-1]
        self.assertEqual(revision['latest_known_name'],row['latest_known_name'])
        self.assertEqual(revision['latest_known_profile_id'],row['latest_known_profile_id'])

    def test_structural_unknown_revision_clears_name_metadata(self):
        from .research_scheduler_v3 import CausalSchedulerV3
        from types import SimpleNamespace
        _,gallery=create_gallery(self.root/'g')
        class Tracker:
            config=SimpleNamespace(mode='fixture')
            def __init__(self):self.n=0
            def update(self,*args,**kwargs):
                self.n+=1
                if self.n==1:return {**decision(),'decision_id':'d1','evidence_id':'e1'}
                return {'anonymous_label':'Unknown','display_label':'Unknown','tracker_id':None,'state':'unknown',
                    'decision_id':'d2','evidence_id':'e2','lineage':[{'event':'label_revision','revision_of':'d1',
                    'replacement_anonymous_label':'Unknown','replacement_track_id':None,'replacement_state':'unknown'}]}
            def scheduling_state(self,now):return [{'track_id':1,'snapshot_available_at_sec':now}] if self.n==1 else []
        r=ResearchIdentityResolver(IdentitySettingsV3(mode='post_association',minimum_unique_sec=.5,minimum_disjoint_count=1),gallery)
        output=[]; s=CausalSchedulerV3(Tracker(),r,emit=output.append)
        s.push(event(1,0.,.5),'speaker');s.advance({'speaker':.52,'asr':.52})
        s.push({'kind':'asr','event_id':'a','utterance_id':'u','text':'hello','final':True,
            'source_start_sec':0.,'source_end_sec':.6,'available_at_sec':.61},'asr')
        s.advance({'speaker':.62,'asr':.62})
        s.push(event(2,.5,1.,unit(1)),'speaker');s.advance({'speaker':1.02,'asr':1.02})
        row=s.snapshot()['utterances'][0]
        self.assertEqual(row['latest_label'],'Unknown')
        self.assertIsNone(row['latest_known_name'])
        revision=[x for x in output if x['event_type']=='transcript_label_revision'][-1]
        self.assertIsNone(revision['latest_known_profile_id'])
        self.assertEqual(row['first_known_name'],'ResearchPerson_000')

    def test_ongoing_name_change_and_unknown_match_following_display(self):
        _,g=create_gallery(self.root/'g')
        p=profile(tracker={'mode':'old_voice_gate','lifecycle_policy':'none'},
            identity={'mode':'post_association','minimum_unique_sec':.5,'minimum_disjoint_count':1})
        for target in ('different','expired'):
            with self.subTest(target=target):
                output=[];s=build_s6c_policy(p,g,emit=output.append)
                def deliver(row,lane):
                    s.push(row,lane);s.advance({'speaker':row['available_at_sec']+.001,'asr':row['available_at_sec']+.001})
                deliver(event(1,0.,.5),'speaker')
                deliver({'kind':'asr','event_id':'a1','utterance_id':'u','text':'hello','final':False,
                    'source_start_sec':0.,'source_end_sec':.6,'available_at_sec':.61},'asr')
                if target=='different':
                    deliver(event(2,.5,1.,unit(1)),'speaker');end=1.1
                else:end=2.
                deliver({'kind':'asr','event_id':'a2','utterance_id':'u','text':'hello there','final':False,
                    'source_start_sec':0.,'source_end_sec':end,'available_at_sec':end+.01},'asr')
                revision=[x for x in output if x['event_type']=='transcript_label_revision' and x.get('revision_scope')=='ongoing_utterance_display'][-1]
                display=[x for x in output if x['event_type']=='transcript_partial'][-1]
                self.assertEqual(revision['latest_known_name'],display['latest_known_name'])
                self.assertEqual(revision['latest_known_profile_id'],display['latest_known_profile_id'])
                self.assertEqual(display['latest_known_name'],'ResearchPerson_001' if target=='different' else None)

    def test_actual_enrollment_entrypoint_window_frontend(self):
        from .enrollment import enroll_wavs
        class Models:
            def __init__(self): self.lengths = []
            def embed(self, wave): self.lengths.append(len(wave)); return unit()
        model = Models()
        path = self.root/"enroll.wav"
        sf.write(path, np.full(40000, .1, np.float32), 16000, subtype="FLOAT")
        config = replace(PipelineConfig(), profile_root=self.root/"profiles")
        meta = enroll_wavs("ResearchPerson_fixture", [path], models=model, config=config)
        self.assertEqual(model.lengths, [32000, 24000, 8000])
        self.assertEqual(meta["embedding_count"], 3)
        self.assertTrue(Path(meta["vector_path"]).exists())

    def test_full_native_file_entrypoint_with_injected_models(self):
        from .runtime import PipelineEngine
        class Models:
            last_segment_ms = last_embed_ms = 0.
            def __init__(self): self.lengths=[]; self.means=[]
            def segment(self, wave, **kwargs):
                return {"speech":np.ones(589,np.int8),"overlap":np.zeros(589,np.int8),
                    "speech_probability":np.ones(589,np.float32),"overlap_probability":np.zeros(589,np.float32)}
            def embed(self, wave): self.lengths.append(len(wave)); self.means.append(float(np.mean(wave))); return unit()
        class ASR:
            utterance_index=0; decode_ms=0.
            def __init__(self): self.received=[]
            def accept(self, a): self.received.extend(a.tolist()); return "hello there",False
            def finish(self): return "hello there"
            def punctuate(self, text): return {"text":"Hello there.","compute_ms":0.,"status":"OK", "terminal_fallback":None}
        class Bundle:
            sessions_created=1; admission_elapsed_sec=0.
            def __init__(self): self.models=Models(); self.asr=ASR(); self.released=False
            def acquire(self, config): return self.models,self.asr
            def release(self): self.released=True
        samples=64107
        for name, level in (("asr.wav", .1),("identity.wav",.2)):
            sf.write(self.root/name, np.full(samples,level,np.float32),16000,subtype="FLOAT")
        _, gallery=create_gallery(self.root/"gallery")
        p=profile(input={"asr_tap":"O0","identity_tap":"O1"}, asr={"journal_read_ms":50},
            embedding={"purity_policy":"gate_only"}, identity={"mode":"post_association","minimum_unique_sec":.5,"minimum_disjoint_count":1},
            tracker={"mode":"old_voice_gate","lifecycle_policy":"none"})
        bundle=Bundle()
        engine=PipelineEngine(replace(PipelineConfig(),session_root=self.root/"sessions",profile_root=self.root/"unused"),
            research_profile=p,research_gallery=gallery,model_bundle=bundle)
        session=engine.start_paired_files(self.root/"asr.wav",self.root/"identity.wav",realtime=False,accelerated_factor=0)
        engine.wait_for_completion(15)
        self.assertEqual(engine.state,"COMPLETED")
        self.assertTrue(bundle.released)
        self.assertEqual(len(bundle.asr.received),samples)
        self.assertTrue(all(abs(x-.2)<1e-4 for x in bundle.models.means))
        self.assertEqual(set(bundle.models.lengths),{8000,24000})
        self.assertEqual((session/"audio_spool.pcm16").stat().st_size,samples*2)
        self.assertEqual((session/"identity_audio_spool.pcm16").stat().st_size,samples*2)
        events=[json.loads(x) for x in (session/"events.jsonl").read_text().splitlines()]
        self.assertTrue(any(x["event_type"]=="identity_decision" for x in events))
        self.assertTrue(any(x["event_type"]=="research_asr_tail_dispatch" and x["payload"]["samples"]==107 for x in events))
        self.assertTrue((session/"latest_labelled_transcript.jsonl").exists())
        self.assertEqual(engine.telemetry()["asr_cursor_sec"],samples/16000)
        closure=json.loads((session/'session_finalization_v3.json').read_text())
        self.assertEqual(closure['live_lanes_at_finalization'],[])
        self.assertFalse(closure['resident_bundle_lease_retained'])
        self.assertTrue(closure['resident_bundle_reuse_allowed'])
        self.assertTrue(closure['event_and_transcript_handles_closed'])

    def test_writer_close_failure_is_durably_not_reported_closed(self):
        from .runtime import PipelineEngine
        class BadClose:
            closed=False
            def __init__(self,wrapped):self.wrapped=wrapped
            def __getattr__(self,name):return getattr(self.wrapped,name)
            def close(self):raise OSError('injected writer close failure')
        engine=PipelineEngine(replace(PipelineConfig(),session_root=self.root/'sessions'),research_profile=profile())
        engine._begin_session('fixture')
        engine._journal.finish()
        actual=engine._transcript_handle
        engine._transcript_handle=BadClose(actual)
        try:
            engine._watch_session()
            self.assertEqual(engine.state,'FAILED')
            with self.assertRaises(RuntimeError):engine.wait_for_completion(1.)
            closure=json.loads((engine.session_dir/'session_finalization_v3.json').read_text())
            self.assertFalse(closure['event_and_transcript_handles_closed'])
            self.assertFalse(closure['handle_close_results']['_transcript_handle']['closed'])
            self.assertIn('injected writer close failure',closure['finalization_error'])
        finally:actual.close()

    def test_slow_failed_native_lane_does_not_release_resident_bundle(self):
        import threading
        from .runtime import PipelineEngine
        class Bundle:
            released=False
            def acquire(self,_):return None,None
            def release(self):self.released=True
        source=self.root/'tiny.wav'
        sf.write(source,np.ones(160,np.float32)*.1,16000,subtype='FLOAT')
        p=profile(runtime={'lane_drain_timeout_sec':.01})
        bundle=Bundle();release=threading.Event()
        engine=PipelineEngine(replace(PipelineConfig(),session_root=self.root/'sessions'),research_profile=p,model_bundle=bundle)
        engine._asr_loop=lambda _: engine._scheduler_advance('asr',float('inf'),0.)
        engine._speaker_loop=lambda _: release.wait(3.)
        try:
            engine.start_paired_files(source,source,realtime=False,accelerated_factor=0)
            with self.assertRaises(RuntimeError):engine.wait_for_completion(2.)
            self.assertEqual(engine.state,'FAILED')
            self.assertFalse(bundle.released)
            self.assertTrue(engine.telemetry()['bundle_retained_due_live_lanes'])
            closure=json.loads((engine.session_dir/'session_finalization_v3.json').read_text())
            self.assertEqual(closure['state'],'FAILED')
            self.assertTrue(closure['resident_bundle_lease_retained'])
            self.assertFalse(closure['resident_bundle_reuse_allowed'])
        finally:
            release.set()
            for thread in engine._threads:thread.join(2.)
            self.assertTrue(all(not t.is_alive() for t in engine._threads))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--receipt",type=Path,required=True)
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ComponentChecks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    bound=list(Path(__file__).parent.glob('*v3.py'))+[Path(__file__).with_name(name) for name in
        ('runtime.py','cli.py','research_profiles.py','research_scheduler.py','models.py','audio.py','speakers.py','enrollment.py','README_RESEARCH_S6C.md')]
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in bound}
    sources[Path(__file__).name]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    receipt={"schema":"s6c_component_model_free_checks.v1","status":"PASS" if result.wasSuccessful() else "FAIL",
        "tests_run":result.testsRun,"failures":[{"test":str(t),"traceback":s} for t,s in result.failures+result.errors],
        "source_sha256":sources,"neural_model_invocations":0,"hardware_invocations":0,
        "scope":"Constructed vectors/synthetic WAVs and deterministic injected models; actual ProfileStore/enrollment frontend, scheduler, paired producer and PipelineEngine/export paths. No empirical neural accuracy or timing claim."}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    with args.receipt.open('x',encoding='utf-8') as f:
        json.dump(receipt,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
