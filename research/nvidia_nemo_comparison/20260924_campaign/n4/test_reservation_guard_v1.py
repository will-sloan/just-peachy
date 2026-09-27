"""Guard accounting and refusal tests; README_RESERVATION_GUARD_V1.md."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import bind, freeze
from reservation_budget_v1 import GIB, DEADLINE
from reservation_guard_v1 import (OutputGuard, TERMINAL_RESERVE, check_runtime, exact_projection,
                                   output_limit, validate_boundary)
from test_reservation_budget_v1 import facts, active, lookup, who


class Accounting(unittest.TestCase):
    def setUp(self):
        self.f = facts(); own = self.f['active'][0]; own['admission'] = dict(path='owned-admission')
        self.owner = own['owner']; self.output = own['root']
        self.observed = dict(active_allocations=self.f['active'], inventory=self.f['inventory'],
            closed_components=self.f['closed'], free_bytes=self.f['free_bytes'],
            complete_recorded_N4_admission_census=True, active_set_supplied_by_caller=False,
            supervisor=dict(state='RUNNING', driver=self.owner))
    def check(self, production=True):
        return exact_projection(self.observed,self.owner,self.output,self.f['policy'],
                                self.f['now'],GIB//4,production=production,lookup=lookup)
    def test_own_existing_bytes_and_remainder_are_counted_once(self):
        r = self.check(); self.assertEqual(r['projected_bytes'], int(43.25*GIB))
        self.assertEqual(r['active_remaining_bytes'], 0); self.assertEqual(r['own_remaining_bytes'], 3*GIB//4)
        self.assertTrue(r['own_allocation_counted_once']); self.assertFalse(r['worker_execution_authorized'])
    def test_output_growth_keeps_the_same_commitment(self):
        before = self.check()['projected_bytes']; own = self.observed['active_allocations'][0]
        own['observed_used_bytes'] += 123; own['remaining_bytes'] -= 123
        self.observed['inventory']['total_logical_bytes'] += 123
        self.assertEqual(self.check()['projected_bytes'], before)
    def test_production_refuses_legacy_or_other_active_allocation(self):
        self.observed['active_allocations'].append(active(4, 'G:/private/n4/other',GIB//2,0))
        with self.assertRaisesRegex(ValueError, 'every other'): self.check()
        r = self.check(False); self.assertEqual(r['projected_bytes'], int(43.75*GIB))
        self.assertEqual(r['other_allocation_count'], 1); self.assertFalse(r['production_scope_checked'])
    def test_production_requires_exact_supervised_driver(self):
        for supervision in [dict(state='CLOSED'),dict(state='RUNNING',driver=who(99))]:
            self.observed['supervisor'] = supervision
            with self.subTest(supervision=supervision),self.assertRaisesRegex(ValueError,'supervised driver'):self.check()
    def test_missing_duplicate_foreign_or_caller_supplied_own_allocation_refuses(self):
        original = deepcopy(self.observed)
        for change in ['missing','duplicate','foreign','partial','caller']:
            self.observed = deepcopy(original)
            if change == 'missing':self.observed['active_allocations'] = []
            elif change == 'duplicate':self.observed['active_allocations'] *= 2
            elif change == 'foreign':self.observed['active_allocations'][0]['root'] = 'G:/other'
            elif change == 'partial':self.observed['complete_recorded_N4_admission_census'] = False
            else:self.observed['active_set_supplied_by_caller'] = True
            with self.subTest(change=change),self.assertRaises(ValueError):self.check()
    def test_invented_remaining_and_own_peak_exhaustion_refuse(self):
        own = self.observed['active_allocations'][0]; own['remaining_bytes'] -= 1
        with self.assertRaisesRegex(ValueError,'remainder is invalid'):self.check()
        own['observed_used_bytes'] = GIB-GIB//4; own['remaining_bytes'] = GIB//4
        with self.assertRaisesRegex(ValueError,'terminal headroom'):self.check()
    def test_overlap_inventory_and_exact_owner_loss_refuse(self):
        self.observed['active_allocations'].append(active(4,self.output+'/child',GIB//4,0))
        with self.assertRaisesRegex(ValueError,'overlaps'):self.check(False)
        self.observed['active_allocations'].pop();self.observed['inventory']['total_logical_bytes'] = 0
        with self.assertRaisesRegex(ValueError,'predates'):self.check()
        self.observed['inventory']['total_logical_bytes'] = 40*GIB
        with self.assertRaisesRegex(ValueError,'owner exited'):
            exact_projection(self.observed,self.owner,self.output,self.f['policy'],self.f['now'],0,
                             production=True,lookup=lambda _:None)
    def test_ceiling_floor_and_deadline_still_apply(self):
        original = deepcopy(self.observed)
        for change in ['ceiling','floor','deadline']:
            self.observed = deepcopy(original);now = self.f['now']
            if change == 'ceiling':self.observed['inventory']['total_logical_bytes'] = 49*GIB
            elif change == 'floor':self.observed['free_bytes']['G:'] = 75*GIB
            else:now = DEADLINE-timedelta(hours=12)
            with self.subTest(change=change),self.assertRaises(ValueError):
                exact_projection(self.observed,self.owner,self.output,self.f['policy'],now,GIB//4,
                                 production=True,lookup=lookup)


class Runtime(unittest.TestCase):
    def setUp(self):
        f=facts();self.args=dict(policy=f['policy'],cap=GIB,used=GIB//4,peak=GIB//4,
            elapsed=10,maximum_seconds=1200,free=f['free_bytes'],now=f['now'])
    def check(self):check_runtime(**self.args)
    def test_exact_tailroom_boundary(self):
        self.args['used']=self.args['cap']-self.args['peak']-TERMINAL_RESERVE;self.check()
        self.args['used']+=1
        with self.assertRaisesRegex(ValueError,'headroom'):self.check()
    def test_deadline_cannot_be_extended_and_stricter_deadline_is_obeyed(self):
        self.args['policy']['target_utc']=(DEADLINE+timedelta(days=10)).isoformat()
        self.args['now']=DEADLINE-timedelta(hours=12)
        with self.assertRaisesRegex(ValueError,'Packaging'):self.check()
        self.args['policy']['target_utc']=(DEADLINE-timedelta(days=2)).isoformat()
        self.args['now']=DEADLINE-timedelta(days=1)
        with self.assertRaisesRegex(ValueError,'Packaging'):self.check()
    def test_elapsed_limit_invalid_values_and_negative_usage_refuse(self):
        original=deepcopy(self.args)
        for key,value in [('elapsed',1200),('elapsed',-1),('maximum_seconds',14401),
                          ('maximum_seconds',True),('used',-1),('peak',True),('cap',9*GIB)]:
            self.args=dict(original,**{key:value})
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.check()
    def test_each_drive_floor_is_enforced_even_if_configured_lower(self):
        for drive,floor in [('C:',50),('G:',75)]:
            self.args['policy']['resource_policy']['minimum_free_gib'][drive]=0
            self.args['free'][drive]=floor*GIB+self.args['peak'];self.check()
            self.args['free'][drive]-=1
            with self.subTest(drive=drive),self.assertRaisesRegex(ValueError,'Drive floor'):self.check()
            self.args['free'][drive]=100*GIB
    def test_stricter_floor_is_preserved(self):
        self.args['policy']['resource_policy']['minimum_free_gib']['G:']=101
        with self.assertRaisesRegex(ValueError,'Drive floor'):self.check()
    def test_ambiguous_zero_boolean_and_oversized_caps_refuse(self):
        for a in [{},dict(allocation_bytes=GIB,maximum_output_bytes=GIB),
                  dict(allocation_bytes=0),dict(allocation_bytes=True),dict(allocation_bytes=9*GIB)]:
            with self.subTest(a=a),self.assertRaises(ValueError):output_limit(a)


class Ownership(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.local=Path(self.temp.name);self.output=self.local/'n4/guarded';self.output.mkdir(parents=True)
        self.code=[dict(path='admitted.py',sha256='a'*64,bytes=1)]
        self.a=dict(owner=who(3),maximum_output_bytes=GIB,code=self.code)
    def check(self):return validate_boundary(self.a,who(3),self.output,self.local,self.code,lookup=lookup)
    def test_exact_live_owner_source_and_root_join(self):self.assertEqual(self.check(),GIB)
    def test_owner_reuse_changed_code_and_foreign_output_refuse(self):
        for field,value in [('owner',who(4)),('code',[])]:
            original=self.a[field];self.a[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.check()
            self.a[field]=original
        with self.assertRaises(ValueError):validate_boundary(self.a,who(3),self.local,self.local,self.code,lookup=lookup)
    def test_unheld_guard_refuses_runtime_work(self):
        guard=OutputGuard.__new__(OutputGuard);guard.held=False
        with self.assertRaisesRegex(ValueError,'lock is not held'):guard.fast_check()
    def test_lock_release_does_not_swallow_a_producer_failure(self):
        class Held:
            released=False
            def __exit__(self,*args):self.released=True;return False
        guard=OutputGuard.__new__(OutputGuard);guard.held=True;guard.lock_context=Held()
        self.assertFalse(guard.__exit__(ValueError,ValueError('producer failure'),None))
        self.assertFalse(guard.held);self.assertTrue(guard.lock_context.released)


if __name__=='__main__':unittest.main()
