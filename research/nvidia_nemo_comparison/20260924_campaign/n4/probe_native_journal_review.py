"""Guarded model-free qualification; README_NATIVE_JOURNAL_REVIEW.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
from review_native_journal import segments
import test_native_journal_review as regression

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')


def code_bindings():
    names = ('review_native_journal.py','test_native_journal_review.py','probe_native_journal_review.py',
             'README_NATIVE_JOURNAL_REVIEW.md','probe_application_transport_review.py')
    entries = [bind(HERE/name) for name in names]
    q = load(HERE/'APPLICATION_TRANSPORT_REVIEW_CHECK_V1.json')
    require(q['status'] == 'PASS_APPLICATION_TRANSPORT_REVIEW_DEVELOPMENT_ONLY', 'Transport qualification differs')
    entries += [bind(HERE/'APPLICATION_TRANSPORT_REVIEW_CHECK_V1.json'), *q['code']]
    result = {}
    for b in entries:
        require(b['path'] not in result or b == result[b['path']], 'Conflicting source bindings')
        result[b['path']] = b
    return list(result.values())


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private N4 output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output,LOCAL,started,720); inventory=shared_allowance(LOCAL); numerical=active_d1()
        code=code_bindings()
        for b in code: verify(b)
        closure=load(HERE/'APPLICATION_CLOSURE_CHECK_V2.json'); verify(closure['private_receipt'])
        previous=load(closure['private_receipt']['path']); verify(previous['admission'])
        old=load(previous['admission']['path'])
        require(exact_process(old['owner']) is None, 'Historical closure helper remains active')
        cases=old['cases']; require(len(cases)==9, 'Historical case population differs')
        evidence=[]
        for case in cases:
            evidence += segments(case['session'])+[case['consumer'],case['finalization']]
        for b in evidence: verify(b)
        verify(closure['source_receipt']); source=load(closure['source_receipt']['path'])
        native_code=[dict(path=str(Path(source['prototype'])/name),**source['files'][name]) for name in
                     ('app/buffers.py','app/pipeline.py','vendor/edge_speech_pipeline/runtime.py')]
        for b in native_code: verify(b)
        (output/'source').mkdir(parents=True); snapshots=[]
        for b in code[:4]:
            target=output/'source'/Path(b['path']).name;target.write_bytes(Path(b['path']).read_bytes())
            require(bind(target)['sha256']==b['sha256'],'Attempt snapshot differs');snapshots.append(bind(target))
        freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,source_snapshots=snapshots,
            inventory=inventory,D1_snapshot=numerical,historical_admission=previous['admission'],
            historical_evidence=evidence,native_source=native_code,new_application_or_model_started=False))
        try:
            regression.OUTPUT=output/'tests';regression.CASES=cases;regression.OUTPUT.mkdir()
            stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.NativeJournalTests))
            (output/'tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun==12 and not tests.skipped,'Native journal review checks failed')
            for b in code+evidence+native_code: verify(b)
            guard(output,LOCAL,started,720);after=active_d1()
            require(after['result']['owner']==numerical['result']['owner'] and after['result']['child']==numerical['result']['child']
                    and after['run_id']==numerical['run_id'],'Numerical ownership changed; re-observe')
            freeze(output/'RESULT.json',dict(status='PASS_NATIVE_JOURNAL_REVIEW_CHECKS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'),tests=bind(output/'tests.txt'),tests_passed=tests.testsRun,
                historical_census=bind(output/'tests/test_nine_saved_native_journals_are_classified_without_transcript_output/HISTORICAL_JOURNAL_CENSUS.json'),
                synthetic_complete=bind(output/'tests/test_complete_rotated_journal_preserves_scope_and_source_overhang/SYNTHETIC_COMPLETE_ENVELOPE.json'),
                D1_after=after,new_application_or_model_started=False,native_retention_repaired=False,
                actual_panel_reviewed=False,integrated_N4_cells=0,N4_accepted=False))
            print('PASS: 12 native journal tests; nine saved incomplete prefixes detected; no inference',flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json',dict(status='FAILED_NATIVE_JOURNAL_REVIEW_PROBE_PRESERVED',error_type=type(exc).__name__,
                admission=bind(output/'ADMISSION.json')))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
