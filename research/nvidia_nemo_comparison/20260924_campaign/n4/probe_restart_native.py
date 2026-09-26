"""Guarded explicit-prefix native reader checks; README_RESTART_NATIVE.md."""
import argparse
from datetime import datetime,timezone
import io
from pathlib import Path
import time
import unittest

from common import bind,freeze,load,verify
from metric_process import exact_process,identity,pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard,require,shared_allowance
from scoring_bank import writer_lock
from review_native_journal import segments
import test_restart_native as tests

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN=('restart_native_journal.py','test_restart_native.py','probe_restart_native.py','README_RESTART_NATIVE.md')


def inputs():
    qb=bind(HERE/'NATIVE_JOURNAL_REVIEW_CHECK_V1.json');q=load(qb['path'])
    require(q['status']=='PASS_NATIVE_JOURNAL_REVIEW_DEVELOPMENT_ONLY','Original native reader qualification differs')
    verify(q['private_receipt']);r=load(q['private_receipt']['path']);verify(r['admission']);a=load(r['admission']['path'])
    require(exact_process(a['owner']) is None and a['code']==q['code'],'Historical native probe still active or changed')
    verify(a['historical_admission']);historical=load(a['historical_admission']['path'])
    require(exact_process(historical['owner']) is None,'Historical closure probe still active')
    cases=historical['cases'];require(len(cases)==9,'Expected nine historical native cases')
    code={}
    for b in [bind(HERE/n) for n in OWN]+[qb]+q['code']:
        verify(b);require(b['path'] not in code or code[b['path']]==b,'Conflicting native dependency');code[b['path']]=b
    evidence=[]
    for case in cases:evidence.extend(segments(case['session'])+[case['consumer'],case['finalization']])
    for b in evidence+a['native_source']:verify(b)
    return dict(code=list(code.values()),original_qualification=qb,historical_admission=a['historical_admission'],
        cases=cases,historical_evidence=evidence,native_source=a['native_source'])


def run(output):
    process=pin();started=time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'),'Fresh private native-prefix probe required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(output,LOCAL,started,720)
        check();inventory=shared_allowance(LOCAL);active=active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir();snapshots=[]
        for name in OWN:
            target=output/'source'/name;target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256']==bind(HERE/name)['sha256'],'Attempt source snapshot changed');snapshots.append(bind(target))
        try:
            admitted=inputs()
            freeze(output/'ADMISSION.json',dict(owner=identity(process),source_snapshots=snapshots,inventory=inventory,
                D1_snapshot=active,**admitted,new_application_or_model_started=False))
            tests.OUTPUT=output/'tests';tests.OUTPUT.mkdir();tests.CASES=admitted['cases']
            stream=io.StringIO();outcome=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(tests.RestartNativeTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(outcome.wasSuccessful() and outcome.testsRun==19 and not outcome.skipped,'Released-native regression checks failed')
            for b in admitted['code']+admitted['historical_evidence']+admitted['native_source']+snapshots:verify(b)
            after=active_d1();require(after['result']['child']==active['result']['child'] and after['run_id']==active['run_id'],'D1 owner changed')
            check()
            freeze(output/'RESULT.json',dict(status='PASS_RELEASED_NATIVE_REVIEW_DEVELOPMENT_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=outcome.testsRun,
                historical_parity=bind(tests.OUTPUT/'test_nine_saved_native_journals_are_classified_without_transcript_output/HISTORICAL_PREFIX_PARITY.json'),
                synthetic_prefix=bind(tests.OUTPUT/'test_complete_rotated_journal_preserves_scope_and_source_overhang/SYNTHETIC_PREFIX_CENSUS.json'),
                historical_cases=9,D1_after=after,new_application_or_model_started=False,
                new_audio_or_GUI_started=False,delivered_length_independently_joined=False,actual_restart_qualified=False,
                integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 19 explicit-prefix native checks; nine historical full-file classifications preserved; no inference',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_RELEASED_NATIVE_PROBE_PRESERVED',error_type=type(exc).__name__,
                owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
