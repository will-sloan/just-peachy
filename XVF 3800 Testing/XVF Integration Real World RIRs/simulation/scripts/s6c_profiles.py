"""Compile registered settings into the real v3 schema. README_S6C_PROFILES.md."""
from copy import deepcopy
import argparse
import sys
from s6c_common import *

def make_profile(candidate, asr_tap, identity_tap, recipes):
    from edge_speech_pipeline.research_profiles import ResearchProfile
    settings=candidate['settings'];recipe=recipes[settings['recipe_id']]
    p=dict(schema_version='edge-research-profile.v3',profile_id=candidate['candidate_id']+'_'+asr_tap+'_'+identity_tap,
        input=dict(asr_tap=asr_tap,identity_tap=identity_tap,gain=1.,already_gained=True,common_origin='paired_capture_sample_zero'),
        segmentation=dict(window_sec=10.,hop_sec=.5,post_policy='posterior_hysteresis'),
        tracker=deepcopy(settings['tracker']),identity=deepcopy(settings['identity']),
        xvf=dict(mode='tracking_only' if settings['tracker']['cues_enabled'] else 'none'))
    if settings['recipe_id']=='N00':
        p['segmentation']=dict(window_sec=10.,hop_sec=.75,post_policy='hard_argmax_fraction')
        p['embedding']=dict(evidence_policy='mature_only',window_sec=.5,hop_sec=.25,mature_hop_sec=.25,
                            rms_policy='dispatch',purity_policy='gate_only')
    else:
        p['embedding']=dict(evidence_policy='dual',window_sec=1.5,hop_sec=.25,short_window_sec=.5,short_hop_sec=.25,
                            mature_hop_sec=.5,rms_policy='full_window',purity_policy='fraction',minimum_clean_fraction=.8)
    for key,value in recipe.get('changes',{}).items():
        section,name=key.split('.')
        p.setdefault(section,{})[name]=value
    return ResearchProfile.from_dict(p)

def compile_profiles():
    sys.path.insert(0,str(H2/'app'))
    design=read(REPORT/'design/REGISTERED_DESIGN_V1.json')
    recipes={r['recipe_id']:r for r in design['recipes']}
    target=REPORT/'EFFECTIVE_PROFILE_REGISTRY_V1.json'
    if target.exists():return read(target)
    rows=[]
    for c in design['candidates']:
        if c['origin']=='PRESERVED_S6B':continue
        route=c['settings']['route']
        routes=[('O0','O0'),('O1','O1')] if route=='SAME' else [(route.split('_')[0],route.split('_')[2])]
        for asr_tap,identity_tap in routes:
            p=make_profile(c,asr_tap,identity_tap,recipes)
            value=p.to_dict()
            folder=REPORT/'profiles'/c['candidate_id']
            path=folder/(asr_tap+'_ASR_'+identity_tap+'_ID.json')
            save(path,value,immutable=True)
            rows.append(dict(candidate_id=c['candidate_id'],family=c['family'],parent=c['parent'],
                recipe_id=c['settings']['recipe_id'],cue_condition=c['settings']['cue_condition'],
                gallery_condition=c['settings']['gallery_condition'],enrollment_tier=c['settings']['enrollment_tier'],
                asr_tap=asr_tap,identity_tap=identity_tap,route=route,profile=value,profile_binding=bind(path),
                profile_digest=p.digest(),field_usage=p.field_usage(),tracker_field_usage=p.tracker.field_usage(),
                effective_key=digest(dict(profile=value,cue=c['settings']['cue_condition'],gallery=c['settings']['gallery_condition'],tier=c['settings']['enrollment_tier'])),
                neural_dependency='FULL_PROFILE_AND_CUES' if p.embedding.cadence_policy=='uncertainty' or p.xvf.mode in ('endpoint_only','both') else 'EXOGENOUS_AUDIO_ASR_SEGMENTATION_EMBEDDING_ROUTING_ONLY'))
    result=dict(status='VALIDATED_REAL_V3_API',created_utc=utc(),design=bind(REPORT/'design/REGISTERED_DESIGN_V1.json'),
        profiles=rows,candidate_count=len({r['candidate_id'] for r in rows}),effective_route_count=len(rows),
        actual_neural_jobs_executed=0,gallery_material_binding='Applied only when frozen research galleries exist; no implicit private/empty fallback',
        n00_evidence_role='Legacy single-lane .5s R0 is assigned mature role for matched prototype updating; it is not new long-mature or dual evidence')
    save(target,result,immutable=True)
    return dict(status=result['status'],candidate_count=result['candidate_count'],routes=len(rows),path=str(target))

if __name__=='__main__':
    print(json.dumps(compile_profiles(),indent=2))
