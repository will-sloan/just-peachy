"""Plan actual journal-derivative panels from reviewed parent banks. README_PACED_PANEL_PLAN_V2.md."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import time

from common import bind,fingerprint,freeze,load,verify
from metric_process import exact_process,identity,pin
from application_source_context import review as review_source_context
import paced_panel_plan as original
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock

HERE=Path(__file__).resolve().parent
SCHEMA='n4-paced-panel-plan-v2'


def code_bindings():
    names=('paced_panel_plan_v2.py','test_paced_panel_plan_v2.py','probe_paced_panel_plan_v2.py','README_PACED_PANEL_PLAN_V2.md')
    entries=[bind(HERE/name) for name in names]+original.code_bindings()
    q=load(HERE/'JOURNAL_APPLICATION_PRESTART_CHECK_V1.json')
    entries += [bind(HERE/'JOURNAL_APPLICATION_PRESTART_CHECK_V1.json'),*q['code']]
    result={}
    for b in entries:
        require(b['path'] not in result or result[b['path']]==b,'Conflicting planner dependency');result[b['path']]=b
    return list(result.values())


def application_qualification():
    qb=bind(HERE/'JOURNAL_APPLICATION_PRESTART_CHECK_V1.json');q=load(qb['path'])
    require(q['status']=='PASS_JOURNAL_APPLICATION_PRESTART_DEVELOPMENT_ONLY' and q['tests_passed']==13
        and len(q['prepared_backends'])==len(set(q['prepared_backends']))==16
        and q['actual_source_or_model_execution'] is False,'Complete derivative prestart qualification required')
    for b in q['code']+[q['private_receipt']]:verify(b)
    tested=load(q['private_receipt']['path']);verify(tested['admission']);a=load(tested['admission']['path'])
    verify(tested['lifetime']);lifetime=load(tested['lifetime']['path'])
    require(exact_process(a['owner']) is None and exact_process(lifetime['owner']) is None
        and tested['status']=='PASS_JOURNAL_DERIVATIVE_CONTEXT_AND_PRESTART_ONLY'
        and tested['tests_passed']==13 and tested['prepared_backends']==16
        and tested['application_context']==q['application_context'],'Prestart proof or owner differs')
    context=review_source_context(q['application_context'])
    for name in ('source_receipt','catalog','gallery_preparation','runtimes'):
        require(q[name]==context[name],'Qualification/context binding differs')
    return qb,q,context


def application_context(scored, source, source_binding, app_binding, common):
    """Pure context join; only the qualified logging derivative may replace source."""
    for old,new in (('source_receipt','component_source_receipt'),('catalog','component_catalog'),
                    ('gallery_preparation','component_gallery_preparation')):
        require(scored[old]==source[new],'Scored component parent differs from derivative context')
    runtimes={Path(b['path']).name:b for b in source['runtimes']}
    require(set(runtimes)=={'n2_runtime.json','n3_runtime.json'} and scored['runtimes']==runtimes,
        'Scored and application runtime metadata differ')
    require(set(common)=={'manifest','panel','regression','models_root','assets','planner_qualification','code'},
        'Unexpected common application context fields')
    require(common['manifest']==scored['manifest'] and common['panel']==scored['panel'],'Prepared panel differs from scored bank')
    return dict(**deepcopy(common),source_receipt=deepcopy(source['source_receipt']),catalog=deepcopy(source['catalog']),
        gallery_preparation=deepcopy(source['gallery_preparation']),runtimes=deepcopy(runtimes),
        component_source_receipt=deepcopy(scored['source_receipt']),component_catalog=deepcopy(scored['catalog']),
        component_gallery_preparation=deepcopy(scored['gallery_preparation']),
        application_source_context=deepcopy(source_binding),application_qualification=deepcopy(app_binding))


def build_plan(selection,reviews,jobs,panel,regression,catalog,context):
    require(all(k in context for k in ('component_source_receipt','component_catalog','component_gallery_preparation',
        'application_source_context','application_qualification')),'Explicit journal derivative context required')
    plan=original.build_plan(selection,reviews,jobs,panel,regression,catalog,context)
    plan['schema']=SCHEMA
    plan['source_relationship']='Reviewed component parent plus qualified common complete-journal application derivative'
    return plan


def execution_payload(plan,index):
    require(plan['schema']==SCHEMA and plan['source_relationship']==
        'Reviewed component parent plus qualified common complete-journal application derivative','Wrong V2 application plan')
    # The unchanged child allowlist receives only actual application bindings.
    # A shallow header view does not change row/context objects or their hashes.
    legacy=dict(plan,schema='n4-paced-panel-plan-v1')
    return original.execution_payload(legacy,index)


def reconstruct(selection_binding,reviews,preparation_binding,code):
    mb,main=original.read_review(Path(reviews['main']['path']));xb,modes=original.read_review(Path(reviews['modes-panel']['path']))
    original.validate_review_pair(main,modes)
    require(reviews=={'main':mb,'modes-panel':xb},'Comparison review binding differs')
    verify(selection_binding);selection=load(selection_binding['path']);original.validate_selection(selection,reviews)
    verify(preparation_binding);preparation=load(preparation_binding['path'])
    outputs={Path(b['path']).name:b for b in preparation['outputs']}
    manifest,panel,regression=[outputs[name] for name in ('AUDIO_ONLY_480.json','PACED_AUDIO_ONLY_24.json','REGRESSION_AUDIO_ONLY_8.json')]
    for b in (manifest,panel,regression):verify(b)
    ab,app,source=application_qualification();scored=main['context'];assets={};models_root=None
    for kind in ('ASR','D1'):
        verify(scored['reviews'][kind]);component_review=load(scored['reviews'][kind]['path']);verify(component_review['admission'])
        a=load(component_review['admission']['path'])
        require(a['component_contract']['source_receipt']==scored['source_receipt'],'Component asset/source parent differs')
        if models_root is None:models_root=a['models_root']
        require(models_root==a['models_root'],'Component model root differs')
        for b in a['component_contract']['assets']:
            require(b['path'] not in assets or assets[b['path']]==b,'Conflicting component assets');assets[b['path']]=b
    require(bool(assets),'Bound actual component assets required')
    for b in assets.values():verify(b)
    planner=bind(HERE/'PACED_PANEL_PLAN_CHECK_V2.json');q=load(planner['path'])
    require(q['status']=='PASS_JOURNAL_DERIVATIVE_PANEL_PLANNER_DEVELOPMENT_ONLY' and q['code']==code,
        'V2 planner qualification or code differs')
    common=dict(manifest=manifest,panel=panel,regression=regression,models_root=models_root,assets=list(assets.values()),
        planner_qualification=planner,code=code)
    context=application_context(scored,source,app['application_context'],ab,common)
    jobs,panel_jobs,regression_jobs=[load(b['path'])['jobs'] for b in (manifest,panel,regression)]
    for job in panel_jobs:require(bind(job['audio_path'])['sha256']==job['audio_sha256'],'Saved panel audio changed')
    plan=build_plan(selection,reviews,jobs,panel_jobs,regression_jobs,load(context['catalog']['path']),context)
    for b in code+[mb,xb,selection_binding,preparation_binding]:verify(b)
    return plan


def admit_plan(path):
    """Versioned production reconstruction API for the future V2 runner/reviewer."""
    pb=bind(path);plan=load(path);result=load(Path(path).parent/'RESULT.json');verify(result['admission'])
    a=load(result['admission']['path']);code=code_bindings()
    require(result['status']=='PREPARED_PANELS_AND_REPEATS_ONLY' and result['plan']==pb
        and exact_process(a['owner']) is None and a['code']==code,'Plan receipt, stopped preparer or code differs')
    rebuilt=reconstruct(a['selection'],a['reviews'],a['preparation'],code)
    require(plan==rebuilt and result['required']==plan['required'],'V2 prepared panel reconstruction differs')
    verify(pb);return pb,plan


def prepare(args):
    process=pin();started=time.monotonic();prep=load(HERE/'PREPARATION_V2_CHECK.json')['preparation']
    local=Path(prep['path']).parents[2]
    require(not args.output.exists() and args.output.resolve().is_relative_to(local/'n4'),'Fresh private planner output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(args.output,local,started,720);inventory=shared_allowance(local);code=code_bindings()
        reviews={'main':bind(args.main_review),'modes-panel':bind(args.modes_review)};selection=bind(args.selection)
        plan=reconstruct(selection,reviews,prep,code);guard(args.output,local,started,720)
        freeze(args.output/'ADMISSION.json',dict(owner=identity(process),code=code,selection=selection,reviews=reviews,
            preparation=prep,inventory=inventory,inference_started=False,model_slot_admitted=False))
        freeze(args.output/'PLAN.json',plan)
        freeze(args.output/'RESULT.json',dict(status='PREPARED_PANELS_AND_REPEATS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
            admission=bind(args.output/'ADMISSION.json'),plan=bind(args.output/'PLAN.json'),required=plan['required'],
            candidates=len(plan['candidates']),source_execution_authorized=False,continuity_included=False,integrated_N4_cells=0))
        print('Prepared V2 paired panels with explicit component/application source lineage; no launch',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('main-review','modes-review','selection','output'):parser.add_argument('--'+name,type=Path,required=True)
    prepare(parser.parse_args())
