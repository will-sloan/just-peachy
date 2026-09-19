"""Tiny model-free V2 calibration checks; see README_S6D_BEAM_CALIBRATION_V2.md."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import unittest
import s6d_beam_calibration_v2 as C

class Checks(unittest.TestCase):
    output=None
    def settings(self):return dict(identity_streams=['f0','f1'],selected_profile_ids=['A','B'],maximum_evidence_age_sec=.75)
    def identity(self):return dict(capture_source_id='cap',route_id='route')
    def row(self,event,stream,label,source,score=.9,margin=.8,corr=.9,known='A'):
        ident=dict(known_profile_id=known,naming_state='confirmed' if known else 'unresolved',current_query_name_cosine=score,margin=margin)
        return dict(event_id=event,stream_id=stream,capture_source_id='cap',route_id='route',source_start_sec=2.,source_end_sec=3.5,available_at_sec=3.6,speech=True,overlap=False,identity=ident,same_auto_window=True,auto_waveform_correlation=corr,calibration_truth=dict(label=label,source_id=source,reason='fixture_only'))
    def record(self,index,selector,rows):return dict(job_id='fixture',probe_index=index,selector=selector,selector_now_sec=3.7,auto_support=[2.,3.5],exclusive_auto_speech=True,candidates=rows)
    def records(self,conflicting_gates=False):
        records=[];i=0
        for source in ('C1','C2'):
            for selector in ('selected','auto'):
                i+=1;p=self.row(f'p{i}','f0','positive',source);n=self.row(f'n{i}','f1','negative',source,.4,.3,.4,'B')
                if conflicting_gates and selector=='selected':p['identity']['margin']=.1;n['identity']['margin']=.4
                records.append(self.record(i,selector,[p,n]))
                i+=1;p=self.row(f'p{i}','f0','positive',source,.3,.8,.3);n=self.row(f'n{i}','f1','negative',source,.4,.3,.4,'B')
                if conflicting_gates and selector=='selected':p['identity']['current_query_name_cosine']=.1;n['identity']['margin']=.4
                records.append(self.record(i,selector,[p,n]))
        return records
    def fit(self,records):return C.fit_thresholds([f for r in records for f in C.feature_rows(r,self.settings(),self.identity())])
    def support(self,name,change=None):
        d=self.output/name;d.mkdir()
        case=dict(path='fixture-case',sha256='c'*64,bytes=1);part=dict(path='fixture-partition',sha256='p'*64,bytes=1);gallery=dict(path='fixture-gallery',sha256='g'*64,bytes=1)
        base=dict(schema_version='edge-s6d-beam-calibration-partition.v1',status='ROOT_ACCEPTED_CAPTURED_C_FOR_COLLECTION_ONLY',partition='C',Q_used=False,disjoint_from_E_Q_verified=True,accepted_case_results=[case],C_source_ids=['C1'])
        s=dict(schema='s6d-C-captured-support.v1',status='ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT',case_result=case,partition=part,gallery=gallery,no_per_beam_alignment=True,rir_origin_added_again=False,spans=[dict(source_id='C1',role='C',profile_id='A',start_min=0,start_max=0,stop_min=64000,stop_max=64000)])
        target=dict(case_result=case,partition=part,gallery=gallery,support_payload_sha256=C.payload_digest(s),C_source_ids=['C1'])
        root=dict(schema='s6d-C-support-root-acceptance.v1',status='ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT',Q_used=False,disjoint_from_E_Q_verified=True,acceptances=[target])
        if change:change(root)
        rp=d/'root.json';C.save(rp,root);s['root_acceptance']=C.bind(rp)
        return s,dict(original_case_result=case),part,base,gallery
    def test_semantic_exact_root_acceptance_passes(self):
        self.assertEqual(C.require_support_authority(*self.support('accepted'))['C_source_ids'],['C1'])
    def test_unrelated_root_status_rejected(self):
        args=self.support('status',lambda x:x.update(status='FIXTURE_UNRELATED_NOT_ACCEPTED'))
        with self.assertRaisesRegex(ValueError,'Semantic root'):C.require_support_authority(*args)
    def test_wrong_case_root_scope_rejected(self):
        args=self.support('case',lambda x:x['acceptances'][0].update(case_result={}))
        with self.assertRaisesRegex(ValueError,'this exact support'):C.require_support_authority(*args)
    def test_wrong_partition_root_scope_rejected(self):
        args=self.support('partition',lambda x:x['acceptances'][0].update(partition={}))
        with self.assertRaisesRegex(ValueError,'this exact support'):C.require_support_authority(*args)
    def test_changed_support_bounds_rejected(self):
        args=self.support('bounds');args[0]['spans'][0]['stop_min']=63000
        with self.assertRaisesRegex(ValueError,'this exact support'):C.require_support_authority(*args)
    def test_Q_acceptance_rejected(self):
        args=self.support('Q',lambda x:x.update(Q_used=True))
        with self.assertRaisesRegex(ValueError,'Semantic root'):C.require_support_authority(*args)
    def test_wrong_C_source_scope_rejected(self):
        args=self.support('C_sources',lambda x:x['acceptances'][0].update(C_source_ids=['C2']))
        with self.assertRaisesRegex(ValueError,'this exact support'):C.require_support_authority(*args)
    def test_unknown_auto_candidate_retained_with_ambiguous_truth(self):
        rows=[self.row('a','f0','positive','C1',corr=.8),self.row('b','f1','ambiguous','C1',corr=.95,known=None)]
        seen={}
        for row in rows:
            event={k:deepcopy(v) for k,v in row.items() if k not in ('same_auto_window','auto_waveform_correlation','calibration_truth')}
            event.update(evidence_kind='mature',clean_fraction=.9);seen[(row['stream_id'],row['event_id'])]=event
        p=self.record(1,'auto',rows);p.update(collection_only=True,thresholds_applied=False,actual_disabled_result=dict(calibrated=False,status='NO_MATCH'))
        spans=[dict(source_id='C1',profile_id='A',start_min=0,start_max=0,stop_min=64000,stop_max=64000)]
        record,features,counts=C.collect_probe(p,seen,self.identity(),self.settings(),1.5,.8,spans,{'A','B'},'fixture')
        self.assertEqual([(r['value'],r['label']) for r in features if r['metric']=='minimum_auto_correlation'],[(.95,'ambiguous'),(.8,'positive')])
        self.assertEqual(len(record['candidates']),2)
        chosen=C.replay_probe(record,{k:.1 for k in C.METRICS},self.settings(),self.identity())
        self.assertEqual(chosen['selected_stream'],'f1')
        self.assertIsNone(chosen['known_profile_id'])
    def test_ambiguity_high_metric_blocks_unsupported_thresholds(self):
        records=self.records();rows=[f for r in records for f in C.feature_rows(r,self.settings(),self.identity())]
        rows.append(dict(metric='minimum_auto_correlation',value=.99,label='ambiguous',source_id=None))
        self.assertIsNone(C.fit_thresholds(rows)['thresholds'])
    def test_future_or_stale_candidate_not_runtime_eligible(self):
        r=self.row('a','f0','positive','C1');r['available_at_sec']=4.
        self.assertFalse(C.runtime_eligible(r,3.7,self.settings(),self.identity()))
        r['available_at_sec']=3.6
        self.assertFalse(C.runtime_eligible(r,4.26,self.settings(),self.identity()))
    def test_per_gate_support_can_fail_actual_joint_selected_gates(self):
        records=self.records(conflicting_gates=True);fit=self.fit(records)
        self.assertIsNotNone(fit['thresholds'])
        replay=C.joint_replay(records,fit['thresholds'],self.settings(),self.identity())
        self.assertEqual(replay['status'],'JOINT_REPLAY_INSUFFICIENT')
        self.assertEqual(replay['selectors']['selected']['retained_positive_source_ids'],[])
    def test_real_joint_positive_negative_competition_scope_can_pass_synthetic(self):
        records=self.records();fit=self.fit(records);self.assertIsNotNone(fit['thresholds'])
        replay=C.joint_replay(records,fit['thresholds'],self.settings(),self.identity())
        self.assertEqual(replay['status'],'JOINT_REPLAY_SUPPORTED',replay)
        for selector in ('selected','auto'):
            self.assertEqual(replay['selectors'][selector]['retained_positive_source_ids'],['C1','C2'])
            self.assertEqual(replay['selectors'][selector]['negative_challenge_source_ids'],['C1','C2'])
    def test_ambiguous_runtime_winner_blocks_joint_support(self):
        records=self.records();fit=self.fit(records)
        r=self.row('unknown','f0','ambiguous','C1',corr=.99,known=None)
        records.append(self.record(99,'auto',[r]))
        replay=C.joint_replay(records,fit['thresholds'],self.settings(),self.identity())
        self.assertEqual(replay['status'],'JOINT_REPLAY_INSUFFICIENT')
        self.assertTrue(any('ambiguous' in x for x in replay['issues']))
    def test_no_negative_challenges_or_competition_cannot_pass(self):
        records=[r for r in self.records() if r['probe_index']%2==1]
        for r in records:r['candidates']=r['candidates'][:1]
        replay=C.joint_replay(records,{k:.5 for k in C.METRICS},self.settings(),self.identity())
        self.assertEqual(replay['status'],'JOINT_REPLAY_INSUFFICIENT')
        self.assertEqual(replay['selectors']['auto']['negative_challenge_source_ids'],[])
    def test_repeated_one_source_does_not_make_two(self):
        records=self.records()
        for r in records:
            for c in r['candidates']:c['calibration_truth']['source_id']='C1'
        self.assertIsNone(self.fit(records)['thresholds'])
    def test_case_identity_map_does_not_pool_wrong_capture(self):
        records=self.records();fit=self.fit(records)
        tagged=[(r,self.identity()) for r in records]
        self.assertEqual(C.joint_replay_by_case(tagged,fit['thresholds'],self.settings())['status'],'JOINT_REPLAY_SUPPORTED')
        with self.assertRaisesRegex(ValueError,'Duplicate actual'):C.joint_replay_by_case(tagged+[tagged[0]],fit['thresholds'],self.settings())
    def test_empty_capture_identifiers_are_not_runtime_eligible(self):
        row=self.row('a','f0','positive','C1');row.update(capture_source_id='',route_id='')
        self.assertFalse(C.runtime_eligible(row,3.7,self.settings(),dict(capture_source_id='',route_id='')))
    def test_same_event_id_in_distinct_streams_joins_selected_stream(self):
        records=self.records();fit=self.fit(records)
        for record in records:
            for row in record['candidates']:row['event_id']='shared-event-id'
        self.assertEqual(C.joint_replay(records,fit['thresholds'],self.settings(),self.identity())['status'],'JOINT_REPLAY_SUPPORTED')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    C.need(a.output.drive.upper()=='G:' and not a.output.exists(),'Fresh G fixture output required');a.output.mkdir(parents=True);Checks.output=a.output
    with (a.output/'TESTS.log').open('x',encoding='utf-8') as log:r=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    C.save(a.output/'RECEIPT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),source=C.bind(C.__file__),checks=C.bind(__file__),selector_source=C.bind(C.BEAM_PATH),actual_C_scoring=False,models=0,hardware=0,scope='Synthetic eligibility/support authority/negative and ambiguous metric guards/exact selector joint replay only'))
    print(json.dumps(C.bind(a.output/'RECEIPT.json')));raise SystemExit(not r.wasSuccessful())
