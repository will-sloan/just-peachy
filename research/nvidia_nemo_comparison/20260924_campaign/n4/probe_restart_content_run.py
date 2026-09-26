"""Bounded restart content composition probe. README_RESTART_CONTENT_RUN.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import identity, pin
from paced_panel_plan_v3 import application_qualification
from probe_scoring_history_v3 import active_bank
from review_scoring_bank_v3 import guard, shared_allowance
from review_scoring_bank import require
from scoring_bank import writer_lock
import review_restart_content_run as subject
import test_restart_content_run as tests
import test_restart_native_content as native_tests
import test_native_caption_review as pure_fixture
import test_restart_complete as complete_tests
import test_restart_run_review as population_tests


def run(output):
    process=pin();started=time.monotonic();local=subject.LOCAL
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'),'Fresh private probe output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,local,started,1200)
        check();resources=shared_allowance(local);active=active_bank(local)
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        snapshots=[]
        for name in subject.OWN:
            target=output/'source'/name;target.parent.mkdir(exist_ok=True);target.write_bytes((subject.HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(subject.HERE/name)['sha256'],'Source snapshot differs');snapshots.append(bind(target))
        try:
            code=subject.code_bindings();qb,q,context=application_qualification()
            native=load(subject.HERE/'NATIVE_WIDGET_REVIEW_CHECK_V1.json')
            require(native['application_source']==context['source_receipt'],'Native fixture and admitted application source differ')
            for b in native['native_pure_modules']:verify(b)
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,
                resources=resources,bank_start=active,application_qualification=qb,application_context=q['application_context'],
                application_source=context['source_receipt'],native_pure_modules=native['native_pure_modules'],
                maximum_seconds=1200,maximum_output_bytes=8*1024**2,actual_application_or_model_started=False,
                fixture_scope='Real native/viewport/fixed-roster readers with synthetic content/clocks/geometry; completed lifecycle leaf and plan admission mocked in composition/population fixtures'))
            tests.CONTEXT.update(context,output=output/'tests/content');tests.CONTEXT['output'].mkdir(parents=True)
            native_tests.OUTPUT=output/'tests/native';(native_tests.OUTPUT/'native').mkdir(parents=True);(native_tests.OUTPUT/'widget').mkdir()
            native_tests.SOURCE_RECEIPT=context['source_receipt'];pure_fixture.SOURCE=Path(load(context['source_receipt']['path'])['prototype'])
            complete_tests.OUTPUT=output/'tests/complete';complete_tests.OUTPUT.mkdir()
            population_tests.OUTPUT=output/'tests/population';population_tests.OUTPUT.mkdir()
            suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in (
                tests.ContentCellTests,tests.ContentPopulationTests,native_tests.ReleasedNativeContentTests,
                native_tests.RestartNativeWidgetTests,complete_tests.RestartCompleteTests,population_tests.RestartPopulationTests))
            stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(result.wasSuccessful() and result.testsRun==68 and not result.skipped,'Restart content composition tests failed')
            for b in code+snapshots+native['native_pure_modules']+[qb,q['application_context']]:verify(b)
            for b in native['native_pure_modules']:
                if Path(b['path']).name=='casing.py':
                    from review_native_widget import casing
                    function,loaded=casing(context['source_receipt'])
                    require(loaded==b and Path(function.__code__.co_filename).resolve()==Path(b['path']).resolve(),
                            'Foreign pure casing function')
                else:
                    name='jp_n4_caption_fixture.'+Path(b['path']).stem
                    require(Path(sys.modules[name].__file__).resolve()==Path(b['path']).resolve(),'Foreign fixture pure module')
            require('torch' not in sys.modules,'Model runtime imported by development probe')
            after=active_bank(local);require(after['plan']==active['plan'],'Active bank plan changed')
            check();end_resources=shared_allowance(local)
            freeze(output/'RESULT.json',dict(status='PASS_RESTART_CONTENT_RUN_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=result.testsRun,
                source_snapshots=snapshots,code_records=len(code),bank_end=after,resources_end=end_resources,
                actual_native_roster_viewport_readers=True,synthetic_ownership_clocks_geometry=True,
                complete_lifecycle_leaf_mocked_in_content_tests=True,plan_admission_and_cells_mocked_in_population_tests=True,
                actual_production_restart_run_reviewed=False,actual_application_or_model_started=False,
                source_to_widget_latency_qualified=False,actual_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 68 restart content/population development checks; no app, model, audio or Pi execution',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RESTART_CONTENT_RUN_PROBE_PRESERVED',owner=identity(process),
                error_type=type(exc).__name__,source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
