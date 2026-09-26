"""Guarded restart composition/population checks. README_RESTART_COMPLETE_REVIEW.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, verify
from metric_process import identity, pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import review_restart_complete as subject
import test_restart_complete as tests
import test_restart_run_review as original


def run(output):
    process = pin(); started = time.monotonic(); local = subject.LOCAL
    require(not output.exists() and output.resolve().is_relative_to(local/'n4'), 'Fresh private complete-review probe required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        check = lambda: guard(output, local, started, 720)
        check(); inventory = shared_allowance(local); active = active_d1()
        freeze(output/'PROBE_OWNER.json', dict(owner=identity(process), utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(); snapshots = []
        for name in subject.OWN:
            target = output/'source'/name; target.write_bytes((subject.HERE/name).read_bytes())
            require(bind(target)['sha256'] == bind(subject.HERE/name)['sha256'], 'Source snapshot differs'); snapshots.append(bind(target))
        try:
            code = subject.code_bindings()
            freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, source_snapshots=snapshots,
                inventory=inventory, D1_snapshot=active, actual_application_or_model_started=False))
            tests.OUTPUT = output/'tests/new'; tests.OUTPUT.mkdir(parents=True)
            original.OUTPUT = output/'tests/population'; original.OUTPUT.mkdir()
            suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(tests.RestartCompleteTests),
                unittest.defaultTestLoader.loadTestsFromTestCase(original.RestartPopulationTests)])
            stream = io.StringIO(); result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(result.wasSuccessful() and result.testsRun == 24 and not result.skipped, 'Complete restart review checks failed')
            for b in code+snapshots: verify(b)
            after = active_d1()
            require(after['run_id'] == active['run_id'] and after['result']['child'] == active['result']['child'], 'D1 owner changed')
            check()
            freeze(output/'RESULT.json', dict(status='PASS_RESTART_COMPLETE_REVIEW_CHECKS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), tests=bind(output/'tests.txt'), tests_passed=result.testsRun,
                code_records=len(code), D1_after=after, synthetic_composition_and_population=True,
                mocked_cell_leaf_readers_and_payload_in_population=True, mocked_production_plan_admission=True,
                actual_application_or_model_started=False, actual_production_run_reviewed=False,
                native_caption_payloads_joined=False, source_to_widget_latency_qualified=False,
                controlled_resources_qualified=False, actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False))
            print('PASS: 24 complete restart composition/population development checks; no model or production run', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_RESTART_COMPLETE_REVIEW_PROBE_PRESERVED', owner=identity(process),
                error_type=type(exc).__name__, source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
