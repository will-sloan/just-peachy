"""Compile fixed-competitor duration controls. README_S6C_COMMON_ROSTER_PROFILES.md."""
from copy import deepcopy
import sys
from s6c_common import *
from s6c_profiles import make_profile

def compile_controls():
    base_path=REPORT/'EFFECTIVE_PROFILE_REGISTRY_V3.json'
    base=verified(bind(base_path,'af1cddad72299884f18c1a69da6afd7b15256ffbbd64a9a027c4fcb526076e60'))
    design=read(REPORT/'design/REGISTERED_DESIGN_V1.json')
    recipes={r['recipe_id']:r for r in design['recipes']}
    definitions={r['candidate_id']:r for r in design['candidates']}
    extension_path=REPORT/'enrollment/common30_v1/RESEARCH_GALLERY_INDEX_EXTENSION.json'
    extension=verified(bind(extension_path,'c1f538dfe58a906ca451d3df0c47e6c15e67baefbee52863ea7bd97d95d14bb7'))
    original=verified(extension['original_gallery_index'])
    completion_path=REPORT/'enrollment/common30_v1/COMMON30_GALLERY_COMPLETION.json'
    completion=read(completion_path)
    if completion['status']!='COMPLETE' or extension['status']!='COMPLETE':raise ValueError('Completed galleries required')
    for b in completion['outputs']+completion['original_authorities_unchanged']+completion['template_dependencies']:bind(b['path'],b['sha256'])
    expected={(g,t,None) for g in ('COMMON30_FIXED_ROSTER_A','COMMON30_FIXED_ROSTER_B') for t in (5,15,30)}
    keys=lambda rows:[(r['gallery_condition'],r['enrollment_tier'],r.get('case_id')) for r in rows]
    if set(keys(extension['rows']))!=expected or len(extension['rows'])!=6:raise ValueError('Exact six additive conditions required')
    if set(keys(original['rows']))&expected:raise ValueError('Original gallery assignment cannot be replaced')
    for b in extension['rows']:
        manifest=verified(b['manifest'])
        if len(manifest['profiles'])!=14:raise ValueError('Common roster size differs')
    additions=[]
    for side,parents in (('A',('C087','C088','C089')),('B',('C090','C091','C092'))):
        for tier,parent in zip((5,15,30),parents):
            c=deepcopy(definitions[parent]);c.update(candidate_id='C%03d'%(141+len(additions)),parent=parent,
                title='Common30 fixed roster '+side+' '+str(tier)+'s original naming thresholds',family='matched_roster_enrollment_duration',
                disposition='REGISTERED_OUTCOME_INFORMED_CONTROL_NOT_YET_EXECUTED')
            c['settings']['gallery_condition']='COMMON30_FIXED_ROSTER_'+side
            c['settings_sha256']=digest(c['settings'])
            if c['settings']['enrollment_tier']!=tier:raise ValueError('Parent tier differs')
            additions.append(c)
    amendment_path=REPORT/'design/COMMON_ROSTER_DURATION_AMENDMENT_V1.json'
    amendment=dict(schema='jp_s6c_common_roster_duration_amendment.v1',status='REGISTERED_BEFORE_COMMON_ROSTER_PROBE_EXECUTION',
        created_utc=utc(),parent_design=bind(REPORT/'design/REGISTERED_DESIGN_V1.json'),parent_registry=bind(base_path),
        gallery_extension=bind(extension_path),gallery_completion=bind(completion_path),candidates=additions,
        additional_configurations=6,total_registered_configurations=190,source=bind(__file__),
        motivating_results=bind(REPORT/'n01_gallery_panel_names_v2/NAME_ANALYSIS_RECEIPT.json'),
        chronology='Outcome-informed amendment after variable-roster naming results. Cohort selection uses only existing E eligibility, never Q scores. No independent holdout claim.',
        hypothesis='With the same14 roster competitors perA/B condition, 5/15/30 second E templates permit a matched duration comparison. Lower-tier variable rosters could not isolate duration.',
        preserved_policy='N01 cue-off, original score and margin thresholds, query/unique/disjoint rules, tracking and all240 probe scenes remain identical. Every777 occurrence and all empty/visitor cases remain eligible for their metrics.',
        limitations=['Common cohorts each contain9 CMU ARCTIC and5 HiFiTTS metadata identities; no Common Voice tier-effect claim.',
            'C143/C146 reuse original30s native gallery manifests fromC089/C092. Runtime behavior can be an alias; intended-roster eligibility labels differ and remain explicit.',
            'Reference templates are clean-source, not device-matched; no new inference, C fitting or Q-based enrollment selection.'],
        budget='Six labels, four newly assembled manifests and two explicit30s anchors. Existing95 native templates only; zero extra template inference. Within240 expansion allowance.')
    # Preserve timestamp/registration bytes on exact rerun; no retroactive overwrite.
    if amendment_path.exists():
        old=read(amendment_path);amendment['created_utc']=old['created_utc']
    save(amendment_path,amendment,immutable=True)
    sys.path.insert(0,str(H2/'app'));rows=deepcopy(base['profiles'])
    for c in additions:
        for tap in ('O0','O1'):
            p=make_profile(c,tap,tap,recipes);value=p.to_dict()
            parent=next(r for r in base['profiles'] if r['candidate_id']==c['parent'] and r['asr_tap']==tap)
            before=deepcopy(parent['profile']);before['profile_id']=value['profile_id']
            if before!=value:raise ValueError('Only roster condition may change native policy')
            path=REPORT/'profiles'/c['candidate_id']/(tap+'_ASR_'+tap+'_ID.json');save(path,value,immutable=True)
            row=deepcopy(parent);row.update(candidate_id=c['candidate_id'],family=c['family'],parent=c['parent'],
                gallery_condition=c['settings']['gallery_condition'],profile=value,profile_binding=bind(path),profile_digest=p.digest(),
                field_usage=p.field_usage(),tracker_field_usage=p.tracker.field_usage(),
                effective_key=digest(dict(profile=value,cue=c['settings']['cue_condition'],gallery=c['settings']['gallery_condition'],tier=c['settings']['enrollment_tier'])),
                common_roster_registration=bind(amendment_path))
            rows.append(row)
    target=REPORT/'EFFECTIVE_PROFILE_REGISTRY_V4.json'
    registry=dict(status='VALIDATED_REAL_V3_API',profiles=rows,candidate_count=146,effective_route_count=len(rows),
        parent_registry=bind(base_path),rescue_registration=base['rescue_registration'],common_roster_registration=bind(amendment_path),source=bind(__file__))
    save(target,registry,immutable=True)
    combined=dict(schema='s6c-research-gallery-index.additive.v2',status='COMPLETE',original_index=extension['original_gallery_index'],
        extensions=[bind(extension_path)],rows=deepcopy(original['rows'])+deepcopy(extension['rows']),
        merge_policy='Append exact unique assignment keys; all original rows and original file bytes preserved',source=bind(__file__))
    combined_path=REPORT/'RESEARCH_GALLERY_INDEX_V2.json';save(combined_path,combined,immutable=True)
    return dict(status='REGISTERED_VALIDATED',new_configurations=6,total_registered=190,candidate_count=146,
        registry=bind(target),gallery_index=bind(combined_path),native_template_calls=0)

if __name__=='__main__':print(json.dumps(compile_controls(),indent=2))
