"""Model-free full continuity input and selected-plan checks; see accompanying README."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import time
import unittest

from common import bind,fingerprint,freeze,load,verify
from metric_process import identity,pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
import continuity_application_plan as subject
import test_continuity_application_plan as tests
import test_paced_panel_plan_v3 as fixtures

HERE=Path(__file__).resolve().parent
LOCAL=subject.LOCAL


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private continuity probe output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,LOCAL,started,720)
        check();inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir()
        for name in subject.OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Continuity source snapshot differs')
        snapshots=[bind(p) for p in sorted((output/'source').iterdir())]
        try:
            code=subject.code_bindings();qb,q,job=subject.read_input(check)
            ab,app,source=subject.panels.application_qualification()
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,sequence=qb,application_qualification=ab,actual_production_plan=False,actual_source_execution=False))
            for b in code:verify(b)
            fixtures.CONTEXT.update(source=source,source_binding=app['application_context'],app_binding=ab)
            qualified=load(q['qualification']['path']);a=load(q['private_admission']['path']);result=load(q['private_receipt']['path'])
            sequence,audio,truth,copy=[load(q[n]['path']) for n in ('plan','audio_only','evaluator_truth','copy_receipt')]
            prep,bindings,docs=subject.sequence.inputs();rebuilt,rebuilt_truth=subject.sequence.build(docs,bindings)
            tests.CONTEXT.update(sequence_binding=qb,job=job,proof=(q,qualified,a,result,sequence,audio,truth,copy,rebuilt,rebuilt_truth))
            tests.OUTPUT=output/'tests';tests.OUTPUT.mkdir();stream=io.StringIO()
            outcome=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.ContinuityPlanTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(outcome.wasSuccessful() and outcome.testsRun==14 and not outcome.skipped,'Continuity planner regression failed')
            routes=[]
            for candidate in sorted(subject.original.COMPOSITIONS):
                chosen=[subject.original.BASELINE] if candidate==subject.original.BASELINE else [subject.original.BASELINE,candidate]
                plan=tests.plan(chosen)
                for index in range(plan['required']):
                    payload=subject.execution_payload(plan,index)
                    require(payload['job']==job and 'sequence' not in payload and 'continuity' not in payload,'Audio firewall differs')
                routes.append(dict(candidate=candidate,fixture_cells=plan['required'],plan_content_sha256=fingerprint(plan)))
            for b in code+[qb,ab]:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            check()
            freeze(output/'RESULT.json',dict(status='PASS_CONTINUITY_APPLICATION_PLANNING_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=outcome.testsRun,
                sequence=qb,segments_compared=len(copy['segments']),frames=job['frames'],seconds=job['frames']/16000,
                routes=routes,fixture_payloads=sum(r['fixture_cells'] for r in routes),D1_after=after,
                actual_production_plan=False,actual_shortlist_selected=False,actual_source_execution=False,
                actual_continuity_run=False,stop_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 14 continuity planner tests, 27 PCM segments and 31 fixture payloads; no source or production plan',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_CONTINUITY_PLANNER_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
