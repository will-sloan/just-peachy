"""V3-reviewed scores to delivery-observed panels. README_PACED_PANEL_PLAN_V4.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import time

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
import paced_panel_plan as original
import paced_panel_plan_v3 as previous
import panel_scoring_admission_v3 as scores
from review_scoring_bank_v3 import guard, require, shared_allowance
from scoring_bank_v3 import writer_lock

HERE=Path(__file__).resolve().parent
LOCAL=previous.LOCAL
SCHEMA='n4-paced-panel-plan-v4'
APPLICATION_POLICY=previous.APPLICATION_POLICY
SOURCE_RELATIONSHIP=previous.SOURCE_RELATIONSHIP
SCORING_RELATIONSHIP='Both closed V3 score reviews; exact shared context except verified main-only prefix reuse'
OWN=('panel_scoring_admission_v3.py','paced_panel_plan_v4.py','test_paced_panel_plan_v4.py',
     'probe_paced_panel_plan_v4.py','README_PACED_PANEL_PLAN_V4.md')
application_qualification=previous.application_qualification


def code_bindings():
    qb=bind(HERE/'PACED_PANEL_PLAN_CHECK_V3.json');q=load(qb['path']);old=previous.code_bindings()
    require(q['status']=='PASS_DELIVERY_PANEL_PLANNER_DEVELOPMENT_ONLY' and q['code']==old,
        'Parent delivery planner is not qualified')
    for b in old+[q['private_receipt']]:verify(b)
    tested=load(q['private_receipt']['path']);verify(tested['admission']);a=load(tested['admission']['path'])
    require(a['code']==old and exact_process(a['owner']) is None,'Parent planner probe remains active or differs')
    sb,sq=scores.qualification();entries=[bind(HERE/n) for n in OWN]+[qb,sb]+old+sq['review_code']
    unique={}
    for b in entries:
        require(b['path'] not in unique or unique[b['path']]==b,'Conflicting V4 planner dependency')
        unique[b['path']]=b
    return [b for _,b in sorted(unique.items())]


def application_context(scored, source, source_binding, app_binding, common):
    context=previous.application_context(scored,source,source_binding,app_binding,common)
    context['scoring_review_policy']=deepcopy(scores.POLICY)
    return context


def build_plan(selection,reviews,jobs,panel,regression,catalog,context):
    require(context.get('scoring_review_policy')==scores.POLICY,'Exact V3 reviewed-score policy required')
    plan=previous.build_plan(selection,reviews,jobs,panel,regression,catalog,context)
    plan['schema']=SCHEMA;plan['scoring_relationship']=SCORING_RELATIONSHIP
    return plan


def execution_payload(plan,index):
    require(plan['schema']==SCHEMA and plan['scoring_relationship']==SCORING_RELATIONSHIP
        and plan['context'].get('scoring_review_policy')==scores.POLICY,'Wrong V4 scored application plan')
    # No score, reference, selection or provenance is introduced into the child.
    return previous.execution_payload(dict(plan,schema=previous.SCHEMA),index)


def reconstruct(selection_binding,reviews,preparation_binding,code):
    mb,main=scores.read_review(Path(reviews['main']['path']));xb,modes=scores.read_review(Path(reviews['modes-panel']['path']))
    scores.validate_review_pair(main,modes)
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
    planner=bind(HERE/'PACED_PANEL_PLAN_CHECK_V4.json');q=load(planner['path'])
    require(q['status']=='PASS_V3_SCORED_PANEL_PLANNER_DEVELOPMENT_ONLY' and q['code']==code,
        'V4 planner qualification or code differs')
    common=dict(manifest=manifest,panel=panel,regression=regression,models_root=models_root,assets=list(assets.values()),
        planner_qualification=planner,code=code)
    context=application_context(scored,source,app['application_context'],ab,common)
    jobs,panel_jobs,regression_jobs=[load(b['path'])['jobs'] for b in (manifest,panel,regression)]
    for job in panel_jobs:require(bind(job['audio_path'])['sha256']==job['audio_sha256'],'Saved panel audio changed')
    plan=build_plan(selection,reviews,jobs,panel_jobs,regression_jobs,load(context['catalog']['path']),context)
    for b in code+[mb,xb,selection_binding,preparation_binding]:verify(b)
    return plan


def admit_plan(path):
    """Versioned production reconstruction API for the future V4 runner/reviewer."""
    pb=bind(path);plan=load(path);result=load(Path(path).parent/'RESULT.json');verify(result['admission'])
    a=load(result['admission']['path']);code=code_bindings()
    require(result['status']=='PREPARED_PANELS_AND_REPEATS_ONLY' and result['plan']==pb
        and exact_process(a['owner']) is None and a['code']==code,'Plan receipt, stopped preparer or code differs')
    rebuilt=reconstruct(a['selection'],a['reviews'],a['preparation'],code)
    require(plan==rebuilt and result['required']==plan['required'],'V4 prepared panel reconstruction differs')
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
        print('Prepared V4 paired panels with explicit component/application source lineage; no launch',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('main-review','modes-review','selection','output'):parser.add_argument('--'+name,type=Path,required=True)
    prepare(parser.parse_args())
