"""Build bound explicit native panels. README_S6C_EXPLICIT_PANEL_JOBS_V1.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import s6c_orchestrator_scan_v3 as overlay

PANEL_SHA='f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da'
PAIR_IDS=(('C117','C118'),('C065','C079'),('C119','C120'),('C121','C122'),
          ('C123','C124'),('C125','C126'),('C127','C128'),('C129','C130'))
PAIR_MODES=('old_voice_gate','normalized_joint','reliability_joint','hypothesis_joint',
            'semimarkov_joint','bounded_global_joint','quarantine_joint','shadow_gallery_joint')


def select_cases(proposal,panel):
    key={'gate6':'family_native_gate_case_ids','paced16':'case_ids','repeat4':'repeated_case_ids'}[panel]
    cases=proposal[key];expected={'gate6':6,'paced16':16,'repeat4':4}[panel]
    if len(cases)!=expected or len(set(cases))!=expected or not set(cases)<=set(proposal['case_ids']):
        raise ValueError('Exact registered panel case set required')
    if proposal['streams']!=['O0','O1']:raise ValueError('Registered both-tap scope differs')
    return list(cases)


def select_profiles(spec,panel,candidates):
    gate=[p for pair in PAIR_IDS for p in pair]
    if panel=='gate6':
        if candidates is not None and (len(candidates)!=len(set(candidates)) or set(candidates)!=set(gate)):
            raise ValueError('Gate requires all exact eight cue-off/on pairs')
        ids=gate
    else:
        if not candidates or len(candidates)!=len(set(candidates)):raise ValueError('Paced panels require explicit unique selected candidate IDs')
        ids=list(candidates)
    profiles=[p for pid in ids for p in sorted((r for r in spec['profiles'] if r['candidate_id']==pid),key=lambda r:(r['asr_tap'],r['identity_tap']))]
    if {p['candidate_id'] for p in profiles}!=set(ids):raise ValueError('Unknown candidate requested')
    for pid in ids:
        rows=[p for p in profiles if p['candidate_id']==pid]
        if len(rows)!=2 or {p['asr_tap'] for p in rows}!={'O0','O1'}:raise ValueError('Each selected candidate must have both admitted ASR routes')
    if panel=='gate6':
        for pair,mode in zip(PAIR_IDS,PAIR_MODES):
            for tap in ('O0','O1'):
                off,on=[next(p for p in profiles if p['candidate_id']==pid and p['asr_tap']==tap) for pid in pair]
                for p in (off,on):
                    if p['recipe_id']!='N01' or p['gallery_condition']!='NONE' or p['route']!='SAME' or p['identity_tap']!=tap or p['profile']['tracker']['mode']!=mode:
                        raise ValueError('Registered native family mode/recipe/route differs')
                if off['cue_condition']!='CUES_OFF' or on['cue_condition']!='REAL_ALIGNED_CUES':raise ValueError('Gate cue pairing differs')
    return ids,profiles


def repetition_contract(panel,repetition):
    if type(repetition) is not int or not 1<=repetition<=4:raise ValueError('Repetition must be integer1..4')
    if panel in ('gate6','paced16') and repetition!=1:raise ValueError('Initial gate/full paced panel is repetition1')
    if panel=='repeat4' and repetition<2:raise ValueError('Repeat4 is a separately executed repetition2..4')


def make_manifest(spec_binding,spec,common,execution,proposal_binding,proposal,panel,candidates,attempt,repetition):
    if not attempt or not attempt.replace('_','').isalnum():raise ValueError('Simple attempt label required')
    repetition_contract(panel,repetition)
    cases=select_cases(proposal,panel);ids,profiles=select_profiles(spec,panel,candidates)
    canonical=common.verified(spec['scene_manifest'])
    if not set(cases)<={s['case_id'] for s in canonical['scenes']}:raise ValueError('Noncanonical panel source')
    assignments=common.verified(spec['gallery_index'])['rows'] if spec.get('gallery_index') else []
    variants={(r['case_id'],r['stream'],r['condition']):r['telemetry'] for r in common.verified(spec['cue_variant_index'])['rows']} if spec.get('cue_variant_index') else {}
    stage='explicit_'+panel;run_attempt=attempt+'_rep'+str(repetition);jobs=[]
    # Repeat4 reverses the fixed profile-route and case order. This is a declared
    # balancing operation, never a choice based on the preceding measurements.
    execution_profiles=list(reversed(profiles)) if repetition%2==0 else profiles
    execution_cases=list(reversed(cases)) if repetition%2==0 else cases
    for p in execution_profiles:
        for cid in execution_cases:
            gallery=None;telemetry=None
            if p['gallery_condition']!='NONE':
                found=[r for r in assignments if r['gallery_condition']==p['gallery_condition'] and r['enrollment_tier']==p['enrollment_tier'] and r.get('case_id') in (None,cid)]
                if len(found)!=1:raise ValueError('Exact registered gallery condition/tier/case assignment required')
                gallery=found[0]['manifest']
            if p['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES'):telemetry=variants[cid,p['asr_tap'],p['cue_condition']]
            jobs.append(execution.make_job(spec,p,cid,stage,panel!='gate6',run_attempt,gallery,telemetry))
    inputs={(r['case_id'],r['stream']):r for r in common.verified(spec['input_index'])['rows']}
    for job in jobs:execution.validate_job(spec,job,inputs,check_assets=False)
    if len({j['job_key'] for j in jobs})!=len(jobs):raise ValueError('Duplicate effective native jobs in one panel')
    return dict(schema='jp_s6c_native_jobs.v1',status='REGISTERED_EXACT_JOBS',stage=stage,epoch=spec['epoch'],attempt=run_attempt,
        jobs=jobs,requested=len(jobs),case_ids=cases,candidate_ids=ids,
        profile_routes=[dict(candidate_id=p['candidate_id'],stream=p['asr_tap'],identity_tap=p['identity_tap']) for p in profiles],
        execution_manifest=spec_binding,builder_source=overlay.binding(__file__),builder_readme=overlay.binding(Path(__file__).with_name('README_S6C_EXPLICIT_PANEL_JOBS_V1.md')),
        original_builder=next(b for b in spec['execution_files'] if Path(b['path']).name=='s6c_jobs.py'),
        overlay_sources=overlay.source_rows(),panel_proposal=proposal_binding,repetition=repetition,created_utc=common.utc(),
        panel_scope=panel,selection='Exact registered whole-capture case list and explicitly retained candidates; no scorer results read. Evaluator-only proposal metadata stays outside job identity/runtime inputs.',
        repeat_scope='Repetition is invocation metadata and output folder only; identical same-source native identity is deliberately retained across separately executed repeat manifests. No repeated job is duplicated inside one manifest.',
        execution_order='profile/route then case; even numbered repeat reverses both fixed lists',
        resource_contract=dict(max_workers=4 if panel=='gate6' else 1,inner_threads=1,paced=panel!='gate6'),hardware_invocations=0,models_executed_by_builder=0)


def load_proposal(common):
    b=overlay.binding(overlay.REPORT/'design/confirmation_plan_v1/PACED_PANEL_PROPOSAL_V1.json')
    if b['sha256']!=PANEL_SHA:raise ValueError('Explicit reviewed panel proposal changed')
    proposal=common.verified(b)
    if proposal['schema']!='jp_s6c_paced_panel_proposal.v1' or proposal['status']!='PROPOSED_NOT_EXECUTED':raise ValueError('Original prospective panel authority differs')
    return b,proposal


def build(args):
    sb,spec,common,execution=overlay.load_native(args.epoch);pb,proposal=load_proposal(common)
    result=make_manifest(sb,spec,common,execution,pb,proposal,args.panel,args.candidates,args.attempt,args.repetition)
    target=overlay.REPORT/'jobs'/spec['epoch']/(result['stage']+'_'+result['attempt']+'.json')
    if target.exists():
        old=common.read(target)
        if {k:v for k,v in old.items() if k!='created_utc'}!={k:v for k,v in result.items() if k!='created_utc'}:
            raise ValueError('Existing exact panel manifest differs; preserve and choose a new reviewed name')
    else:common.save(target,result,immutable=True)
    return dict(status='REGISTERED_EXACT_JOBS',binding=overlay.binding(target),jobs=result['requested'],candidates=len(result['candidate_ids']),cases=len(result['case_ids']),neural_invocations=0)


def fixtures(args):
    sb,spec,common,execution=overlay.load_native(args.epoch);pb,proposal=load_proposal(common);checks=[]
    assert len(select_cases(proposal,'gate6'))==6 and len(select_cases(proposal,'paced16'))==16 and len(select_cases(proposal,'repeat4'))==4
    checks.append('exact six/sixteen/four registered case counts')
    ids,profiles=select_profiles(spec,'gate6',None)
    assert len(ids)==16 and len(profiles)==32;checks.append('all eight actual registered mode/cue pairs and both taps')
    for bad in (ids[:-1],ids+[ids[0]],['wrong']):
        try:select_profiles(spec,'gate6',bad)
        except ValueError:checks.append('partial duplicate or substituted gate rejected')
        else:raise AssertionError('Gate altered')
    altered=deepcopy(proposal);altered['family_native_gate_case_ids'][0]='wrong'
    try:select_cases(altered,'gate6')
    except ValueError:checks.append('unregistered gate source rejected')
    else:raise AssertionError('Source altered')
    for panel,rep in [('gate6',2),('paced16',2),('repeat4',1),('repeat4',True)]:
        try:repetition_contract(panel,rep)
        except ValueError:checks.append('invalid repetition admission rejected')
        else:raise AssertionError('Repetition altered')
    # Actual original make_job/validate_job once per tap, with no model factory.
    inputs={(r['case_id'],r['stream']):r for r in common.verified(spec['input_index'])['rows']}
    for p in profiles[:2]:
        first=execution.make_job(spec,p,proposal['family_native_gate_case_ids'][0],'fixture',True,'rep1')
        repeated=execution.make_job(spec,p,proposal['family_native_gate_case_ids'][0],'fixture',True,'rep2')
        execution.validate_job(spec,first,inputs,check_assets=False);execution.validate_job(spec,repeated,inputs,check_assets=False)
        assert first['job_key']==repeated['job_key'] and first['identity']==repeated['identity'] and first['folder']!=repeated['folder']
    checks.append('original two-tap job validation; repeated identity exact with distinct folders')
    target=overlay.REPORT/'orchestration_review'/('EXPLICIT_PANEL_JOB_FIXTURES_'+args.attempt+'.json')
    common.save(target,dict(status='PASS',schema='jp_s6c_explicit_panel_fixtures.v1',checks=checks,native_epoch=sb,panel_proposal=pb,
        sources=[overlay.binding(__file__),overlay.binding(Path(__file__).with_name('README_S6C_EXPLICIT_PANEL_JOBS_V1.md'))],
        neural_invocations=0,scope='Profile/panel metadata guards and two-tap original job validation only. No job output folder, model or native worker created.'),immutable=True)
    return overlay.binding(target)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('build','test'));p.add_argument('--epoch',choices=tuple(overlay.TRUSTED_EPOCHS),default='epoch4')
    p.add_argument('--panel',choices=('gate6','paced16','repeat4'),default='gate6');p.add_argument('--candidates',nargs='+')
    p.add_argument('--attempt',default='v1');p.add_argument('--repetition',type=int,default=1);args=p.parse_args()
    print(json.dumps({'build':build,'test':fixtures}[args.mode](args),indent=2,allow_nan=False))

if __name__=='__main__':main()
