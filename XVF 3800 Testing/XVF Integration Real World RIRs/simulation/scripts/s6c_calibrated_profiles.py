"""Bind pre-registered C-only fit results to actual v3 profiles. README_S6C_CALIBRATED_PROFILES.md."""
from copy import deepcopy
import sys
from s6c_common import *
from s6c_profiles import make_profile

def compile_calibrated():
    base_path=REPORT/'EFFECTIVE_PROFILE_REGISTRY_V1.json'
    amendment_path=REPORT/'design/C_ONLY_CALIBRATION_AMENDMENT_V1.json'
    calibration_path=REPORT/'enrollment/C_ONLY_CALIBRATION_INDEX.json'
    base=read(base_path);amendment=read(amendment_path);calibration=read(calibration_path)
    rows=deepcopy(base['profiles']);fits={r['candidate_id']:r for r in calibration['rows']}
    if set(fits)!={r['candidate_id'] for r in amendment['candidates']}:raise ValueError('Calibration alternatives differ from registered seven')
    sys.path.insert(0,str(H2/'app'))
    design=read(REPORT/'design/REGISTERED_DESIGN_V1.json');recipes={r['recipe_id']:r for r in design['recipes']}
    for original in amendment['candidates']:
        c=deepcopy(original);fit=fits[c['candidate_id']]
        if fit['status'] not in ('FITTED_C_ONLY','UNAVAILABLE_CALIBRATION'):raise ValueError('C-only fit has no terminal disposition')
        if fit['gallery_condition']!=c['settings']['gallery_condition'] or fit['enrollment_tier']!=c['settings']['enrollment_tier']:raise ValueError('Calibration roster/tier mismatch')
        if fit['selected']['score_threshold'] not in amendment['fitted_rule']['threshold_grid'] or fit['selected']['margin_threshold'] not in amendment['fitted_rule']['margin_grid']:raise ValueError('Fitted threshold outside registered grid')
        c['settings']['identity'].update(score_threshold=fit['selected']['score_threshold'],margin_threshold=fit['selected']['margin_threshold'])
        for tap in ('O0','O1'):
            p=make_profile(c,tap,tap,recipes);value=p.to_dict();path=REPORT/'profiles'/c['candidate_id']/(tap+'_ASR_'+tap+'_ID.json')
            save(path,value,immutable=True)
            rows.append(dict(candidate_id=c['candidate_id'],family=c['family'],parent=c['parent'],recipe_id=c['settings']['recipe_id'],
                cue_condition=c['settings']['cue_condition'],gallery_condition=c['settings']['gallery_condition'],enrollment_tier=c['settings']['enrollment_tier'],
                asr_tap=tap,identity_tap=tap,route='SAME',profile=value,profile_binding=bind(path),profile_digest=p.digest(),
                field_usage=p.field_usage(),tracker_field_usage=p.tracker.field_usage(),
                effective_key=digest(dict(profile=value,cue=c['settings']['cue_condition'],gallery=c['settings']['gallery_condition'],tier=c['settings']['enrollment_tier'])),
                neural_dependency='EXOGENOUS_AUDIO_ASR_SEGMENTATION_EMBEDDING_ROUTING_ONLY',
                calibration_status=fit['status'],calibration=fit))
    result=dict(status='VALIDATED_REAL_V3_API',profiles=rows,candidate_count=len({r['candidate_id'] for r in rows}),effective_route_count=len(rows),
        parent_registry=bind(base_path),registration_amendment=bind(amendment_path),calibration_index=bind(calibration_path),gallery_index=bind(REPORT/'RESEARCH_GALLERY_INDEX.json'),
        source=bind(__file__),calibration_scope='Pre-registered C-only scalar naming thresholds; no Q fitting, no model or anonymous association changes')
    target=REPORT/'EFFECTIVE_PROFILE_REGISTRY_V2.json';save(target,result,immutable=True)
    return dict(status=result['status'],candidate_count=result['candidate_count'],routes=len(rows),registry=bind(target))

if __name__=='__main__':print(json.dumps(compile_calibrated(),indent=2))
