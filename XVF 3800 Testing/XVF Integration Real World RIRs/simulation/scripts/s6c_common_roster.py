"""Add six common-roster E-duration galleries; README_S6C_COMMON_ROSTER.md."""
from __future__ import annotations
import argparse
import collections
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import sys
import s6c_enrollment as E
import numpy as np

OUT=E.REPORT/'enrollment/common30_v1'
PAYLOAD=E.PAYLOAD/'common30_v1'
CONDITIONS={'COMMON30_FIXED_ROSTER_A':'FIXED_ROTATION_A','COMMON30_FIXED_ROSTER_B':'FIXED_ROTATION_B'}
TIERS=(5,15,30)

def checked(binding):
    E.verify(binding)
    return E.read(binding['path'])

def available_members(original,coverage):
    """Metadata eligibility only; no C/Q scores or template quality ranking."""
    result=sorted(x for x in original if coverage.get((x,30),{}).get('status')=='AVAILABLE')
    if len(result)!=len(set(result)):raise ValueError('Duplicate common roster identity')
    for person in result:
        if any(coverage.get((person,t),{}).get('status')!='AVAILABLE' for t in TIERS):
            raise ValueError('Thirty-second member is not available at every smaller tier')
    return result

def original_authority():
    completion_path=E.OUT/'ENROLLMENT_COMPLETION.json'
    completion=E.read(completion_path)
    if completion['status']!='COMPLETE':raise ValueError('Original enrollment is incomplete')
    plan=checked(completion['plan'])
    def output(path):
        rows=[b for b in completion['outputs'] if Path(b['path']).resolve()==Path(path).resolve()]
        if len(rows)!=1:raise ValueError('Original completion does not resolve output once')
        return rows[0],checked(rows[0])
    gi,galleries=output(E.REPORT/'RESEARCH_GALLERY_INDEX.json')
    sm,scorer=output(E.OUT/'SCORER_GALLERY_MAP.json')
    ti,templates=output(E.OUT/'TEMPLATE_INDEX.json')
    material=checked(plan['material_manifest'])
    checked(plan['material_receipt']);checked(plan['query_manifest']);scenes=checked(plan['scene_manifest'])
    if len(scenes['scenes'])!=240 or len({s['case_id'] for s in scenes['scenes']})!=240 or plan['Q_occurrence_count']!=777:
        raise ValueError('Canonical Q/case population changed')
    if scorer['people']!=plan['people'] or len(scorer['rows'])!=2169 or len(galleries['rows'])!=2169:
        raise ValueError('Original gallery authority differs')
    return dict(plan=plan,completion=completion,material=material,galleries=galleries,scorer=scorer,templates=templates,
        bindings=[E.bind(completion_path),completion['plan'],gi,sm,ti,plan['material_manifest'],plan['material_receipt'],plan['query_manifest'],plan['scene_manifest']])

def freeze():
    target=OUT/'COMMON30_GALLERY_PLAN.json'
    if target.exists():
        value=E.read(target)
        for b in value['bindings']:E.verify(b)
        return value
    authority=original_authority();old=authority['plan']
    coverage={(r['identity'],r['requested_usable_seconds']):r for r in authority['material']['coverage']}
    rows=[]
    for condition,original in CONDITIONS.items():
        old_rows=[r for r in authority['scorer']['rows'] if r['gallery_condition']==original and r['case_id'] is None]
        if len(old_rows)!=3 or {r['enrollment_tier'] for r in old_rows}!=set(TIERS):raise ValueError('Original fixed tier rows missing')
        intended=old_rows[0]['intended_identities']
        if any(r['intended_identities']!=intended for r in old_rows):raise ValueError('Original intended fixed roster changes with tier')
        members=available_members(intended,coverage)
        if not members:raise ValueError('Common roster empty; no substitute identities allowed')
        for tier in TIERS:
            row=next(r for r in old_rows if r['enrollment_tier']==tier)
            if not set(members)<=set(row['available_identities']):raise ValueError('Old gallery eligibility contradicts E metadata')
            rows.append(dict(gallery_condition=condition,enrollment_tier=tier,case_id=None,
                original_gallery_condition=original,intended_identities=members,available_identities=members,
                unavailable_identities=[],excluded_from_original_roster=sorted(set(intended)-set(members)),
                withheld_metadata_identities=sorted(set(old['people'])-set(members)),scene_derived_setup=False,
                original_fixed_row_manifest=row['manifest'],
                reuse_original_manifest=row['available_identities']==members))
    value=dict(schema='s6c-common30-gallery-plan.v1',status='FROZEN_BEFORE_GALLERY_MATERIALIZATION',created_utc=E.utc(),
        bindings=authority['bindings']+[E.bind(__file__),E.bind(Path(__file__).with_name('README_S6C_COMMON_ROSTER.md')),E.bind(Path(E.__file__))]+old['app_modules'],
        amendment=dict(outcome_informed=True,reason='Added after initial S6C results exposed roster-availability as a confound in duration comparisons',
            roster_selection='Original fixed A/B intended roster intersect metadata-eligible full30s E people, with all smaller tiers asserted available',
            selection_reads_scores=False,selection_reads_template_consistency=False,template_fitting=False,calibration_fitting=False,
            scope='Exploratory additive control; not an untouched prospective comparison or new independent validation set'),
        rows=rows,canonical_cases=240,canonical_Q_occurrences=777,source_empty_cases=old['source_empty_cases'],
        keep_all_Q_and_empty_cases=True,all_tiers_use_same_members_and_competitors=True,
        expected_backend_sha256=next(x['sha256'] for x in old['assets'] if x['component_id']=='redimnet2_b2_fp32'),
        original_plan=authority['completion']['plan'],payload_root=str(PAYLOAD.resolve()),
        limitations=['Common cohort is restricted by original E availability; current members are CMU ARCTIC and HiFiTTS, not a Common Voice duration experiment.',
            'Each tier retains its original whole-clip native centroid; natural speech content/window count and duration change together.',
            'No new C threshold fit, Q filtering, template update or model inference. Prior domain and metadata-person limitations remain.'])
    E.save(target,value)
    return value

def native_store(old_plan):
    if any(k=='edge_speech_pipeline' or k.startswith('edge_speech_pipeline.') for k in sys.modules):raise ValueError('Fresh interpreter required')
    for b in old_plan['app_modules']:E.verify(b)
    if sys.version!=old_plan['python'] or any(version(k)!=v for k,v in old_plan['versions'].items()):raise ValueError('Native numerical runtime differs')
    sys.path.insert(0,old_plan['app_root'])
    from edge_speech_pipeline.speakers import ProfileStore
    import edge_speech_pipeline.speakers as speakers
    if Path(speakers.__file__).resolve().parent!=(Path(old_plan['app_root'])/'edge_speech_pipeline').resolve():raise ValueError('Wrong ProfileStore import')
    return ProfileStore

def expected_template(authority,person,tier):
    old=authority['plan'];material=authority['material'];sources={r['source_id']:r for r in material['accepted_sources']}
    matches=[r for r in material['coverage'] if r['identity']==person and r['requested_usable_seconds']==tier and r['status']=='AVAILABLE']
    if len(matches)!=1:raise ValueError('Expected E coverage missing or duplicated')
    ids=matches[0]['source_ids']
    if any(sources[x]['identity']!=person or sources[x]['s6c_role']!='E' for x in ids):raise ValueError('Non-E template input')
    return dict(plan_sha256=authority['completion']['plan']['sha256'],metadata_identity=person,tier=tier,
        display_name=old['people'][person]['display_name'],source_ids=ids,source_bindings=[sources[x]['decoded_16k_binding'] for x in ids],
        backend_sha256=next(x['sha256'] for x in old['assets'] if x['component_id']=='redimnet2_b2_fp32'),
        native_embedding_count=sum(len(range(0,max(1,sources[x]['samples']-8000+1),16000)) for x in ids))

def check_manifest(manifest,planned,records,store_class,backend):
    if manifest['schema_version']!='edge-research-gallery.v1' or manifest['backend_sha256']!=backend:raise ValueError('Wrong gallery backend/schema')
    names={r['identity']['display_name'] for r in records};expected_ids={r['profile_id'] for r in records}
    if len(manifest['profiles'])!=len(records) or {p['profile_id'] for p in manifest['profiles']}!=expected_ids:
        raise ValueError('Gallery roster count/profile IDs differ')
    if {p['display_name'] for p in manifest['profiles']}!=names:raise ValueError('Wrong gallery display roster')
    root=Path(manifest['profile_root']).resolve();expected_files=set()
    for p in manifest['profiles']:
        original=next(r for r in records if r['profile_id']==p['profile_id'])
        for key in ('metadata','vector'):
            E.verify(p[key]);expected_files.add(Path(p[key]['path']).resolve())
            if p[key]['sha256']!=original[key]['sha256'] or p[key]['bytes']!=original[key]['bytes']:raise ValueError('Native template bytes changed')
            suffix='.json' if key=='metadata' else '.npy'
            if Path(p[key]['path']).resolve()!=root/(p['profile_id']+suffix):raise ValueError('Not exact sibling profile path')
    if {p.resolve() for p in root.iterdir()}!=expected_files:raise ValueError('Foreign file in gallery root')
    loaded=store_class(root,expected_backend_sha256=backend).load()
    if set(loaded)!=names:raise ValueError('Actual ProfileStore did not load exact common roster')
    for record in records:
        original=store_class(Path(record['metadata']['path']).parent,expected_backend_sha256=backend).load()
        name=record['identity']['display_name']
        if set(original)!={name} or not np.array_equal(loaded[name],original[name]):raise ValueError('ProfileStore-normalized vector differs from original native tier')
    return dict(actual_loaded_count=len(loaded),normalized_vectors_bit_exact_to_original=True,
                gallery_member_identities=list(planned['available_identities']))

def build():
    plan=freeze()
    target=OUT/'COMMON30_GALLERY_COMPLETION.json'
    if target.exists():return verify()
    authority=original_authority();store=native_store(authority['plan']);backend=plan['expected_backend_sha256']
    template_rows={(r['metadata_identity'],r['enrollment_tier']):r['receipt'] for r in authority['templates']['rows']}
    rows=[];scorer_rows=[];dependencies=[];new_bytes=0;reuse=0
    for p in plan['rows']:
        records=[]
        for person in p['available_identities']:
            binding=template_rows[person,p['enrollment_tier']];record=checked(binding)
            E.validate_template(record,expected_template(authority,person,p['enrollment_tier']))
            records.append(record);dependencies.append(binding)
        if p['reuse_original_manifest']:
            manifest=checked(p['original_fixed_row_manifest']);manifest_binding=p['original_fixed_row_manifest'];reuse+=1
        else:
            root=(PAYLOAD/p['gallery_condition']/('T'+str(p['enrollment_tier']))/'profiles').resolve()
            if not root.is_relative_to(PAYLOAD.resolve()):raise ValueError('Output path escapes additive gallery root')
            root.mkdir(parents=True,exist_ok=True);profiles=[]
            for record in records:
                item=dict(profile_id=record['profile_id'],display_name=record['identity']['display_name'])
                for key in ('metadata','vector'):
                    source=record[key];dest=root/Path(source['path']).name
                    if dest.exists():
                        got=E.bind(dest)
                        if got['sha256']!=source['sha256'] or got['bytes']!=source['bytes']:raise ValueError('Unreceipted changed gallery bytes retained')
                    else:shutil.copy2(source['path'],dest);new_bytes+=source['bytes']
                    item[key]=E.bind(dest)
                profiles.append(item)
            manifest=dict(schema_version='edge-research-gallery.v1',gallery_id='S6C_'+p['gallery_condition']+'_T'+str(p['enrollment_tier']),
                profile_root=str(root),backend_sha256=backend,profiles=profiles)
            path=root.parent/'GALLERY.json';E.save(path,manifest);manifest_binding=E.bind(path)
        validation=check_manifest(manifest,p,records,store,backend)
        key={k:p[k] for k in ('gallery_condition','enrollment_tier','case_id')}
        rows.append(dict(**key,manifest=manifest_binding))
        scorer_rows.append(dict(**p,manifest=manifest_binding,loaded_count=len(records),eligibility='AVAILABLE',
            profiles=[dict(metadata_identity=r['identity']['metadata_identity'],profile_id=r['profile_id'],display_name=r['identity']['display_name']) for r in records],
            native_template_receipts=[template_rows[x,p['enrollment_tier']] for x in p['available_identities']],actual_validation=validation))
    gallery_path=OUT/'RESEARCH_GALLERY_INDEX_EXTENSION.json';scorer_path=OUT/'SCORER_GALLERY_MAP_EXTENSION.json'
    original_gallery=next(b for b in authority['bindings'] if Path(b['path']).name=='RESEARCH_GALLERY_INDEX.json')
    original_map=next(b for b in authority['bindings'] if Path(b['path']).name=='SCORER_GALLERY_MAP.json')
    E.save(gallery_path,dict(schema='s6c-research-gallery-index-extension.v1',status='COMPLETE',plan=E.bind(OUT/'COMMON30_GALLERY_PLAN.json'),
        original_gallery_index=original_gallery,rows=rows,merge_policy='Append these six unique condition/tier/null-case keys; never replace the original index'))
    E.save(scorer_path,dict(schema='s6c-scorer-gallery-map-extension.v1',status='COMPLETE',runtime_input=False,
        plan=E.bind(OUT/'COMMON30_GALLERY_PLAN.json'),original_scorer_map=original_map,people=authority['scorer']['people'],rows=scorer_rows,
        canonical_case_ids=sorted(s['case_id'] for s in checked(authority['plan']['scene_manifest'])['scenes']),
        Q_occurrences=777,source_empty_cases=authority['plan']['source_empty_cases'],keep_all_Q_and_empty_cases=True,
        warning='Metadata identities, availability and original roster lineage are evaluator-only; never anonymous association input'))
    for b in authority['bindings']:E.verify(b)
    result=dict(schema='s6c-common30-gallery-completion.v1',status='COMPLETE',created_utc=E.utc(),
        plan=E.bind(OUT/'COMMON30_GALLERY_PLAN.json'),outputs=[E.bind(gallery_path),E.bind(scorer_path)],
        original_authorities_unchanged=authority['bindings'],template_dependencies=list({b['path']:b for b in dependencies}.values()),
        gallery_rows=6,native_template_assignments=sum(len(r['profiles']) for r in scorer_rows),
        reused_original_manifests=reuse,new_manifests=6-reuse,new_copied_template_bytes_this_invocation=new_bytes,
        counts_by_condition={c:dict(members=len(next(r for r in plan['rows'] if r['gallery_condition']==c)['available_identities']),
            corpus_counts=dict(collections.Counter('CMU ARCTIC' if x.startswith('CMU_ARCTIC_') else 'HiFiTTS' if x.startswith('HIFITTS_') else 'Common Voice' for x in next(r for r in plan['rows'] if r['gallery_condition']==c)['available_identities']))) for c in CONDITIONS},
        actual_ProfileStore_loads=6+sum(len(r['profiles']) for r in scorer_rows),model_loads=0,embedding_calls=0,calibration_fits=0,Q_score_calls=0,
        outcome_informed_amendment=True,selection_uses_only_E_eligibility=True,all240_Q_cases_retained=True,
        scope='Additive common-roster duration controls using original byte-exact native templates; no new inference or accuracy claim')
    E.save(target,result);return result

def verify():
    plan=freeze();done=E.read(OUT/'COMMON30_GALLERY_COMPLETION.json')
    if done['status']!='COMPLETE' or done['plan']!=E.bind(OUT/'COMMON30_GALLERY_PLAN.json'):raise ValueError('Completion/plan mismatch')
    for b in done['outputs']+done['original_authorities_unchanged']+done['template_dependencies']:E.verify(b)
    authority=original_authority();store=native_store(authority['plan'])
    galleries=checked(done['outputs'][0]);scorer=checked(done['outputs'][1])
    expected={(c,t,None) for c in CONDITIONS for t in TIERS}
    for index in (galleries,scorer):
        if len(index['rows'])!=6 or {(r['gallery_condition'],r['enrollment_tier'],r['case_id']) for r in index['rows']}!=expected:raise ValueError('Six-map grid differs')
    for row in scorer['rows']:
        p=next(x for x in plan['rows'] if all(x[k]==row[k] for k in ('gallery_condition','enrollment_tier','case_id')))
        if any(row[k]!=p[k] for k in p):raise ValueError('Scorer eligibility differs from frozen common roster')
        records=[checked(b) for b in row['native_template_receipts']]
        for person,record in zip(p['available_identities'],records):E.validate_template(record,expected_template(authority,person,p['enrollment_tier']))
        check_manifest(checked(row['manifest']),p,records,store,plan['expected_backend_sha256'])
        gr=next(x for x in galleries['rows'] if all(x[k]==row[k] for k in ('gallery_condition','enrollment_tier','case_id')))
        if gr['manifest']!=row['manifest']:raise ValueError('Gallery/scorer manifest mismatch')
    return dict(status='VERIFIED_COMMON30_GALLERIES',completion=E.bind(OUT/'COMMON30_GALLERY_COMPLETION.json'),model_calls=0)

def checks():
    coverage={(p,t):dict(status='AVAILABLE') for p in ['A','B'] for t in TIERS}
    coverage['C',5]=dict(status='AVAILABLE')
    assert available_members(['A','B','C'],coverage)==['A','B']
    assert available_members(['B','A'],coverage)==['A','B']
    altered={k:dict(v,unused_score=-999,unused_consistency=0) for k,v in coverage.items()}
    assert available_members(['A','B','C'],altered)==['A','B']
    bad=dict(coverage);bad['A',5]=dict(status='UNAVAILABLE')
    try:available_members(['A','B'],bad)
    except ValueError:pass
    else:raise AssertionError('Non-nested tier incorrectly admitted')
    try:available_members(['A','A'],coverage)
    except ValueError:pass
    else:raise AssertionError('Duplicated identity incorrectly admitted')
    assert len({(c,t,None) for c in CONDITIONS for t in TIERS})==6
    return dict(status='PASS',checks=6,model_calls=0)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('freeze','build','verify','checks'));args=parser.parse_args()
    result={'freeze':freeze,'build':build,'verify':verify,'checks':checks}[args.action]()
    print(json.dumps(result if args.action in ('verify','checks') else {k:v for k,v in result.items() if k not in ('rows','bindings','template_dependencies','original_authorities_unchanged')},indent=2))
