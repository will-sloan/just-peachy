"""Guarded model-free text-lineage checks; README_NATIVE_TEXT_REVIEW.md."""
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
import test_native_text_review as regression

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')
OWN = ('review_native_text.py', 'test_native_text_review.py', 'probe_native_text_review.py', 'README_NATIVE_TEXT_REVIEW.md')


def code_bindings():
    qpath = HERE/'NATIVE_JOURNAL_REVIEW_CHECK_V1.json'; q = load(qpath)
    require(q['status'] == 'PASS_NATIVE_JOURNAL_REVIEW_DEVELOPMENT_ONLY', 'Native envelope qualification differs')
    entries = [*[bind(HERE/name) for name in OWN], bind(qpath), *q['code']]
    result = {}
    for b in entries:
        require(b['path'] not in result or result[b['path']] == b, 'Conflicting code bindings')
        result[b['path']] = b
    return list(result.values())


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private N4 output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output, LOCAL, started, 720); inventory = shared_allowance(LOCAL); active = active_d1()
        freeze(output/'PROBE_OWNER.json', dict(owner=identity(process), utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(); snapshots = []
        for name in OWN:
            target = output/'source'/name; target.write_bytes((HERE/name).read_bytes())
            require(bind(target)['sha256'] == bind(HERE/name)['sha256'], 'Source snapshot differs'); snapshots.append(bind(target))
        try:
            code = code_bindings()
            for b in code: verify(b)
            q = load(HERE/'NATIVE_JOURNAL_REVIEW_CHECK_V1.json'); verify(q['private_receipt'])
            prior = load(q['private_receipt']['path']); verify(prior['admission']); admission = load(prior['admission']['path'])
            require(exact_process(admission['owner']) is None, 'Qualified native review helper still active')
            historical = admission['historical_admission']; verify(historical)
            cases = load(historical['path'])['cases']; require(len(cases) == 9, 'Historical population differs')
            evidence = []
            for case in cases: evidence += segments(case['session'])+[case['consumer'], case['finalization']]
            for b in evidence: verify(b)
            # Bind the shared emitting runtime inspected to define this interpreter.
            source_receipt = bind(LOCAL/'releases/n4-complete-journal-v1/SOURCE_RECEIPT.json')
            source = load(source_receipt['path']); emitter = []
            for name in ('vendor/edge_speech_pipeline/runtime.py', 'app/pipeline.py', 'app/n2_pipeline.py', 'app/n3_pipeline.py'):
                emitter.append(dict(path=str(Path(source['prototype'])/name), **source['files'][name]))
            for b in emitter: verify(b)
            freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, source_snapshots=snapshots,
                inventory=inventory, D1_snapshot=active, historical_admission=historical, historical_evidence=evidence,
                application_source=source_receipt, emitting_source=emitter, new_application_or_model_started=False))
            regression.OUTPUT = output/'tests'; regression.OUTPUT.mkdir(); regression.CASES = cases
            stream = io.StringIO(); tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(regression.NativeTextTests))
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun == 12 and not tests.skipped, 'Native text lineage tests failed')
            for b in code+evidence+emitter+[source_receipt]: verify(b)
            after = active_d1(); require(after['result']['child'] == active['result']['child']
                and after['run_id'] == active['run_id'], 'Active numerical owner changed')
            guard(output, LOCAL, started, 720)
            freeze(output/'RESULT.json', dict(status='PASS_NATIVE_TEXT_REVIEW_CHECKS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), tests=bind(output/'tests.txt'), tests_passed=tests.testsRun,
                synthetic_text=bind(output/'tests/test_interleaved_revisions_preserve_raw_words_and_separate_formatting/SYNTHETIC_TEXT_REVIEW.json'),
                historical_refusals=bind(output/'tests/test_all_nine_historical_prefixes_remain_unavailable/HISTORICAL_REFUSALS.json'),
                D1_after=after, new_application_or_model_started=False, actual_complete_source_history_projected=False,
                actual_panel_reviewed=False, integrated_N4_cells=0, N4_accepted=False))
            print('PASS: 12 native raw-text checks; nine incomplete histories refused; no source/model launch', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_NATIVE_TEXT_PROBE_PRESERVED', error_type=type(exc).__name__,
                owner=identity(process), source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
