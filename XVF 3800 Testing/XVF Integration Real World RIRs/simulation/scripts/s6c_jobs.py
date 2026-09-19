"""Build explicit frozen native job manifests. See README_S6C_JOBS.md."""
import argparse
from s6c_common import *
from s6c_execution import make_job,validate_job

def build(epoch,stage,candidates=None,attempt='v1'):
    spec_path=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json');spec=read(spec_path)
    for b in spec['execution_files']:bind(b['path'],b['sha256'])
    profiles=spec['profiles'];bank={s['case_id']:s for s in verified(spec['scene_manifest'])['scenes']}
    panel=set(verified(spec['panel'])['case_ids'])
    by_family={family:sorted(cid for cid in panel if bank[cid]['family_id']==family) for family in sorted({s['family_id'] for s in bank.values()})}
    canonical=[p for p in profiles if p['gallery_condition']=='NONE' and p['route']=='SAME' and p['cue_condition']=='CUES_OFF']
    first_recipe={}
    for p in canonical:first_recipe.setdefault(p['recipe_id'],p['candidate_id'])
    if stage=='smoke':
        selected={first_recipe['N01']}
        ids=[by_family[f][0] for f in ('F01','F03','F12')]
    elif stage=='recipes':
        selected={cid for rid,cid in first_recipe.items() if rid!='N00'}
        selected|={p['candidate_id'] for p in profiles if p['recipe_id']=='N07' and p['cue_condition']=='REAL_ALIGNED_CUES' and p['gallery_condition']=='NONE'}
        ids=sorted(panel)
    elif stage in ('families','fresh_families'):
        # Each structurally different family gets real cue-off/on checks at a
        # matched capacity64; preserve whole scenes and exact source timings.
        selected=set()
        for mode in ('old_voice_gate','normalized_joint','reliability_joint','hypothesis_joint','semimarkov_joint','bounded_global_joint','quarantine_joint','shadow_gallery_joint'):
            for cue in ('CUES_OFF','REAL_ALIGNED_CUES'):
                eligible=[p for p in profiles if p['recipe_id']==('N01' if stage=='fresh_families' else 'N00') and p['gallery_condition']=='NONE' and p['route']=='SAME'
                    and p['cue_condition']==cue and p['profile']['tracker']['mode']==mode and p['profile']['tracker']['max_tracks']==64
                    and p['profile']['tracker']['lifecycle_policy']=='retire_archive']
                if not eligible:raise ValueError('Missing native family companion: '+mode+' '+cue)
                selected.add(min(p['candidate_id'] for p in eligible))
        ids=[by_family[f][0] for f in ('F01','F03','F04','F06','F08','F12')]
    elif stage=='split':
        selected={p['candidate_id'] for p in profiles if p['route']!='SAME'}
        ids=sorted(panel)
    elif stage=='enrollment':
        selected={p['candidate_id'] for p in profiles if p['gallery_condition']!='NONE'}
        ids=[by_family[f][0] for f in ('F01','F03','F04','F06','F08','F12')]
    elif stage=='full':
        if not candidates:raise ValueError('Full confirmation requires explicit retained candidate IDs')
        selected=set(candidates);ids=sorted(bank)
    elif stage=='paced':
        if not candidates:raise ValueError('Paced confirmation requires explicit candidate IDs')
        selected=set(candidates);ids=[by_family[f][0] for f in sorted(by_family)]
    else:raise ValueError('Unknown bounded stage')
    if candidates and stage not in ('full','paced'):selected &= set(candidates)
    if not selected:raise ValueError('Empty selected candidate set')
    selected_profiles=[p for p in profiles if p['candidate_id'] in selected]
    if {p['candidate_id'] for p in selected_profiles}!=selected:raise ValueError('Unknown requested candidate ID')
    gallery_rows=verified(spec['gallery_index'])['rows'] if spec.get('gallery_index') else []
    cue_rows={}
    if spec.get('cue_variant_index'):
        cue_rows={(r['case_id'],r['stream'],r['condition']):r['telemetry'] for r in verified(spec['cue_variant_index'])['rows']}
    jobs=[]
    for p in selected_profiles:
        for cid in ids:
            gallery=None;telemetry=None
            if p['gallery_condition']!='NONE':
                match=[r for r in gallery_rows if r['gallery_condition']==p['gallery_condition'] and r['enrollment_tier']==p['enrollment_tier'] and r.get('case_id') in (None,cid)]
                if len(match)!=1:raise ValueError('Exactly assigned gallery required for '+p['candidate_id']+'/'+cid)
                gallery=match[0]['manifest']
            if p['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES'):
                telemetry=cue_rows[cid,p['asr_tap'],p['cue_condition']]
            jobs.append(make_job(spec,p,cid,stage,stage=='paced',attempt,gallery,telemetry))
    inputs={(r['case_id'],r['stream']):r for r in verified(spec['input_index'])['rows']}
    for job in jobs:validate_job(spec,job,inputs,check_assets=False)
    target=REPORT/'jobs'/epoch/(stage+'_'+attempt+'.json')
    data=dict(schema='jp_s6c_native_jobs.v1',status='REGISTERED_EXACT_JOBS',stage=stage,epoch=epoch,attempt=attempt,
        jobs=jobs,requested=len(jobs),case_ids=ids,candidate_ids=sorted(selected),
        profile_routes=[dict(candidate_id=p['candidate_id'],stream=p['asr_tap'],identity_tap=p['identity_tap']) for p in selected_profiles],
        execution_manifest=bind(spec_path),builder_source=bind(__file__),created_utc=utc(),
        selection='Frozen metadata panel/family recipe plus explicit retained candidate set; no reference labels supplied to engine')
    if target.exists():
        previous=read(target)
        if previous['jobs']!=jobs:raise ValueError('Existing job manifest differs; use named revision')
    else:save(target,data,immutable=True)
    return dict(status='REGISTERED_EXACT_JOBS',jobs=len(jobs),candidates=len(selected),scenes=len(ids),path=str(target))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('smoke','recipes','families','fresh_families','split','enrollment','full','paced'))
    p.add_argument('--epoch',default='epoch1');p.add_argument('--candidates',nargs='*');p.add_argument('--attempt',default='v1');a=p.parse_args()
    print(json.dumps(build(a.epoch,a.stage,a.candidates,a.attempt),indent=2))
