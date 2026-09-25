"""Owner, reservation and fail-closed resource tests. README_PACED_SLOT.md."""
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import time
import unittest

from common import freeze
from metric_process import identity, pin
from paced_slot import (DEADLINE, GIB, MAX_CELL_BYTES, ExclusiveApplicationSlot, bounded_output_bytes,
                        competitors, process_census, validate_policy, validate_supervision)
from scoring_bank import writer_lock


def supervision_fixture():
    coordinator = dict(pid=200, create_time=20.)
    worker = dict(status='RUNNING', pid=100, create_time=10., child_pid=200, child_create_time=20.,
                  heartbeat_unix=1000., child_launch_pending=False, run_id='fixture')
    observations = {100: dict(pid=100, create_time=10., parent_pid=1, affinity=[14]),
                    200: dict(pid=200, create_time=20., parent_pid=100, affinity=[14])}
    return worker, coordinator, observations


def policy_fixture():
    return dict(target_utc=DEADLINE.isoformat(), resource_policy=dict(gpu_owner=None, max_cpu_cores=2,
        max_parallel_workers=2, minimum_free_gib={'C:': 50, 'G:': 75}, new_payload_allowance_gib=50))


class PacedSlotTests(unittest.TestCase):
    def test_exact_supervised_owner_and_healthy_heartbeat(self):
        w, c, obs = supervision_fixture()
        self.assertEqual(validate_supervision(w, c, obs, 1001), dict(pid=100, create_time=10.))
        for field, value in [('status', 'COMPLETE'), ('child_create_time', 21.), ('child_launch_pending', True),
                             ('heartbeat_unix', 900.), ('heartbeat_unix', 1002.), ('heartbeat_unix', float('nan')), ('run_id', '')]:
            changed = deepcopy(w); changed[field] = value
            with self.assertRaises(ValueError): validate_supervision(changed, c, obs, 1001)

    def test_reused_absent_wrong_cpu_and_foreign_parent_fail(self):
        for field, value in [('create_time', 21.), ('parent_pid', 99), ('affinity', [4, 14])]:
            w, c, obs = supervision_fixture(); obs[200][field] = value
            with self.assertRaises(ValueError): validate_supervision(w, c, obs, 1001)
        w, c, obs = supervision_fixture(); del obs[100]
        with self.assertRaises(ValueError): validate_supervision(w, c, obs, 1001)

    def test_other_model_helper_pid_reuse_and_unknown_access_are_not_allowed(self):
        owner = dict(pid=100, create_time=10.)
        census = dict(rows=[owner, dict(pid=200, create_time=20.)], errors=[])
        self.assertEqual(competitors(census, [owner]), [dict(pid=200, create_time=20.)])
        self.assertEqual(len(competitors(census, [dict(pid=100, create_time=11.)])), 2)
        census['errors'] = [dict(pid=300, kind='AccessDenied')]
        with self.assertRaises(ValueError): competitors(census, [owner])
        with self.assertRaises(ValueError): competitors(dict(rows=[], errors=[]), [owner, owner])

    def test_deadline_extension_cannot_move_packaging_reserve(self):
        policy = policy_fixture(); free = {'C:': 60*GIB, 'G:': 90*GIB}; cutoff = DEADLINE-timedelta(hours=12)
        validate_policy(policy, free, cutoff-timedelta(seconds=1))
        policy['target_utc'] = (DEADLINE+timedelta(days=2)).isoformat()
        with self.assertRaises(ValueError): validate_policy(policy, free, cutoff)
        policy['target_utc'] = (DEADLINE-timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError): validate_policy(policy, free, cutoff-timedelta(hours=1))

    def test_cpu_gpu_disk_and_shared_policy_cannot_be_relaxed(self):
        now = DEADLINE-timedelta(days=1); free = {'C:': 60*GIB, 'G:': 90*GIB}
        for key, value in [('gpu_owner', 'foreign'), ('max_cpu_cores', 3), ('max_parallel_workers', 3), ('new_payload_allowance_gib', 80)]:
            policy = policy_fixture(); policy['resource_policy'][key] = value
            with self.assertRaises(ValueError): validate_policy(policy, free, now)
        for drive, floor in [('C:', 50), ('G:', 75)]:
            changed = dict(free); changed[drive] = floor*GIB+MAX_CELL_BYTES-1
            with self.assertRaises(ValueError): validate_policy(policy_fixture(), changed, now)
        with self.assertRaises(ValueError): validate_policy(policy_fixture(), free, now, output_bytes=MAX_CELL_BYTES+1)

    def test_output_census_and_fresh_private_destination(self):
        with tempfile.TemporaryDirectory(prefix='n4-slot-fixture-') as tmp:
            root = Path(tmp); state = root/'supervision'; state.mkdir(); freeze(state/'campaign.json', policy_fixture())
            slot = ExclusiveApplicationSlot(state, root/'n4/cell'); self.assertEqual(bounded_output_bytes(slot.output), 0)
            slot.output.mkdir(parents=True); (slot.output/'a.txt').write_bytes(b'abc'); (slot.output/'nested').mkdir()
            (slot.output/'nested/b.txt').write_bytes(b'12345'); self.assertEqual(bounded_output_bytes(slot.output), 8)
            with self.assertRaises(ValueError): ExclusiveApplicationSlot(state, slot.output)
            with self.assertRaises(ValueError): ExclusiveApplicationSlot(state, root/'outside')
            with self.assertRaises(ValueError): ExclusiveApplicationSlot(state, root/'n4/other', reservation_bytes=MAX_CELL_BYTES+1)

    def test_real_os_lock_refuses_another_holder_and_releases_after_error(self):
        with tempfile.TemporaryDirectory(prefix='n4-slot-lock-') as tmp:
            path = Path(tmp)/'owner.lock'
            with writer_lock(path):
                with self.assertRaises(OSError):
                    with writer_lock(path): self.fail('Duplicate holder admitted')
            try:
                with writer_lock(path): raise RuntimeError('fixture cancellation')
            except RuntimeError: pass
            with writer_lock(path): pass

    def test_release_refuses_live_application_and_retains_locks(self):
        process = pin()
        with tempfile.TemporaryDirectory(prefix='n4-slot-release-') as tmp:
            root = Path(tmp); state = root/'supervision'; state.mkdir(); freeze(state/'campaign.json', policy_fixture())
            slot = ExclusiveApplicationSlot(state, root/'n4/cell'); slot.locks = ExitStack()
            slot.locks.enter_context(writer_lock(root/'test.lock')); slot.application = identity(process)
            try:
                with self.assertRaisesRegex(ValueError, 'Application still alive'): slot.release()
                with self.assertRaises(OSError):
                    with writer_lock(root/'test.lock'): self.fail('Live-owner lock was released')
                # This is a dictionary state fixture, not evidence of real child exit.
                slot.application = None; self.assertEqual(slot.release()['status'], 'APPLICATION_SLOT_RELEASED')
            finally:
                if slot.locks is not None: slot.locks.close()

    def test_actual_current_interpreter_is_observed_without_device_calls(self):
        process = pin(); census = process_census(Path(__file__).resolve().parents[4])
        matches = [r for r in census['rows'] if r['pid'] == process.pid]
        self.assertEqual(len(matches), 1); self.assertEqual(matches[0]['create_time'], process.create_time())
        self.assertEqual(matches[0]['affinity'], [14]); self.assertIn('limitations', census)


if __name__ == '__main__':
    pin(); unittest.main()
