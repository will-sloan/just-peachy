"""Guarded application content composition checks. README_APPLICATION_CONTENT.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_panel_plan_v2 import application_qualification
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_application_content as regression

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN = ('review_application_content.py','test_application_content.py','probe_application_content.py','README_APPLICATION_CONTENT.md')
QUALIFICATIONS = {
    'APPLICATION_CELL_REVIEW_CHECK_V2.json':'PASS_V2_APPLICATION_CELL_REVIEW_DEVELOPMENT_ONLY',
    'NATIVE_WIDGET_REVIEW_CHECK_V1.json':'PASS_NATIVE_WIDGET_REVIEW_DEVELOPMENT_ONLY',
}


def code_bindings():
    entries = [bind(HERE/name) for name in OWN]
    for name,status in QUALIFICATIONS.items():
        q=load(HERE/name); require(q['status']==status,'Prerequisite qualification differs: '+name)
        verify(q['private_receipt']); proof=load(q['private_receipt']['path']);verify(proof['admission'])
        require(exact_process(load(proof['admission']['path'])['owner']) is None,'Prerequisite helper remains active')
        entries.extend([bind(HERE/name),*q['code']])
    result={}
    for b in entries:
        require(b['path'] not in result or result[b['path']]==b,'Conflicting helper dependencies');result[b['path']]=b
    return list(result.values())


def run(output):
    process=pin();started=time.monotonic();sys.path.insert(0,str(HERE.parents[3]))
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private N4 output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720);inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in OWN:
            path=output/'source'/name;path.write_bytes((HERE/name).read_bytes())
            require(bind(path)['sha256']==bind(HERE/name)['sha256'],'Attempt snapshot differs');snapshots.append(bind(path))
        try:
            code=code_bindings()
            for b in code:verify(b)
            ab,app,context=application_qualification()
            q=load(HERE/'APPLICATION_CELL_REVIEW_CHECK_V2.json');prior=load(q['private_receipt']['path']);a=load(prior['admission']['path'])
            verify(a['historical_closure_admission']);historical=load(a['historical_closure_admission']['path'])
            require(exact_process(historical['owner']) is None,'Historical closure helper remains active')
            case=historical['cases'][0]
            for name in ('finalization','consumer','archive'):verify(case[name])
            wq=load(HERE/'NATIVE_WIDGET_REVIEW_CHECK_V1.json')
            require(wq['application_source']==context['source_receipt'],'Widget and application sources differ')
            for b in wq['native_pure_modules']:verify(b)
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,
                inventory=inventory,D1_snapshot=active,application_qualification=ab,application_context=app['application_context'],
                application_source=context['source_receipt'],native_pure_modules=wq['native_pure_modules'],
                historical_closure_admission=a['historical_closure_admission'],
                fixture_scope='Actual independent readers with synthetic cell/process/clock/widget facts; unchanged pure span/casing calls; copied closure metadata within fresh fixtures; no app/model/source start'))
            regression.CONTEXT.update(output=output/'tests',case=case,source=context['source_receipt'],
                catalog=context['catalog'],galleries=context['gallery_preparation'],runtimes=context['runtimes'])
            (output/'tests').mkdir();stream=io.StringIO()
            tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(regression.ContentTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==12 and not tests.skipped,'Application content composition tests failed')
            for b in code+wq['native_pure_modules']+[ab,app['application_context'],context['source_receipt']]:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'Numerical owner changed')
            guard(output,LOCAL,started,720)
            freeze(output/'RESULT.json',dict(status='PASS_APPLICATION_CONTENT_COMPOSITION_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                synthetic_content=bind(output/'tests/test_actual_readers_join_complete_synthetic_n2_cell/SYNTHETIC_CONTENT_REVIEW.json'),
                D1_after=after,actual_readers_composed=True,synthetic_cell_ownership_clocks_geometry=True,
                native_pure_span_and_casing_methods_actually_called=True,actual_complete_application_widget_history_joined=False,
                new_application_or_model_started=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 12 application-content checks; actual readers, synthetic cell facts; no app/audio/model launch',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_APPLICATION_CONTENT_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
