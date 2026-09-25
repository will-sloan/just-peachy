"""Saved-resource replay and malformed-evidence checks. README_RESOURCE_REVIEW.md."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from application_resources import FIELDS, PHASES, ResourceLedger
from common import bind, load, verify
from review_resource_evidence import review
from test_application_resources import process, sample

SAVED = None
OWNER = dict(pid=2147483000, create_time=1.)


def fixture(*, incomplete=False, phases=PHASES):
    rows = []; ledger = ResourceLedger(OWNER); marks=[]
    for index, phase in enumerate(phases):
        mark=dict(kind='phase', phase=phase, monotonic_sec=10.+index*10)
        rows.append(mark); marks.append(mark)
        for step in range(2 if phase=='running' else 1):
            row=sample(mark['monotonic_sec']+1+step,
                [process(pid=OWNER['pid'],created=OWNER['create_time'],cpu=index+1+step*.5,memory=(index+1)*100+step*50)],phase=phase)
            row['kind']='sample';row['tree']['incomplete_processes']=[]
            if incomplete and phase=='running':
                row['tree']['complete']=False;row['tree']['incomplete_processes']=[dict(pid=99,status='UNAVAILABLE_ACCESS_DENIED')]
            rows.append(row);ledger.accept(row)
    result=dict(ledger.summary(), status='OBSERVED_HOST_RESOURCES', owner=OWNER, error=None, observer_thread_exited=True,
        phase_marks=marks, all_lifecycle_marks_present=tuple(phases)==PHASES, interval_sec=.5, elapsed_sec=100.,
        gpu_visibility_environment='', controlled_whole_stack_qualified=False,target_qualified=False,integrated_N4_cells=0)
    return rows,result


def write(root, rows, result, *, suffix=b''):
    data=b''.join((json.dumps(row)+'\n').encode() for row in rows)+suffix
    (root/'SAMPLES.jsonl').write_bytes(data);result=deepcopy(result)
    result['evidence']=bind(root/'SAMPLES.jsonl');result['observer_bytes']=len(data)
    (root/'RESULT.json').write_text(json.dumps(result),encoding='utf-8')
    return bind(root/'RESULT.json')


class ResourceReviewTests(unittest.TestCase):
    def test_saved_actual_resource_tree_reconstructs(self):
        if SAVED is None:self.skipTest('Guarded probe supplies original saved observation binding')
        verify(SAVED);row=review(SAVED,require_all_phases=True)
        original=load(SAVED['path'])
        self.assertEqual(row['reconstructed']['samples'],original['samples'])
        self.assertGreaterEqual(len(row['reconstructed']['sampled_owners']),2)
        self.assertFalse(row['controlled_whole_stack_qualified']);self.assertEqual(row['deployment_tier'],'UNKNOWN')

    def test_independent_per_process_sum_rejects_wrong_total(self):
        with tempfile.TemporaryDirectory() as temp:
            rows,result=fixture();next(r for r in rows if r['kind']=='sample')['tree'][FIELDS[0]]+=1
            with self.assertRaisesRegex(ValueError,'does not match the stored sum'):review(write(Path(temp),rows,result))

    def test_summary_peak_and_cpu_totals_must_reconstruct(self):
        with tempfile.TemporaryDirectory() as temp:
            for field in ('peak','cpu'):
                rows,result=fixture()
                if field=='peak':result['phases']['running']['peaks'][FIELDS[1]]+=1
                else:result['observed_cpu_delta_seconds_lower_bound']+=1
                with self.assertRaisesRegex(ValueError,'Reconstructed resource summary differs'):review(write(Path(temp),rows,result))

    def test_invalid_cpu_and_clock_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            rows,result=fixture();next(r for r in rows if r['kind']=='sample')['tree']['processes'][0]['cpu_seconds']['user']=float('nan')
            with self.assertRaisesRegex(ValueError,'Invalid raw CPU'):review(write(Path(temp),rows,result))
            rows,result=fixture();next(r for r in rows if r['kind']=='sample')['began_monotonic_sec']=0.
            with self.assertRaisesRegex(ValueError,'precedes its phase'):review(write(Path(temp),rows,result))

    def test_phase_order_and_census_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            rows,result=fixture();rows[2]['phase']='closed'
            with self.assertRaisesRegex(ValueError,'Phase mark order'):review(write(Path(temp),rows,result))
            rows,result=fixture();rows[1]['tree']['processes']*=2
            with self.assertRaisesRegex(ValueError,'duplicated or unbounded'):review(write(Path(temp),rows,result))

    def test_missing_lifecycle_remains_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            rows,result=fixture(phases=PHASES[:3]);binding=write(Path(temp),rows,result)
            row=review(binding);self.assertFalse(row['all_lifecycle_marks_present']);self.assertIsNone(row['running_growth'])
            with self.assertRaisesRegex(ValueError,'lifecycle marks are missing'):review(binding,require_all_phases=True)

    def test_unavailable_and_incomplete_never_become_zero_or_growth(self):
        with tempfile.TemporaryDirectory() as temp:
            rows,result=fixture(incomplete=True);row=review(write(Path(temp),rows,result))
            self.assertEqual(row['reconstructed']['incomplete_samples'],2)
            self.assertIsNone(row['sampled_global_peaks']['pss_sum_bytes']);self.assertIsNone(row['running_growth'])
            rows,result=fixture();row=review(write(Path(temp),rows,result))
            self.assertEqual(row['running_growth']['delta_bytes'][FIELDS[0]],50)
            self.assertIsNone(row['running_growth']['delta_bytes']['pss_sum_bytes'])

    def test_truncated_log_rejected_even_with_matching_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            rows,result=fixture()
            with self.assertRaisesRegex(ValueError,'truncated'):review(write(Path(temp),rows,result,suffix=b'{'))

    def test_foreign_root_and_false_acceptance_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            rows,result=fixture();binding=write(Path(temp),rows,result)
            with self.assertRaisesRegex(ValueError,'different application'):review(binding,expected_owner=dict(pid=OWNER['pid'],create_time=2.))
            result['target_qualified']=True
            with self.assertRaisesRegex(ValueError,'improperly asserted acceptance'):review(write(Path(temp),rows,result))
