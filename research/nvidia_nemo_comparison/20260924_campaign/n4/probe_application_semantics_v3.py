"""Guarded V3 semantic composition checks; README_APPLICATION_SEMANTICS_V3.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_panel_plan_v3 import application_qualification
from probe_application_transport_review import active_d1
from review_application_semantics_v3 import OWN, code_bindings, load_reference_context
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_application_semantics_v3 as regression

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')


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
            closure=load(HERE/'APPLICATION_CLOSURE_CHECK_V2.json');verify(closure['private_receipt'])
            previous=load(closure['private_receipt']['path']);verify(previous['admission'])
            old=load(previous['admission']['path']);require(exact_process(old['owner']) is None,'Fixture helper remains active')
            case=old['cases'][0]
            for name in ('finalization','consumer','archive'):verify(case[name])
            wq=load(HERE/'NATIVE_WIDGET_REVIEW_CHECK_V1.json')
            require(wq['application_source']==context['source_receipt'],'Widget and application source differs')
            for b in wq['native_pure_modules']:verify(b)
            nq=load(HERE/'NAMING_REFERENCE_CHECK_V1.json')
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,
                inventory=inventory,D1_snapshot=active,application_qualification=ab,application_context=app['application_context'],
                application_source=context['source_receipt'],native_pure_modules=wq['native_pure_modules'],
                historical_closure_admission=previous['admission'],prior_reference_inputs=nq['reference_inputs'],
                fixture_scope='Actual readers and pure span/casing methods, synthetic process/source/delivery/widget facts and copied closure metadata; fixed accepted evaluator reference rebuilt for V3; no app/audio/model launch'))
            def checkpoint():guard(output,LOCAL,started,720)
            references=load_reference_context(checkpoint=checkpoint)
            freeze(output/'REFERENCE_INPUTS.json',dict(inputs=references['inputs'],population=references['population'],
                NEVER_PASS_TO_RUNTIME=True,models_loaded=0,audio_loaded=False))
            regression.CONTEXT.update(output=output/'tests',case=case,source=context['source_receipt'],
                catalog=context['catalog'],galleries=context['gallery_preparation'],runtimes=context['runtimes'],
                references=references,old_reference_context=nq['reference_inputs']['application_context'])
            (output/'tests').mkdir();stream=io.StringIO()
            tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.SemanticTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==20 and not tests.skipped,'V3 semantic composition tests failed')
            for b in code+wq['native_pure_modules']+references['evidence']+[ab,app['application_context']]:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            checkpoint();positive=output/'tests/test_full_semantic_chain_and_reference_join_stay_development_only'
            freeze(output/'RESULT.json',dict(status='PASS_V3_APPLICATION_SEMANTIC_COMPOSITION_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),
                tests_passed=tests.testsRun,reference_inputs=bind(output/'REFERENCE_INPUTS.json'),
                synthetic_semantic_review=bind(positive/'SYNTHETIC_SEMANTIC_REVIEW.json'),
                synthetic_name_score=bind(positive/'SYNTHETIC_NAME_SCORE.json'),D1_after=after,
                actual_readers_composed=True,new_application_or_model_started=False,actual_panel_reviewed=False,
                actual_continuity_test=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 20 V3 semantic composition checks; no new application/audio/model',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_V3_SEMANTIC_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
