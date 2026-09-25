"""Observe active ownership and qualify fail-closed guards only. README_PACED_SLOT.md."""
import argparse
from datetime import datetime, timezone
import io
from pathlib import Path
import time
import unittest

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_slot import competitors, observe_owner, process_census, validate_supervision
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock
from test_paced_slot import PacedSlotTests


def code_bindings():
    here = Path(__file__).resolve().parent
    return [bind(here/name) for name in ('paced_slot.py', 'test_paced_slot.py', 'probe_paced_slot.py', 'README_PACED_SLOT.md',
            'metric_process.py', 'scoring_bank.py', 'review_scoring_bank.py', 'common.py', 'asr_full_bank.py')]


def run(output):
    process = pin(); started = time.monotonic(); local = Path('G:/Just_Peachy_N1/20260924_campaign/local')
    require(not output.exists() and output.resolve().is_relative_to((local/'n4').resolve()), 'Fresh private output required')
    # Only the existing metric helper lock. This probe never acquires an actual
    # application slot, registers a child, changes supervision or launches one.
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(output, local, started, 720); inventory = shared_allowance(local); code = code_bindings()
        freeze(output/'ADMISSION.json', dict(owner=identity(process), code=code, inventory=inventory,
            model_inference_started=False, application_slot_acquired=False))
        try:
            stream = io.StringIO(); tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PacedSlotTests))
            (output/'tests.txt').write_text(stream.getvalue(), encoding='utf-8'); require(tests.wasSuccessful(), 'Slot guard regression failed')
            record = load(local/'supervision/worker.json')
            supervisor = dict(pid=record['pid'], create_time=record['create_time'])
            coordinator = dict(pid=record['child_pid'], create_time=record['child_create_time'])
            observations = {p['pid']: observe_owner(p) for p in (supervisor, coordinator, identity(process))}
            validate_supervision(record, coordinator, observations, time.time())
            refused = False
            try: validate_supervision(record, identity(process), observations, time.time())
            except ValueError: refused = True
            require(refused, 'Unsupervised development helper was not rejected')
            census = process_census(local.parent); found = competitors(census, [identity(process), supervisor])
            run_root = local/'n4/asr-full-bank-v1'; active = load(run_root/'RESULT.json')
            require(active['status'] == 'RUNNING' and active['owner'] == coordinator and exact_process(active['child']) is not None,
                    'Live ASR owner changed; preserve this checkpoint and re-observe')
            for owner in (active['owner'], active['child']):
                require(any(r['pid'] == owner['pid'] and r['create_time'] == owner['create_time'] for r in found), 'Existing model/coordinator was missed')
            guard(output, local, started, 720)
            for b in code: verify(b)
            freeze(output/'RESULT.json', dict(status='PASS_SLOT_GUARD_REJECTION_CHECKS_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(output/'ADMISSION.json'), tests=bind(output/'tests.txt'), tests_passed=tests.testsRun,
                live_worker_snapshot=record, live_ASR_owner_snapshot=active, census=census,
                current_model_and_coordinator_detected=True, unsupervised_helper_rejected=True,
                application_slot_acquired=False, actual_application_spawned=False, process_terminated=False,
                supervisor_modified=False, integrated_N4_cells=0, exclusive_application_execution_qualified=False))
            print('PASS: '+str(tests.testsRun)+' tests; current model detected, unsupervised launch refused', flush=True)
        except BaseException as exc:
            freeze(output/'FAILED.json', dict(status='FAILED_SLOT_GUARD_PROBE_PRESERVED', error_type=type(exc).__name__,
                admission=bind(output/'ADMISSION.json'), integrated_N4_cells=0))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
