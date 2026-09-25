"""Guarded qualification of joined saved application observations; no inference."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import sys
import time
import unittest

from common import bind,freeze,load,verify
from metric_process import exact_process,identity,pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
import test_application_observation_review as regression

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
QUALIFICATIONS={
    'APPLICATION_TRANSPORT_REVIEW_CHECK_V1.json':'PASS_APPLICATION_TRANSPORT_REVIEW_DEVELOPMENT_ONLY',
    'APPLICATION_CLOSURE_CHECK_V2.json':'PASS_APPLICATION_CLOSURE_HELPER_ONLY',
    'RESOURCE_REVIEW_CHECK_V1.json':'PASS_RESOURCE_REVIEW_DEVELOPMENT_ONLY',
    'VIEWPORT_REVIEW_CHECK_V1.json':'PASS_VIEWPORT_REVIEW_DEVELOPMENT_ONLY',
}


def code_bindings():
    names=('review_application_observations.py','test_application_observation_review.py','probe_application_observation_review.py',
        'README_APPLICATION_OBSERVATION_REVIEW.md','probe_application_transport_review.py','mode_galleries.py',
        'test_application_closure.py','test_application_closure_v2.py','test_application_resources.py','test_resource_review.py',
        'test_viewport_ledger_v2.py')
    entries=[bind(HERE/name) for name in names]
    for name,status in QUALIFICATIONS.items():
        q=load(HERE/name);require(q['status']==status,'Required observation review qualification differs')
        entries += [bind(HERE/name),*q['code']]
    result={}
    for b in entries:
        require(b['path'] not in result or b==result[b['path']],'Conflicting dependency binding');result[b['path']]=b
    return list(result.values())


def run(output):
    process=pin();started=time.monotonic();sys.path.insert(0,str(HERE.parents[3]))
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private N4 output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720);inventory=shared_allowance(LOCAL);active=active_d1();code=code_bindings()
        for b in code:verify(b)
        closure=load(HERE/'APPLICATION_CLOSURE_CHECK_V2.json');verify(closure['private_receipt']);old=load(closure['private_receipt']['path'])
        verify(old['admission']);old_admission=load(old['admission']['path']);require(exact_process(old_admission['owner']) is None,'Historical closure helper still active')
        case=old_admission['cases'][0]
        for key in ('archive','finalization','consumer'):verify(case[key])
        app=load(HERE/'PACED_APPLICATION_CELL_CHECK_V1.json')
        require(app['source_receipt']==closure['source_receipt'],'Fixture source prerequisites differ')
        verify(app['source_receipt']);verify(app['gallery_preparation']);gallery=load(app['gallery_preparation']['path']);verify(gallery['catalog'])
        (output/'source').mkdir(parents=True);snapshots=[]
        for b in code[:4]:
            path=output/'source'/Path(b['path']).name;path.write_bytes(Path(b['path']).read_bytes())
            require(bind(path)['sha256']==b['sha256'],'Attempt snapshot differs');snapshots.append(bind(path))
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,inventory=inventory,
            D1_snapshot=active,historical_closure_admission=old['admission'],source_receipt=app['source_receipt'],gallery_preparation=app['gallery_preparation'],
            fixture_scope='Synthetic owner/clock/resource/viewport facts plus copied historical terminal/archive metadata; no new application execution'))
        try:
            regression.CONTEXT.update(output=output/'tests',case=case,source=app['source_receipt'],catalog=gallery['catalog'],galleries=app['gallery_preparation'])
            (output/'tests').mkdir();stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.ObservationReviewTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==12 and not tests.skipped,'Application observation join checks failed')
            for b in code:verify(b)
            guard(output,LOCAL,started,720);after=active_d1()
            require(after['result']['owner']==active['result']['owner'] and after['result']['child']==active['result']['child'],'Numerical owner changed; re-observe')
            freeze(output/'RESULT.json',dict(status='PASS_APPLICATION_OBSERVATION_REVIEW_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                synthetic_join_review=bind(output/'tests/test_real_review_components_compose_on_explicit_synthetic_owner_facts/SYNTHETIC_JOIN_REVIEW.json'),
                D1_after=after,new_application_or_model_started=False,actual_panel_reviewed=False,source_to_widget_latency_qualified=False,
                controlled_resources_qualified=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 12 joined observation tests; real validators on explicitly synthetic owner/clock/UI/resource facts; no inference',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_APPLICATION_OBSERVATION_REVIEW_PROBE_PRESERVED',error_type=type(exc).__name__,admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
