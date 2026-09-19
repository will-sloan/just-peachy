"""Bounded fresh-evidence followups. README_S6C_FRESH_FOLLOWUP_DESIGN.md."""
from copy import deepcopy
import sys
from s6c_common import *
from s6c_profiles import make_profile

def register():
    base_path=REPORT/'EFFECTIVE_PROFILE_REGISTRY_V4.json'
    base=verified(bind(base_path,'8e5f164e0caeefd40ecdeefef1fce61a17893ef2e5d2b50243e22f67085d5a6d'))
    design=read(REPORT/'design/REGISTERED_DESIGN_V1.json')
    rescue=read(REPORT/'design/ADMISSION_AND_FAMILY_RESCUE_V1.json')
    definitions={c['candidate_id']:c for c in design['candidates']+rescue['candidates']}
    recipes={r['recipe_id']:r for r in design['recipes']};additions=[]
    def add(parent,title,family,tracker=None,cue=None):
        c=deepcopy(definitions[parent]);c.update(candidate_id='C%03d'%(147+len(additions)),parent=parent,title=title,family=family,
            disposition='REGISTERED_OUTCOME_INFORMED_FOLLOWUP_NOT_YET_EXECUTED')
        if tracker:c['settings']['tracker'].update(tracker)
        if cue:c['settings']['cue_condition']=cue
        c['settings_sha256']=digest(c['settings']);additions.append(c)
    for parent in ('C079','C120','C122','C124','C126'):
        for cue in ('UNINFORMATIVE_SEED_11','UNINFORMATIVE_SEED_29','UNINFORMATIVE_SEED_47','NOMINAL_GEOMETRY_DIAGNOSTIC'):
            add(parent,'N01 '+definitions[parent]['settings']['tracker']['mode']+' '+cue,'fresh_evidence_cue_null_and_nominal',cue=cue)
    families=[('C117','C118'),('C065','C079'),('C119','C120'),('C121','C122'),('C123','C124'),('C125','C126'),('C127','C128'),('C129','C130')]
    for pair in families:
        for parent in pair:
            add(parent,definitions[parent]['title']+' commitment0.75s','fresh_evidence_commitment_neighborhood',tracker=dict(commit_evidence_sec=.75))
    for capacity in (16,32,128,256):
        for parent in ('C065','C079'):
            add(parent,'N01 normalized capacity'+str(capacity)+' '+definitions[parent]['settings']['cue_condition'],
                'fresh_evidence_capacity_controls',tracker=dict(max_tracks=capacity))
    if len(additions)!=44:raise ValueError('Expected bounded44 followups')
    amendment_path=REPORT/'design/FRESH_EVIDENCE_FOLLOWUP_AMENDMENT_V1.json'
    amendment=dict(schema='jp_s6c_fresh_evidence_followup.v1',status='REGISTERED_BEFORE_FOLLOWUP_EXECUTION',created_utc=utc(),
        parent_design=bind(REPORT/'design/REGISTERED_DESIGN_V1.json'),parent_registry=bind(base_path),
        source=bind(__file__),candidates=additions,additional_configurations=44,total_registered_configurations=234,
        motivating_results=[bind(REPORT/p/'ANALYSIS_RECEIPT.json') for p in ('n00_challenge_core_v1','n01_panel_core_v2','n02_panel_core_v2','fresh_family_rescue_core_v2')],
        chronology='Exploratory, outcome-informed after N00 starvation, N01/N02 support/return tradeoffs and fresh eight-family panel results. No pristine preregistration or untouched subset claim.',
        hypotheses=[dict(axis='20cue controls',question='Do real cue changes differ from three frozen correspondence-breaking nulls and same-delivery nominal geometry under the usable N01 evidence regime?',control='Matched original real-cue parent; all raw input, frontend, tracking settings and original null seeds unchanged; nominal condition remains oracle-like.'),
            dict(axis='16commitment controls',question='Is remaining brief/return abstention partly a1.0second commitment-duration barrier?',control='Only commit_evidence_sec becomes0.75; disjoint_count2, cosine/score thresholds, maturity, unique support, lifecycle and cue policy identical across eight families x off/real.',limit='Two-point sensitivity. Quarantine/shadow retain extra escrow/shadow gates; lack of rescue cannot reject those mechanisms.'),
            dict(axis='8capacity controls',question='Does the usable N01 evidence regime change capacity pressure or accuracy at16/32/128/256 versus64?',control='Only max_tracks changes for normalized off/real. Finite lifecycle/archive/prototype budgets unchanged. No claim capacity fixes fragmentation.')],
        preserved_population='All240 canonical scenes and bothoutputs remain eligible. Initial56scene screen only; retained broad claims require all240/two-output confirmation and actual native/paced acceptance.',
        budget='44 policy-only settings with already computed exogenous N01 observations; no new model/frontend/template inference. Total234 including44 preserved S6B labels; leave6 slots unfilled unless a specific unresolved mechanism warrants them.',
        source_conditions=bind(REPORT/'CUE_VARIANT_INDEX_V1.json'),no_q_truth_in_runtime=True,
        geometry_exception='Only explicitly labeled NOMINAL_GEOMETRY_DIAGNOSTIC contains supported numeric nominal angles; no person IDs, transcript labels or early packets.')
    if amendment_path.exists():amendment['created_utc']=read(amendment_path)['created_utc']
    save(amendment_path,amendment,immutable=True)
    sys.path.insert(0,str(H2/'app'));rows=deepcopy(base['profiles'])
    for c in additions:
        for tap in ('O0','O1'):
            p=make_profile(c,tap,tap,recipes);value=p.to_dict()
            parent=next(r for r in base['profiles'] if r['candidate_id']==c['parent'] and r['asr_tap']==tap)
            before=deepcopy(parent['profile']);before['profile_id']=value['profile_id']
            if c['family']=='fresh_evidence_commitment_neighborhood':before['tracker']['commit_evidence_sec']=.75
            if c['family']=='fresh_evidence_capacity_controls':before['tracker']['max_tracks']=c['settings']['tracker']['max_tracks']
            if before!=value:raise ValueError('Unexpected effective parent-profile change')
            if value['tracker']['commit_disjoint_count']!=2:raise ValueError('Unchanged disjoint count must stay2')
            path=REPORT/'profiles'/c['candidate_id']/(tap+'_ASR_'+tap+'_ID.json');save(path,value,immutable=True)
            row=deepcopy(parent);row.update(candidate_id=c['candidate_id'],family=c['family'],parent=c['parent'],cue_condition=c['settings']['cue_condition'],
                profile=value,profile_binding=bind(path),profile_digest=p.digest(),field_usage=p.field_usage(),tracker_field_usage=p.tracker.field_usage(),
                effective_key=digest(dict(profile=value,cue=c['settings']['cue_condition'],gallery='NONE',tier=None)),followup_registration=bind(amendment_path))
            rows.append(row)
    result=dict(status='VALIDATED_REAL_V3_API',profiles=rows,candidate_count=190,effective_route_count=len(rows),parent_registry=bind(base_path),
        rescue_registration=base['rescue_registration'],common_roster_registration=base['common_roster_registration'],followup_registration=bind(amendment_path),source=bind(__file__))
    target=REPORT/'EFFECTIVE_PROFILE_REGISTRY_V5.json';save(target,result,immutable=True)
    return dict(status='REGISTERED_VALIDATED',new_configurations=44,total_registered=234,new_candidate_count=190,routes=len(rows),registry=bind(target),new_model_calls=0)

if __name__=='__main__':print(json.dumps(register(),indent=2))
