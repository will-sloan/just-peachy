"""Guarded saved-log restart attribution tests. README_RESTART_OBSERVATIONS.md."""
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
import review_restart_observations as subject
import test_restart_observations as tests

LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private probe output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check = lambda: guard(output, LOCAL, started, 720)
        check(); inventory = shared_allowance(LOCAL); active = active_d1()
        freeze(output/'PROBE_OWNER.json', dict(owner=identity(process), utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(); snapshots = []
        for name in subject.OWN:
            target = output/'source'/name; target.write_bytes((subject.HERE/name).read_bytes())
            require(bind(target)['sha256'] == bind(subject.HERE/name)['sha256'], 'Snapshot differs'); snapshots.append(bind(target))
        try:
            code = subject.code_bindings()
            freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, source_snapshots=snapshots,
                inventory=inventory, D1_snapshot=active, actual_application_or_model_started=False))
            tests.OUTPUT = output/'tests'; tests.OUTPUT.mkdir()
            stream = io.StringIO(); suite = unittest.defaultTestLoader.loadTestsFromTestCase(tests.RestartObservationTests)
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(result.wasSuccessful() and result.testsRun == 22 and not result.skipped, 'Restart observation checks failed')
            for b in code+snapshots: verify(b)
            after = active_d1()
            require(after['result']['child'] == active['result']['child'] and after['run_id'] == active['run_id'], 'D1 owner changed')
            check()
            freeze(output/'RESULT.json', dict(status='PASS_RESTART_OBSERVATION_CHECKS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), tests=bind(output/'tests.txt'), tests_passed=result.testsRun,
                code_records=len(code), D1_after=after, synthetic_saved_logs=True,
                mocked_pair_leaf_and_prepared_context_for_composition=True, actual_source_or_model_run=False,
                actual_GUI_created=False, actual_production_pair_reviewed=False, native_caption_payloads_joined=False,
                source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
                actual_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False))
            print('PASS: 22 restart viewport/resource attribution checks; saved synthetic logs only', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_RESTART_OBSERVATION_PROBE_PRESERVED', owner=identity(process),
                error_type=type(exc).__name__, source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
