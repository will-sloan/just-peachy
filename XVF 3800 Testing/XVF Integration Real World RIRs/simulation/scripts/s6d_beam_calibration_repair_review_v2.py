"""Independent narrow V2 repair probes; README_S6D_BEAM_CALIBRATION_REPAIR_REVIEW_V2.md."""
import argparse
from copy import deepcopy
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys
import traceback


def binding(path):
    p=Path(path).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.drive.upper()!='G:' or a.output.exists():raise ValueError('Fresh G fixture directory required')
    a.output.mkdir(parents=True);tree=a.output/'review_source';tree.mkdir()
    freeze_ref=binding(a.freeze)
    if freeze_ref['sha256']!='c71f6a3f6989c95b7b05713a475e22014e4bda7077de42c06737bd33dd617d52':raise ValueError('Exact calibration V2 freeze required')
    freeze=json.loads(a.freeze.read_text(encoding='utf-8-sig'));refs=[x['frozen'] for x in freeze['source_files']]+[freeze['selector_source'],freeze['evidence_reader'],freeze['tests']]
    for ref in refs:
        if binding(ref['path'])!=ref:raise ValueError('Frozen graph changed: '+ref['path'])
    for row in freeze['source_files']:
        ref=row['frozen'];shutil.copyfile(ref['path'],tree/Path(ref['path']).name)
    sys.dont_write_bytecode=True;sys.path.insert(0,str(tree));C=importlib.import_module('s6d_beam_calibration_v2')
    results=[];observations={}
    def check(name,call):
        try:call();results.append(dict(name=name,status='PASS'))
        except BaseException:results.append(dict(name=name,status='FAIL',error=traceback.format_exc()))
    def reject(call):
        try:call()
        except ValueError:return
        raise AssertionError('Expected rejection')
    settings=dict(identity_streams=['left','right'],selected_profile_ids=['A','B'],maximum_evidence_age_sec=.75)
    admission=dict(capture_source_id='source',route_id='same-pass')
    spans=[dict(role='C',source_id='original_C1',profile_id='A',start_min=16000,start_max=16000,stop_min=64000,stop_max=64000)]
    def row(event,stream,known='A',score=.8,margin=.6,corr=.8,label='positive',source='original_C1'):
        return dict(event_id=event,stream_id=stream,capture_source_id='source',route_id='same-pass',source_start_sec=2.,source_end_sec=3.5,available_at_sec=3.55,speech=True,overlap=False,identity=dict(known_profile_id=known,naming_state='confirmed' if known else 'unresolved',current_query_name_cosine=score,margin=margin),same_auto_window=True,auto_waveform_correlation=corr,calibration_truth=dict(label=label,source_id=source))
    def probe(i,selector,rows):return dict(job_id='synthetic_C',probe_index=i,selector=selector,selector_now_sec=3.6,auto_support=[2.,3.5],exclusive_auto_speech=True,candidates=rows,collection_only=True,thresholds_applied=False,actual_disabled_result=dict(calibrated=False,status='NO_MATCH'))
    def collect(value,intervals=spans):
        seen={}
        for r in value['candidates']:
            native={k:deepcopy(v) for k,v in r.items() if k not in ('same_auto_window','auto_waveform_correlation','calibration_truth')}
            native.update(evidence_kind='mature',clean_fraction=.9);seen[(r['stream_id'],r['event_id'])]=native
        return C.collect_probe(value,seen,admission,settings,1.5,.8,intervals,{'A','B'},'synthetic_C')
    def unnamed():
        record,features,counts=collect(probe(1,'auto',[row('named','left'),row('unknown','right',known=None,corr=.95)]))
        values=[(x['value'],x['label']) for x in features if x['metric']=='minimum_auto_correlation']
        assert values==[(.95,'ambiguous'),(.8,'positive')],values
        chosen=C.replay_probe(record,{k:.05 for k in C.METRICS},settings,admission)
        assert chosen['selected_stream']=='right' and chosen['known_profile_id'] is None
        observations['unnamed_competitor']=dict(features=features,chosen=chosen,candidates_retained=len(record['candidates']))
    check('original_unnamed_point95_competitor_retained',unnamed)
    def mixed_support():
        mixed=deepcopy(spans);mixed.append(dict(mixed[0],source_id='original_C2',profile_id='B'))
        record,features,counts=collect(probe(2,'auto',[row('ambiguous','left')]),mixed)
        assert record['candidates'][0]['calibration_truth']['label']=='ambiguous'
        assert all(f['label']=='ambiguous' for f in features)
    check('overlap_not_fabricated_as_negative',mixed_support)
    def root_args(name,root_change=None):
        case=dict(path='synthetic-case',bytes=1,sha256='a'*64);part=dict(path='synthetic-partition',bytes=1,sha256='b'*64);gallery=dict(path='synthetic-gallery',bytes=1,sha256='c'*64)
        base=dict(schema_version='edge-s6d-beam-calibration-partition.v1',status='ROOT_ACCEPTED_CAPTURED_C_FOR_COLLECTION_ONLY',partition='C',Q_used=False,disjoint_from_E_Q_verified=True,accepted_case_results=[case],C_source_ids=['original_C1'])
        support=dict(schema='s6d-C-captured-support.v1',status='ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT',case_result=case,partition=part,gallery=gallery,no_per_beam_alignment=True,rir_origin_added_again=False,spans=deepcopy(spans),excluded_fragments=[dict(reason='ambiguous')],fixture_only=True)
        target=dict(case_result=case,partition=part,gallery=gallery,support_payload_sha256=C.payload_digest(support),C_source_ids=['original_C1'])
        authority=dict(schema='s6d-C-support-root-acceptance.v1',status='ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT',Q_used=False,disjoint_from_E_Q_verified=True,acceptances=[target],fixture_only=True)
        if root_change:root_change(authority)
        path=a.output/(name+'_SYNTHETIC_AUTHORITY.json');C.save(path,authority);support['root_acceptance']=C.bind(path)
        return support,dict(original_case_result=case),part,base,gallery
    check('exact_semantic_payload_authority_passes',lambda:C.require_support_authority(*root_args('positive')))
    check('original_unrelated_root_status_rejected',lambda:reject(lambda:C.require_support_authority(*root_args('unrelated',lambda r:r.update(status='FIXTURE_UNRELATED_NOT_ACCEPTED')))))
    def payload_change():
        args=root_args('exclusion');args[0]['excluded_fragments']=[];reject(lambda:C.require_support_authority(*args))
    check('excluded_ambiguous_population_digest_bound',payload_change)
    check('Q_authority_rejected',lambda:reject(lambda:C.require_support_authority(*root_args('q',lambda r:r.update(Q_used=True)))))
    def wrong_C():
        args=root_args('wrong_C');args[0]['spans'][0]['role']='Q';reject(lambda:C.require_support_authority(*args))
    check('Q_span_rejected_before_any_fit',wrong_C)
    def records(conflict=False):
        result=[];serial=0
        for source in ('original_C1','original_C2'):
            for selector in ('selected','auto'):
                for good in (True,False):
                    serial+=1
                    positive=row('p'+str(serial),'left',score=.9 if good else .2,margin=.1 if conflict and good else .8,corr=.9 if good else .2,source=source)
                    negative=row('n'+str(serial),'right',known='B',score=.4,margin=.3,corr=.4,label='negative',source=source)
                    result.append(probe(serial,selector,[positive,negative]))
        return result
    def gates(values):return C.fit_thresholds([f for r in values for f in C.feature_rows(r,settings,admission)])
    def joint_failure():
        rs=records(True);fit=gates(rs);assert fit['thresholds'] is not None
        value=C.joint_replay(rs,fit['thresholds'],settings,admission)
        assert value['status']=='JOINT_REPLAY_INSUFFICIENT' and value['selectors']['selected']['retained_positive_source_ids']==[]
        observations['per_metric_but_zero_joint']=dict(fit=fit,joint=value)
    check('original_per_gate_but_zero_joint_support_rejected',joint_failure)
    def joint_positive():
        rs=records();fit=gates(rs);value=C.joint_replay(rs,fit['thresholds'],settings,admission)
        assert value['status']=='JOINT_REPLAY_SUPPORTED'
        for selector in ('selected','auto'):assert value['selectors'][selector]['retained_positive_source_ids']==['original_C1','original_C2']
    check('actual_selector_joint_positive_control',joint_positive)
    def one_source():
        rs=records()
        for p in rs:
            for r in p['candidates']:r['calibration_truth']['source_id']='original_C1'
        assert gates(rs)['thresholds'] is None
    check('repeated_windows_do_not_inflate_unique_C_sources',one_source)
    def bad_winner():
        rs=records();fit=gates(rs);rs.append(probe(99,'auto',[row('unknown','left',known=None,corr=.99,label='ambiguous')]))
        value=C.joint_replay(rs,fit['thresholds'],settings,admission)
        assert value['status']=='JOINT_REPLAY_INSUFFICIENT' and any('ambiguous evidence' in x for x in value['issues'])
    check('ambiguous_runtime_winner_blocks_enablement_candidate',bad_winner)
    unchanged=all(binding(ref['path'])==ref for ref in refs) and binding(a.freeze)==freeze_ref
    check('exact_frozen_source_graph_unchanged',lambda:assert_true(unchanged))
    C.save(a.output/'OBSERVATIONS.json',observations)
    receipt=dict(status='SOURCE_REPAIRS_VERIFIED_NO_EXECUTION_ADMISSION' if all(r['status']=='PASS' for r in results) else 'CHANGES_REQUESTED',freeze=freeze_ref,reviewer_source=binding(__file__),source_graph=refs,review_copies=[binding(tree/Path(row['frozen']['path']).name) for row in freeze['source_files']],tests=results,passed=sum(r['status']=='PASS' for r in results),total=len(results),source_graph_unchanged=unchanged,actual_C_feature_extraction=False,actual_threshold_fit=False,models_started=0,hardware_commands=0,root_acceptance_created=False,limits=['Synthetic root status examples are fixture-only; no actual C support accepted.','Actual closed C journal/source/whole-window support and source counts must pass production guards.','No Q selection, model changes, runtime gate changes or acoustic source-survival truth inferred.','Duplicate resolution remains disabled; exact frozen choose AST reused.'])
    C.save(a.output/'INDEPENDENT_REPAIR_REVIEW_V2.json',receipt);print(json.dumps(dict(status=receipt['status'],passed=receipt['passed'],total=receipt['total'],receipt=binding(a.output/'INDEPENDENT_REPAIR_REVIEW_V2.json'))));return 0 if receipt['status']=='SOURCE_REPAIRS_VERIFIED_NO_EXECUTION_ADMISSION' else 1


def assert_true(value):assert value


if __name__=='__main__':raise SystemExit(main())
