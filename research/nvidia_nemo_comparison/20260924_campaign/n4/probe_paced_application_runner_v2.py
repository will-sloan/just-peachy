"""Model-free V2 runner qualification. README_PACED_APPLICATION_RUNNER_V2.md."""
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
from paced_application_runner_v2 import code_bindings, qualified_interpreter
from test_paced_application_runner_v2 import RunnerTests

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private probe output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output, LOCAL, started, 720); inventory = shared_allowance(LOCAL); active = active_d1()
        code = code_bindings(); executable = qualified_interpreter()
        require(len(code) <= 128, 'Child code binding count exceeded')
        for b in code: verify(b)
        (output/'source').mkdir(parents=True); snapshots = []
        for name in ('paced_application_runner_v2.py', 'test_paced_application_runner_v2.py',
                     'probe_paced_application_runner_v2.py', 'README_PACED_APPLICATION_RUNNER_V2.md'):
            source = HERE/name; target = output/'source'/name; target.write_bytes(source.read_bytes())
            require(bind(target)['sha256'] == bind(source)['sha256'], 'Attempt snapshot changed')
            snapshots.append(bind(target))
        freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, executable=executable,
            source_snapshots=snapshots, inventory=inventory, D1_snapshot=active,
            actual_application_spawned=False, model_inference_started=False))
        try:
            stream = io.StringIO()
            tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(RunnerTests))
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun == 16 and not tests.skipped, 'V2 runner wiring regression failed')
            for b in code: verify(b)
            after = active_d1()
            require(after['result']['child'] == active['result']['child'] and after['run_id'] == active['run_id'], 'D1 ownership changed')
            guard(output, LOCAL, started, 720)
            freeze(output/'RESULT.json', dict(status='PASS_PACED_RUNNER_V2_WIRING_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(), admission=bind(output/'ADMISSION.json'),
                tests=bind(output/'tests.txt'), tests_passed=tests.testsRun, D1_after=after,
                actual_atomic_lease_writes_with_synthetic_permit=True, mocked_coordinator_and_child_lifecycle=True,
                native_envelope_gate_tested_with_synthetic_journal=True,
                production_plan_admitted=False, successful_supervised_application_admission=False,
                actual_application_spawned=False, model_inference_started=False,
                source_execution_branch_tested_with_real_application=False, integrated_N4_cells=0, N4_accepted=False))
            print('PASS: 16 V2 runner/envelope checks; no actual application, model or source launch', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_PACED_RUNNER_V2_PROBE_PRESERVED',
                error_type=type(exc).__name__, admission=bind(output/'ADMISSION.json')))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
