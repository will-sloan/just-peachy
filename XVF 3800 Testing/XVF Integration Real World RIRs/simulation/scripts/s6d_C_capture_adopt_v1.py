"""Materialize root-authorized12 C collection metadata only; see README_S6D_C_CAPTURE_ADOPT_V1.md."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import json
import s6d_beam_native_run_v1 as N
import s6d_beam_execution_prepare_v1 as P

ROOT_SHA='87721aa36ce5cf5e00f1060bf134f08e052798d1f686a5cc101dd65130bf8550'
FREEZE_SHA='f3b0a5942b7726a560bfbae0a5d4d01d13994bfa549c695cb93e7f528c280c4e'
SCOPE='Collection only: exact verified route/common decoded frame origin and observed guard-tail adequacy. Not exact per-focus DSP delay, every-event source survival, speaker identity, clean separation or level guarantee.'

def adopt(output):
    out=Path(output).resolve();N.need(out.parent==P.R and not out.exists(),'Fresh report-root C admission directory required')
    root_ref=N.bind(P.R/'physical_qualification_review_v1/ROOT_PHYSICAL_QUALIFICATION_V1.json');N.need(root_ref['sha256']==ROOT_SHA,'Exact root acceptance changed');root=N.verified(root_ref)
    N.need(root.get('status')=='ROOT_ACCEPTED_PHYSICAL_QUALIFICATION_WITH_LIMITATIONS' and root.get('routes_reviewed') is True and root.get('processed_tail_reviewed') is True and root.get('owners_closed_and_restored') is True,'Root physical gates absent')
    freeze_ref=N.bind(P.R/'physical_route_proposals_v1/SOURCE_FREEZE_V1.json');N.need(freeze_ref['sha256']==FREEZE_SHA,'Exact inactive proposal freeze changed');freeze=N.verified(freeze_ref)
    bound={Path(b['path']).name:b for b in freeze['files']}
    cp_ref=bound['C_CALIBRATION_PARTITION_PROPOSAL.json'];cp=N.verified(cp_ref);candidates=cp['candidate_case_results']
    case_refs=[candidate['case_result'] for candidate in candidates]
    N.need(len(candidates)==len({b['sha256'] for b in case_refs})==12 and cp['accepted_case_results']==[],'Exactly12 unadopted C candidates required')
    N.need(cp.get('partition')=='C' and cp.get('Q_used') is False and cp.get('disjoint_from_E_Q_verified') is True,'Original disjoint C partition missing')
    accepted_root_bindings={b['path']:b for b in root['evidence_bindings']}
    out.mkdir();routes=out/'routes';routes.mkdir();rows=[];accepted_routes=[];sources=[]
    for candidate in candidates:
        case_ref=candidate['case_result']
        case=N.verified(case_ref);attempt=case['attempt'];case_id=attempt['case_id'];profile=attempt['profile'];attempt_id=attempt['attempt_id']
        N.need((candidate['case_id'],candidate['profile'],candidate['attempt_id'],candidate['source_audio'])==(case_id,profile,attempt_id,attempt['source_audio']),'Candidate identity differs from original case')
        N.validate_original_identity(case,case_id,profile)
        q_ref=bound[attempt_id+'_ROUTE_QUALIFICATION_PROPOSAL.json'];N.need(q_ref==candidate['route_qualification_proposal'],'Candidate route binding differs');q=N.verified(q_ref)
        N.need(q.get('status')=='PROPOSAL_PENDING_ROOT_ACCEPTANCE' and q['case_result']==case_ref and q['configuration']==case['configuration'],'Proposal original identity differs')
        N.need(case.get('status')==case.get('transport_integrity_status')=='PASS','Original transport rejected')
        tail=q['tail_and_route_evidence'];N.verified(tail)
        N.need(tail['path'] in accepted_root_bindings and tail==accepted_root_bindings[tail['path']],'Per-case route/tail evidence outside exact root acceptance')
        N.need(q['source_audio']==attempt['source_audio'] and q['stream_names']==[s['name'] for s in case['streams']],'Original source/stream names differ')
        actual=deepcopy(q);actual.update(status='PASS',stream_identity_verified=True,common_frame_origin_verified=True,source_tail_validity_verified=True,root_review_required=False,root_acceptance=root_ref,original_proposal=q_ref,collection_only=True,verification_scope=SCOPE,exact_per_focus_DSP_delay_proven=False,every_source_event_survived_proven=False,identity_or_level_guarantee=False,gold_time_projection_admitted=False,selector_thresholds_admitted=False,root_limitations=root['limitations'])
        path=routes/(attempt_id+'_ROUTE_QUALIFICATION.json');N.save(path,actual);qb=N.bind(path);accepted_routes.append(qb)
        rows.append(dict(case_id=case_id,capture_profile=profile,attempt_id=attempt_id,case_result=case_ref,qualification=qb));sources.extend([case_ref,q_ref,tail])
    actual_cp=deepcopy(cp);actual_cp.update(status='ROOT_ACCEPTED_CAPTURED_C_FOR_COLLECTION_ONLY',acquisition_status='ACTUAL12_CASES_ROOT_ROUTE_ACCEPTED',accepted_case_results=case_refs,root_accepted_route_qualifications=accepted_routes,original_proposal=cp_ref,root_acceptance=root_ref,collection_only=True,verification_scope=SCOPE,gold_time_projection_admitted=False,selector_thresholds_admitted=False)
    cp_path=out/'C_CALIBRATION_PARTITION.json';N.save(cp_path,actual_cp);cp_bound=N.bind(cp_path)
    for row in rows:row['calibration_partition']=cp_bound
    catalog=dict(schema='s6d-native-capture-catalog.v1',status='ROOT_ACCEPTED_CASES',created_utc=datetime.now(timezone.utc).isoformat(),scope=SCOPE,collection_only=True,permitted_modes=['calibration_collection'],root_acceptance=root_ref,original_proposal_freeze=freeze_ref,rows=rows,case_count=12,physical_passes_created=0,model_calls=0,gold_time_projection_admitted=False,selector_thresholds_admitted=False)
    N.save(out/'CAPTURE_CATALOG.json',catalog)
    N.save(out/'ADOPTION_RECEIPT.json',dict(status='ROOT_AUTHORIZED_METADATA_MATERIALIZED_COLLECTION_ONLY',source=N.bind(__file__),readme=N.bind(Path(__file__).with_name('README_S6D_C_CAPTURE_ADOPT_V1.md')),root_acceptance=root_ref,proposal_freeze=freeze_ref,partition=cp_bound,catalog=N.bind(out/'CAPTURE_CATALOG.json'),routes=accepted_routes,original_sources=sources,root_instruction='Root explicitly authorized materializing exactly12 proposed C-case route/catalog/partition records for collection only; original proposal/case bytes remain unchanged.',scope=SCOPE,models_started=0,hardware_calls=0,actual_capture_attempts_added=0))
    print(json.dumps(N.bind(out/'ADOPTION_RECEIPT.json')))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();adopt(a.output)
