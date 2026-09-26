"""Model-free continuity runner qualification. README_CONTINUITY_APPLICATION_RUNNER.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import tempfile
import unittest
from unittest.mock import patch

from common import bind, freeze, verify, load
from metric_process import identity, pin
from probe_application_transport_review import active_d1
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
from continuity_application_runner import code_bindings, qualified_interpreter
import test_continuity_application_runner as regression
from paced_panel_plan_v3 import application_qualification

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')


def run(output):
    process = pin(); started = time.monotonic()
    require(not output.exists() and output.resolve().is_relative_to(LOCAL/'n4'), 'Fresh private probe output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        guard(output, LOCAL, started, 720); inventory = shared_allowance(LOCAL); active = active_d1()
        freeze(output/'PROBE_OWNER.json',dict(owner=identity(process),utc=datetime.now(timezone.utc).isoformat()))
        (output/'source').mkdir(parents=True); snapshots = []
        for name in ('continuity_application_runner.py', 'test_continuity_application_runner.py',
                     'probe_continuity_application_runner.py', 'README_CONTINUITY_APPLICATION_RUNNER.md'):
            source = HERE/name; target = output/'source'/name; target.write_bytes(source.read_bytes())
            require(bind(target)['sha256'] == bind(source)['sha256'], 'Attempt snapshot changed')
            snapshots.append(bind(target))
        try:
            code=code_bindings();executable=qualified_interpreter()
            require(len(code)<=128,'Child code binding count exceeded')
            for b in code:verify(b)
            ab,app,source=application_qualification();prototype=Path(load(source['source_receipt']['path'])['prototype'])
            freeze(output/'ADMISSION.json',dict(owner=identity(process),code=code,executable=executable,
                source_snapshots=snapshots,inventory=inventory,D1_snapshot=active,application_qualification=ab,
                source_receipt=source['source_receipt'],actual_application_spawned=False,model_inference_started=False))
            checkpoint=lambda:guard(output,LOCAL,started,720)
            regression.CONTEXT.update(output=output,prototype=prototype,checkpoint=checkpoint)
            regression.delivery_tests.CONTEXT.update(output=output,prototype=prototype,checkpoint=checkpoint)
            regression.delivery_tests.source_tests.CONTEXT.update(output=output,prototype=prototype,checkpoint=checkpoint)
            fixtures=output/'fixtures';fixtures.mkdir()
            stream = io.StringIO()
            with patch.object(tempfile,'tempdir',str(fixtures)):
                tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(
                    unittest.defaultTestLoader.loadTestsFromTestCase(regression.RunnerTests))
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(tests.wasSuccessful() and tests.testsRun == 22 and not tests.skipped, 'continuity runner wiring regression failed')
            for b in code: verify(b)
            after = active_d1()
            require(after['result']['child'] == active['result']['child'] and after['run_id'] == active['run_id'], 'D1 ownership changed')
            guard(output, LOCAL, started, 720)
            freeze(output/'RESULT.json', dict(status='PASS_CONTINUITY_RUNNER_WIRING_CHECKS_ONLY',
                utc=datetime.now(timezone.utc).isoformat(), admission=bind(output/'ADMISSION.json'),
                tests=bind(output/'tests.txt'), tests_passed=tests.testsRun, D1_after=after,
                actual_atomic_lease_writes_with_synthetic_permit=True, mocked_coordinator_and_child_lifecycle=True,
                native_envelope_gate_tested_with_synthetic_journal=True,
                delivery_gate_tested_with_RAM_source_and_synthetic_receipt=True,
                synthetic_delivery_envelope=bind(output/'SYNTHETIC_PARENT_ENVELOPE.json'),
                production_plan_admitted=False, successful_supervised_application_admission=False,
                actual_application_spawned=False, model_inference_started=False,
                source_execution_branch_tested_with_real_application=False, actual_continuity_run=False, stop_restart_qualified=False, integrated_N4_cells=0, N4_accepted=False))
            print('PASS: 22 continuity runner/envelope checks; no actual application, model or saved-audio launch', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_CONTINUITY_RUNNER_PROBE_PRESERVED',
                error_type=type(exc).__name__,owner=identity(process),source_snapshots=snapshots,
                admission=bind(output/'ADMISSION.json') if (output/'ADMISSION.json').exists() else None))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
