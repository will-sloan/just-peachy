"""Explicit delivery-observed application panels. README_PACED_PANEL_PLAN_V3.md."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import time

from common import bind,fingerprint,freeze,load,verify
from metric_process import exact_process,identity,pin
from application_source_context import review as review_source_context
from application_delivery import POLICY as DELIVERY_POLICY
from paced_child_admission import assert_plain_path
from review_application_transport import validate_lifetime
import paced_panel_plan as original
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock

HERE=Path(__file__).resolve().parent
SCHEMA='n4-paced-panel-plan-v3'
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
APPLICATION_POLICY=dict(schema='n4-paced-application-variant-v1',cell_module='paced_application_cell_v2',
    variant='source-delivery-v2',success_status='CELL_WITH_SOURCE_DELIVERY_CLOSED_REQUIRES_REVIEW',
    delivery=deepcopy(DELIVERY_POLICY),independent_delivery_review_required=True)
SOURCE_RELATIONSHIP='Reviewed component parent plus qualified complete-journal and source-delivery application variant'


def code_bindings():
    names=('paced_panel_plan_v3.py','test_paced_panel_plan_v3.py','probe_paced_panel_plan_v3.py','README_PACED_PANEL_PLAN_V3.md')
    entries=[bind(HERE/name) for name in names]+original.code_bindings()
    q=load(HERE/'DELIVERY_APPLICATION_PRESTART_CHECK_V1.json')
    entries += [bind(HERE/'DELIVERY_APPLICATION_PRESTART_CHECK_V1.json'),*q['code']]
    result={}
    for b in entries:
        require(b['path'] not in result or result[b['path']]==b,'Conflicting planner dependency');result[b['path']]=b
    return list(result.values())


def validate_prestart(q,tested,admission,checks,child,records,catalog,source_files):
    """Reconstruct all 16 recorded preparations; counts alone are insufficient."""
    require(q['status']=='PASS_APPLICATION_DELIVERY_PRESTART_DEVELOPMENT_ONLY' and q['tests_passed']==13
        and q['prepared_backends']==16 and q['actual_source_or_model_execution'] is False
        and q['integrated_N4_cells']==0 and q['N4_accepted'] is False,'Delivery prestart qualification differs')
    require(tested['status']=='PASS_DELIVERY_CONTEXT_AND_PRESTART_ONLY' and tested['tests_passed']==13
        and tested['prepared_backends']==16 and tested['actual_source_or_model_execution'] is False
        and tested['application_context']==q['application_context']==admission['application_context']
        and tested['lifetime']==q['lifetime'] and tested['integrated_N4_cells']==0
        and tested['N4_accepted'] is False,'Prestart proof or context differs')
    require(child['status']=='PASS_DELIVERY_APPLICATION_PRESTART_ONLY' and child['tests_run']==9
        and child['failures']==child['errors']==child['skipped']==0 and child['admission']==tested['admission']
        and child['owner']==checks['owner']==q['child'] and child['actual_source_or_model_execution'] is False
        and child['integrated_N4_cells']==0 and child['N4_accepted'] is False
        and checks['source_or_model_execution'] is False and checks['integrated_N4_cells']==0,
        'Prestart child failed, executed a source, or belongs to another owner')
    contracts={c['backend_key']:c for c in original.composition_catalog(catalog).values()}
    require(len(checks['prepared_cells'])==len(records)==16 and [r[0] for r in records]==checks['prepared_cells']
        and {r['backend'] for r in checks['prepared_cells']}==set(contracts),'Prepared backend census differs')
    for record,prepared,closed,capture in records:
        require(record in checks['prepared_cells'] and record['engine']==contracts[record['backend']]['engine']
            and prepared['contract']==contracts[record['backend']] and prepared['job']==admission['job']
            and prepared['runtimes']==q['runtimes'] and prepared['gallery_preparation']==q['gallery_preparation']
            and prepared['desktop']==checks['desktop'],'Prepared route/job/runtime/gallery/desktop differs')
        require(prepared['status']=='PREPARED_NO_SOURCE_OR_MODELS_STARTED' and prepared['no_auto_start'] is True
            and prepared['application_variant']==APPLICATION_POLICY['variant']
            and prepared['delivery_policy']==DELIVERY_POLICY and prepared['integrated_N4_cells']==0,
            'Wrong prepared application variant')
        require(closed['status']=='PREPARED_ONLY_CLOSED' and closed['controller_closed'] is True
            and closed['controller_worker_exited'] is True and closed['source_start_requested'] is False
            and closed['errors']==closed['callback_errors']==[] and closed['delivery_join'] is None
            and closed['application_variant']==APPLICATION_POLICY['variant'] and closed['delivery_policy']==DELIVERY_POLICY
            and closed['delivery_capture']==record['delivery_capture'] and closed['integrated_N4_cells']==0
            and closed['complete_N4_acceptance'] is False,'Prepared Controller closure differs')
        require(capture['status']=='PREPARED_WITHOUT_SOURCE_DELIVERY' and capture['policy']==DELIVERY_POLICY
            and capture['test_seams_used'] is False and capture['launch_attempts']==0
            and capture['installed'] is False and capture['observation'] is None and capture['trace'] is None
            and capture['errors']==[] and capture['job_fingerprint']==fingerprint(prepared['job'])
            and capture['contract_fingerprint']==fingerprint(prepared['contract']) and capture['source_files']==source_files
            and capture['owner_join']['controller_closed'] is True and capture['owner_join']['controller_worker_exited'] is True
            and capture['model_accuracy_qualified'] is False and capture['deadline_or_continuity_accepted'] is False
            and capture['integrated_N4_cells']==0, 'Prestart delivery capture differs')


def _read(binding,root):
    path=Path(binding['path']);assert_plain_path(path,root)
    require(path.stat().st_size<=2*1024**2,'Oversize prestart proof')
    verify(binding);value=load(path);verify(binding);return value


def prestart_evidence(q):
    root=Path(q['private_receipt']['path']).parent;assert_plain_path(root,LOCAL/'n4')
    tested=_read(q['private_receipt'],root);admission=_read(tested['admission'],root)
    checks=_read(tested['checks'],root);child=_read(tested['child_result'],root)
    lifetime=_read(tested['lifetime'],root);records=[]
    require(len(checks['prepared_cells'])==16,'Prepared backend population differs')
    for r in checks['prepared_cells']:
        require(isinstance(r['backend'],str) and Path(r['backend']).name==r['backend'], 'Invalid backend path')
        folder=root/'prepared'/r['backend']
        for key,name in (('prepared','PREPARED.json'),('result','RESULT.json'),('delivery_capture','delivery/CAPTURE.json')):
            require(Path(r[key]['path'])==folder/name,'Foreign prepared-cell evidence')
        records.append((r,_read(r['prepared'],root),_read(r['result'],root),_read(r['delivery_capture'],root)))
    return tested,admission,checks,child,lifetime,records


def application_qualification():
    qb=bind(HERE/'DELIVERY_APPLICATION_PRESTART_CHECK_V1.json');q=load(qb['path'])
    for b in q['code']+q['source_snapshots']+[q['private_receipt']]:verify(b)
    tested,a,checks,child,lifetime,records=prestart_evidence(q)
    require(q['helper']==a['owner'] and lifetime['owner']==q['child']
        and all(exact_process(who) is None for who in (a['owner'],q['child'],q['publication_owner'])),
        'Exact prestart helper, child or publisher remains active')
    require(a['code']==q['code'] and lifetime['script']==bind(HERE/'probe_delivery_application_prestart.py'),
        'Prestart code or script differs')
    checked=validate_lifetime(lifetime,owner=q['child'],executable=lifetime['executable'],
        script=lifetime['script'],argv_sha256=lifetime['argv_sha256'],desktop=checks['desktop'],cpu=14)
    require(checked==tested['lifetime_review']==q['lifetime_review'],'Recorded native closure review differs')
    context=review_source_context(q['application_context'])
    for name in ('source_receipt','catalog','gallery_preparation','runtimes'):
        require(q[name]==context[name],'Qualification/context binding differs')
    prototype=Path(load(context['source_receipt']['path'])['prototype'])
    source_files=[bind(prototype/'app'/name) for name in ('pipeline.py','buffers.py')]
    validate_prestart(q,tested,a,checks,child,records,load(context['catalog']['path']),source_files)
    verify(qb);return qb,q,context


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
        application_source_context=deepcopy(source_binding),application_qualification=deepcopy(app_binding),
        application_policy=deepcopy(APPLICATION_POLICY))


def build_plan(selection,reviews,jobs,panel,regression,catalog,context):
    require(all(k in context for k in ('component_source_receipt','component_catalog','component_gallery_preparation',
        'application_source_context','application_qualification')),'Explicit journal derivative context required')
    require(context.get('application_policy')==APPLICATION_POLICY,'Explicit qualified delivery variant required')
    plan=original.build_plan(selection,reviews,jobs,panel,regression,catalog,context)
    plan['schema']=SCHEMA
    plan['source_relationship']=SOURCE_RELATIONSHIP
    return plan


def execution_payload(plan,index):
    require(plan['schema']==SCHEMA and plan['source_relationship']==SOURCE_RELATIONSHIP
        and plan['context'].get('application_policy')==APPLICATION_POLICY,'Wrong V3 application plan')
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
    planner=bind(HERE/'PACED_PANEL_PLAN_CHECK_V3.json');q=load(planner['path'])
    require(q['status']=='PASS_DELIVERY_PANEL_PLANNER_DEVELOPMENT_ONLY' and q['code']==code,
        'V3 planner qualification or code differs')
    common=dict(manifest=manifest,panel=panel,regression=regression,models_root=models_root,assets=list(assets.values()),
        planner_qualification=planner,code=code)
    context=application_context(scored,source,app['application_context'],ab,common)
    jobs,panel_jobs,regression_jobs=[load(b['path'])['jobs'] for b in (manifest,panel,regression)]
    for job in panel_jobs:require(bind(job['audio_path'])['sha256']==job['audio_sha256'],'Saved panel audio changed')
    plan=build_plan(selection,reviews,jobs,panel_jobs,regression_jobs,load(context['catalog']['path']),context)
    for b in code+[mb,xb,selection_binding,preparation_binding]:verify(b)
    return plan


def admit_plan(path):
    """Versioned production reconstruction API for the future V3 runner/reviewer."""
    pb=bind(path);plan=load(path);result=load(Path(path).parent/'RESULT.json');verify(result['admission'])
    a=load(result['admission']['path']);code=code_bindings()
    require(result['status']=='PREPARED_PANELS_AND_REPEATS_ONLY' and result['plan']==pb
        and exact_process(a['owner']) is None and a['code']==code,'Plan receipt, stopped preparer or code differs')
    rebuilt=reconstruct(a['selection'],a['reviews'],a['preparation'],code)
    require(plan==rebuilt and result['required']==plan['required'],'V3 prepared panel reconstruction differs')
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
        print('Prepared V3 paired panels with explicit component/application source lineage; no launch',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('main-review','modes-review','selection','output'):parser.add_argument('--'+name,type=Path,required=True)
    prepare(parser.parse_args())
