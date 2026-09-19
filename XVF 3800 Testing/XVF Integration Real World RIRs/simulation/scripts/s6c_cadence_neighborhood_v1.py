"""Four actual N07 due-floor neighbors; README_S6C_CADENCE_NEIGHBORHOOD_V1.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'
BASE=REPORT/'EFFECTIVE_PROFILE_REGISTRY_V5.json'
BASE_SHA='15e7b1e2b4ca93d0f8c1cf3c47fa46456396e1263145ae1b3c453e8a4a35b5ab'
EPOCH_SHA='720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945'
AUDIT_SHA='96f9b5d604001f740543dc98945e8ad6f31b30aa137687e973bb9aec77779e4d'
ADDITIONS=(('C191','C071',.5),('C192','C082',.5),('C193','C071',2.),('C194','C082',2.))

def utc():return datetime.now(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def bind(path,expected=None):
    p=Path(path).resolve();raw=p.read_bytes();b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if expected is not None and b['sha256']!=expected:raise ValueError('Expected source bytes differ: '+str(p))
    return b
def read(path,expected=None):
    p=Path(path).resolve();raw=p.read_bytes();b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if expected is not None and b['sha256']!=expected:raise ValueError('Expected source bytes differ: '+str(p))
    return json.loads(raw.decode('utf-8-sig')),b
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);raw=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return dict(path=str(path.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def api():
    epoch,eb=read(REPORT/'EPOCH4_EXECUTION_MANIFEST.json',EPOCH_SHA)
    root=Path(epoch['root'])/'app'
    bindings=[b for b in epoch['execution_files'] if root in Path(b['path']).parents]
    if len(bindings)!=29:raise ValueError('Exact original29 APP modules required')
    for b in bindings:
        if bind(b['path'])!=b:raise ValueError('Frozen APP bytes changed')
    if 'edge_speech_pipeline' in sys.modules:raise ValueError('APP preloaded before frozen admission')
    sys.path.insert(0,str(root))
    from edge_speech_pipeline.research_profiles import ResearchProfile
    from edge_speech_pipeline.research_evidence_v3 import EvidenceAdmissionV3
    return ResearchProfile,EvidenceAdmissionV3,eb,bindings

def changed_profile(parent,candidate,floor,Profile):
    value=deepcopy(parent['profile']);value['profile_id']=candidate+'_'+parent['asr_tap']+'_'+parent['identity_tap'];value['embedding']['voice_observation_floor_sec']=floor
    profile=Profile.from_dict(value)
    if profile.to_dict()!=value:raise ValueError('Profile API normalized an unplanned change')
    normalized=deepcopy(value);normalized['profile_id']=parent['profile']['profile_id'];normalized['embedding']['voice_observation_floor_sec']=1.
    if normalized!=parent['profile'] or parent['profile']['embedding']['voice_observation_floor_sec']!=1.:raise ValueError('Only declared floor/profile ID may change')
    if profile.embedding.cadence_policy!='uncertainty' or parent['neural_dependency']!='FULL_PROFILE_AND_CUES':raise ValueError('Actual N07 native policy dependency required')
    return profile

def due_checks(base,Profile,Admission):
    import numpy as np
    parent=next(r for r in base['profiles'] if r['candidate_id']=='C071' and r['asr_tap']=='O0')
    roll=np.full(48000,.1,dtype=np.float32);block=roll[:4000];vector=np.zeros(256,dtype=np.float32);vector[0]=1.
    count=0;rows=[]
    for floor in (.5,1.,2.):
        p=changed_profile(parent,'FIXTURE',floor,Profile);a=Admission(p);a.clean=[(0.,30.)];a.previous_speech=True
        context=[dict(track_id=7,state='provisional',unique_clean_sec=.25,disjoint_count=1),dict(track_id=9,state='unresolved',unique_clean_sec=0.,disjoint_count=0)]
        initial=a.candidates(roll,block,3.,True,False,tracking_context=context)
        assert all(d['due'] for d in initial[0]['track_debts']);count+=1
        a.admitted('short',vector,3.,initial[0])
        assert a.last_track_admission=={7:3.,9:3.};count+=1
        before=a.candidates(roll,block,3.+floor-.25,True,False,tracking_context=context)
        assert not any(d['due'] for d in before[0]['track_debts']);count+=1
        assert all(d['selected_hop_sec']==1. for d in before);count+=1
        exact=a.candidates(roll,block,3.+floor,True,False,tracking_context=context)
        assert all(d['due'] for d in exact[0]['track_debts']);count+=1
        assert [d['selected_hop_sec'] for d in exact]==[.25,.5];count+=1
        a.admitted('short',vector,3.+floor,exact[0])
        assert a.last_track_admission=={7:3.+floor,9:3.+floor};count+=1
        # Rejection alone cannot acknowledge debt; a fresh unresolved third
        # track remains due until an admitted window is explicitly reported.
        blocked_context=[dict(track_id=11,state='unresolved',unique_clean_sec=0.,disjoint_count=0)]
        ledger=deepcopy(a.last_track_admission)
        denied=a.candidates(roll,block,7.+floor,False,False,tracking_context=blocked_context)
        assert all(not d['admitted'] and d['reason']=='no_speech_gate' for d in denied) and a.last_track_admission==ledger;count+=1
        mature=[dict(track_id=12,state='committed',unique_clean_sec=3.,disjoint_count=3)]
        a.previous_speech=True
        settled=a.candidates(roll,block,10.+floor,True,False,tracking_context=mature)
        assert not settled[0]['track_debts'];count+=1
        rows.append(dict(floor_sec=floor,initial_due=initial[0]['track_debts'],before_boundary_hops=[d['selected_hop_sec'] for d in before],
            at_boundary_hops=[d['selected_hop_sec'] for d in exact],all_due_entries_acknowledged=a.last_track_admission,
            scope='Functional real admission policy with synthetic acoustic vectors/support/context; no neural model. The global accepted window acknowledges all due ledger entries, without proving any named debtor spoke.'))
    return dict(status='PASS_ACTUAL_ADMISSION_POLICY_MODEL_FREE',checks=count,rows=rows,model_calls=0)

def register():
    targets=[REPORT/'EFFECTIVE_PROFILE_REGISTRY_V6.json',REPORT/'design/CADENCE_FLOOR_NEIGHBORHOOD_V1.json',REPORT/'cadence_neighborhood_v1/DUE_LEDGER_CHECKS.json']
    if any(p.exists() for p in targets):raise ValueError('Preserve prior neighborhood registration; no overwrite')
    base,bb=read(BASE,BASE_SHA);design,db=read(REPORT/'design/REGISTERED_DESIGN_V1.json');audit,ab=read(REPORT/'cadence_audit_v1/RESULT.json',AUDIT_SHA)
    if audit['status']!='COMPLETE_336_BOUND_NATIVE_CELLS':raise ValueError('Actual motivating cadence audit incomplete')
    Profile,Admission,eb,app=api();fixtures=due_checks(base,Profile,Admission)
    fb=save(targets[2],dict(**fixtures,epoch=eb,source=bind(__file__),app_sources=app,readme=bind(Path(__file__).with_name('README_S6C_CADENCE_NEIGHBORHOOD_V1.md'))))
    definitions={c['candidate_id']:c for c in design['candidates']};additions=[];newrows=[]
    for cid,parent_id,floor in ADDITIONS:
        definition=deepcopy(definitions[parent_id]);definition.update(candidate_id=cid,parent=parent_id,title=f'N07 due-ledger floor {floor:g}s '+definition['settings']['cue_condition'],family='cadence_floor_neighborhood',disposition='OUTCOME_INFORMED_REGISTERED_NOT_YET_EXECUTED')
        definition['settings']['embedding_override']={'voice_observation_floor_sec':floor};definition['settings_sha256']=digest(definition['settings'])
        definition['effective_profile_changes']={'embedding.voice_observation_floor_sec':floor};additions.append(definition)
        for tap in ('O0','O1'):
            parent=next(r for r in base['profiles'] if r['candidate_id']==parent_id and r['asr_tap']==tap and r['identity_tap']==tap)
            p=changed_profile(parent,cid,floor,Profile);value=p.to_dict();path=REPORT/'profiles'/cid/(tap+'_ASR_'+tap+'_ID.json')
            pb=save(path,value);row=deepcopy(parent)
            row.update(candidate_id=cid,parent=parent_id,family='cadence_floor_neighborhood',profile=value,profile_binding=pb,profile_digest=p.digest(),field_usage=p.field_usage(),tracker_field_usage=p.tracker.field_usage(),
                effective_key=digest(dict(profile=value,cue=row['cue_condition'],gallery=row['gallery_condition'],tier=row['enrollment_tier'])))
            newrows.append(row)
    amendment=dict(schema='jp_s6c_cadence_floor_neighborhood.v1',status='REGISTERED_BEFORE_NEW_NATIVE_EXECUTION',created_utc=utc(),parent_design=db,parent_registry=bb,source=bind(__file__),
        candidates=additions,additional_configurations=4,total_registered_configurations=238,motivating_results=[ab],functional_due_ledger_checks=fb,
        chronology='Outcome-informed after the actual336-cell N01/N07 cadence audit. Existing1.0second parents retained. Not a pristine preregistration or held-out evaluation.',
        exact_changes='Only executable profile_id and embedding.voice_observation_floor_sec (.5 or2.0) differ from C071 off/C082 real. Original continuous ASR, cue delivery, tracker/name/lifecycle and all other settings/weights stay exact.',
        compiler_scope='Dedicated additive compiler applies the declared embedding_override to exact frozen parent profiles. The old generic make_profile does not compile this extension; native jobs consume the bound effective profiles directly.',
        planned_native_cells=448,panel_cases=56,asr_identity_routes=['O0/O0','O1/O1'],dependency='FULL_PROFILE_AND_CUES; native contexts cannot be substituted from another parent/cue/floor policy.',
        semantic_limit='voice_observation_floor_sec controls when each unresolved/provisional/debt entry becomes due. An accepted global acoustic window acknowledges every due ledger entry; this does not select a debtor or establish that debtor voice evidence was delivered. Other onset/cosine/cue triggers and sparse admission remain operative.',
        no_new_model_families_or_weights=True,no_hardware_launch=True)
    amendment_binding=save(targets[1],amendment)
    for row in newrows:row['cadence_registration']=amendment_binding
    rows=deepcopy(base['profiles'])+newrows
    if len(rows)!=384 or len({r['candidate_id'] for r in rows})!=194 or rows[:376]!=base['profiles']:raise ValueError('Additive registry count or original-row preservation failed')
    registry=deepcopy(base);registry.update(profiles=rows,candidate_count=194,effective_route_count=384,parent_registry=bb,cadence_registration=amendment_binding,source=bind(__file__))
    result=save(targets[0],registry)
    print(json.dumps(dict(status='REGISTERED_VALIDATED_NOT_EXECUTED',registry=result,amendment=amendment_binding,checks=fb,total_labels=238,new_native_jobs=448,new_model_calls=0),indent=2))

def jobs():
    import s6c_orchestrator_scan_v4 as overlay
    eb,spec,common,execution=overlay.load_native('epoch5')
    registry=common.verified(spec['effective_profile_registry'])
    if registry['candidate_count']!=194 or len(registry['profiles'])!=384:raise ValueError('Epoch5 must bind exact cadence registry')
    profiles=[p for p in spec['profiles'] if p['candidate_id'] in {r[0] for r in ADDITIONS}]
    cases=sorted(common.verified(spec['panel'])['case_ids'])
    if len(profiles)!=8 or len(cases)!=56:raise ValueError('Exact four-candidate/two-tap56-case panel required')
    inputs={(r['case_id'],r['stream']):r for r in common.verified(spec['input_index'])['rows']}
    output=[]
    for p in profiles:
        for case in cases:
            job=execution.make_job(spec,p,case,'cadence_floor',False,'v1')
            execution.validate_job(spec,job,inputs,check_assets=False);output.append(job)
    value=dict(schema='jp_s6c_native_jobs.v1',status='REGISTERED_EXACT_JOBS',stage='cadence_floor',epoch='epoch5',attempt='v1',jobs=output,requested=448,case_ids=cases,
        candidate_ids=[r[0] for r in ADDITIONS],profile_routes=[dict(candidate_id=p['candidate_id'],stream=p['asr_tap'],identity_tap=p['identity_tap']) for p in profiles],
        execution_manifest=eb,builder_source=bind(__file__),created_utc=utc(),cadence_registration=registry['cadence_registration'],selection='Exact registered four due-floor neighbors ×56 original panel cases ×both same-tap routes; no outcome-specific case selection.')
    result=save(REPORT/'jobs/epoch5/cadence_floor_v1.json',value)
    print(json.dumps(dict(status='PREPARED_NO_MODELS_STARTED',manifest=result,jobs=len(output)),indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);parser.add_argument('action',choices=('register','jobs'));args=parser.parse_args()
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    sys.dont_write_bytecode=True
    {'register':register,'jobs':jobs}[args.action]()
