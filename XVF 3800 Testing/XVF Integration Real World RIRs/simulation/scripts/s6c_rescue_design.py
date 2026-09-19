"""Register the bounded N00 admission and N01 family rescue. README_S6C_RESCUE_DESIGN.md."""
from copy import deepcopy
import sys
from s6c_common import *
from s6c_profiles import make_profile

def register():
    design=read(REPORT/'design/REGISTERED_DESIGN_V1.json');base=read(REPORT/'EFFECTIVE_PROFILE_REGISTRY_V2.json')
    definitions={c['candidate_id']:c for c in design['candidates']};recipes={r['recipe_id']:r for r in design['recipes']}
    additions=[]
    def add(parent,title,family,changes):
        c=deepcopy(definitions[parent]);c.update(candidate_id='C%03d'%(117+len(additions)),parent=parent,title=title,family=family,
            disposition='REGISTERED_OUTCOME_INFORMED_RESCUE_NOT_YET_EXECUTED')
        c['settings']['tracker'].update(changes);c['settings_sha256']=digest(c['settings']);additions.append(c)
    for mode in ('old_voice_gate','reliability_joint','hypothesis_joint','semimarkov_joint','bounded_global_joint','quarantine_joint','shadow_gallery_joint'):
        for parent,cue in (('C065','cue-off'),('C079','real cues')):
            add(parent,'N01 '+mode+' '+cue,'fresh_evidence_structural_rescue',dict(mode=mode))
    for minimum in (0.,.25):
        for parent in ('C021','C022','C011','C012'):
            add(parent,definitions[parent]['title']+' clean support floor '+str(minimum),'legacy_clean_admission_rescue',dict(minimum_clean_fraction=minimum))
    for parent,cue in (('C065','cue-off'),('C079','real cues')):
        add(parent,'N01 short prototype updates permitted '+cue,'short_mature_update_coupling',dict(mature_only_prototype_updates=False))
    assert len(additions)==24
    for c in additions:
        if c['settings']['recipe_id']=='N00' and c['settings']['tracker']['minimum_clean_fraction']==0.:
            # This amendment never lowers the positive unique-duration criterion.
            assert c['settings']['tracker'].get('commit_evidence_sec',1.)>0
    amendment=dict(schema='jp_s6c_outcome_informed_rescue.v1',status='REGISTERED_BEFORE_56_SCENE_N01_SCORING',created_utc=utc(),
        parent_design=bind(REPORT/'design/REGISTERED_DESIGN_V1.json'),parent_registry=bind(REPORT/'EFFECTIVE_PROFILE_REGISTRY_V2.json'),
        motivating_outcomes=bind(REPORT/'n00_challenge_core_v1/ANALYSIS_RECEIPT.json'),
        previously_available_N01_smoke=bind(REPORT/'smoke_core_v1/ANALYSIS_RECEIPT.json'),
        chronology='Outcome-informed from completed N00 panel and inspected N01 functional smoke. No claim of pristine preregistration. The complete56-scene N01 results and all rescue outcomes have not been scored or inspected at registration.',
        reason='N00 supplies actual legacy .5-second vectors but new v3 clean-support/commit semantics reject most stale .75-second segmentation-context observations; all83 complete-panel returns per tap remain unknown. This prevents meaningful capacity/family ranking.',
        candidates=additions,additional_configurations=24,total_registered_configurations=184,
        budget_reason='Finite24 policy-only rescue configurations inside the permitted240 expansion ceiling, with unchanged models and reused genuine frontend observations. Fourteen fresh-evidence family pairs, eight explicit clean-threshold controls and two short-prototype-update controls answer three identified confounds.',
        hypotheses=[
            dict(axis='fresh family support',falsifier='No reduced unknown/fragmentation or improved conditional speaker consistency under N01 despite active family logic; retain failure and compare cue-off/on at exact common capacity/lifecycle/evidence'),
            dict(axis='legacy clean admission',falsifier='Lowered estimator-support floor creates false merges/prototype contamination or leaves unique-duration/commit starvation; zero-support observations cannot earn any unique clean duration'),
            dict(axis='short prototype update',falsifier='Allowing short updates worsens mature identity consistency or first/final label stability; this is an update-role coupling, not a window-length-only effect')],
        native_confirmation='Before empirical family rejection, actual six varied paired scenes with complete original audio: F01,F03,F04,F06,F08,F12, then inspect coverage for short/return/overlap/empty/noise/cue-dropout. Retained candidates and matched parents all240/both taps; paced/endurance still mandatory.',
        preserved_status='All previous settings/outcomes/failures retained; N00 remains a v3 clean-support diagnostic, not an S6B-equivalent old-control or capacity-ranking result. No angle benefit is required.',
        source=bind(__file__))
    amendment_path=REPORT/'design/ADMISSION_AND_FAMILY_RESCUE_V1.json';save(amendment_path,amendment,immutable=True)
    sys.path.insert(0,str(H2/'app'));rows=deepcopy(base['profiles'])
    for c in additions:
        for tap in ('O0','O1'):
            p=make_profile(c,tap,tap,recipes);value=p.to_dict();path=REPORT/'profiles'/c['candidate_id']/(tap+'_ASR_'+tap+'_ID.json')
            save(path,value,immutable=True)
            rows.append(dict(candidate_id=c['candidate_id'],family=c['family'],parent=c['parent'],recipe_id=c['settings']['recipe_id'],
                cue_condition=c['settings']['cue_condition'],gallery_condition='NONE',enrollment_tier=None,asr_tap=tap,identity_tap=tap,route='SAME',
                profile=value,profile_binding=bind(path),profile_digest=p.digest(),field_usage=p.field_usage(),tracker_field_usage=p.tracker.field_usage(),
                effective_key=digest(dict(profile=value,cue=c['settings']['cue_condition'],gallery='NONE',tier=None)),
                neural_dependency='EXOGENOUS_AUDIO_ASR_SEGMENTATION_EMBEDDING_ROUTING_ONLY',rescue_registration=bind(amendment_path)))
    result=dict(status='VALIDATED_REAL_V3_API',profiles=rows,candidate_count=len({r['candidate_id'] for r in rows}),effective_route_count=len(rows),
        parent_registry=bind(REPORT/'EFFECTIVE_PROFILE_REGISTRY_V2.json'),rescue_registration=bind(amendment_path),source=bind(__file__))
    target=REPORT/'EFFECTIVE_PROFILE_REGISTRY_V3.json';save(target,result,immutable=True)
    return dict(status='REGISTERED_VALIDATED',new_configurations=24,total_registered=184,profiles=result['candidate_count'],routes=len(rows),registry=bind(target))

if __name__=='__main__':print(json.dumps(register(),indent=2))
