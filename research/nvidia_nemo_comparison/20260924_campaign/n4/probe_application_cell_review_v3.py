"""Qualify V3 cell evidence composition without inference or GUI execution."""
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
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_application_cell_review_v3 as regression

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('review_application_cell_v3.py','test_application_cell_review_v3.py','probe_application_cell_review_v3.py',
     'README_APPLICATION_CELL_REVIEW_V3.md','review_application_observations_v2.py')
QUALIFICATIONS = {
    'APPLICATION_TRANSPORT_REVIEW_CHECK_V3.json': 'PASS_APPLICATION_TRANSPORT_V3_REVIEW_DEVELOPMENT_ONLY',
    'APPLICATION_OBSERVATION_REVIEW_CHECK_V1.json': 'PASS_APPLICATION_OBSERVATION_REVIEW_DEVELOPMENT_ONLY',
    'DELIVERY_APPLICATION_PRESTART_CHECK_V1.json': 'PASS_APPLICATION_DELIVERY_PRESTART_DEVELOPMENT_ONLY',
}


def code_bindings():
    entries = [bind(HERE/name) for name in OWN]
    for name, status in QUALIFICATIONS.items():
        q = load(HERE/name); require(q['status'] == status, 'Component qualification differs')
        verify(q['private_receipt']); proof = load(q['private_receipt']['path']); verify(proof['admission'])
        require(exact_process(load(proof['admission']['path'])['owner']) is None, 'Qualification helper remains active')
        entries += [bind(HERE/name), *q['code']]
    result = {}
    for b in entries:
        require(b['path'] not in result or result[b['path']] == b, 'Conflicting component dependency')
        result[b['path']] = b
    return list(result.values())


def run(output):
    process = pin(); started = time.monotonic(); sys.path.insert(0,str(HERE.parents[3]))
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720); inventory = shared_allowance(LOCAL); active = active_d1()
        freeze(output/'PROBE_OWNER.json', dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(parents=True); snapshots=[]
        for name in OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Source snapshot differs');snapshots.append(bind(target))
        try:
            code=code_bindings()
            for b in code:verify(b)
            app_binding,app,source=application_qualification()
            closure=load(HERE/'APPLICATION_CLOSURE_CHECK_V2.json');verify(closure['private_receipt'])
            previous=load(closure['private_receipt']['path']);verify(previous['admission'])
            old=load(previous['admission']['path']);require(exact_process(old['owner']) is None,'Fixture helper remains active')
            case=old['cases'][0]
            for name in ('finalization','consumer','archive'):verify(case[name])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,application_qualification=app_binding,application_context=app['application_context'],
                historical_closure_admission=previous['admission'],
                fixture_scope='Synthetic transport/source/owner/clock/native/resource/viewport facts; copied historical terminal/archive metadata changed only within fixtures; no new source/model/application execution'))
            regression.CONTEXT.update(output=output/'tests',case=case,source=source['source_receipt'],
                catalog=source['catalog'],galleries=source['gallery_preparation'],runtimes=source['runtimes'])
            (output/'tests').mkdir(); stream = io.StringIO()
            tests = unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.CellReviewTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun == 11 and not tests.skipped, 'V3 joined cell checks failed')
            for b in code+[app_binding]: verify(b)
            after = active_d1()
            require(after['result']['child'] == active['result']['child'] and after['run_id'] == active['run_id'], 'D1 owner changed')
            guard(output,LOCAL,started,720)
            freeze(output/'RESULT.json',dict(status='PASS_V3_APPLICATION_CELL_REVIEW_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                synthetic_join_review=bind(output/'tests/test_all_real_readers_compose_with_synthetic_facts/SYNTHETIC_COMPLETE_JOIN_REVIEW.json'),
                D1_after=after,new_application_or_model_started=False,actual_panel_reviewed=False,
                native_payload_semantics_reviewed=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 11 V3 cell joins using actual readers and synthetic facts; no source/model/application execution',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_V3_APPLICATION_CELL_REVIEW_PROBE_PRESERVED',
                error_type=type(exc).__name__,owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
