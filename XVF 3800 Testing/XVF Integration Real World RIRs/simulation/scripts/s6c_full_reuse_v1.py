"""Build full native grids preserving exact prior jobs. README_S6C_FULL_REUSE_V1.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
from s6c_orchestrator_scan_v2 import load_native,binding,REPORT,SIM


def select_job(expected,existing):
    prior=existing.get(expected['job_key'])
    if prior is None:return expected,'NEW_FULL_JOB'
    if {k:v for k,v in prior.items() if k!='folder'}!={k:v for k,v in expected.items() if k!='folder'}:
        raise ValueError('Same native key has conflicting top-level job fields')
    # Preserve every old field, especially the receipt-bearing folder. Never
    # move/copy native outputs or relabel a prior receipt as a fresh invocation.
    return deepcopy(prior),'EXACT_SOURCE_JOB'


def check_prior_grid(manifest,spec_binding):
    if manifest.get('schema')!='jp_s6c_native_jobs.v1' or manifest.get('status')!='REGISTERED_EXACT_JOBS' or manifest['execution_manifest']!=spec_binding:
        raise ValueError('Prior manifest must bind exact original native epoch2')
    if len(manifest['jobs'])!=manifest['requested'] or len({j['job_key'] for j in manifest['jobs']})!=len(manifest['jobs']):
        raise ValueError('Prior native grid has missing or duplicate keys')


def sources():
    return [binding(Path(__file__).with_name(name)) for name in ('s6c_full_reuse_v1.py','README_S6C_FULL_REUSE_V1.md','s6c_orchestrator_scan_v2.py')]


def fixtures(common,spec_binding,name):
    expected=dict(job_key='k',identity={'audio':'a'},case_id='x',candidate_id='C',folder='new_full')
    prior={**expected,'folder':'old_panel'};checks=[]
    job,origin=select_job(expected,{'k':prior})
    assert job==prior and job['folder']=='old_panel' and origin=='EXACT_SOURCE_JOB';checks.append('same native key preserves exact old job and folder')
    job['identity']['audio']='changed';assert prior['identity']['audio']=='a';checks.append('selected manifest copy cannot mutate original job object')
    job,origin=select_job(expected,{})
    assert job==expected and origin=='NEW_FULL_JOB';checks.append('absent key creates only intended new full job')
    for change in ({'case_id':'other'},{'candidate_id':'different'},{'identity':{'audio':'changed'}}):
        try:select_job(expected,{'k':{**prior,**change}})
        except ValueError:pass
        else:raise AssertionError('Conflicting same-key job metadata accepted')
    checks.append('same-key route/case/identity mismatches reject')
    m=dict(schema='jp_s6c_native_jobs.v1',status='REGISTERED_EXACT_JOBS',execution_manifest=spec_binding,requested=2,jobs=[expected,expected])
    try:check_prior_grid(m,spec_binding)
    except ValueError:checks.append('duplicate prior manifest keys reject')
    else:raise AssertionError('Duplicate source keys accepted')
    result=dict(schema='jp_s6c_full_reuse_checks.v1',status='PASS',sources=sources(),checks=checks,neural_invocations=0)
    path=REPORT/'orchestration_review'/('FULL_REUSE_FIXTURES_'+name+'.json');common.save(path,result,immutable=True)
    return binding(path)


def build(args,spec_binding,spec,common,execution):
    source_path=args.source_manifest.resolve();source_binding=binding(source_path);source=common.verified(source_binding)
    check_prior_grid(source,spec_binding);existing={j['job_key']:j for j in source['jobs']}
    candidates=set(args.candidates)
    if len(candidates)!=len(args.candidates):raise ValueError('Explicit unique retained candidates required')
    profiles=[p for p in spec['profiles'] if p['candidate_id'] in candidates]
    if {p['candidate_id'] for p in profiles}!=candidates:raise ValueError('Unknown retained candidate')
    cases=sorted(s['case_id'] for s in common.verified(spec['scene_manifest'])['scenes'])
    if len(cases)!=240 or len(set(cases))!=240:raise ValueError('Exact canonical240 bank required')
    inputs={(r['case_id'],r['stream']):r for r in common.verified(spec['input_index'])['rows']}
    galleries=common.verified(spec['gallery_index'])['rows'] if spec.get('gallery_index') else []
    variants={(r['case_id'],r['stream'],r['condition']):r['telemetry'] for r in common.verified(spec['cue_variant_index'])['rows']} if spec.get('cue_variant_index') else {}
    jobs=[];ledger=[]
    for profile in sorted(profiles,key=lambda p:(p['candidate_id'],p['asr_tap'],p['identity_tap'])):
        for case in cases:
            gallery=telemetry=None
            if profile['gallery_condition']!='NONE':
                matched=[r for r in galleries if r['gallery_condition']==profile['gallery_condition'] and r['enrollment_tier']==profile['enrollment_tier'] and r.get('case_id') in (None,case)]
                if len(matched)!=1:raise ValueError('Exactly assigned gallery required')
                gallery=matched[0]['manifest']
            if profile['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES'):
                telemetry=variants[case,profile['asr_tap'],profile['cue_condition']]
            expected=execution.make_job(spec,profile,case,'full',False,args.attempt,gallery,telemetry)
            job,origin=select_job(expected,existing)
            execution.validate_job(spec,job,inputs,check_assets=False)
            cached=execution.verify_job(job)
            if cached is None and (Path(job['folder'])/'attempt_receipt.json').exists():
                raise ValueError('Prior incomplete/failed attempt requires diagnosed named retry: '+job['folder'])
            status='COMPLETE_VERIFIED_REUSABLE' if cached else 'MISSING_REQUIRES_NATIVE'
            ledger.append(dict(job_key=job['job_key'],candidate_id=job['candidate_id'],case_id=case,asr_tap=job['asr_tap'],identity_tap=job['identity_tap'],
                origin=origin,status=status,selected_folder=job['folder'],unused_new_full_folder=expected['folder'] if origin=='EXACT_SOURCE_JOB' else None,
                complete_receipt=cached['receipt'] if cached else None))
            jobs.append(job)
    if len({j['job_key'] for j in jobs})!=len(jobs):raise ValueError('Duplicate final native job key')
    completed=sum(r['status']=='COMPLETE_VERIFIED_REUSABLE' for r in ledger);missing=len(jobs)-completed
    if args.expected_completed is not None and completed!=args.expected_completed:raise ValueError('Verified completed count differs from explicit expected count')
    if args.expected_new is not None and missing!=args.expected_new:raise ValueError('Missing native count differs from explicit expected count')
    target=REPORT/'jobs/epoch2'/('full_reuse_'+args.name+'.json')
    if target.exists():raise ValueError('Preserve prior full manifest; choose a fresh name')
    ledger_path=REPORT/'orchestration_review'/('FULL_REUSE_LEDGER_'+args.name+'.json')
    data=dict(schema='jp_s6c_full_reuse_admission.v1',status='VALIDATED_EXACT_NATIVE_JOBS',utc=common.utc(),source_manifest=source_binding,
        execution_manifest=spec_binding,builder_sources=sources(),requested=len(jobs),completed_verified=completed,missing_native=missing,
        exact_source_objects=sum(r['origin']=='EXACT_SOURCE_JOB' for r in ledger),new_full_objects=sum(r['origin']=='NEW_FULL_JOB' for r in ledger),rows=ledger,
        scope='All job identities and input/asset/receipt/native artifact hashes verified by unchanged frozen epoch2 functions. Prior output folders/receipts are retained exactly; no native files copied or rewritten. Verification is repeated at actual run admission. This is a full-grid manifest, not full inference completion.')
    common.save(ledger_path,data,immutable=True)
    manifest=dict(schema='jp_s6c_native_jobs.v1',status='REGISTERED_EXACT_JOBS',stage='full',epoch='epoch2',attempt=args.attempt,
        jobs=jobs,requested=len(jobs),case_ids=cases,candidate_ids=sorted(candidates),
        profile_routes=[dict(candidate_id=p['candidate_id'],stream=p['asr_tap'],identity_tap=p['identity_tap']) for p in sorted(profiles,key=lambda p:(p['candidate_id'],p['asr_tap'],p['identity_tap']))],
        execution_manifest=spec_binding,builder_source=binding(__file__),created_utc=common.utc(),reuse_admission=binding(ledger_path),
        selection='Explicit retained candidates over all240 cases; exact prior source job objects/folders selected by unchanged full native identity. Only missing job keys need inference.')
    common.save(target,manifest,immutable=True)
    return dict(manifest=binding(target),reuse_ledger=binding(ledger_path),requested=len(jobs),completed_verified=completed,missing_native=missing,neural_invocations=0)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--test',action='store_true');p.add_argument('--source-manifest',type=Path);p.add_argument('--candidates',nargs='+')
    p.add_argument('--name',default='v1');p.add_argument('--attempt',default='v1');p.add_argument('--expected-completed',type=int);p.add_argument('--expected-new',type=int)
    args=p.parse_args()
    if any(not value.replace('_','').isalnum() for value in (args.name,args.attempt)):p.error('Simple unique name/attempt required')
    if not args.test and (args.source_manifest is None or not args.candidates):p.error('Build requires source manifest and explicit retained candidates')
    spec_binding,spec,common,execution=load_native()
    result=fixtures(common,spec_binding,args.name) if args.test else build(args,spec_binding,spec,common,execution)
    print(json.dumps(result,indent=2,allow_nan=False),flush=True)


if __name__=='__main__':main()
