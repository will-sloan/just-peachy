"""Reservation failure and boundary checks; README_RESERVATION_BUDGET_V1.md."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from common import bind, freeze
from reservation_budget_v1 import (GIB, DEADLINE, calculate, live_allocation, validate_closed)


def who(pid):
    return dict(pid=pid, create_time=1000.0+pid)


def closed():
    return [dict(kind=kind, expired_reservation_bytes=2*GIB, completed=n,
                 exact_owner_exited=True, owner=who(pid))
            for kind, n, pid in [('ASR', 1920, 1), ('D1', 960, 2)]]


def active(pid=3, root='G:/private/n4/scoring', cap=GIB, used=GIB//4):
    return dict(owner=who(pid), root=root, allocation_bytes=cap,
                observed_used_bytes=used, remaining_bytes=cap-used)


def facts():
    return dict(inventory=dict(errors=[], total_logical_bytes=40*GIB), closed=closed(),
                active=[active()], requested_bytes=3*GIB//2,
                policy=dict(target_utc=DEADLINE.isoformat(), resource_policy=dict(
                    new_payload_allowance_gib=50, minimum_free_gib={'C:': 50, 'G:': 75})),
                free_bytes={'C:': 100*GIB, 'G:': 100*GIB}, now=DEADLINE-timedelta(days=1),
                peak_bytes=GIB//4)


def lookup(owner):
    return object() if owner['pid'] >= 3 else None


def component(kind='ASR'):
    count = 1920 if kind == 'ASR' else 960
    ab = dict(path='G:/admission', sha256='a'*64, bytes=1)
    tb = dict(path='G:/terminal', sha256='b'*64, bytes=1)
    manifest = dict(path='G:/manifest', sha256='c'*64, bytes=1)
    review = dict(status=f'PASS_{kind}_FULL_BANK_COMPONENTS_ONLY', full_bank_component_coverage=True,
                  component_cells=count, admission=ab)
    review['final_result' if kind == 'ASR' else 'terminal'] = tb
    review['cells' if kind == 'ASR' else 'rows'] = [dict(result=dict(path=str(i))) for i in range(count)]
    admission = dict(manifest=manifest, total=count, allocation_bytes=2*GIB)
    terminal = dict(status='FULL_BANK_COLLECTED_REQUIRES_REVIEW', admission=ab,
                    completed=count, total=count, child=None, owner=who(1))
    return dict(kind=kind, review=review, admission=admission, terminal=terminal,
                admission_binding=ab, terminal_binding=tb, manifest_binding=manifest)


class CalculationTests(unittest.TestCase):
    def result(self, data=None):
        return calculate(**(data or facts()), lookup=lookup)

    def test_exact_accounting_retains_all_physical_bytes(self):
        r = self.result()
        self.assertEqual(r['projected_bytes'], 44.75*GIB)
        self.assertEqual(r['physical_bytes_removed_or_credited'], 0)
        self.assertFalse(r['worker_execution_authorized'])

    def test_exact_ceiling_and_one_byte_over(self):
        d = facts(); d['inventory']['total_logical_bytes'] += int(5.25*GIB)
        self.assertEqual(self.result(d)['projected_bytes'], 50*GIB)
        d['inventory']['total_logical_bytes'] += 1
        with self.assertRaises(ValueError): self.result(d)

    def test_simultaneous_allocations_are_added(self):
        d = facts(); d['active'].append(active(4, 'G:/private/n4/waiter', GIB//4, 0))
        self.assertEqual(self.result(d)['active_remaining_bytes'], GIB)

    def test_growing_output_keeps_commitment(self):
        d = facts(); before = self.result(d)['projected_bytes']
        d['inventory']['total_logical_bytes'] += 123
        d['active'][0]['observed_used_bytes'] += 123; d['active'][0]['remaining_bytes'] -= 123
        self.assertEqual(self.result(d)['projected_bytes'], before)

    def test_inventory_must_include_observed_used_bytes(self):
        d = facts(); d['inventory']['total_logical_bytes'] = 1
        with self.assertRaises(ValueError): self.result(d)

    def test_inventory_errors_refuse(self):
        d = facts(); d['inventory']['errors'] = ['denied']
        with self.assertRaises(ValueError): self.result(d)

    def test_unknown_or_duplicate_closed_release(self):
        for value in [[], closed()[:1], [closed()[0]]*2]:
            with self.subTest(value=value):
                d = facts(); d['closed'] = value
                with self.assertRaises(ValueError): self.result(d)

    def test_active_closed_owner_refuses_release(self):
        d = facts(); d['closed'][0]['owner'] = who(8)
        with self.assertRaises(ValueError): self.result(d)

    def test_incomplete_closed_proof_refuses(self):
        for key, value in [('expired_reservation_bytes', 3*GIB), ('completed', 1919), ('exact_owner_exited', False)]:
            d = facts(); d['closed'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.result(d)

    def test_stale_active_owner_requires_resample(self):
        d = facts(); d['active'][0]['owner'] = who(1)
        with self.assertRaises(ValueError): self.result(d)

    def test_duplicate_active_owner_refuses(self):
        d = facts(); d['active'].append(active(3, 'G:/private/n4/other'))
        with self.assertRaises(ValueError): self.result(d)

    def test_overlap_in_both_directions_refuses(self):
        for root in ['G:/private/n4/scoring', 'G:/private/n4/scoring/child', 'G:/private/n4']:
            d = facts(); d['active'].append(active(4, root))
            with self.subTest(root=root), self.assertRaises(ValueError): self.result(d)

    def test_negative_and_invented_remaining_refuse(self):
        for cap, used, left in [(GIB, GIB+1, -1), (GIB, 0, 0), (True, 0, 1)]:
            d = facts(); d['active'][0].update(allocation_bytes=cap, observed_used_bytes=used, remaining_bytes=left)
            with self.subTest(cap=cap,used=used), self.assertRaises(ValueError): self.result(d)

    def test_invalid_request_and_peak_refuse(self):
        for requested, peak in [(0, 0), (-1, 0), (True, 0), (9*GIB, 0), (GIB, GIB+1), (GIB, -1)]:
            d = facts(); d.update(requested_bytes=requested, peak_bytes=peak)
            with self.subTest(requested=requested,peak=peak), self.assertRaises(ValueError): self.result(d)

    def test_each_drive_peak_boundary(self):
        for drive,floor in [('C:',50),('G:',75)]:
            d = facts(); d['free_bytes'][drive] = floor*GIB+d['peak_bytes']; self.result(d)
            d['free_bytes'][drive] -= 1
            with self.subTest(drive=drive), self.assertRaises(ValueError): self.result(d)

    def test_stricter_floor_and_lower_ceiling_preserved(self):
        d=facts(); d['policy']['resource_policy']['minimum_free_gib']['G:']=101
        with self.assertRaises(ValueError): self.result(d)
        d=facts(); d['policy']['resource_policy']['new_payload_allowance_gib']=44
        with self.assertRaises(ValueError): self.result(d)

    def test_limit_increase_or_nonfinite_refuses(self):
        for value in [51, float('nan'), float('inf'), True, 0, -1]:
            d=facts(); d['policy']['resource_policy']['new_payload_allowance_gib']=value
            with self.subTest(value=value), self.assertRaises(ValueError): self.result(d)

    def test_original_packaging_cutoff_cannot_be_extended(self):
        d=facts(); d['policy']['target_utc']=(DEADLINE+timedelta(days=20)).isoformat()
        d['now']=DEADLINE-timedelta(hours=12)
        with self.assertRaises(ValueError): self.result(d)

    def test_earlier_configured_cutoff_and_naive_time(self):
        d=facts(); d['policy']['target_utc']=(DEADLINE-timedelta(hours=13)).isoformat()
        with self.assertRaises(ValueError): self.result(d)
        d=facts(); d['now']=d['now'].replace(tzinfo=None)
        with self.assertRaises(ValueError): self.result(d)

    def test_access_denial_does_not_mean_exit(self):
        def denied(owner): raise PermissionError('denied')
        with self.assertRaises(PermissionError): calculate(**facts(),lookup=denied)


class ClosureTests(unittest.TestCase):
    def test_both_real_shapes_and_reused_pid(self):
        # An exact-identity lookup returns None for a different creation time.
        for kind in ['ASR','D1']:
            d=component(kind); seen=[]
            def exited(owner): seen.append(owner.copy()); return None
            r=validate_closed(**d,lookup=exited)
            self.assertEqual(r['expired_reservation_bytes'],2*GIB); self.assertEqual(seen,[who(1)])

    def test_live_owner_or_child_refuses(self):
        with self.assertRaises(ValueError): validate_closed(**component(),lookup=lambda owner:object())
        d=component(); d['terminal']['child']=who(9)
        with self.assertRaises(ValueError): validate_closed(**d,lookup=lambda owner:None)

    def test_missing_and_duplicate_reviewed_rows_refuse(self):
        for duplicate in [False,True]:
            d=component()
            if duplicate:d['review']['cells'][-1]=d['review']['cells'][0]
            else:d['review']['cells'].pop()
            with self.assertRaises(ValueError): validate_closed(**d,lookup=lambda owner:None)

    def test_failed_review_and_partial_terminal_refuse(self):
        for part,key,value in [('review','status','READY_FOR_REVIEW'),('review','full_bank_component_coverage',False),
                               ('terminal','completed',1919),('terminal','failed',1),('admission','allocation_bytes',GIB)]:
            d=component(); d[part][key]=value
            with self.subTest(part=part,key=key), self.assertRaises(ValueError):validate_closed(**d,lookup=lambda owner:None)

    def test_changed_manifest_or_join_refuses(self):
        for part,key in [('admission','manifest'),('terminal','admission'),('review','final_result')]:
            d=component();d[part][key]={'different':True}
            with self.subTest(part=part,key=key), self.assertRaises(ValueError):validate_closed(**d,lookup=lambda owner:None)

    def test_actual_admission_hash_and_reparse_check(self):
        with tempfile.TemporaryDirectory() as name:
            local=Path(name);root=local/'n4/run';root.mkdir(parents=True)
            path=root/'ADMISSION.json';freeze(path,dict(owner=who(3),maximum_output_bytes=GIB));b=bind(path)
            inventory=lambda root:dict(errors=[],total_logical_bytes=10,reparse_not_traversed=[])
            r=live_allocation(b,root,local,lookup=lookup,inventory=inventory)
            self.assertEqual(r['remaining_bytes'],GIB-10)
            with self.assertRaises(ValueError):live_allocation(b,root,local,lookup=lookup,
                inventory=lambda root:dict(errors=[],total_logical_bytes=10,reparse_not_traversed=['link']))
            path.write_text('{}',encoding='utf-8')
            with self.assertRaises(ValueError):live_allocation(b,root,local,lookup=lookup,inventory=inventory)


if __name__=='__main__':unittest.main()
