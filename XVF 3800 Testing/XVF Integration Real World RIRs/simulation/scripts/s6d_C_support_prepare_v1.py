"""Inactive whole-window C support projection; see README_S6D_C_SUPPORT_PREPARE_V1.md."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil
import s6d_beam_native_run_v1 as N
import s6d_beam_execution_prepare_v1 as P

CLOCK_SHA='dc42888793452ddbf470649df5b6aa127ae462dcf6a62c39b3b14687861ddac4'
ENROLLMENT_SHA='6cbcd082b2afb7f640363d533211b93a3d79e69582f3e34a5306c3a20bca2e84'
GALLERY_SHA='8042fbec1cdd4632d90b9d2148c37114e3fcd1aa8cc39a442d22a575e4177018'
PARTITION_SHA='98d4f5bde18c13fecff0d14e7ab5cd4504490be2da742874b598dd4600d26f0a'
need=N.need;bind=N.bind;verified=N.verified;save=N.save

def project_fragment(case,fragment,source_identities,profile_ids):
    """Copy a pre-eroded interval exactly; never add the case lag/guard a second time."""
    left,right=fragment['input_span_samples'];low,high=case['proposed_case_lag_envelope_samples']
    start,stop=fragment['proposed_capture_interior_samples']
    need(all(type(v) is int for v in (left,right,low,high,start,stop)) and 0<=left<right and low<=high,'Invalid original integer clock interval')
    need([start,stop]==[16000+left+high,16000+right+low],'Projection differs from frozen common case envelope')
    identities=fragment['possible_source_identities'];source_ids=fragment['source_ids']
    need(source_ids and len(source_ids)==len(set(source_ids)) and all(s in source_identities for s in source_ids),'Unknown/duplicate original C source')
    need(set(identities)=={source_identities[s] for s in source_ids},'Original C source identity mapping differs')
    if fragment.get('unique_source_identity') is not True or len(identities)!=1 or len(source_ids)!=1:
        return None,'multiple_source_or_identity_support'
    if stop-start<24000:return None,'less_than_one_1p5s_mature_window'
    need(start>=0 and start<stop,'Invalid eroded captured interval')
    identity=identities[0]
    return dict(role='C',source_id=source_ids[0],metadata_identity=identity,profile_id=profile_ids.get(identity),start_min=start,start_max=start,stop_min=stop,stop_max=stop,eligibility_fragment_only=True,unique_auto_to_focus_target_proven=False),'proposed_unique_mature_window_interior'

def prepare(output):
    out=Path(output).resolve();need(out.parent==P.R and not out.exists(),'Fresh report-root proposal directory required')
    clock_ref=bind(P.R/'physical_route_proposals_v1/C_CLOCK_PROJECTION_PROPOSAL_V1.json');need(clock_ref['sha256']==CLOCK_SHA,'Frozen clock differs');clock=verified(clock_ref)
    cp_ref=bind(P.R/'physical_C_collection_admission_v2/C_CALIBRATION_PARTITION.json');need(cp_ref['sha256']==PARTITION_SHA,'Exact collection-only partition differs');cp=verified(cp_ref)
    need(cp.get('collection_only') is True and cp.get('gold_time_projection_admitted') is False and cp.get('selector_thresholds_admitted') is False and cp.get('admission_created') is True and cp.get('disjoint_from_E_Q_verified') is True and cp.get('Q_used') is False,'Collection/label authority differs')
    need(cp['original_proposal']==clock['partition'] and len(clock['cases'])==len(cp['accepted_case_results'])==12,'Exact12 original clock cases required')
    enroll_ref=bind(P.SIM/'reports/S6C/20260910T123540Z/enrollment/ENROLLMENT_PLAN_V2.json');need(enroll_ref['sha256']==ENROLLMENT_SHA,'Original person mapping differs');enroll=verified(enroll_ref)
    gallery_ref=bind(Path('G:/Just_Peachy_S6C/20260910T123540Z/enrollment/galleries/84f59413a02827ef445c66be/GALLERY.json'));need(gallery_ref['sha256']==GALLERY_SHA,'Actual A15 gallery differs');gallery=verified(gallery_ref)
    people=enroll['people'];by_display={p['display_name']:identity for identity,p in people.items()}
    need(len(by_display)==len(people),'Ambiguous original person names')
    mapping={};profile_bindings=[]
    for profile in gallery['profiles']:
        meta=verified(profile['metadata']);need(bind(profile['vector']['path'])==profile['vector'],'Original actual profile vector differs')
        need(meta['profile_id']==profile['profile_id'] and meta['display_name']==profile['display_name'],'Actual gallery profile metadata differs')
        identity=by_display[profile['display_name']];need(identity not in mapping,'Duplicate actual gallery identity');mapping[identity]=profile['profile_id'];profile_bindings.extend([profile['metadata'],profile['vector']])
    need(len(mapping)==15,'Exact actual A15 profiles required, never intended larger rosters')
    source_map={s['source_id']:s['identity'] for s in cp['sources']};need(set(source_map)==set(cp['C_source_ids']),'Original C source set differs')
    out.mkdir();outputs=[];totals=Counter();cases_seen=set()
    for case in clock['cases']:
        cref=case['case_result'];need(cref in cp['accepted_case_results'] and cref['sha256'] not in cases_seen,'Clock case missing/duplicate');cases_seen.add(cref['sha256'])
        original=verified(cref);N.validate_original_identity(original,case['case_id'],case['profile']);need(original['attempt']['source_audio']==case['original_source_audio'],'Clock source differs')
        spans=[];excluded=[];counts=Counter()
        for index,fragment in enumerate(case['candidate_identity_interiors']):
            span,reason=project_fragment(case,fragment,source_map,mapping);counts[reason]+=1
            if span is None:excluded.append(dict(fragment_index=index,reason=reason,original_fragment=fragment))
            else:span['fragment_index']=index;spans.append(span)
        ordered=sorted(spans,key=lambda s:s['start_min']);need(all(a['stop_max']<=b['start_min'] for a,b in zip(ordered,ordered[1:])),'Eligible fragments overlap')
        result=dict(schema='s6d-C-captured-support.v1',status='PROPOSED_CONSERVATIVE_SOURCE_SUPPORT_PENDING_ROOT_REVIEW',source=bind(__file__),case_result=cref,partition=cp_ref,gallery=gallery_ref,original_person_mapping=enroll_ref,original_profile_bindings=profile_bindings,clock_proposal=clock_ref,original_case_projection=deepcopy(case),case_id=case['case_id'],capture_profile=case['profile'],spans=spans,excluded=excluded,counts=dict(counts),no_per_beam_alignment=True,rir_origin_added_again=False,additional_guard_or_lag_added=False,root_review_required=True,root_acceptance=None,selector_thresholds_admitted=False,scope='The equal min/max bounds describe an already-eroded eligibility fragment. They do not assert zero physical timing uncertainty, exact per-focus delay or source survival. Only actual mature native event whole spans and their existing clean/exclusive speech gates may be evaluated. The original empirical envelope plus20ms is a proposal, not a confidence interval. Unknown actual-gallery identities retain null profile_id; overlap/source ambiguity and short fragments remain listed. Never runtime identity hints.',actual_mature_windows_observed=0,model_calls=0)
        path=out/(case['attempt_id']+'_SUPPORT_PROPOSAL.json');save(path,result);outputs.append(bind(path));totals.update(counts)
    helpers=out/'helpers';helpers.mkdir()
    helper_sources=[]
    for path in (Path(__file__),Path(__file__).with_name('README_S6D_C_SUPPORT_PREPARE_V1.md'),Path(__file__).with_name('s6d_C_support_checks_v1.py'),Path(N.__file__),Path(P.__file__),Path(__file__).with_name('README_S6D_BEAM_EXECUTION_V1.md')):
        shutil.copyfile(path,helpers/path.name);helper_sources.append(bind(helpers/path.name))
    receipt=dict(status='INACTIVE_SUPPORT_PROPOSALS_ONLY',helpers=helper_sources,partition=cp_ref,clock=clock_ref,gallery=gallery_ref,enrollment_plan=enroll_ref,proposals=outputs,case_count=len(outputs),counts=dict(totals),original_event_measurements=sum(len(c['event_measurements']) for c in clock['cases']),actual_mature_windows_observed=0,physical_attempts_added=0,model_calls=0,root_review_required=True)
    save(out/'SUPPORT_PROPOSAL_RECEIPT.json',receipt);print(json.dumps(bind(out/'SUPPORT_PROPOSAL_RECEIPT.json')))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();prepare(a.output)
