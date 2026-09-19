"""Model-free S6B checks and optional full cached-vector original-control parity.

Run from Evaluation Tool: python -m app.edge_speech_pipeline.checks_research_tracking_v2
See README_RESEARCH_TRACKING_V2.md for Windows commands and all inputs/outputs.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np

from .research_tracking_v2 import MODES, SPATIAL_ONLY, S6BTracker, S6BTrackingConfig, decision_to_speaker


def unit(*values):
    v=np.zeros(192,np.float32);v[:len(values)]=values
    return v/np.linalg.norm(v)


def cue(angle,end,sequence=None,reliability=1.,**extra):
    row=dict(angle_deg=angle,available_at_sec=end,source_end_sec=end,reliability=reliability,energy=1.,valid=True,sequence=sequence)
    row.update(extra);return SimpleNamespace(**row)


def run_rows(config,rows):
    tracker=S6BTracker(config);outputs=[]
    for row in rows:outputs.append(tracker.update(*row))
    return tracker,outputs


class TrackerChecks(unittest.TestCase):
    def test_every_mode_is_callable_and_bounded(self):
        for mode in MODES:
            c=S6BTrackingConfig(mode=mode,cues_enabled=mode in SPATIAL_ONLY)
            t=S6BTracker(c)
            for i in range(80):
                v=unit(1,0) if i%4<2 else unit(0,1)
                d=t.update(v,i*.5,(i+1)*.5,(i+1)*.5,spatial=cue(10 if i%4<2 else 150,(i+1)*.5,i))
                self.assertEqual(d['decision_id'],'D%08d'%(i+1))
                self.assertIsInstance(decision_to_speaker(d).anonymous_label,str)
            s=t.snapshot();self.assertLessEqual(s['track_count'],c.max_tracks)
            self.assertLessEqual(s['state_bounds']['retained_nodes'],c.max_revision_records)
            self.assertLessEqual(s['state_bounds']['hypotheses'],c.hypothesis_count)
            self.assertLessEqual(s['state_bounds']['global_groups'],c.global_max_groups)
            self.assertLessEqual(s['state_bounds']['hsmm_states'],(c.max_tracks+1)*(c.hsmm_duration_bins+1))

    def test_first_one_second_window_is_not_committed(self):
        t=S6BTracker();d=t.update(unit(1),0,1,1)
        self.assertFalse(d['committed']);self.assertEqual(d['disjoint_evidence_count'],1)
        self.assertEqual(d['unique_evidence_sec'],1.)

    def test_overlap_is_unique_time_not_independent_count(self):
        t=S6BTracker();a=t.update(unit(1),0,1,1);b=t.update(unit(1),.5,1.5,1.5);c=t.update(unit(1),1.5,2.5,2.5)
        self.assertEqual(b['unique_evidence_sec'],1.5);self.assertEqual(b['disjoint_evidence_count'],1)
        self.assertEqual(b['prototype_version'],0);self.assertFalse(b['committed'])
        self.assertEqual(c['unique_evidence_sec'],2.5);self.assertEqual(c['disjoint_evidence_count'],2);self.assertTrue(c['committed'])

    def test_silence_and_overlap_do_not_admit_identity(self):
        t=S6BTracker();t.update(unit(1),0,1,1)
        for i,kwargs in enumerate((dict(speech=False),dict(overlap=True)),1):
            d=t.update(unit(1),i,i+1,i+1,**kwargs);self.assertEqual(d['anonymous_label'],'Unknown')
        self.assertEqual(t.snapshot()['tracks'][0]['unique_evidence_sec'],1.)

    def test_duplicate_future_and_backward_audio_rejected(self):
        t=S6BTracker();t.update(unit(1),0,1,1)
        for args in ((unit(1),0,1,1),(unit(1),1,2,1.5),(unit(1),0,.5,2)):
            with self.assertRaises(ValueError):t.update(*args)
        with self.assertRaises(TypeError):t.update(unit(1),1,2,2,true_speaker='oracle')

    def test_short_and_long_equal_end_count_once(self):
        t=S6BTracker();t.update(unit(1),.5,1,1);d=t.update(unit(1),0,1,1.1)
        self.assertEqual(d['unique_evidence_sec'],1.);self.assertEqual(d['disjoint_evidence_count'],1)

    def test_all_spatial_disabled_exact_voice_parent(self):
        rows=[(unit(1,0),0,1,1,cue(0,1)),(unit(0,1),1,2,2,cue(180,2)),(unit(.7,.7),2,3,3,cue(0,3)),(unit(1,.1),3,4,4,None)]
        baseline=run_rows(S6BTrackingConfig(),rows)[1]
        for mode in SPATIAL_ONLY:
            for extra in ({},{'sensor_quarantine_enabled':True},{'update_escrow_enabled':True}):
                result=run_rows(S6BTrackingConfig(mode=mode,cues_enabled=False,**extra),rows)[1]
                self.assertEqual(result,baseline)

    def test_structural_cue_off_same_code_parent(self):
        rows=[(unit(1,0),0,1,1,cue(0,1)),(unit(0,1),1,2,2,cue(180,2)),(unit(.7,.7),2,3,3,cue(0,3))]
        for mode in ('bayes','hsmm','dual_memory','global_assignment','delay_graph','multiprototype','quarantine'):
            c=S6BTrackingConfig(mode=mode)
            self.assertEqual(run_rows(c,rows)[1],run_rows(replace(c,sensor_quarantine_enabled=True,update_escrow_enabled=True),rows)[1])

    def test_prefix_future_and_untrusted_metadata_invariance(self):
        rows=[(unit(1,0),i,i+1,i+1,cue(10,i+1,i)) for i in range(5)]
        renamed=[r[:4]+(SimpleNamespace(**vars(r[4]),true_speaker='renamed',room='different',future_schedule=[99]),) for r in rows]
        for mode in MODES:
            config=S6BTrackingConfig(mode=mode,cues_enabled=mode in SPATIAL_ONLY)
            prefix=run_rows(config,rows[:3])[1]
            extended=run_rows(config,rows+[(unit(0,1),5,6,6,cue(170,6,5))])[1]
            self.assertEqual(prefix,extended[:3])
            self.assertEqual(run_rows(config,rows)[1],run_rows(config,renamed)[1])

    def test_delivery_and_source_freshness_reorder(self):
        t=S6BTracker(S6BTrackingConfig(mode='adaptive',cues_enabled=True))
        t.update(unit(1),0,1,1,cue(20,1,5))
        fixtures=[(cue(20,2,4),'reordered'),(cue(20,3,6,source_end_sec=1),'invalid_or_stale_source'),
                  (cue(20,5,7),'future_delivery'),(cue(20,4,8),'stale_delivery')]
        for i,(obs,expected) in enumerate(fixtures,1):
            d=t.update(unit(1),i,i+1,i+1,obs)
            self.assertEqual(d['cue']['reason'],expected)

    def test_folded_endpoints_are_not_neighbours(self):
        t=S6BTracker(S6BTrackingConfig(mode='angle',cues_enabled=True))
        a=t.update(unit(1),0,1,1,cue(0,1));b=t.update(unit(1),1,2,2,cue(180,2))
        self.assertNotEqual(a['tracker_id'],b['tracker_id'])

    def test_wrong_stable_same_bearing_cannot_override_orthogonal_voice(self):
        for mode in ('angle','adaptive'):
            t=S6BTracker(S6BTrackingConfig(mode=mode,cues_enabled=True))
            a=t.update(unit(1,0),0,1,1,cue(20,1));b=t.update(unit(0,1),1,2,2,cue(20,2));c=t.update(unit(0,1),2,3,3,cue(20,3))
            self.assertNotEqual(a['tracker_id'],b['tracker_id']);self.assertEqual(b['tracker_id'],c['tracker_id'])
        parent=S6BTracker();a=parent.update(unit(1,0),0,1,1);b=parent.update(unit(0,1),1,2,2)
        self.assertNotEqual(a['tracker_id'],b['tracker_id'])

    def test_sustained_half_second_cadence_and_innovation(self):
        t=S6BTracker(S6BTrackingConfig(mode='sustained',cues_enabled=True))
        out=[]
        for i in range(4):out.append(t.update(unit(1),i*.5,(i+1)*.5,(i+1)*.5,cue(20,(i+1)*.5,i)))
        self.assertGreaterEqual(t.last_available-t.pending_since,.75)
        q=S6BTracker(S6BTrackingConfig(mode='innovation',cues_enabled=True))
        q.update(unit(1),0,1,1,cue(0,1));d=q.update(unit(1),1,2,2,cue(90,2))
        self.assertTrue(any(e['event']=='innovation_change_proposal' for e in d['lineage']))

    def test_sensor_quarantine_and_disjoint_recovery(self):
        t=S6BTracker(S6BTrackingConfig(mode='adaptive',cues_enabled=True,sensor_quarantine_enabled=True))
        vectors=[unit(1,0),unit(0,1),unit(1,0),unit(1,0),unit(1,0),unit(1,0)]
        angles=[0,180,180,180,0,0];credit=[]
        for i,(v,a) in enumerate(zip(vectors,angles)):
            d=t.update(v,i,i+1,i+1,cue(a,i+1,i));credit.append(d['cue']['sensor_credit'])
        self.assertEqual(credit[3],0.);self.assertEqual(credit[5],1.)
        self.assertEqual(t.operations['sensor_quarantine'],1);self.assertEqual(t.operations['sensor_recovery'],1)

    def test_escrow_requires_later_disjoint_audio(self):
        t=S6BTracker(S6BTrackingConfig(mode='adaptive',cues_enabled=True,update_escrow_enabled=True))
        a=t.update(unit(1,0),0,1,1,cue(20,1));b=t.update(unit(.99,.1),1,2,2,cue(20,2))
        self.assertEqual(b['prototype_version'],0);self.assertFalse(b['committed'])
        c=t.update(unit(.99,.1),1.5,2.5,2.5,cue(20,2.5));self.assertEqual(c['prototype_version'],0)
        d=t.update(unit(.99,.1),2.5,3.5,3.5,cue(20,3.5))
        self.assertEqual(t.operations['prototype_escrow_release'],1);self.assertEqual(d['prototype_version'],1);self.assertTrue(d['committed'])

    def test_sensor_can_revalidate_after_all_locations_age_out(self):
        t=S6BTracker(S6BTrackingConfig(mode='adaptive',cues_enabled=True,sensor_quarantine_enabled=True))
        for i,(v,a) in enumerate(((unit(1,0),0),(unit(0,1),180),(unit(1,0),180),(unit(1,0),180))):
            t.update(v,i,i+1,i+1,cue(a,i+1,i))
        self.assertEqual(t.sensor_credit,0.)
        a=t.update(unit(1,0),20,21,21,cue(0,21,5));self.assertEqual(a['cue']['sensor_credit'],0.)
        b=t.update(unit(1,0),21,22,22,cue(0,22,6));self.assertEqual(b['cue']['sensor_credit'],1.)
        self.assertEqual(t.operations['sensor_stale_anchor_audit'],2)
        self.assertEqual(t.operations['sensor_recovery'],1)

    def test_multiprototype_and_slow_memory_activation(self):
        t=S6BTracker(S6BTrackingConfig(mode='multiprototype'));t.update(unit(1,0),0,1,1);t.update(unit(.7,.714),1,2,2)
        self.assertEqual(t.operations['prototype_slot_add'],1)
        slow=S6BTracker(S6BTrackingConfig(mode='dual_memory'));slow.update(unit(1,0),0,1,1)
        d=slow.update(unit(1,0),7,8,8);self.assertEqual(d['tracker_id'],1)
        self.assertEqual(slow.operations['track_dormant'],1);self.assertEqual(slow.operations['track_reactivate'],1)

    def test_escrow_expires_even_after_cue_dropout(self):
        t=S6BTracker(S6BTrackingConfig(mode='adaptive',cues_enabled=True,update_escrow_enabled=True))
        t.update(unit(1),0,1,1,cue(20,1));t.update(unit(1),1,2,2,cue(20,2))
        self.assertIsNotNone(t.tracks[0].escrow)
        d=t.update(unit(1),5,6,6)
        self.assertIsNone(t.tracks[0].escrow);self.assertTrue(d['committed'])
        self.assertEqual(t.operations['prototype_escrow_expire'],1)

    def test_rollback_and_forward_revision_preserve_first_object(self):
        t=S6BTracker(S6BTrackingConfig(mode='quarantine',voice_learning_rate=.5))
        t.update(unit(1,0),0,.5,.5);first=t.update(unit(.6,.8),.5,1,1);saved=json.dumps(first,sort_keys=True)
        d=t.update(unit(1,0),1,1.5,1.5)
        revisions=[e for e in d['lineage'] if e['event']=='label_revision']
        self.assertEqual(t.operations['prototype_rollback'],1);self.assertEqual(len(revisions),1)
        self.assertEqual(revisions[0]['revision_of'],first['decision_id']);self.assertEqual(revisions[0]['replacement_anonymous_label'],'Unknown')
        self.assertEqual(json.dumps(first,sort_keys=True),saved)
        self.assertGreater(revisions[0]['available_at_sec'],first['available_at_sec'])

    def test_delayed_graph_real_unknown_revision(self):
        t=S6BTracker(S6BTrackingConfig(mode='delay_graph',voice_learning_rate=.5,revision_margin=.08))
        t.update(unit(1,0),0,.5,.5);t.update(unit(0,1),.5,1,1)
        first=t.update(unit(1,1),1,1.5,1.5);self.assertEqual(first['anonymous_label'],'Unknown')
        d=t.update(unit(.95,.312),1.5,2,2)
        revisions=[e for e in d['lineage'] if e['event']=='label_revision' and e['revision_of']==first['decision_id']]
        self.assertTrue(revisions);self.assertEqual(first['anonymous_label'],'Unknown')

    def test_global_group_assignment_allows_sequential_same_voice_identity(self):
        t=S6BTracker(S6BTrackingConfig(mode='global_assignment'));t.update(unit(1,0),0,1,1)
        d=t.update(unit(.6,.8),1,2,2)
        self.assertEqual(d['anonymous_label'],'Speaker_1');self.assertGreater(t.operations['bounded_global_assignment'],0)
        assignment=[e for e in d['lineage'] if e['event']=='bounded_global_assignment'][0]
        self.assertEqual(assignment['assignment'],[1,1]);self.assertFalse(assignment['independent_simultaneous_observations_available'])

    def test_temporal_families_propagate_bounded_states(self):
        for mode,key in (('bayes','bayes_hypothesis_update'),('hsmm','hsmm_duration_update')):
            t=S6BTracker(S6BTrackingConfig(mode=mode));t.update(unit(1,0),0,1,1)
            for i in range(1,8):t.update(unit(1,.1),i,i+1,i+1)
            self.assertEqual(t.operations[key],7)

    def test_diagnostic_controls_are_actual_input_only(self):
        for mode,label in (('one_person','Speaker_1'),('all_unknown','Unknown')):
            t=S6BTracker(S6BTrackingConfig(mode=mode))
            for i in range(3):self.assertEqual(t.update(np.eye(192,dtype=np.float32)[i],i,i+1,i+1)['anonymous_label'],label)

    def test_capacity_and_invalid_configs(self):
        t=S6BTracker(S6BTrackingConfig(max_tracks=2))
        for i in range(2):t.update(np.eye(192,dtype=np.float32)[i],i,i+1,i+1)
        self.assertEqual(t.update(np.eye(192,dtype=np.float32)[2],2,3,3)['anonymous_label'],'Unknown')
        for changes in ({'max_tracks':0},{'max_prototypes':9},{'continuity_prior':1.},{'max_window_sec':4.},{'mode':'fake'}, {'commit_disjoint_count':True}):
            with self.assertRaises(ValueError):S6BTrackingConfig(**changes)
        usage=S6BTrackingConfig(mode='voice',hsmm_switch_penalty=.8).field_usage()
        self.assertEqual(usage['nondefault_inactive_fields'],['hsmm_switch_penalty'])


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def full_parity(index_path):
    """Consume only already-produced audio vectors; historical labels used solely by this checker."""
    from .speakers import SpeakerTracker
    class EmptyProfiles:
        def load(self):return {}
    cfg=SimpleNamespace(clustering_threshold=.35,embedding_window_sec=.5,identity_score_threshold=.5128856897354127,
                        identity_margin_threshold=.03,identity_minimum_evidence_sec=2.)
    index=json.loads(Path(index_path).read_text(encoding='utf-8'));count=0;mismatches=[];rows=[]
    for row in index['rows']:
        path=Path(row['result']['path']);assert sha(path)==row['result']['sha256']
        data=json.loads(path.read_text(encoding='utf-8'));vector_path=Path(data['vectors']['path']);assert sha(vector_path)==data['vectors']['sha256']
        with np.load(vector_path,allow_pickle=False) as archive:
            matrix=archive['vectors'] if 'vectors' in archive.files else archive[archive.files[0]]
            assert len(matrix)==len(data['features'])
            old=SpeakerTracker(cfg,EmptyProfiles());new=S6BTracker(S6BTrackingConfig(mode='original_common',max_tracks=256))
            for feature,vector in zip(data['features'],matrix):
                expected=asdict(old.update(vector,feature['source_end_sec']))
                actual=new.update(vector,feature['source_start_sec'],feature['source_end_sec'],feature['available_at_sec'],speech=feature['speech'],overlap=feature['overlap'])
                for key,value in expected.items():
                    if actual[key]!=value:mismatches.append({'case':row['case_id'],'stream':row['stream'],'index':feature['index'],'field':key})
                if actual['anonymous_label']!=feature['native_anonymous_label']:mismatches.append({'case':row['case_id'],'stream':row['stream'],'index':feature['index'],'field':'native_anonymous_label'})
                count+=1
        rows.append({'case_id':row['case_id'],'stream':row['stream'],'features':len(data['features']),'original_track_count':len(old.clusters)})
    return {'status':'PASS' if not mismatches else 'FAIL','feature_index':{'path':str(index_path),'sha256':sha(index_path)},
            'outputs':len(rows),'vectors':count,'mismatches':mismatches,'rows':rows,'original_common_max_tracks':256,
            'observed_max_original_tracks':max(r['original_track_count'] for r in rows),
            'scope':'All SpeakerDecision fields exact against actual existing SpeakerTracker plus cached native anonymous label; explicit control max_tracks256; no inference.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--feature-index',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(TrackerChecks);result=unittest.TextTestRunner(verbosity=2).run(suite)
    receipt={'schema':'jp_s6b_tracker_checks_v1','utc':datetime.now(timezone.utc).isoformat(),'status':'PASS' if result.wasSuccessful() else 'FAIL',
             'tests':result.testsRun,'failures':[str(t) for t,_ in result.failures],'errors':[str(t) for t,_ in result.errors],
             'module_sha256':sha(Path(__file__).with_name('research_tracking_v2.py')),'checks_sha256':sha(__file__),
             'modes':list(MODES),'method_results_not_inferred_from_fixture_success':True}
    if args.feature_index:
        receipt['original_common_full_parity']=full_parity(args.feature_index)
        if receipt['original_common_full_parity']['status']!='PASS':receipt['status']='FAIL'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='original_common_full_parity'},indent=2))
    raise SystemExit(0 if receipt['status']=='PASS' else 1)


if __name__=='__main__':main()
