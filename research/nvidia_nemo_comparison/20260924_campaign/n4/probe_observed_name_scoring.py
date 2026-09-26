"""Guarded fixed-name diagnostics probe; see README_OBSERVED_NAME_SCORING.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import time
import unittest

from common import bind,freeze,load,verify
from metric_process import exact_process,identity,pin
from naming_reference import load_qualified_context
from probe_application_transport_review import active_d1
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
import test_observed_name_scoring as regression

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('score_observed_names.py','test_observed_name_scoring.py','probe_observed_name_scoring.py','README_OBSERVED_NAME_SCORING.md')


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private name-scoring probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720);inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in OWN:
            path=output/'source'/name;path.write_bytes((HERE/name).read_bytes())
            require(bind(path)['sha256']==bind(HERE/name)['sha256'],'Name-scoring source snapshot differs');snapshots.append(bind(path))
        try:
            qb=bind(HERE/'NAMING_REFERENCE_CHECK_V1.json');q=load(qb['path'])
            require(q['status']=='PASS_EVALUATOR_NAMING_REFERENCE_DEVELOPMENT_ONLY','Reference prerequisite differs')
            verify(q['private_receipt']);prior=load(q['private_receipt']['path']);verify(prior['admission'])
            require(exact_process(load(prior['admission']['path'])['owner']) is None,'Prior helper remains active')
            code={}
            for b in [*[bind(HERE/name) for name in OWN],qb,*q['code']]:
                require(b['path'] not in code or code[b['path']]==b,'Conflicting naming dependency');verify(b);code[b['path']]=b
            code=list(code.values());verify(q['synthetic_observed_review']);verify(q['private_context'])
            observed=load(q['synthetic_observed_review']['path'])
            payloads=[b for b in observed['observed']['content']['cell']['transport']['evidence'] if Path(b['path']).name=='INPUT.json']
            require(len(payloads)==1,'One independently observed input required');verify(payloads[0])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,
                inventory=inventory,D1_snapshot=active,reference_qualification=qb,
                reference_inputs=q['reference_inputs'],synthetic_observed_review=q['synthetic_observed_review'],
                observed_payload=payloads[0],fixture_scope='Existing reference context and saved synthetic observation plus hand-computed name controls; no new GUI/audio/model'))
            checkpoint=lambda:guard(output,LOCAL,started,720)
            context=load_qualified_context(checkpoint=checkpoint)
            require(context==load(q['private_context']['path']),'Reconstructed reference context differs')
            regression.CONTEXT.update(context=context,observed=observed,payload=load(payloads[0]['path']),checkpoint=checkpoint)
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.NameScoringTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==18 and not tests.skipped,'Observed-name scoring checks failed')
            freeze(output/'SYNTHETIC_NAME_SCORE.json',regression.CONTEXT['saved_score'])
            for b in code+context['evidence']+[q['synthetic_observed_review'],payloads[0]]:verify(b)
            after=active_d1()
            require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'Numerical owner changed')
            checkpoint()
            freeze(output/'RESULT.json',dict(status='PASS_OBSERVED_NAME_DIAGNOSTIC_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                synthetic_score=bind(output/'SYNTHETIC_NAME_SCORE.json'),D1_after=after,
                fixed_identity_controls_tested=True,evaluator_truth_loaded=True,models_loaded=0,audio_loaded=False,
                synthetic_observation_only=True,naming_accuracy_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 18 observed-name checks, including fixed-name/all-Unknown controls; synthetic observations only',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_OBSERVED_NAME_SCORING_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
