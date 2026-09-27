"""Nested reservation provenance regressions; README_PACED_SLOT_GUARDED_V1.md."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import paced_slot_guarded_v1 as subject


def fixture():
    root = Path(__file__).resolve().parent/'INERT_RUN_FIXTURE'
    ab = dict(path=str(root/'ADMISSION.json'), sha256='0'*64, bytes=1)
    owner = dict(pid=123, create_time=123.0)
    a = dict(owner=owner, allocation_bytes=2*1024**3)
    proof = dict(projection=dict(own_admission=ab, own_allocation_bytes=a['allocation_bytes'],
        production_scope_checked=True, own_allocation_counted_once=True, other_allocation_count=0),
        observed=dict(complete_recorded_N4_admission_census=True, active_set_supplied_by_caller=False,
            active_allocations=[dict(admission=ab)], supervisor=dict(state='RUNNING', driver=owner)))
    return [proof, ab, a, owner, root, root/'cells'/'cell_001', subject.MAX_CELL_BYTES]


class AllocationSlotTests(unittest.TestCase):
    def test_sole_parent_allocation_is_used_once_without_mutation(self):
        v = fixture(); before = deepcopy(v); subject.validate_parent(*v); self.assertEqual(v, before)

    def test_escaped_or_deeply_nested_cell_is_refused(self):
        for path in ('other/cell', 'cells/cell/sub', 'cells'):
            v = fixture(); v[5] = v[4]/path
            with self.subTest(path=path), self.assertRaises(ValueError): subject.validate_parent(*v)

    def test_other_owner_or_foreign_admission_is_refused(self):
        for change in ('owner', 'admission'):
            v = fixture()
            if change == 'owner': v[2]['owner'] = dict(pid=124, create_time=123.0)
            else: v[1]['path'] = str(v[4]/'FOREIGN.json')
            with self.subTest(change=change), self.assertRaises(ValueError): subject.validate_parent(*v)

    def test_peak_and_terminal_headroom_are_required(self):
        for value in (0, True, subject.MAX_CELL_BYTES+1):
            v = fixture(); v[6] = value
            with self.subTest(value=value), self.assertRaises(ValueError): subject.validate_parent(*v)
        v = fixture(); v[2]['allocation_bytes'] = subject.MAX_CELL_BYTES
        with self.assertRaises(ValueError): subject.validate_parent(*v)

    def test_projection_cannot_hide_another_allocation(self):
        for field, value in (('other_allocation_count', 1), ('production_scope_checked', False),
            ('own_allocation_counted_once', False), ('own_allocation_bytes', 1), ('own_admission', {})):
            v = fixture(); v[0]['projection'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): subject.validate_parent(*v)

    def test_census_must_be_complete_discovered_and_supervised(self):
        for change in ('incomplete', 'supplied', 'extra', 'driver', 'closed'):
            v = fixture(); c = v[0]['observed']
            if change == 'incomplete': c['complete_recorded_N4_admission_census'] = False
            if change == 'supplied': c['active_set_supplied_by_caller'] = True
            if change == 'extra': c['active_allocations'].append({})
            if change == 'driver': c['supervisor']['driver'] = {}
            if change == 'closed': c['supervisor']['state'] = 'CLOSED'
            with self.subTest(change=change), self.assertRaises(ValueError): subject.validate_parent(*v)

    def test_cell_resource_check_retains_parent_cap_and_remaining_peak(self):
        calls = []
        slot = object.__new__(subject.ExclusiveApplicationSlot)
        slot.reservation = subject.MAX_CELL_BYTES; slot.output_size = 1024
        slot.allocation_guard = SimpleNamespace(fast_check=lambda **kw: calls.append(kw))
        with patch.object(subject.PreviousSlot, '_resources') as previous:
            slot._resources(force_scan=True); previous.assert_called_once_with(force_scan=True)
        self.assertEqual(calls, [dict(peak=subject.MAX_CELL_BYTES-1024)])

    def test_lost_run_lock_stops_before_runtime_check(self):
        slot = object.__new__(subject.ExclusiveApplicationSlot); slot.coordinator = fixture()[3]
        slot.allocation_guard = SimpleNamespace(held=False, owner=slot.coordinator)
        with patch.object(subject.PreviousSlot, 'check') as previous:
            with self.assertRaises(ValueError): slot.check()
            previous.assert_not_called()
