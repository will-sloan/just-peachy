"""Register S6C study before new outcomes. See README_S6C_DESIGN.md."""
from copy import deepcopy
import sys
from s6c_common import *

def register():
    target=REPORT/'design/REGISTERED_DESIGN_V1.json'
    if target.exists():return read(target)
    admit_work(full=True)
    old=read(S6B/'EFFECTIVE_PROFILE_REGISTRY.json')
    rows=[];seen={}
    for p in old['profiles']:
        rows.append(dict(candidate_id=p['profile_id'],origin='PRESERVED_S6B',family=p.get('mechanism_family','control'),
                         title=p.get('name',p['profile_id']),parent=p.get('comparison_parent'),old_profile=p,
                         disposition='REGISTERED_PRESERVED_CONTROL',scope='Immutable S6B native evidence and shared scheduler behavior; no old artifact overwrite'))
    def add(title,family,tracker=None,recipe='N00',cue='CUES_OFF',route='SAME',gallery='NONE',tier=None,parent=None,identity=None):
        t=dict(mode='normalized_joint',max_tracks=64,lifecycle_policy='retire_archive')
        t.update(tracker or {});t['cues_enabled']=cue!='CUES_OFF'
        settings=dict(tracker=t,recipe_id=recipe,cue_condition=cue,route=route,gallery_condition=gallery,enrollment_tier=tier,identity=identity or {})
        signature=digest(settings)
        if signature in seen:return seen[signature]
        cid='C%03d'%(len(seen)+1);seen[signature]=cid
        rows.append(dict(candidate_id=cid,origin='NEW_S6C',title=title,family=family,parent=parent,settings=settings,
                         settings_sha256=signature,disposition='REGISTERED_NOT_YET_EXECUTED',
                         empirical_rejection_gate='Reachability and >=6 varied scene/tap-paired native checks, matched capacity/evidence/lifecycle/cue-off parent, local neighborhood; else precise implementation/support disposition'))
        return cid
    capacity={}
    for cap in (16,32,64,128,256):
        legacy=add(f'Old gate stored capacity {cap}','capacity',dict(mode='old_voice_gate',max_tracks=cap,lifecycle_policy='none',max_prototypes=1,mature_only_prototype_updates=False),parent='B01')
        life=add(f'Old gate finite lifecycle capacity {cap}','lifecycle',dict(mode='old_voice_gate',max_tracks=cap,max_prototypes=1,mature_only_prototype_updates=False),parent=legacy)
        voice=add(f'Joint voice finite capacity {cap}','joint_capacity',dict(max_tracks=cap),parent=life)
        cue=add(f'Joint real cues finite capacity {cap}','joint_capacity',dict(max_tracks=cap),cue='REAL_ALIGNED_CUES',parent=voice)
        capacity[cap]=(legacy,life,voice,cue)
    modes=('old_voice_gate','normalized_joint','reliability_joint','hypothesis_joint','semimarkov_joint','bounded_global_joint','quarantine_joint','shadow_gallery_joint')
    family={}
    for mode in modes:
        off=add(mode+' cue-off','structural_family',dict(mode=mode),parent=capacity[64][2])
        on=add(mode+' real cues','structural_family',dict(mode=mode),cue='REAL_ALIGNED_CUES',parent=off)
        family[mode]=(off,on)
    for mode in ('normalized_joint','reliability_joint','hypothesis_joint','semimarkov_joint','bounded_global_joint'):
        for cue in ('UNINFORMATIVE_SEED_11','UNINFORMATIVE_SEED_29','UNINFORMATIVE_SEED_47','NOMINAL_GEOMETRY_DIAGNOSTIC'):
            add(mode+' '+cue,'cue_authority',dict(mode=mode),cue=cue,parent=family[mode][1])
    neighborhoods=[('borderline_low',dict(cosine_threshold=.30,conflict_cosine_floor=.15)),
                   ('borderline_high',dict(cosine_threshold=.40,conflict_cosine_floor=.25)),
                   ('weak_direction',dict(joint_spatial_weight=.30,direction_change_deg=15.,direction_persistence_sec=.25)),
                   ('strong_direction',dict(joint_spatial_weight=.90,direction_change_deg=45.,direction_persistence_sec=1.)),
                   ('short_lifecycle',dict(retirement_sec=10.,provisional_retirement_sec=5.,position_decay_sec=2.)),
                   ('long_lifecycle',dict(retirement_sec=120.,provisional_retirement_sec=30.,position_decay_sec=120.))]
    for title,changes in neighborhoods:
        # Inactive cue settings are omitted in the cue-off matched parent.
        off_changes={k:v for k,v in changes.items() if k not in ('joint_spatial_weight','direction_change_deg','direction_persistence_sec','position_decay_sec')}
        off=add(title+' cue-off','parameter_neighborhood',off_changes,parent=capacity[64][2])
        add(title+' real cues','parameter_neighborhood',changes,cue='REAL_ALIGNED_CUES',parent=off)
    recipes=[
        dict(recipe_id='N00',source='VERIFIED_S6B_R0',purpose='Historical short fixed evidence and continuous original ASR; v3 policy only'),
        dict(recipe_id='N01',source='NEW_NATIVE',purpose='Simultaneous .5s short and 1.5s mature, .25/.5s hops, full-window RMS, fraction purity',changes={}),
        dict(recipe_id='N02',source='NEW_NATIVE',purpose='N02 context refresh rescue',changes={'segmentation.hop_sec':.25,'embedding.window_sec':1.0}),
        dict(recipe_id='N03',source='NEW_NATIVE',purpose='Long mature context 3s',changes={'embedding.window_sec':3.0}),
        dict(recipe_id='N04',source='NEW_NATIVE',purpose='Short .75s interaction',changes={'embedding.short_window_sec':.75}),
        dict(recipe_id='N05',source='NEW_NATIVE',purpose='Gate-only purity companion',changes={'embedding.purity_policy':'gate_only'}),
        dict(recipe_id='N06',source='NEW_NATIVE',purpose='N06 clipped-window protection rescue',changes={'embedding.clipping_fraction_max':.001}),
        dict(recipe_id='N07',source='NEW_NATIVE_POLICY_DEPENDENT',purpose='Per-track uncertainty/evidence debt cadence',changes={'embedding.cadence_policy':'uncertainty'}),
        dict(recipe_id='N08',source='NEW_NATIVE',purpose='Hard powerset post-policy companion',changes={'segmentation.post_policy':'hard_argmax_fraction'}),
        dict(recipe_id='N09',source='NEW_NATIVE',purpose='Dispatch RMS companion',changes={'embedding.rms_policy':'dispatch'}),
        dict(recipe_id='N10',source='NEW_NATIVE',purpose='ASR decoder isolated at original 100ms host read',changes={'asr.decoding_method':'modified_beam_search','asr.max_active_paths':2}),
        dict(recipe_id='N11',source='NEW_NATIVE',purpose='ASR host dispatch isolated with greedy',changes={'asr.journal_read_ms':50}),
        dict(recipe_id='N12',source='NEW_NATIVE',purpose='Endpoint isolated with continuous greedy',changes={'asr.endpoint_rule1_silence_sec':1.6,'asr.endpoint_rule2_silence_sec':.8}),
        dict(recipe_id='N13',source='NEW_NATIVE',purpose='Decoder plus host dispatch interaction',changes={'asr.decoding_method':'modified_beam_search','asr.max_active_paths':2,'asr.journal_read_ms':50}),
        dict(recipe_id='N14',source='NEW_NATIVE',purpose='Decoder/host/endpoint interaction',changes={'asr.decoding_method':'modified_beam_search','asr.max_active_paths':2,'asr.journal_read_ms':50,'asr.endpoint_rule1_silence_sec':1.6,'asr.endpoint_rule2_silence_sec':.8})]
    component={}
    for recipe in recipes[1:]:
        rid=recipe['recipe_id']
        component[rid]=add(recipe['purpose'],'component',recipe=rid,parent=capacity[64][2] if rid=='N01' else component['N01'])
    for rid in ('N01','N02','N06','N07'):
        add(rid+' with real cues','component_interaction',recipe=rid,cue='REAL_ALIGNED_CUES',parent=component[rid])
    for route in ('O0_ASR_O0_ID','O1_ASR_O1_ID','O0_ASR_O1_ID','O1_ASR_O0_ID'):
        add(route+' actual synchronized route','split_route',recipe='N01',route=route,parent=component['N01'])
    for gallery in ('FIXED_ROTATION_A','FIXED_ROTATION_B','LARGE_COHORT','ALL_EXPECTED_SETUP','SELECTED_PARTICIPANTS','WRONG_SELECTION_VISITORS'):
        for tier in (5,15,30):
            add(gallery+' tier '+str(tier),'enrollment',recipe='N01',gallery=gallery,tier=tier,parent=component['N01'],identity={'mode':'post_association'})
    for gallery in ('FIXED_ROTATION_A','FIXED_ROTATION_B','LARGE_COHORT'):
        add(gallery+' real cues 15s','enrollment_interaction',recipe='N01',cue='REAL_ALIGNED_CUES',gallery=gallery,tier=15,
            parent=next(r['candidate_id'] for r in rows if r.get('settings',{}).get('gallery_condition')==gallery and r['settings']['enrollment_tier']==15),identity={'mode':'post_association'})
    add('Quarantine structural split','structural_lineage',dict(mode='quarantine_joint',structural_split_enabled=True),parent=family['quarantine_joint'][0])
    add('Shadow structural merge','structural_lineage',dict(mode='shadow_gallery_joint',structural_merge_enabled=True),parent=family['shadow_gallery_joint'][0])
    # Panel uses only reference metadata, never new outcomes. Keep all historical
    # rescue cells, every complete <2s occurrence and every actual empty control.
    ids=set(read(S6B/'design/CHALLENGE_PANEL.json')['case_ids'])
    inputs=read(S6B/'INPUT_INDEX.json')['rows'];short=[];panel_reasons={cid:['historical_balanced_panel'] for cid in ids}
    reference_rows=[]
    for item in inputs:
        if item['stream']!='O0':continue
        support=verified(item['support'])['support']
        scene=next(s for s in read(BANK)['scenes'] if s['case_id']==item['case_id'])
        turns=support['turns']
        # Whole original clip duration reproduces the prior 40 / 34 denominators.
        small=[t for t in turns if t['whole_clip_duration_s']<2.]
        if small:
            ids.add(item['case_id']);panel_reasons.setdefault(item['case_id'],[]).append('all_complete_under_2s')
            short.extend(dict(case_id=item['case_id'],source_id=t['source_id'],duration_sec=t['whole_clip_duration_s'],bin=t['whole_clip_bin']) for t in small)
        if not turns:
            ids.add(item['case_id']);panel_reasons.setdefault(item['case_id'],[]).append('all_no_known_source_turn_controls')
        reference_rows.append(dict(case_id=item['case_id'],turns=len(turns),subsecond=sum(t['whole_clip_duration_s']<1 for t in turns),one_to_under2=sum(1<=t['whole_clip_duration_s']<2 for t in turns),support=item['support'],family=scene['family_id']))
    panel=dict(status='REGISTERED_METADATA_ONLY',case_ids=sorted(ids),count=len(ids),streams=['O0','O1'],
               reasons=panel_reasons,all_under2_occurrences=short,rows=reference_rows,
               selection='All historical balanced cells, every complete <2s original-clip occurrence, and every source-empty control; no new outcome selection')
    save(REPORT/'design/REGISTERED_PANEL_V1.json',panel,immutable=True)
    registered=dict(schema='jp_s6c_registered_design.v1',status='REGISTERED_BEFORE_NEW_S6C_OUTCOMES',created_utc=utc(),
        run_id=RUN,total_configurations=len(rows),preserved_s6b_controls=len(old['profiles']),new_s6c_configurations=len(seen),
        candidates=rows,recipes=recipes,capacity_axis=[16,32,64,128,256],families=list(modes),
        cue_seeds=[11,29,47],enrollment_unique_target_seconds=[5,15,30],
        panel=bind(REPORT/'design/REGISTERED_PANEL_V1.json'),source_authority=bind(S6B/'EFFECTIVE_PROFILE_REGISTRY.json'),
        planned_confirmation=dict(general='all240 both outputs, matched parents and conditions',
            enrollment='all240 under >=2 frozen known/unknown conditions plus empty controls, no query exclusions',
            native='>=6 varied paired scenes per meaningful family before empirical rejection; 4-6 finalists plus controls >=12 balanced scenes per tap and >=4 repeated sensitive cells',
            endurance='30-60 min uninterrupted paced file per retained fallback/top, fresh session per concatenated study not per turn'),
        selection_rule='No single cpWER optimization. Compare unknown/fragmentation/mixed/return/short-turn and raw-word/empty/naming errors; retain 2-4 defensible tradeoffs after local rescue and full confirmation.',
        scientific_limits=['All240 are exploratory/descriptive; historical tags preserved.','Manual bearing +/-5 degrees is reference uncertainty; no physical calibration claim.',
                           'Fixed clean enrollment from permitted E only; C-only calibration, never Q.','No new model weights/training/downloads/GUI promotion.',
                           'Null cue permutation reassigns angle content preserving delivery/missingness; nominal diagnostic remains oracle-like.'],
        implementation_status='Settings are registered hypotheses; exact effective API profiles and execution digests are frozen only after implementation/review. Any unsupported setting remains an explicit disposition.')
    save(target,registered,immutable=True)
    csv_write(REPORT/'CANDIDATE_COVERAGE_AND_DISPOSITION.csv',[{k:v for k,v in r.items() if k!='old_profile'} for r in rows])
    save(REPORT/'S6C_CHECKPOINT.json',dict(status='IN_PROGRESS',phase='DESIGN_REGISTERED_IMPLEMENTATION_REVIEW',run_id=RUN,
         design=bind(target),hardware='PENDING_FRESH_OPERATOR_FACT',new_native_jobs=0,policy_replays=0,
         completed_foundation_reference_audit='See foundation/audit_v1',resources=resources(full=True),updated_utc=utc()))
    return dict(status=registered['status'],total=len(rows),new=len(seen),panel_scenes=len(ids),path=str(target))

def calibration_amendment():
    path=REPORT/'design/C_ONLY_CALIBRATION_AMENDMENT_V1.json'
    if path.exists():return read(path)
    base=read(REPORT/'design/REGISTERED_DESIGN_V1.json');rows=[]
    conditions=[(g,t) for g in ('FIXED_ROTATION_A','FIXED_ROTATION_B') for t in (5,15,30)]+[('LARGE_COHORT',15)]
    for gallery,tier in conditions:
        parent=next(r for r in base['candidates'] if r.get('settings',{}).get('gallery_condition')==gallery and r['settings']['enrollment_tier']==tier and r['settings']['cue_condition']=='CUES_OFF')
        row=deepcopy(parent);row['candidate_id']='C%03d'%(110+len(rows));row['parent']=parent['candidate_id']
        row['title']=gallery+' '+str(tier)+'s C-only calibrated resolver';row['family']='C_only_identity_calibration'
        row['settings']['calibration_rule']='FROZEN_C_ONLY_OPEN_SET_V1';row['settings_sha256']=digest(row['settings'])
        row['disposition']='PENDING_C_ONLY_CALIBRATION_BEFORE_Q_EXECUTION';rows.append(row)
    amendment=dict(schema='jp_s6c_registration_amendment.v1',status='REGISTERED_BEFORE_NEW_S6C_MODEL_OUTCOMES',created_utc=utc(),
        parent_design=bind(REPORT/'design/REGISTERED_DESIGN_V1.json'),additional_configurations=7,total_registered_configurations=160,candidates=rows,
        reason='Mandatory matched C-only identity calibration alternatives while retaining inherited thresholds and frozen rosters',
        fitted_rule=dict(threshold_grid=[.45,.50,.5128856897354127,.55,.60,.65,.70,.75],margin_grid=[.0,.03,.05,.10],
            eligible_calibration='Only C identities in the tested gallery roster; canonical withheld strangers excluded from that condition calibration',
            objective='Lexicographic: minimize wrong-known accepted Cqueries, then maximize correct accepted Cqueries, then choose higher threshold/margin among equal outcomes; report coverage and calibration counts',
            minimum_queries=4,undercoverage='Retain control thresholds with explicitly UNAVAILABLE_CALIBRATION status, never call it fitted',
            probe_dependency=False,score_scale='Actual cosine and cosine margin; do not use joint association scores'),
        cold_warm_reporting='First eligible identity query per actual anonymous track is cold; subsequent track memory is warm. Also report first query per reference person offline; short name carry never refreshes evidence.' )
    save(path,amendment,immutable=True)
    csv_write(REPORT/'CANDIDATE_COVERAGE_AND_DISPOSITION.csv',[{k:v for k,v in r.items() if k!='old_profile'} for r in base['candidates']+rows])
    return dict(status=amendment['status'],total=160,path=str(path))

if __name__=='__main__':
    print(json.dumps(calibration_amendment() if '--calibration-amendment' in sys.argv else register(),indent=2))
