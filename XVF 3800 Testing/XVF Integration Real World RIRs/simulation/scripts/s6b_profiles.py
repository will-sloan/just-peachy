"""Compile actual S6B profiles and dependency-distinct neural recipes. README_S6B_PROFILES.md."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
import json
import sys
from s6b_common import *

def compile_profiles():
    sys.path.insert(0,str(H2/'app'))
    from edge_speech_pipeline.research_profiles import ResearchProfile
    from edge_speech_pipeline.research_tracking_v2 import S6BTrackingConfig
    registry=read(REPORT/'design/CANDIDATE_REGISTRY.json')
    families={r['recipe_family_id']:r['base_settings'] for r in read(REPORT/'design/RECIPE_GROUP_PROPOSAL.json')['families']}
    expected={'B19':'voice','B21':'voice','B29':'voice'}
    if any(next(c for c in registry['profiles'] if c['profile_id']==k)['tracker_mode']!=v for k,v in expected.items()):
        raise ValueError('Require reviewed explicit B19/B21/B29 fractional-design mapping')
    profiles=[];recipes={};deltas=[]
    core_recipe={**{f'B{i:02d}':'R0' for i in range(40)},'B16':'R1','B17':'R1','B18':'R2','B19':'R2_GATE',
        'B20':'R3','B21':'R2_HARD','B22':'R4','B23':'R0_ENDPOINT','B24':'R5','B25':'R5_CUES',
        'B26':'R6','B27':'R6_FULL_RMS','B28':'R7','B29':'R0_POST','B34':'R3_SHORT_LONG','B35':'R0_FULL_RMS','B39':'R0_ENDPOINT'}
    for c in registry['profiles']:
        pid=c['profile_id'];family=c['recipe_family_id']
        if pid=='B00':
            profiles.append(dict(profile_id=pid,name=c['name'],recipe_id='HISTORICAL_B0',profile={'historical_control':True},
                classification='control',comparison_parent=None,mechanism_family='controls',field_usage={},status='EXACT_S6A_BOUND_CONTROL'))
            continue
        # The explicit base is original neural settings unless a component family differs.
        base=deepcopy(families[family]);base['profile_id']=pid;base['schema_version']='edge-research-profile.v2'
        base['runtime'].update(asr_threads=1,speaker_threads=1,punctuation_threads=1)
        e=base['embedding'];e.update(rms_policy='dispatch',purity_policy='gate_only')
        base['tracker']=dict(mode=c['tracker_mode'],cues_enabled=c['cue_route'] in ('tracking_only','both'))
        base['xvf']=dict(mode=c['cue_route'])
        if pid in ('B18','B20'):e['purity_policy']='fraction'
        if pid=='B20':e.update(hop_sec=.25,frequent_hop_sec=.25)
        if pid=='B19':
            base['segmentation'].update(hop_sec=.5,post_policy='posterior_hysteresis')
            e.update(window_sec=.5,hop_sec=.25,frequent_hop_sec=.25,purity_policy='gate_only')
        if pid=='B21':
            base['segmentation'].update(hop_sec=.5,post_policy='hard_argmax_fraction')
            e.update(window_sec=.5,hop_sec=.25,frequent_hop_sec=.25,purity_policy='fraction')
        if pid=='B29':
            # A reviewed replacement of the inherited redundant beam+cue companion.
            base=deepcopy(families['R0']);base.update(profile_id=pid,schema_version='edge-research-profile.v2',tracker=dict(mode='voice',cues_enabled=False),xvf=dict(mode='none'))
            base['runtime'].update(asr_threads=1,speaker_threads=1,punctuation_threads=1)
            base['segmentation'].update(post_policy='posterior_hysteresis')
            e=base['embedding'];e.update(rms_policy='dispatch',purity_policy='gate_only',frequent_hop_sec=.25)
        if pid in ('B24','B25'):
            e.update(window_sec=1.,hop_sec=.25,frequent_hop_sec=.25,sparse_hop_sec=1.,voice_observation_floor_sec=.75,
                cadence_policy='event_driven',evidence_debt_enabled=True,cadence_cues_enabled=pid=='B25',
                evidence_policy='early_short_long',early_window_sec=.5,purity_policy='gate_only')
        if pid in ('B27','B35'):e['rms_policy']='full_window'
        if pid=='B32':base['tracker']['sensor_quarantine_enabled']=True
        if pid=='B33':base['tracker']['update_escrow_enabled']=True
        if pid=='B36':base['tracker']['max_tracks']=256
        if pid=='B34':e.update(evidence_policy='early_short_long',early_window_sec=.5,hop_sec=.25,frequent_hop_sec=.25,purity_policy='contiguous',minimum_contiguous_clean_sec=.45)
        profile=ResearchProfile.from_dict(base)
        usage=profile.tracker.field_usage()
        if usage['nondefault_inactive_fields']:raise ValueError('Changed inactive tracker knobs: '+pid+str(usage['nondefault_inactive_fields']))
        profiles.append(dict(profile_id=pid,name=c['name'],recipe_id=core_recipe[pid],profile=profile.to_dict(),
            classification=c['classification'],comparison_parent=c['comparison_parent'],mechanism_family=c['mechanism_family'],
            field_usage=usage,status='VALIDATED_PENDING_EXECUTION'))
    core={p['profile_id']:p for p in profiles}
    for pid,parent,changes in (
        ('B18_C1','B18',{'tracker':{'commit_disjoint_count':1}}),
        ('B20_C1','B20',{'tracker':{'commit_disjoint_count':1}}),
        ('B24_FREQUENT','B24',{'embedding':{'cadence_policy':'frequent','evidence_debt_enabled':False,'voice_observation_floor_sec':1.0}}),
        ('B24_SPARSE','B24',{'embedding':{'cadence_policy':'sparse','evidence_debt_enabled':False,'voice_observation_floor_sec':1.0}})):
        row=deepcopy(core[parent]);value=row['profile'];value['profile_id']=pid
        for section,fields in changes.items():value[section].update(fields)
        p=ResearchProfile.from_dict(value)
        row.update(profile_id=pid,name='Limited matched diagnostic: '+pid,profile=p.to_dict(),classification='limited_diagnostic',
            comparison_parent=parent,scope='CHALLENGE_ONLY_NOT_GENERAL_RANKING',field_usage=p.tracker.field_usage())
        if pid.startswith('B24_'):row['recipe_id']='R5_'+pid.split('_',1)[1]
        profiles.append(row)
    for row in profiles:
        if row['profile_id']=='B00':continue
        p=deepcopy(row['profile']);rid=row['recipe_id']
        # Prediction-only tracking settings are not an upstream neural dependency.
        # Cadence cues and endpoint advice remain real neural recipe dependencies.
        endpoint=p['xvf']['mode'] in ('endpoint_only','both')
        cadence=p['embedding']['cadence_cues_enabled']
        p['profile_id']='NEURAL_'+rid
        p['tracker']=asdict(S6BTrackingConfig(mode='adaptive' if cadence else 'voice',cues_enabled=cadence))
        p['xvf']['mode']='both' if endpoint and cadence else 'endpoint_only' if endpoint else 'tracking_only' if cadence else 'none'
        p=ResearchProfile.from_dict(p).to_dict()
        spec=dict(recipe_id=rid,recipe_family_id=rid.split('_')[0],profile=p,gain_variant='minus3' if rid.startswith('R6') else 'historical',
            candidate_ids=[row['profile_id']],status='VALIDATED_PENDING_NEURAL_EXECUTION',
            dependency_exclusion='Anonymous tracking labels/parameters do not alter neural admission unless explicit cadence cue or endpoint fields are active; those fields remain in recipe identity')
        if rid in recipes:
            existing=recipes[rid]
            if existing['profile']!=p or existing['gain_variant']!=spec['gain_variant']:
                raise ValueError('Attempted incompatible neural reuse: '+rid+' for '+row['profile_id'])
            existing['candidate_ids'].append(row['profile_id'])
        else:recipes[rid]=spec
    for row in profiles:
        parent=next((p for p in profiles if p['profile_id']==row['comparison_parent']),None)
        if parent and parent['profile_id']!='B00' and row['profile_id']!='B00':
            def flatten(d,prefix=''):
                out={}
                for k,v in d.items():
                    if isinstance(v,dict):out.update(flatten(v,prefix+k+'.'))
                    else:out[prefix+k]=v
                return out
            a,b=flatten(parent['profile']),flatten(row['profile'])
            diff={k:dict(parent=a.get(k),candidate=v) for k,v in b.items() if a.get(k)!=v and k!='profile_id'}
            deltas.append(dict(profile_id=row['profile_id'],parent=parent['profile_id'],different_fields=diff,
                same_neural_recipe=row['recipe_id']==parent['recipe_id']))
    folder=REPORT/'profiles';folder.mkdir(exist_ok=True)
    for row in profiles:
        path=folder/(row['profile_id']+'.json');save(path,row['profile']);row['file_binding']=bind(path)
    value=dict(status='VALIDATED',created_utc=utc(),core_profile_count=40,limited_diagnostics_count=4,total_configurations=44,
        profiles=profiles,design_registry=bind(REPORT/'design/CANDIDATE_REGISTRY.json'),
        companion_count_explanation='Four additional bounded diagnostics isolate mandatory duration/commit and cadence costs. Forty core configurations remain; all44 are enumerated, diagnostics are challenge-only.',
        provider='CPUExecutionProvider/cpu',numeric_pool_threads=1,model_families_or_weights_changed=False)
    save(REPORT/'EFFECTIVE_PROFILE_REGISTRY.json',value)
    recipe_list=sorted(recipes.values(),key=lambda r:(len(r['recipe_id'])!=2,r['recipe_id']))
    save(REPORT/'NEURAL_RECIPE_REGISTRY.json',dict(status='VALIDATED',created_utc=utc(),recipes=recipe_list,
        conceptual_families=8,exact_distinct_recipes=len(recipe_list),initial_balanced_recipes=['R'+str(i) for i in range(8)],
        exact_recipe_count_reason='Necessary protected endpoint, distinct waveform/RMS eligibility, fractional post/stride/purity, early-short/long and matched cadence branches each require actual new neural inference.',
        effective_profiles=bind(REPORT/'EFFECTIVE_PROFILE_REGISTRY.json')))
    save(REPORT/'EFFECTIVE_PROFILE_DIFFS.json',dict(rows=deltas,registry=bind(REPORT/'EFFECTIVE_PROFILE_REGISTRY.json')))
    return dict(status='VALIDATED',core=40,limited_diagnostics=4,profiles=len(profiles),recipes=len(recipe_list))

if __name__=='__main__':print(json.dumps(compile_profiles(),indent=2))
