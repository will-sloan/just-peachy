"""Guarded model-free private-desktop and owned job qualification."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
import test_private_application_process_v3 as regression


def run(output):
    process = pin(); started = time.monotonic(); local = Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to((local/'n4').resolve()), 'Fresh private probe output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output, local, started, 720); inventory = shared_allowance(local)
        here = Path(__file__).resolve().parent
        code = [bind(here/name) for name in ('private_application_process_v3.py', 'private_process_fixture_v3.py',
            'test_private_application_process_v3.py', 'probe_private_application_process_v3.py', 'README_PRIVATE_APPLICATION_PROCESS_V3.md',
            'common.py', 'metric_process.py', 'review_scoring_bank.py', 'scoring_bank.py', 'asr_full_bank.py')]
        active = load(local/'n4/asr-full-bank-v1/RESULT.json')
        require(active['status'] == 'RUNNING' and exact_process(active['child']) is not None, 'Re-observe active ASR before this development probe')
        require(exact_process(active['child']).cpu_affinity() == [4], 'Model CPU changed')
        snapshots = []; (output/'source').mkdir(parents=True)
        for entry in code:
            snapshot = output/'source'/Path(entry['path']).name
            with snapshot.open('xb') as stream: stream.write(Path(entry['path']).read_bytes())
            require(bind(snapshot)['sha256'] == entry['sha256'], 'Source snapshot changed')
            snapshots.append(bind(snapshot))
        freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, inventory=inventory,
            source_snapshots=snapshots, ASR_snapshot=active, fixture_cpu=[14], model_inference_started=False, actual_application_spawned=False))
        try:
            regression.OUTPUT = output/'tests'; regression.OUTPUT.mkdir()
            stream = io.StringIO()
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(regression.PrivateProcessTests))
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8')
            require(result.wasSuccessful() and result.testsRun == 8 and not result.skipped, 'Private process regression failed')
            receipts = [bind(path) for path in sorted((output/'tests').glob('*/lifetime/LIFETIME.json'))]
            require(len(receipts) == 7, 'Missing owned fixture lifetime receipts')
            for receipt in receipts:
                row = load(receipt['path'])
                require(row['job_empty_verified'] and row['status'] == 'OWNED_PROCESS_LIFETIME_CLOSED' and exact_process(row['owner']) is None,
                    'Fixture lifetime not completely closed')
            guard(output, local, started, 720)
            for entry in code: verify(entry)
            freeze(output/'RESULT.json', dict(status='PASS_PRIVATE_PROCESS_LIFETIME_FIXTURES_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), tests=bind(output/'tests.txt'), tests_passed=result.testsRun,
                fixture_lifetimes=receipts, all_owned_jobs_empty=True, model_inference_started=False,
                actual_application_spawned=False, integrated_N4_cells=0, production_launch_admission_qualified=False))
            print('PASS: 8 private process lifetime tests; all owned fixture jobs empty', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_PRIVATE_PROCESS_PROBE_PRESERVED', error_type=type(exc).__name__,
                admission=bind(output/'ADMISSION.json'), integrated_N4_cells=0))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
