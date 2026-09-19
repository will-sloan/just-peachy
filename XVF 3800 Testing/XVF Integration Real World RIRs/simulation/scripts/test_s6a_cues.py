"""Causality, dependency and control fixtures; README_S6A_CUES.md has commands."""
from __future__ import annotations
import copy
from dataclasses import replace
import math
import unittest
import numpy as np
from s6a_cues import (ResearchTracker,TrackingConfig,SpatialObservation,feature_identity,
                      digest,run_policy,assign_finals,HistoricalCueBridge)


def vector(index=0):
    v=np.zeros(192,np.float32);v[index]=1.;return v


def feature(end):
    return dict(source_start_sec=end-.5,source_end_sec=end,available_at_sec=end+.02,speech=True,overlap=False)


class TrackerTests(unittest.TestCase):
    def test_default_association_and_commit_unique_union(self):
        t=ResearchTracker();results=[]
        for end in (.5,.75,1.):results.append(t.update(vector(),end-.5,end,end+.01))
        self.assertEqual([r['evidence_sec'] for r in results],[.5,.75,1.])
        self.assertIsNone(results[1]['committed_track_id']);self.assertEqual(results[2]['committed_track_id'],1)
        self.assertEqual(t.snapshot()['tracks'][0]['unique_evidence_sec'],1.)

    def test_gap_is_not_evidence(self):
        t=ResearchTracker();t.update(vector(),0.,.5,.5)
        result=t.update(vector(),20.,20.5,20.5)
        self.assertEqual(result['evidence_sec'],1.)

    def test_capacity_bounded_and_unknown_visible(self):
        t=ResearchTracker(TrackingConfig(max_tracks=2))
        for i in range(3):result=t.update(vector(i),i,i+.5,i+.5)
        self.assertEqual(result['reason'],'track_capacity');self.assertEqual(result['anonymous_label'],'Unknown')
        self.assertEqual(t.snapshot()['prototype_float32_bytes'],1536)

    def test_prototype_pollution_guard(self):
        t=ResearchTracker();t.update(vector(),0.,.5,.5)
        before=t.tracks[0].center.copy();v=vector(1)*math.sqrt(1-.4**2)+vector(0)*.4
        result=t.update(v,.5,1.,1.)
        self.assertEqual(result['cluster_id'],1);np.testing.assert_array_equal(before,t.tracks[0].center)

    def test_future_availability_refused(self):
        with self.assertRaises(ValueError):ResearchTracker().update(vector(),0.,.5,.4)

    def test_repeated_or_reordered_features_refused(self):
        t=ResearchTracker();t.update(vector(),0.,.5,.5)
        with self.assertRaises(ValueError):t.update(vector(),0.,.5,.6)

    def test_invalid_vector_refused(self):
        for v in (np.zeros(192),np.full(192,np.nan),np.zeros(191)):
            with self.assertRaises(ValueError):ResearchTracker().update(v,0.,.5,.5)

    def test_bad_settings_refused(self):
        for kwargs in ({'mode':'truth'},{'cosine_threshold':2.},{'max_tracks':65},{'direction_max_age_sec':0.},
                       {'position_decay_sec':float('nan')},{'spatial_weight':-1.}):
            with self.assertRaises(ValueError):TrackingConfig(**kwargs)

    def test_overlap_rejects_prototype_and_tracks(self):
        t=ResearchTracker();result=t.update(vector(),0.,.5,.5,overlap=True)
        self.assertEqual(result['state'],'unknown');self.assertEqual(len(t.tracks),0)

    def test_no_speech_rejects(self):
        self.assertEqual(ResearchTracker().update(vector(),0.,.5,.5,speech=False)['state'],'unknown')

    def test_angle_endpoints_are_not_adjacent(self):
        t=ResearchTracker(TrackingConfig(mode='angle_diagnostic'))
        a=t.update(vector(),0.,.5,.5,SpatialObservation(1.,.5))
        b=t.update(vector(),.5,1.,1.,SpatialObservation(179.,1.))
        self.assertNotEqual(a['cluster_id'],b['cluster_id'])

    def test_missing_cue_falls_back_to_voice(self):
        for mode in ('voice_time','sustained_angle','decaying_memory','reliability_adaptive'):
            t=ResearchTracker(TrackingConfig(mode=mode))
            labels=[t.update(vector(),i,i+.5,i+.5)['anonymous_label'] for i in range(3)]
            self.assertEqual(labels,['Speaker_1']*3)

    def test_stale_future_and_reordered_cues(self):
        t=ResearchTracker(TrackingConfig(mode='reliability_adaptive'))
        self.assertEqual(t.update(vector(),0.,.5,.5,SpatialObservation(90.,.6))['spatial_status'],'not_arrived')
        self.assertEqual(t.update(vector(),.5,1.,1.,SpatialObservation(90.,.5))['spatial_status'],'stale')
        self.assertEqual(t.update(vector(),1.,1.5,1.5,SpatialObservation(90.,1.5,sequence=5))['spatial_status'],'qualified')
        self.assertEqual(t.update(vector(),1.25,1.75,1.75,SpatialObservation(90.,1.74,sequence=4))['spatial_status'],'reordered_sequence')

    def test_voice_conflict_cannot_be_overruled_by_direction(self):
        t=ResearchTracker(TrackingConfig(mode='reliability_adaptive',spatial_weight=1.))
        t.update(vector(0),0.,.5,.5,SpatialObservation(90.,.5,1.))
        result=t.update(vector(1),.5,1.,1.,SpatialObservation(90.,1.,1.))
        self.assertEqual(result['cluster_id'],2)

    def test_no_truth_inputs_accepted(self):
        with self.assertRaises(TypeError):ResearchTracker().update(vector(),0.,.5,.5,true_speaker='A')

    def test_identical_prefix_different_future(self):
        features=[feature(.5+i*.25) for i in range(8)]
        left=np.asarray([vector(0)]*8);right=np.asarray([vector(0)]*4+[vector(1)]*4)
        for mode in ('voice_time','sustained_angle','decaying_memory','reliability_adaptive'):
            a,_=run_policy(features,left,mode);b,_=run_policy(features,right,mode)
            self.assertEqual(a[:4],b[:4])

    def test_truth_rename_is_invariant(self):
        f=[dict(feature(.5+i*.25),true_speaker='A',room='one',transcript='reference') for i in range(4)]
        renamed=[dict(x,true_speaker='Z',room='other',transcript='not available to tracker') for x in f]
        v=np.asarray([vector()]*4)
        self.assertEqual(run_policy(f,v,'voice_time'),run_policy(renamed,v,'voice_time'))

    def test_two_host_chunk_patterns_preserve_labels_with_recorded_delay(self):
        base=[feature(.5+i*.25) for i in range(12)];v=np.asarray([vector(i//4) for i in range(12)])
        outputs=[]
        for chunk in (.02,.1):
            f=[dict(x,available_at_sec=math.ceil((x['source_end_sec']-1e-9)/chunk)*chunk+.02) for x in base]
            out,_=run_policy(f,v,'voice_time');outputs.append(out)
            self.assertTrue(all(d['available_at_sec']>=d['source_end_sec'] for d in out))
        self.assertEqual([d['anonymous_label'] for d in outputs[0]],[d['anonymous_label'] for d in outputs[1]])
        self.assertNotEqual([d['available_at_sec'] for d in outputs[0]],[d['available_at_sec'] for d in outputs[1]])

    def test_final_only_uses_available_decision(self):
        events=[dict(event_type='transcript_final',source_time_sec=1.,payload=dict(text='HELLO',speaker='native',utterance_index=0))]
        decisions=[dict(available_at_sec=1.01,anonymous_label='Speaker_2',state='anonymous')]
        result=assign_finals(events,decisions)
        self.assertEqual(result[0]['speaker'],'Unknown');self.assertEqual(result[0]['text'],'HELLO')

    def test_decision_contract_conversion(self):
        from app.edge_speech_pipeline.research_tracking import decision_to_speaker
        row=ResearchTracker().update(vector(),0.,.5,.5)
        self.assertEqual(decision_to_speaker(row).anonymous_label,'Speaker_1')

    def test_fresh_half_second_cadence_supports_sampled_persistence(self):
        t=ResearchTracker(TrackingConfig(mode='sustained_angle'))
        for end,angle in ((.5,20.),(1.,20.),(1.5,140.),(2.,140.),(2.5,140.)):
            out=t.update(vector(),end-.5,end,end,SpatialObservation(angle,end))
        self.assertTrue(any(e['event']=='direction_change_proposal' and e['sustained'] for e in out['lineage']))

    def test_new_delivery_does_not_refresh_old_source_observation(self):
        t=ResearchTracker(TrackingConfig(mode='reliability_adaptive'))
        observation=SpatialObservation(90.,1.,source_start_sec=.1,source_end_sec=.2)
        out=t.update(vector(),.5,1.,1.,observation)
        self.assertEqual(out['spatial_status'],'stale_source_observation')

    def test_real_split_merge_and_forward_revision_preserve_first_events(self):
        t=ResearchTracker(TrackingConfig(mode='reliability_adaptive'))
        for end in (.5,.75,1.):t.update(vector(),end-.5,end,end,SpatialObservation(20.,end))
        branch=t.update(vector(1),.75,1.25,1.25,SpatialObservation(140.,1.25))
        preserved=copy.deepcopy(branch)
        self.assertEqual(branch['cluster_id'],2)
        self.assertIn('split_provisional_branch',[e['event'] for e in branch['lineage']])
        current=t.update(vector(),1.,1.5,1.5,SpatialObservation(140.,1.5))
        self.assertEqual(current['cluster_id'],1);self.assertEqual(branch,preserved)
        revisions=[e for e in current['lineage'] if e['event']=='label_revision']
        self.assertEqual(len(revisions),1);self.assertEqual(revisions[0]['revision_of'],branch['first_decision_id'])
        self.assertGreater(revisions[0]['available_at_sec'],revisions[0]['original_available_at_sec'])
        self.assertEqual(t.snapshot()['track_count'],1);self.assertEqual(t.snapshot()['merges'],1)
        self.assertAlmostEqual(t.tracks[0].unique_evidence_sec,1.5)

    def test_disable_reconciliation_does_not_claim_split_or_merge(self):
        t=ResearchTracker(TrackingConfig(mode='reliability_adaptive',reconciliation_enabled=False))
        for end in (.5,.75,1.):t.update(vector(),end-.5,end,end,SpatialObservation(20.,end))
        t.update(vector(1),.75,1.25,1.25,SpatialObservation(140.,1.25))
        out=t.update(vector(),1.,1.5,1.5,SpatialObservation(140.,1.5))
        self.assertFalse(any(e['event'] in ('merge_provisional_branch','label_revision') for e in out['lineage']))
        self.assertEqual(t.snapshot()['track_count'],2)


class CacheTests(unittest.TestCase):
    def test_exact_feature_identity_hit(self):
        args=({'sha256':'audio','bytes':16000},{'sha256':'events'},'model','ort',2,'source')
        self.assertEqual(digest(feature_identity(*args)),digest(feature_identity(*args)))

    def test_all_supported_feature_dependencies_miss(self):
        base=feature_identity({'sha256':'audio','bytes':16000},{'sha256':'events'},'model','ort',2,'source')
        for key in ('audio_sha256','audio_bytes','rate','channels','format','normalization','native_events_sha256',
                    'window_samples','window_selection','checkpoint_sha256','provider','onnxruntime_version',
                    'intra_op_threads','inter_op_threads','numeric_mode','frontend','model_embed_and_session_source_sha256',
                    'extraction_semantics_sha256','earliest_availability'):
            other=copy.deepcopy(base);other[key]=str(other[key])+'_MUTATED'
            self.assertNotEqual(digest(base),digest(other),key)

    def test_policy_mutation_is_downstream_only(self):
        feature_key=digest(feature_identity({'sha256':'audio','bytes':16000},{'sha256':'events'},'model','ort',2,'source'))
        a=dict(feature_key=feature_key,mode='voice_time',weight=0.)
        b=dict(feature_key=feature_key,mode='reliability_adaptive',weight=.12)
        self.assertEqual(a['feature_key'],b['feature_key']);self.assertNotEqual(digest(a),digest(b))


class BridgeTests(unittest.TestCase):
    @staticmethod
    def row(t,angle,sequence=1):
        return dict(command='AUDIO_MGR_SELECTED_AZIMUTHS',values=[math.radians(angle),math.radians(angle)],
                    parse_ok=True,logical_request_start_monotonic_ns=t-1000000,response_end_monotonic_ns=t-100000,
                    host_line_arrival_monotonic_ns=t,sequence=sequence,invalid_reasons=[None,None])
    @staticmethod
    def metadata():
        return dict(callback_times=[dict(first_native_frame=i*4800,frames=4800,
                                         host_copy_complete_monotonic_ns=1000000000+i*100000000,
                                         host_callback_monotonic_ns=1000000000+i*100000000) for i in range(20)])
    def test_future_telemetry_never_read(self):
        cap={'framing':{'startup_frames_excluded':0}}
        rows=[self.row(1300000000,20),self.row(1500000000,160,2)]
        bridge=HistoricalCueBridge(self.metadata(),cap,rows)
        current=bridge.observation(.5,.52)
        self.assertAlmostEqual(current.angle_deg,20)
        altered=HistoricalCueBridge(self.metadata(),cap,[rows[0],self.row(1500000000,80,2)])
        self.assertEqual(current,altered.observation(.5,.52))
    def test_model_cost_ages_metadata(self):
        cap={'framing':{'startup_frames_excluded':0}}
        bridge=HistoricalCueBridge(self.metadata(),cap,[self.row(1300000000,20)])
        obs=bridge.observation(.5,.8)
        out=ResearchTracker(TrackingConfig(mode='reliability_adaptive')).update(vector(),0.,.5,.8,obs)
        self.assertEqual(out['spatial_status'],'stale')


if __name__=='__main__':unittest.main()
