"""Guarded model-free two-session lifecycle checks; README_RESTART_APPLICATION.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import identity, pin
from probe_restart_session import inputs as prior_inputs
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_restart_application as tests

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('restart_application_cell.py','restart_archive.py','test_restart_application.py',
     'probe_restart_application.py','README_RESTART_APPLICATION.md')


def inputs():
    admitted=prior_inputs();qb=bind(HERE/'RESTART_SESSION_CHECK_V1.json');q=load(qb['path'])
    require(q['status']=='PASS_RELEASED_SESSION_DEVELOPMENT_ONLY','Release-session prerequisite changed')
    verify(q['private_receipt']);registry={}
    for b in admitted['code']+[qb]+q['code']+[bind(HERE/n) for n in OWN]:
        verify(b);require(b['path'] not in registry or registry[b['path']]==b,'Conflicting qualified code')
        registry[b['path']]=b
    admitted.update(code=list(registry.values()),release_qualification=qb)
    return admitted


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private restart-cell probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        checkpoint=lambda:guard(output,LOCAL,started,720)
        checkpoint();inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Source snapshot differs');snapshots.append(bind(target))
        try:
            admitted=inputs()
            freeze(output/'ADMISSION.json',dict(owner=identity(process),source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,**{k:v for k,v in admitted.items() if k!='prototype'},
                actual_application_or_audio_file_started=False,actual_restart_pair=False))
            context=dict(output=output,prototype=admitted['prototype'],checkpoint=checkpoint,cases=admitted['cases'])
            tests.CONTEXT.update(context);tests.session_tests.CONTEXT.update(context)
            tests.session_tests.historical.CONTEXT.update(context)
            sys.path[:0]=[str(admitted['prototype']),str(admitted['prototype']/'vendor'),str(HERE.parents[3])]
            from controller_projection import forbid_inference
            stream=io.StringIO()
            with forbid_inference():
                outcome=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                    unittest.defaultTestLoader.loadTestsFromTestCase(tests.RestartApplicationTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(outcome.wasSuccessful() and outcome.testsRun==21 and not outcome.skipped,'Restart application development checks failed')
            for b in admitted['code']+snapshots:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            checkpoint()
            freeze(output/'RESULT.json',dict(status='PASS_RESTART_APPLICATION_DEVELOPMENT_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(),admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),
                tests_passed=outcome.testsRun,D1_after=after,
                synthetic_pair_wiring=bind(output/'SYNTHETIC_PAIR_WIRING.json'),synthetic_open_archive=bind(output/'SYNTHETIC_OPEN_ARCHIVE.json'),
                lifecycle_methods_with_mocked_owners_and_gates=True,
                actual_application_or_audio_file_started=False,actual_GUI_or_model_started=False,
                actual_restart_pair=False,engine_capture_runtime_not_exercised=True,
                actual_restart_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 21 same-Controller lifecycle and open-archive checks; actual exclusive run remains',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RESTART_APPLICATION_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
