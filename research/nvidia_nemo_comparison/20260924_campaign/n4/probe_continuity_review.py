"""Bounded model-free continuity evidence review checks. README_CONTINUITY_REVIEW.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind,freeze,load,verify
from metric_process import exact_process,identity,pin
from paced_child_admission import assert_plain_path
from paced_panel_plan_v3 import application_qualification
from probe_application_transport_review import active_d1
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
import review_continuity_application as review
import test_continuity_transport as transport
import test_continuity_cell as cell
import test_continuity_application as population

HERE=Path(__file__).resolve().parent
LOCAL=review.LOCAL
EXPECTED={'transport':19,'cell':11,'population':13}


def run(scope,output,cell_proof=None):
    process=pin();started=time.monotonic();sys.path.insert(0,str(HERE.parents[3]))
    require(scope in EXPECTED and not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private review probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,LOCAL,started,720)
        check();inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in review.OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Source snapshot differs');snapshots.append(bind(target))
        try:
            code=review.code_bindings()
            for b in code:verify(b)
            ab,app,source=application_qualification();dependencies=[];extra={}
            tests_root=output/'tests';tests_root.mkdir()
            if scope=='transport':
                q=load(HERE/'PRIVATE_PROCESS_CHECK_V3.json');verify(q['private_receipt']);dependencies.append(q['private_receipt'])
                transport.SAVED=load(q['private_receipt']['path'])['fixture_lifetimes']
                for b in transport.SAVED:
                    verify(b);require(exact_process(load(b['path'])['owner']) is None,'Saved native fixture owner active')
                transport.OUTPUT=tests_root;transport.SOURCE=source['source_receipt'];test_class=transport.TransportReviewTests
            elif scope=='cell':
                q=load(HERE/'APPLICATION_CLOSURE_CHECK_V2.json');verify(q['private_receipt']);prior=load(q['private_receipt']['path'])
                verify(prior['admission']);a=load(prior['admission']['path']);require(exact_process(a['owner']) is None,'Closure fixture helper active')
                case=a['cases'][0]
                for name in ('finalization','consumer','archive'):verify(case[name])
                dependencies.extend([q['private_receipt'],prior['admission']])
                cell.CONTEXT.update(output=tests_root,case=case,source=source['source_receipt'],catalog=source['catalog'],
                    galleries=source['gallery_preparation'],runtimes=source['runtimes']);test_class=cell.CellReviewTests
            else:
                require(cell_proof is not None,'Completed cell-scope probe required')
                assert_plain_path(cell_proof,LOCAL/'n4');cb=bind(cell_proof);c=load(cell_proof);verify(c['admission']);a=load(c['admission']['path'])
                require(c['status']=='PASS_CONTINUITY_REVIEW_DEVELOPMENT_CHECKS_ONLY' and c['scope']=='cell'
                    and c['tests_passed']==11 and a['code']==code and exact_process(a['owner']) is None,'Cell probe identity/code/scope differs')
                verify(c['synthetic_join_review']);dependencies.extend([cb,c['admission'],c['synthetic_join_review']])
                population.CONTEXT.update(output=tests_root,synthetic_join=c['synthetic_join_review']);test_class=population.PanelReviewTests
            freeze(output/'ADMISSION.json',dict(owner=identity(process),scope=scope,code=code,source_snapshots=snapshots,
                dependencies=dependencies,inventory=inventory,D1_snapshot=active,application_qualification=ab,
                actual_source_execution=False,actual_production_plan=False,
                fixture_scope='Synthetic transport/clock/delivery/native/resource/viewport facts; historical copied terminal metadata; no actual application run'))
            stream=io.StringIO();outcome=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(test_class))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(outcome.wasSuccessful() and outcome.testsRun==EXPECTED[scope] and not outcome.skipped,'Continuity '+scope+' checks failed')
            if scope=='transport':
                extra=dict(saved_lifetimes_reviewed=len(transport.SAVED),
                    saved_classifications=bind(tests_root/'test_saved_actual_native_closure_and_failure_classification/SAVED_CLASSIFICATIONS.json'),
                    synthetic_join_review=bind(tests_root/'test_join_preserves_all_acceptance_and_history_limits/SYNTHETIC_REVIEW.json'),
                    synthetic_long_trace_review=bind(tests_root/'test_full_twenty_minute_trace_including_last_partial_chunk/SYNTHETIC_LONG_TRACE_REVIEW.json'))
            elif scope=='cell':extra=dict(synthetic_join_review=bind(tests_root/'test_all_real_readers_compose_with_synthetic_facts/SYNTHETIC_COMPLETE_JOIN_REVIEW.json'))
            for b in code+dependencies+[ab]:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            check();freeze(output/'RESULT.json',dict(status='PASS_CONTINUITY_REVIEW_DEVELOPMENT_CHECKS_ONLY',scope=scope,
                utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),
                tests_passed=outcome.testsRun,D1_after=after,actual_production_plan=False,actual_application_run=False,
                actual_source_execution=False,actual_continuity_qualified=False,stop_restart_qualified=False,
                integrated_N4_cells=0,N4_accepted=False,**extra))
            print('PASS: '+str(outcome.testsRun)+' continuity '+scope+' development checks; no model, source or application',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_CONTINUITY_REVIEW_PROBE_PRESERVED',scope=scope,
                owner=identity(process),error_type=type(exc).__name__,source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--scope',choices=sorted(EXPECTED),required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--cell-proof',type=Path)
    args=parser.parse_args();run(args.scope,args.output,args.cell_proof)
