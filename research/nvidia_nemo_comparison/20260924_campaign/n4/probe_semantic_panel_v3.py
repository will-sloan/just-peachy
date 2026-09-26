"""Guarded whole-panel naming development checks; README_SEMANTIC_PANEL_V3.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import time
import unittest

from common import bind,freeze,load,verify
from metric_process import identity,pin
from review_application_semantics_v3 import load_reference_context
from probe_application_transport_review import active_d1
from review_semantic_panel_v3 import OWN,code_bindings
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
import test_semantic_panel_v3 as regression

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private naming-panel probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720);inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in OWN:
            path=output/'source'/name;path.write_bytes((HERE/name).read_bytes())
            require(bind(path)['sha256']==bind(HERE/name)['sha256'],'Naming-panel source snapshot differs');snapshots.append(bind(path))
        try:
            code=code_bindings()
            for b in code:verify(b)
            q=load(HERE/'APPLICATION_SEMANTICS_CHECK_V3.json');refq=load(q['reference_inputs']['path'])
            old=load(HERE/'APPLICATION_CELL_REVIEW_CHECK_V3.json')
            for b in (q['synthetic_semantic_review'],q['synthetic_name_score'],old['synthetic_join_review']):verify(b)
            observed=load(q['synthetic_semantic_review']['path'])
            payloads=[b for b in observed['observed']['content']['cell']['transport']['evidence'] if Path(b['path']).name=='INPUT.json']
            require(len(payloads)==1,'One observed input required');verify(payloads[0])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,synthetic_observed=q['synthetic_semantic_review'],synthetic_score=q['synthetic_name_score'],
                synthetic_cell=old['synthetic_join_review'],payload=payloads[0],reference_inputs=refq['inputs'],
                production_plan_created=False,new_application_or_model_started=False))
            checkpoint=lambda:guard(output,LOCAL,started,720);references=load_reference_context(checkpoint=checkpoint)
            regression.CONTEXT.update(output=output,synthetic_observed=q['synthetic_semantic_review'],synthetic_score=q['synthetic_name_score'],
                references=references,payload=payloads[0],checkpoint=checkpoint)
            regression.prior.CONTEXT.update(output=output,synthetic_join=old['synthetic_join_review'])
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.SemanticPanelTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==22 and not tests.skipped,'Name-panel development checks failed')
            for b in code+references['evidence']+[q['synthetic_semantic_review'],q['synthetic_name_score'],old['synthetic_join_review'],payloads[0]]:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            checkpoint()
            freeze(output/'RESULT.json',dict(status='PASS_V3_SEMANTIC_PANEL_DEVELOPMENT_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                synthetic_compact=bind(output/'SYNTHETIC_COMPACT_NAME_SCORE.json'),weighted_counts=bind(output/'WEIGHTED_COUNT_FIXTURE.json'),
                output_budget=bind(output/'OUTPUT_BUDGET_FIXTURE.json'),D1_after=after,development_population_sizes=[40,240],
                positive_production_plan_gate_executed=False,actual_panel_reviewed=False,new_application_or_model_started=False,
                evaluator_truth_loaded=True,reference_never_passed_to_runtime=True,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 22 V3 semantic-panel population, compaction, weighted-count and scope checks; no actual panel launched',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_V3_SEMANTIC_PANEL_PROBE_PRESERVED',error_type=type(exc).__name__,owner=identity(process),
                source_snapshots=snapshots,admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
