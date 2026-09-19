"""Focused actual-entrypoint S6B fixtures; no neural weights or hardware needed."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
import unittest

import numpy as np
import soundfile as sf

from .config import PipelineConfig
from .research_profiles import ResearchProfile, EndpointAdvisorV2, DeliveredSpatialObservation
from .research_scheduler import CausalScheduler, EmbeddingAdmission
from .research_tracking_v2 import S6BTracker, S6BTrackingConfig
from .runtime import PipelineEngine


def profile(**sections):
    return ResearchProfile.from_dict({"schema_version": "edge-research-profile.v2", "profile_id": "fixture", **sections})


def vector(index=0):
    result = np.zeros(192, dtype=np.float32)
    result[index] = 1
    return result.tolist()


def embedding(i, start, end, ready, v=None):
    return dict(kind="embedding", event_id=f"E{i}", source_start_sec=start, source_end_sec=end,
                available_at_sec=ready, vector=v or vector(), speech=True, overlap=False)


def asr(i, end, ready, final=False, utterance="U", start=0):
    return dict(kind="asr", event_id=f"A{i}", source_start_sec=start, source_end_sec=end,
                available_at_sec=ready, utterance_id=utterance, text="THE WORDS REMAIN", final=final)


def semantic(rows):
    rows = deepcopy(rows)
    for row in rows:
        row.pop("policy_compute_sec", None)
    return rows


class SchedulerChecks(unittest.TestCase):
    def test_actual_tracker_watermark_thread_order_and_prefix(self):
        prefix = [embedding(1,0,.5,.55), asr(1,.5,.6), embedding(2,.5,1,1.05), asr(2,1,1.1,True)]
        outcomes = []
        for order in (prefix, [prefix[1],prefix[3],prefix[0],prefix[2]]):
            scheduler = CausalScheduler(S6BTracker(S6BTrackingConfig()))
            rows = []
            for event in order:
                rows.extend(scheduler.push(event, "asr" if event["kind"] == "asr" else "speaker"))
            rows.extend(scheduler.advance({"asr":1.2,"speaker":1.2}))
            outcomes.append(semantic(rows))
            first = deepcopy(rows)
            scheduler.push(embedding(3,1,1.5,1.6,vector(1)), "speaker")
            scheduler.finish()
            self.assertEqual(first, rows)
        self.assertEqual(*outcomes)

    def test_future_hidden_until_both_lanes_sealed(self):
        s = CausalScheduler(S6BTracker(S6BTrackingConfig()))
        self.assertEqual(s.push(embedding(1,0,.5,.6), "speaker"), [])
        self.assertEqual(s.advance({"speaker":1.}), [])
        self.assertEqual(s.advance({"asr":.6}), [])
        self.assertEqual(len(s.advance({"asr":.61})),1)
        with self.assertRaises(ValueError): s.push(embedding(2,0,.5,.6),"speaker")

    def test_cueoff_provider_is_never_called(self):
        class FailProvider:
            def evidence(self,*args): raise AssertionError("cue-off called provider")
        outputs=[]
        for provider in (None, FailProvider()):
            s=CausalScheduler(S6BTracker(S6BTrackingConfig()),spatial_provider=provider,cues_enabled=False)
            s.push(embedding(1,0,.5,.6),"speaker")
            s.push(asr(1,.5,.7,True),"asr")
            outputs.append(semantic(s.finish()))
        self.assertEqual(*outputs)

    def test_stale_evidence_expires_without_losing_words(self):
        s=CausalScheduler(S6BTracker(S6BTrackingConfig()),evidence_expiry_sec=.75)
        s.push(embedding(1,0,.5,.6),"speaker")
        s.push(asr(1,2,2.1,True),"asr")
        rows=s.finish()
        final=next(x for x in rows if x['event_type']=='transcript_final')
        self.assertEqual(final['speaker'],'Speaker_?')
        self.assertEqual(final['text'],'THE WORDS REMAIN')

    def test_finalization_carry_is_scoped_to_same_supported_utterance(self):
        for new_partial in (False,True):
            s=CausalScheduler(S6BTracker(S6BTrackingConfig()))
            s.push(embedding(1,0,.5,.6),'speaker')
            s.push(asr(1,.5,.7),'asr')
            if new_partial:s.push(asr(2,1.9,2.),'asr')
            s.push(asr(3,2.,2.1,True),'asr')
            final=next(x for x in s.finish() if x['event_type']=='transcript_final')
            self.assertEqual(final['speaker'],'Speaker_?' if new_partial else 'Speaker_1')
            if not new_partial:self.assertEqual(final['attribution_reason'],'finalization retains prior utterance label')

    def test_actual_commit_and_nonoverlap_revision_guard(self):
        s=CausalScheduler(S6BTracker(S6BTrackingConfig(commit_disjoint_count=2)),revision_horizon_sec=2.)
        for event in (asr(1,.5,.51,True), embedding(1,0,.5,.55), embedding(2,.5,1,1.05)):
            s.push(event,"asr" if event['kind']=='asr' else 'speaker')
        rows=s.finish()
        first=next(x for x in rows if x['event_type']=='transcript_final')
        self.assertEqual(first['first_final_label'],'Speaker_?')
        self.assertTrue(any(x['event_type']=='speaker_decision' and x['decision']['committed'] for x in rows))
        # First overlapping evidence is provisional, the later disjoint evidence
        # does not overlap this tiny utterance. It must remain unknown, not claim
        # a future adjacent speaker as retroactive success.
        self.assertEqual(s.snapshot()['utterances'][0]['first_final_label'],'Speaker_?')

    def test_actual_tracker_commit_activates_overlapping_forward_revision(self):
        s=CausalScheduler(S6BTracker(S6BTrackingConfig(commit_disjoint_count=2)))
        for event in (asr(1,.8,.81,True), embedding(1,0,.5,.9), embedding(2,.5,1,1.05)):
            s.push(event,'asr' if event['kind']=='asr' else 'speaker')
        rows=s.finish()
        revision=next(x for x in rows if x['event_type']=='transcript_label_revision')
        self.assertEqual(revision['first_final_label'],'Speaker_?')
        self.assertEqual(revision['latest_label'],'Speaker_1')
        self.assertEqual(revision['revision_scope'],'bounded_forward_reconciliation')
        self.assertEqual(s.snapshot()['utterances'][0]['first_final_label'],'Speaker_?')

    def test_diagnostic_controls_label_even_without_embeddings(self):
        for mode,label in (('one_person','Speaker_1'),('all_unknown','Unknown')):
            s=CausalScheduler(S6BTracker(S6BTrackingConfig(mode=mode)))
            s.push(asr(1,1.,1.1,True),'asr')
            final=next(x for x in s.finish() if x['event_type']=='transcript_final')
            self.assertEqual(final['speaker'],label)
            self.assertEqual(final['diagnostic_control'],mode)

    def test_revision_preserves_first_final_and_stable_id(self):
        class Tracker:
            def update(self,*args,**kwargs):
                return {'display_label':'Speaker_1','anonymous_label':'Speaker_1','state':'committed','committed':True,
                        'decision_id':'D1','evidence_id':'E1','tracker_id':1,'lineage':[]}
        s=CausalScheduler(Tracker())
        s.push(asr(1,.8,.81,True), 'asr')
        s.push(embedding(1,.2,1,1.1),'speaker')
        rows=s.finish()
        final=next(x for x in rows if x['event_type']=='transcript_final')
        revision=next(x for x in rows if x['event_type']=='transcript_label_revision')
        self.assertEqual(final['first_final_label'],'Speaker_?')
        self.assertEqual(revision['utterance_id'],final['utterance_id'])
        self.assertEqual(revision['latest_label'],'Speaker_1')
        self.assertEqual(s.snapshot()['utterances'][0]['first_final_label'],'Speaker_?')

    def test_unknown_rollback_clears_latest_identity_but_preserves_first(self):
        class Tracker:
            count=0
            def update(self,*a,**k):
                self.count+=1
                return {'display_label':'Speaker_1' if self.count==1 else 'Speaker_2','state':'committed','committed':True,
                        'tracker_id':self.count,'decision_id':f'D{self.count}','evidence_id':f'E{self.count}',
                        'lineage':[] if self.count==1 else [{'event':'label_revision','revision_of':'D1','evidence_id':'E1',
                            'replacement_anonymous_label':'Unknown','replacement_track_id':None,'reason':'rollback'}]}
        s=CausalScheduler(Tracker())
        for event in (embedding(1,0,.5,.55),asr(1,.5,.6,True),embedding(2,.5,1,1.1)):
            s.push(event,'asr' if event['kind']=='asr' else 'speaker')
        s.finish();row=s.snapshot()['utterances'][0]
        self.assertEqual(row['first_final_label'],'Speaker_1')
        self.assertEqual(row['latest_label'],'Unknown');self.assertEqual(row['latest_state'],'unknown')
        self.assertIsNone(row['tracker_id']);self.assertIsNone(row['evidence_id']);self.assertIsNone(row['decision_id'])

    def test_budget_nonfinite_duplicate_and_schema_rejects(self):
        s=CausalScheduler(S6BTracker(S6BTrackingConfig()),max_pending_events=1)
        s.push(embedding(1,0,.5,.6),'speaker')
        with self.assertRaises(RuntimeError):s.push(embedding(2,.5,1,1.1),'speaker')
        for changed in ({'source_end_sec':float('nan')},{'available_at_sec':.1},{'vector':[float('nan')]}):
            bad=embedding(3,0,.5,.6);bad.update(changed)
            with self.assertRaises(ValueError):CausalScheduler(S6BTracker(S6BTrackingConfig())).push(bad,'speaker')
        for settings in ({'xvf':{'mode':'tracking_only'}},{'embedding':{'evidence_debt_enabled':True}},
                         {'embedding':{'evidence_policy':'early_short_long'}},{'asr':{'max_active_paths':2}}):
            with self.assertRaises(ValueError):profile(**settings)

    def test_actual_scheduler_rejects_reference_and_unknown_fields(self):
        for key in ('reference_text','speaker_id','scene_id','participant','ground_truth','arbitrary_ignored_key'):
            event=embedding(1,0,.5,.6);event[key]='forbidden'
            with self.assertRaises(ValueError):CausalScheduler(S6BTracker(S6BTrackingConfig())).push(event,'speaker')
        event=asr(1,.5,.6,True);event['punctuation']={'text':'x','reference_speaker':'forbidden'}
        with self.assertRaises(ValueError):CausalScheduler(S6BTracker(S6BTrackingConfig())).push(event,'asr')


class AdmissionChecks(unittest.TestCase):
    def test_full_window_vs_dispatch_rms_real_samples(self):
        block=np.ones(4000,dtype=np.float32)*.001
        rolling=np.concatenate((np.ones(4000,dtype=np.float32)*.1,block))
        results=[]
        for policy in ('dispatch','full_window'):
            a=EmbeddingAdmission(profile(embedding={'rms_policy':policy,'purity_policy':'gate_only'}))
            results.append(a.candidate(rolling,block,.5,True,False)[1])
        self.assertFalse(results[0]['admitted']);self.assertTrue(results[1]['admitted'])

    def test_contiguous_purity_rejects_fragmented_equal_total(self):
        a=EmbeddingAdmission(profile(embedding={'purity_policy':'contiguous','minimum_clean_fraction':.8,'minimum_contiguous_clean_sec':.4}))
        audio=np.ones(8000,dtype=np.float32)*.1
        a.clean_intervals=[[0,.2],[.25,.5]]
        self.assertEqual(a.candidate(audio,audio[-4000:],.5,True,False)[1]['reason'],'unclean_window')
        a.clean_intervals=[[0,.5]]
        self.assertTrue(a.candidate(audio,audio[-4000:],.5,True,False)[1]['admitted'])

    def test_short_long_and_debt_are_executable_bounded_admissions(self):
        p=profile(embedding={'window_sec':1.,'evidence_policy':'early_short_long','purity_policy':'gate_only',
             'cadence_policy':'event_driven','evidence_debt_enabled':True,'voice_observation_floor_sec':.75})
        a=EmbeddingAdmission(p);audio=np.ones(24000,dtype=np.float32)*.1;block=audio[:4000]
        size,d=a.candidate(audio[:8000],block,.5,True,False);self.assertEqual(size,8000)
        a.admitted(vector(),.5)
        size,d=a.candidate(audio[:16000],block,1.,True,False);self.assertEqual(d['reason'],'cadence_budget')
        size,d=a.candidate(audio[:20000],block,1.25,True,False);self.assertEqual(size,16000);self.assertTrue(d['evidence_debt_due'])
        size,d=a.candidate(audio,block,1.5,True,True);self.assertFalse(d['admitted'])

    def test_endpoint_breaker_rate_limit_and_real_fresh_guard(self):
        p=profile(xvf={'mode':'endpoint_only','endpoint_min_interval_sec':.5,'endpoint_max_per_minute':1})
        advisor=EndpointAdvisorV2(p)
        # Exercise the actual limiting wrapper with a deterministic proposal
        # source; stale/sequence guarding is independently the real base class.
        advisor.base.observe=lambda *a:True
        self.assertTrue(advisor.observe(None,1.,0.,.1,0.))
        self.assertFalse(advisor.observe(None,1.1,0.,.1,0.));self.assertEqual(advisor.last_status['reason'],'rate_limited')
        self.assertFalse(advisor.observe(None,2.,0.,.1,0.));self.assertEqual(advisor.last_status['reason'],'circuit_opened')
        real=EndpointAdvisorV2(p)
        old=DeliveredSpatialObservation(100.,10.,energy=1.,sequence=2,source_start_sec=0.,source_end_sec=.1)
        self.assertFalse(real.observe(old,10.,0.,.5,0.))


class FakeSpeakerModels:
    last_segment_ms=0.;last_embed_ms=0.
    def segment(self,audio,include_posteriors=False):
        assert len(audio)==160000
        return {'speech':np.ones(589,dtype=np.int8),'overlap':np.zeros(589,dtype=np.int8),
                'speech_probability':np.ones(589),'overlap_probability':np.zeros(589)}
    def embed(self,audio):
        assert len(audio)>=8000
        return np.asarray(vector(),dtype=np.float32)


class FakeASR:
    decode_ms=0.;utterance_index=0
    def __init__(self):self.samples=[];self.total=0
    def accept(self,samples):self.samples.append(np.asarray(samples).copy());self.total+=len(samples);return ('ALL SHORT WORDS',False)
    def finish(self):return 'ALL SHORT WORDS'
    def punctuate(self,text):return {'text':text+'.','compute_ms':0.}


class FakeBundle:
    def __init__(self):self.stream=FakeASR();self.released=False
    def acquire(self,config):return FakeSpeakerModels(),self.stream
    def release(self):self.released=True


class NativeEntrypointChecks(unittest.TestCase):
    def test_actual_file_engine_complete_tail_gain_unknown_and_durable_views(self):
        class NoCueCalls:
            def evidence(self,*a):raise AssertionError('cue off reached provider')
        with tempfile.TemporaryDirectory(prefix='s6b_native_fixture_') as temporary:
            root=Path(temporary);source=np.ones(1707,dtype=np.float32)*.125
            sf.write(root/'input.wav',source,16000,subtype='PCM_16')
            p=profile(input={'gain':2.},asr={'journal_read_ms':50},embedding={'purity_policy':'gate_only'})
            bundle=FakeBundle();engine=PipelineEngine(PipelineConfig(session_root=root/'sessions',profile_root=root/'gallery'),
                research_profile=p,spatial_provider=NoCueCalls(),model_bundle=bundle)
            directory=engine.start_file(root/'input.wav',realtime=False,accelerated_factor=100000.)
            deadline=time.monotonic()+15
            while engine.state not in {'COMPLETED','FAILED'} and time.monotonic()<deadline:time.sleep(.01)
            engine.wait_for_completion(15)
            self.assertEqual(engine.state,'COMPLETED');self.assertTrue(bundle.released)
            delivered=np.concatenate(bundle.stream.samples)
            self.assertEqual([len(x) for x in bundle.stream.samples],[800,800,107])
            self.assertEqual(len(delivered),1707);self.assertTrue(np.all(delivered==.25))
            first=[json.loads(x) for x in (directory/'labelled_transcript.jsonl').read_text().splitlines()]
            latest=[json.loads(x) for x in (directory/'latest_labelled_transcript.jsonl').read_text().splitlines()]
            self.assertEqual(first[0]['text'],'ALL SHORT WORDS')
            self.assertEqual(first[0]['first_final_label'],'Speaker_?')
            self.assertEqual(first[0]['utterance_id'],latest[0]['utterance_id'])
            self.assertEqual((directory/'audio_spool.pcm16').stat().st_size,1707*2)


def main():
    import argparse
    import hashlib
    import sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt',type=Path)
    args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if args.receipt:
        files=['research_scheduler.py','research_profiles.py','research_tracking_v2.py','research_s6b_checks.py','runtime.py','models.py','cli.py']
        payload={'schema_version':'s6b-component-fixtures.v1','status':'PASS' if result.wasSuccessful() else 'FAIL',
            'tests_run':result.testsRun,'failures':[(str(t),s) for t,s in result.failures],
            'errors':[(str(t),s) for t,s in result.errors],
            'scope':'Actual shared scheduler+tracker and full file runtime with deterministic model substitutes; not neural prefix proof',
            'code':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in files}}
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps(payload,indent=2),encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
