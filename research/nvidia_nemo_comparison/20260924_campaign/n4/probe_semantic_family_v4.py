"""Model-free V4 semantic/content panel checks. README_SEMANTIC_FAMILY_V4.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind,freeze,load,verify
from metric_process import exact_process,identity,pin
from paced_panel_plan_v4 import application_qualification
from probe_scoring_history_v3 import active_bank
from review_scoring_bank_v3 import guard,shared_allowance
from review_scoring_bank import require
from scoring_bank_v3 import writer_lock
import semantic_family_v4 as family
from review_application_semantics_v4 import load_reference_context
import test_application_semantics_v4 as semantics
import test_semantic_panel_v4 as names
import test_application_content_panel_v4 as content
import test_semantic_family_v4 as cross


def suite(cls,output):
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    path=output/(cls.__name__+'.txt');path.write_text(stream.getvalue(),encoding='utf-8')
    require(result.wasSuccessful() and not result.skipped,'Semantic family check failed: '+cls.__name__)
    return dict(suite=cls.__name__,tests=result.testsRun,log=bind(path))


def run(output):
    process=pin();started=time.monotonic();local=family.LOCAL;sys.path.insert(0,str(family.HERE.parents[3]))
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private semantic family probe required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,local,started,1200)
        check();resources=shared_allowance(local);active=active_bank(local)
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        snapshots=[];checks=[]
        for name in family.OWN:
            p=output/'source'/name;p.parent.mkdir(exist_ok=True);p.write_bytes((family.HERE/name).read_bytes())
            require(bind(p)['sha256']==bind(family.HERE/name)['sha256'],'Attempt source snapshot differs');snapshots.append(bind(p))
        try:
            code=family.code_bindings();ab,app,context=application_qualification()
            closure=load(family.HERE/'APPLICATION_CLOSURE_CHECK_V2.json');verify(closure['private_receipt'])
            previous=load(closure['private_receipt']['path']);verify(previous['admission']);old=load(previous['admission']['path'])
            require(exact_process(old['owner']) is None,'Historical closure helper active');case=old['cases'][0]
            for name in ('finalization','consumer','archive'):verify(case[name])
            wq=load(family.HERE/'NATIVE_WIDGET_REVIEW_CHECK_V1.json')
            require(wq['application_source']==context['source_receipt'],'Native/widget source differs')
            for b in wq['native_pure_modules']:verify(b)
            nq=load(family.HERE/'NAMING_REFERENCE_CHECK_V1.json')
            cellq=load(family.HERE/'APPLICATION_FAMILY_CHECK_V4.json');verify(cellq['synthetic_join_review'])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,
                resources=resources,bank_start=active,application_qualification=ab,application_context=app['application_context'],
                application_source=context['source_receipt'],native_pure_modules=wq['native_pure_modules'],
                historical_closure_admission=previous['admission'],prior_reference_inputs=nq['reference_inputs'],
                synthetic_cell=cellq['synthetic_join_review'],maximum_seconds=1200,maximum_output_bytes=8*1024**2,
                fixture_scope='Actual V4 evidence/content/naming readers and pure span/casing methods over newly generated synthetic process/source/delivery/widget facts; accepted evaluator references rebuilt only in evaluator; no application/audio/model/Pi execution'))
            references=load_reference_context(checkpoint=check)
            freeze(output/'REFERENCE_INPUTS.json',dict(inputs=references['inputs'],population=references['population'],
                NEVER_PASS_TO_RUNTIME=True,models_loaded=0,audio_loaded=False))
            semantics.CONTEXT.update(output=output/'semantics',case=case,source=context['source_receipt'],
                catalog=context['catalog'],galleries=context['gallery_preparation'],runtimes=context['runtimes'],
                references=references,old_reference_context=nq['reference_inputs']['application_context'])
            semantics.CONTEXT['output'].mkdir();checks.append(suite(semantics.SemanticTests,output));check()
            positive=semantics.CONTEXT['output']/'test_full_semantic_chain_and_reference_join_stay_development_only'
            observed=bind(positive/'SYNTHETIC_SEMANTIC_REVIEW.json');score=bind(positive/'SYNTHETIC_NAME_SCORE.json')
            value=load(observed['path']);body=value['observed']['content']
            payloads=[b for b in body['cell']['transport']['evidence'] if Path(b['path']).name=='INPUT.json']
            require(len(payloads)==1,'One semantic input required');verify(payloads[0])
            freeze(output/'SYNTHETIC_CONTENT_REVIEW.json',body);cb=bind(output/'SYNTHETIC_CONTENT_REVIEW.json')
            for label,module in (('names',names),('content',content)):
                root=output/label;root.mkdir();module.CONTEXT.update(output=root,checkpoint=check,
                    synthetic_observed=observed,synthetic_score=score,references=references,payload=payloads[0],synthetic_content=cb)
                module.prior.CONTEXT.update(output=root,synthetic_join=cellq['synthetic_join_review'])
                check();checks.append(suite(module.SemanticPanelTests if label=='names' else module.ContentPanelTests,output))
            cross.CONTEXT.update(output=output/'cross',content=cb,payload=payloads[0]);cross.CONTEXT['output'].mkdir()
            check();checks.append(suite(cross.FamilyTests,output))
            for b in code+snapshots+wq['native_pure_modules']+references['evidence']+[ab,app['application_context'],observed,score,cb]:verify(b)
            require('torch' not in sys.modules,'Model runtime imported by development probe')
            after=active_bank(local);require(after['plan']==active['plan'],'Main plan changed')
            check();end=shared_allowance(local)
            freeze(output/'RESULT.json',dict(status='PASS_V4_SEMANTIC_FAMILY_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),source_snapshots=snapshots,checks=checks,tests_passed=sum(r['tests'] for r in checks),
                code_records=len(code),reference_inputs=bind(output/'REFERENCE_INPUTS.json'),synthetic_semantic_review=observed,
                synthetic_name_score=score,synthetic_content_review=cb,synthetic_compact_names=bind(output/'names/SYNTHETIC_COMPACT_NAME_SCORE.json'),
                synthetic_compact_content=bind(output/'content/SYNTHETIC_COMPACT_CONTENT.json'),
                semantic_output_budget=bind(output/'names/OUTPUT_BUDGET_FIXTURE.json'),
                content_output_budget=bind(output/'cross/test_maximum_content_panel_fits_with_registry_and_failure_reserve/CONTENT_BUDGET.json'),
                bank_end=after,resources_end=end,actual_readers_composed=True,development_population_sizes=[40,240],
                semantic_calculations_unchanged=True,raw_delivery_summary_preserved_in_bound_envelope=True,
                exact_utf8_and_platform_newline_output_bound_tested=True,evaluator_truth_loaded=True,
                reference_never_passed_to_runtime=True,positive_production_plan_gate_executed=False,
                actual_panel_reviewed=False,actual_application_or_model_started=False,actual_continuity_test=False,
                naming_accuracy_qualified=False,source_to_widget_latency_qualified=False,controlled_resources_qualified=False,
                integrated_N4_cells=0,N4_accepted=False,N5_complete=False))
            print('PASS: V4 semantic/content/name family; no application or model launch',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_V4_SEMANTIC_FAMILY_PROBE_PRESERVED',owner=identity(process),
                error_type=type(exc).__name__,checks_completed=checks,source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
