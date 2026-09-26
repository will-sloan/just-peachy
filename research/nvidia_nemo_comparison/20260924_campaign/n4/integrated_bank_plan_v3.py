"""Exact reviewed-component join for N4. See README_INTEGRATED_HISTORY_V3.md."""
from copy import deepcopy
from itertools import product
from pathlib import Path
import argparse
import json
import sys

from common import audio_only,bind,fingerprint,freeze,load,verify
from mode_galleries import CONDITIONS,backend_contract

HERE=Path(__file__).resolve().parent
MAIN_MODE='open_with_names'
SCHEMA='n4-integrated-method-bank-plan-v1'
EXPECTED={'ASR':1920,'D0':960,'D1':960}
PASSED={'ASR':'PASS_ASR_FULL_BANK_COMPONENTS_ONLY','D0':'PASS_MATCHED_FULL_BANK_COMPONENTS_ONLY',
        'D1':'PASS_D1_FULL_BANK_COMPONENTS_ONLY'}


def code_bindings():
    from integrated_bank_plan_v2 import code_bindings as old_code
    return old_code()+[bind(HERE/n) for n in ('method_artifact_v3.py','application_publication_v3.py','controller_projection_v3.py',
        'integrated_bank_v3.py','integrated_bank_plan_v3.py','test_integrated_history_v3.py',
        'probe_integrated_history_v3.py','README_INTEGRATED_HISTORY_V3.md','integrated_prefix_reuse.py','test_integrated_prefix_reuse.py','README_INTEGRATED_PREFIX_REUSE.md')]


def exact_jobs(jobs):
    if len(jobs)!=480:raise ValueError('Require all 480 audio-only jobs')
    by_id={}
    for job in jobs:
        audio_only(job)
        if job['job_id'] in by_id:raise ValueError('Duplicate audio-only job')
        by_id[job['job_id']]=deepcopy(job)
    if {t:sum(j['tap']==t for j in jobs) for t in ('O0','O1')}!={'O0':240,'O1':240}:
        raise ValueError('Both taps must retain 240 jobs')
    return by_id


def review_sources(kind,review):
    """Extract only already-reviewed binding rows; no Q words/activity returned."""
    if review.get('status')!=PASSED[kind]:raise ValueError(kind+' passed terminal review required')
    if kind=='ASR':
        if review.get('component_cells')!=1920:raise ValueError('ASR review census differs')
        admission,terminal=review['admission'],review['final_result']
        rows=[r['result'] for r in review['cells']]
    elif kind=='D1':
        if review.get('component_cells')!=960:raise ValueError('D1 review census differs')
        admission,terminal=review['admission'],review['terminal']
        rows=[r['result'] for r in review['rows']]
    else:
        if review.get('encoder_clip_cells')!=960:raise ValueError('D0 review census differs')
        terminal,admission=review['inputs'][:2]
        rows=[b for r in review['cells'] for b in r['results']]
    if len(rows)!=EXPECTED[kind] or len({r['path'] for r in rows})!=len(rows):
        raise ValueError(kind+' review has missing or duplicated cells')
    return admission,terminal,rows


def nested_bindings(value):
    if isinstance(value,dict):
        if set(value)=={'path','sha256','bytes'}:yield value
        else:
            for part in value.values():yield from nested_bindings(part)
    elif isinstance(value,list):
        for part in value:yield from nested_bindings(part)


def read_component_bank(kind,review_binding,*,source_binding,manifest_binding,jobs):
    """Recheck terminal owner, source/profile/cache receipt and every parent file."""
    import psutil
    verify(review_binding);review=load(review_binding['path'])
    admission_binding,terminal_binding,rows=review_sources(kind,review)
    for b in (admission_binding,terminal_binding):verify(b)
    admission=load(admission_binding['path']);terminal=load(terminal_binding['path'])
    required_status='COLLECTED_REQUIRES_REVIEW' if kind=='D0' else 'FULL_BANK_COLLECTED_REQUIRES_REVIEW'
    owner=terminal['owner']
    try:
        if abs(psutil.Process(owner['pid']).create_time()-owner['create_time'])<.001:
            raise ValueError('Exact component coordinator is still active')
    except psutil.NoSuchProcess:pass
    if (terminal['status']!=required_status or terminal['completed']!=EXPECTED[kind]
            or terminal['total']!=EXPECTED[kind] or terminal['admission']!=admission_binding
            or terminal.get('child') is not None):raise ValueError('Component terminal differs')
    component=admission if kind=='D0' else admission['component_contract']
    if component['source_receipt']!=source_binding or admission['manifest']!=manifest_binding:
        raise ValueError('Component source or admitted audio manifest differs')
    for field in ('code','dependencies'):
        for b in nested_bindings(component.get(field,[])):verify(b)
    for b in review.get('code',[]):verify(b)
    if review.get('reviewer'):verify(review['reviewer'])
    if kind!='D0' and admission['jobs']!=list(jobs.values()):raise ValueError('Component audio job order differs')
    if kind=='D0':
        from d0_bank_components import cell_key
        key_for=lambda j,e,p:cell_key(admission_binding['sha256'],j,e,p)
    elif kind=='D1':
        from d1_full_bank import component_key
        key_for=lambda j,e,p:component_key(admission,j,e,p)
    else:
        from asr_full_bank import component_key
        key_for=lambda j,e,p:component_key(admission,j,e,p)
    from app.pipeline import effective_profile
    records=[]
    for binding in rows:
        verify(binding);cell=load(binding['path']);job=audio_only(cell['job'])
        if jobs.get(job['job_id'])!=job:raise ValueError('Component has a changed or foreign job')
        variant=cell['variant'] if kind=='ASR' else cell['encoder']
        profile=effective_profile('balanced','anonymous_conversation',job['tap']).to_dict()
        if (cell['status']!='COMPLETE' or cell['admission_sha256']!=admission_binding['sha256']
                or cell['profile_sha256']!=fingerprint(profile) or cell['cache_key']!=key_for(job,variant,profile)):
            raise ValueError('Component status, admission, profile or cache key differs')
        if kind!='D0' and (cell.get('actual_neural_inference') is not True or cell.get('cpu_affinity')!=[4]):
            raise ValueError('Actual component inference contract missing')
        if kind=='D0' and (cell.get('error') is not None or cell.get('tracker_name_or_ASR_outputs_present') is not False):
            raise ValueError('D0 component contains an error or downstream prediction')
        if Path(binding['path']).resolve()!=Path(admission['output']).resolve()/variant/job['job_id']/'RESULT.json':
            raise ValueError('Component escaped its admitted bank')
        verify(cell['events'])
        records.append(dict(kind=kind,variant=variant,job=job,result=binding,cache_key=cell['cache_key'],
            events=cell['events'],namespace=cell.get('namespace')))
    return records


def build_join(jobs,catalog,records,galleries,context,*,scope,panel_jobs):
    """Pure exact census join. Missing/failed parents cannot silently reduce it."""
    jobs=exact_jobs(jobs)
    if scope not in ('main','modes-panel'):raise ValueError('Unknown bank scope')
    panel=exact_panel(panel_jobs,jobs)
    from compose_release_v3 import inventory
    composition={}
    for row in inventory(catalog).values():
        c=backend_contract(catalog,row['key'],MAIN_MODE);key=(c['variant'],c['diarization'],c['encoder'])
        if key in composition:raise ValueError('Duplicate composition tuple')
        composition[key]=c
    if set(composition)!=set(product(('A0','A1','A2','A3'),('D0','D1'),('E0','E1'))):
        raise ValueError('Require the exact 16-composition catalog')
    sources={}
    required={(k,v,j) for k,variants in [('ASR',('A0','A1','A2','A3')),('D0',('E0','E1')),('D1',('E0','E1'))]
              for v in variants for j in jobs}
    for r in records:
        key=(r['kind'],r['variant'],r['job']['job_id'])
        if key in sources or key not in required or r['job']!=jobs.get(key[2]):raise ValueError('Duplicate, foreign or altered component parent')
        if r['kind']!='ASR':
            expected=galleries['encoders'][r['variant']]['conditions']['open']['namespace']
            if r['namespace']!=expected:raise ValueError('Embedding namespace differs from fixed gallery')
        sources[key]=r
    if set(sources)!=required:raise ValueError('Incomplete 3840-component parent census')
    rows=[];selected=list(jobs) if scope=='main' else panel
    modes=[MAIN_MODE] if scope=='main' else [m for m in CONDITIONS if m!=MAIN_MODE]
    for jid in selected:
        for (a,d,e),base in sorted(composition.items()):
            for mode in modes:
                contract=backend_contract(catalog,base['backend_key'],mode)
                parents=[sources[('ASR',a,jid)],sources[(d,e,jid)]]
                identity=dict(audio=jobs[jid],contract=contract,context=context,
                    parents=[{k:r[k] for k in ('result','cache_key','events')} for r in parents],
                    clock='MODELED_COMPONENT_AVAILABILITY_AND_100MS_SOURCE_CURSOR')
                rows.append(dict(cell_id=f'{a}_{d}_{e}_{jid}_{mode}',job_id=jid,composition=f'{a}_{d}_{e}',
                    contract=contract,parents=identity['parents'],cache_key=fingerprint(identity),
                    D0_E1_association_qualification='NOMINAL_UNQUALIFIED_C_SCALE_FAILED' if (d,e)==('D0','E1') else 'FROZEN_NOMINAL',
                    physical_widget_observed=False,integrated_N4_cells=0))
    expected=7680 if scope=='main' else 1536
    if len(rows)!=expected or len({r['cell_id'] for r in rows})!=expected:raise ValueError('Integrated census differs')
    return dict(schema=SCHEMA,status='PREPARED_REVIEWED_COMPONENT_JOIN_ONLY',scope=scope,context=context,
        jobs=list(jobs.values()),rows=rows,required=expected,main_mode=MAIN_MODE,
        unavailable_catalog_entries=[dict(key=r['key'],reason=r.get('reason','Unavailable'),execution_credit=0)
            for r in catalog['backends'] if not r['implemented']],
        mode_panel='Four additional modes on 24 frozen cells; main open mode already included in 7680',
        integrated_N4_cells=0,actual_neural_inference=False,physical_widget_observed=False,
        acceptance='Modeled application-method collection only; complete source/GUI/scoring/resource qualification remains required')


def exact_panel(panel_jobs,jobs):
    if len(panel_jobs)!=24 or len({j['job_id'] for j in panel_jobs})!=24:raise ValueError('Require the unchanged 24-cell panel')
    for j in panel_jobs:
        audio_only(j)
        if jobs.get(j['job_id'])!=j:raise ValueError('Panel is not an exact subset of the admitted bank')
    if sum(j['tap']=='O0' for j in panel_jobs)!=12:raise ValueError('Panel must retain both taps')
    return [j['job_id'] for j in panel_jobs]


def prepare(args):
    qualification=load(HERE/'INTEGRATED_HISTORY_CHECK_V3.json')
    if qualification['status']!='PASS_INTEGRATED_HISTORY_BOUND_DERIVATIVE_ONLY' or qualification['code']!=code_bindings():
        raise ValueError('Native clock integration qualification missing or code changed')
    verify(qualification['private_receipt'])
    for b in qualification['code']:verify(b)
    public=load(HERE/'PREPARATION_V2_CHECK.json');verify(public['preparation']);prep=load(public['preparation']['path'])
    outputs={Path(b['path']).name:b for b in prep['outputs']}
    manifest=outputs['AUDIO_ONLY_480.json'];panel=outputs['PACED_AUDIO_ONLY_24.json']
    verify(manifest);verify(panel);jobs=exact_jobs(load(manifest['path'])['jobs'])
    publication=load(HERE/'APPLICATION_PUBLICATION_CHECK_V1.json');empty=load(HERE/'EMPTY_CONTROLLER_CHECK_V1.json')
    if (publication['status']!='PASS_ACTUAL_PUBLICATION_AND_CONSUMER_METHODS'
            or empty['status']!='PASS_38_REAL_EMPTY_OUTPUT_METHOD_CHECKS'
            or empty['source_receipt']!=publication['source_receipt']
            or publication['unchanged_projected_history_cases']!=160 or publication['unchanged_projected_final_cases']!=160
            or publication['checks_count']!=160 or empty['checks_count']!=38):raise ValueError('Method qualification missing')
    for parent in (publication,empty):
        for b in (parent['private_receipt'],*parent['code']):verify(b)
    source=publication['source_receipt'];verify(source);source_doc=load(source['path']);root=Path(source_doc['prototype'])
    for rel,b in source_doc['files'].items():verify(dict(path=str((root/rel).resolve()),**b))
    sys.path[:0]=[str(root),str(root/'vendor')]
    gallery=publication['gallery_preparation'];verify(gallery);galleries=load(gallery['path']);verify(galleries['catalog'])
    wiring=load(HERE/'ACCEPTED_SOURCE_CATALOG_CHECK.json')
    if wiring['source_catalog']!=galleries['catalog'] or galleries['catalog']!=bind(root/'config/backends.json'):
        raise ValueError('Gallery, actual source and Controller catalogs differ')
    for b in wiring['inputs']:verify(b)
    runtimes={Path(b['path']).name:b for b in wiring['inputs'] if Path(b['path']).name in ('n2_runtime.json','n3_runtime.json')}
    if len(runtimes)!=2:raise ValueError('Both actual runtime metadata bindings required')
    reviews={k:bind(getattr(args,k.lower()+'_review')) for k in EXPECTED}
    records=[]
    for kind,b in reviews.items():records.extend(read_component_bank(kind,b,source_binding=source,manifest_binding=manifest,jobs=jobs))
    for j in jobs.values():
        if bind(j['audio_path'])['sha256']!=j['audio_sha256']:raise ValueError('Saved waveform changed')
    context=dict(source_receipt=source,gallery_preparation=gallery,catalog=galleries['catalog'],manifest=manifest,panel=panel,
        reviews=reviews,runtimes=runtimes,qualification=[bind(HERE/'APPLICATION_PUBLICATION_CHECK_V1.json'),bind(HERE/'EMPTY_CONTROLLER_CHECK_V1.json'),bind(HERE/'INTEGRATED_HISTORY_CHECK_V3.json')],
        code=code_bindings())
    if getattr(args,'reuse_review',None) is not None:context['reuse_review']=bind(args.reuse_review)
    plan=build_join(list(jobs.values()),load(galleries['catalog']['path']),records,galleries,context,
        scope=args.scope,panel_jobs=load(panel['path'])['jobs'])
    from integrated_prefix_reuse import load_reuse
    load_reuse(plan)
    if args.output.exists():raise ValueError('Preserve previous plans; choose a fresh output')
    freeze(args.output,plan)
    print(json.dumps(dict(status=plan['status'],required=plan['required'],plan=bind(args.output),integrated_N4_cells=0)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('asr-review','d0-review','d1-review','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--reuse-review',type=Path)
    parser.add_argument('--scope',choices=('main','modes-panel'),required=True)
    import psutil
    p=psutil.Process();p.cpu_affinity([14]);p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    prepare(parser.parse_args())
