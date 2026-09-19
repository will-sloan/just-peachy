"""Issue reviewed conservative C support only; see README_S6D_ADOPT_C_SUPPORT_V1.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'
PREP=R/'physical_C_support_final_preparation_v1'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def bind(path):
    path=Path(path);data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def need(value,message):
    if not value:raise ValueError(message)

def verify_binding(ref):
    need(bind(ref['path'])==ref,'Changed binding: '+ref['path'])
    return ref

def verify(ref):
    verify_binding(ref)
    return read(ref['path'])

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=R/'physical_C_support_adopted_v1')
    args=parser.parse_args();out=args.output.resolve()
    need(out.parent==R.resolve() and not out.exists(),'Fresh direct campaign report child required')
    pr=bind(PREP/'PREPARATION_RECEIPT.json');prop=bind(PREP/'ROOT_ACCEPTANCE_PROPOSAL.json')
    need(pr['sha256']=='abe966c7065bb9c6358b74d86f921f9250909035c026c08c31a2d24b68422b4c','Exact preparation receipt required')
    need(prop['sha256']=='3b9d693b0bcad976c5a0b456987c52b6a4d3adc051b73abe6fba64e9307ded2a','Exact concrete root proposal required')
    prep=verify(pr);proposal=verify(prop)
    need(proposal['status']=='PROPOSAL_NOT_ISSUED_NO_AUTHORITY','Preparation must not be an existing authority')
    receipt=deepcopy(proposal['proposed_receipt'])
    need(receipt['owner_thread_id']=='01a0812d-3ff0-7ed0-a06c-4df61b62a459' and receipt['Q_used'] is False and receipt['disjoint_from_E_Q_verified'] is True,'Exact root/run C-only authority required')
    for ref in receipt['basis'].values():verify_binding(ref)
    need(prep['counts']==dict(cases=12,original_timing_measurements=138,pre_eroded_interiors=128,ambiguity_exclusions=120,short_exclusions=4,actual_gallery_profiles=15,original_C_source_ids=30,member_C_source_ids=15,nonmember_C_source_ids=15,nonmember_interiors=62,actual_mature_windows_observed=0),'Reviewed exact support counts required')
    helper=prep['calibration_helper'];verify_binding(helper)
    need(helper['sha256']=='9ebf3a4976ae7db0de78c982a4216b6220d86e5a82dead62a9502682f93c08fc','Accepted calibration V2 helper required')
    sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(helper['path']).parent))
    spec=importlib.util.spec_from_file_location('root_C_support_calibration_v2',helper['path'])
    cal=importlib.util.module_from_spec(spec);spec.loader.exec_module(cal)
    ready=verify(prep['metadata_readiness']);manifest_ref=ready['bindings']['manifest'];manifest=verify(manifest_ref)
    jobs={j['job_id']:j for j in manifest['jobs']}
    need(len(jobs)==len(prep['cases'])==len(receipt['acceptances'])==12,'Exact12 unique collection jobs and support rows required')
    pending=[]
    for row in prep['cases']:
        support=verify(row['final_unissued_payload']);old=verify(row['old_proposal'])
        expected=deepcopy(old);expected['status']='ROOT_ACCEPTED_CONSERVATIVE_SOURCE_SUPPORT'
        need(support==expected and support['root_acceptance'] is None,'Only reviewed final status may differ from original support')
        need(cal.payload_digest(support)==row['support_payload_sha256'],'Final canonical payload differs')
        job=jobs[row['job_id']];admission=verify(job['admission']);partition=verify(admission['calibration_partition'])
        partition_ref=partition['original_partition'];base=verify(partition_ref)
        need(support['case_result']==admission['original_case_result'] and support['partition']==partition_ref and support['gallery']==job['gallery'],'Actual job/case/partition/gallery mismatch')
        target=dict(case_result=support['case_result'],partition=partition_ref,gallery=job['gallery'],support_payload_sha256=cal.payload_digest(support),C_source_ids=sorted({s['source_id'] for s in support['spans']}))
        need(sum(x==target for x in receipt['acceptances'])==1,'Exactly one reviewed root acceptance target required')
        for span in support['spans']:
            b=[span[k] for k in ('start_min','start_max','stop_min','stop_max')]
            need(all(type(x) is int for x in b) and 0<=b[0]<=b[1]<b[2]<=b[3]<=job['expected_frames'],'Conservative span outside admitted full capture')
        pending.append((row,support,admission,partition_ref,base,job))
    receipt.update(utc=datetime.now(timezone.utc).isoformat(),root_review=dict(preparation=pr,proposal=prop,
        source=bind(__file__),readme=bind(Path(__file__).with_name('README_S6D_ADOPT_C_SUPPORT_V1.md')),
        findings=[
            'Root reviewed all12 concrete acceptance records, final-status payload rules, original case/partition/A15 joins and preserved timing limitations.',
            'The138 original timing measurements yield128 possible pre-eroded source interiors, not observed model opportunities.120 ambiguous and4 short exclusions remain unchanged.',
            'Original30 C source rows remain disjoint from E/Q;15 enrolled and15 nonmember speakers, including62 null-profile fragments, are preserved. No source audio or model vectors were reread.',
            'Authority grants conservative eligible source support only. No exact focus delay, source survival, separation, unique auto-to-focus target, threshold or runtime hint is established.',
            'Actual12 native closures and whole mature clean candidate windows remain required for V2 extraction; joint disjoint positive/negative/competition support and later exact-context calibration authority remain separate.'
        ]))
    save(out/'ROOT_ACCEPTANCE.json',receipt);root_ref=bind(out/'ROOT_ACCEPTANCE.json')
    records=[]
    for row,support,admission,partition_ref,base,job in pending:
        support['root_acceptance']=root_ref
        need(cal.payload_digest(support)==row['support_payload_sha256'],'Root binding insertion changed payload digest')
        path=out/(row['attempt_id']+'_SUPPORT.json');save(path,support)
        target=cal.require_support_authority(read(path),admission,partition_ref,base,job['gallery'])
        need(target in receipt['acceptances'],'Actual frozen V2 authority predicate failed')
        records.append(dict(attempt_id=row['attempt_id'],case_id=row['case_id'],capture_profile=row['capture_profile'],job_id=row['job_id'],
            source_payload=row['final_unissued_payload'],support=bind(path),support_payload_sha256=target['support_payload_sha256'],
            interiors=row['interiors'],exclusions=row['exclusions'],C_source_ids=target['C_source_ids'],actual_frozen_V2_authority_predicate='PASS'))
    save(out/'SUPPORT_CATALOG.json',dict(schema='s6d-root-adopted-C-support-catalog.v1',status='ROOT_ACCEPTED_CONSERVATIVE_SUPPORT_ONLY',
        utc=datetime.now(timezone.utc).isoformat(),root_acceptance=root_ref,preparation=pr,calibration_helper=helper,collection_manifest=manifest_ref,
        cases=records,counts=prep['counts'],actual_features_extracted=False,actual_model_calls=0,hardware_calls=0,actual_thresholds_accepted=False))
    print(json.dumps(dict(status='ROOT_ACCEPTED_CONSERVATIVE_SUPPORT_ONLY',root_acceptance=root_ref,catalog=bind(out/'SUPPORT_CATALOG.json'),cases=12)))

if __name__=='__main__':main()
