"""Resource accounting failure cases and a real hidden child. See README_APPLICATION_RESOURCES.md."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
import psutil
from application_resources import ApplicationResources,ResourceLedger,observe,PHASES,FIELDS
from common import bind,freeze

CONTEXT={}
OWNER=dict(pid=10,create_time=100.)


def process(pid=10,created=100.,cpu=1.,memory=100):
    return dict(pid=pid,create_time=created,ppid=1,memory_info_bytes=dict(rss=memory,private=memory//2),
        unique_set_size_bytes=memory//3,proportional_set_size_bytes=None,threads=2,cpu_seconds=dict(user=cpu,system=0.))


def sample(t, processes=None, complete=True,phase='running'):
    rows=processes if processes is not None else [process()]
    return dict(began_monotonic_sec=t,ended_monotonic_sec=t+.01,phase_at_start=phase,phase_at_end=phase,
        tree=dict(status='ALIVE',complete=complete,processes=rows,retired=[],thread_count_sum=sum(p['threads'] for p in rows),
            rss_sum_bytes_not_unique_physical=sum(p['memory_info_bytes']['rss'] for p in rows),
            unique_set_size_sum_bytes=sum(p['unique_set_size_bytes'] for p in rows),
            private_commit_sum_bytes=sum(p['memory_info_bytes']['private'] for p in rows),pss_sum_bytes=None))


class ResourceTests(unittest.TestCase):
    def test_identity_reuse_has_separate_cpu_and_missing_pss_stays_unavailable(self):
        ledger=ResourceLedger(OWNER)
        ledger.accept(sample(1,[process(cpu=5),process(11,101.,cpu=50,memory=200)]))
        ledger.accept(sample(2,[process(cpu=7),process(11,102.,cpu=.5,memory=300)]))
        ledger.accept(sample(3,[process(cpu=8),process(11,102.,cpu=1.5,memory=300)]))
        result=ledger.summary();self.assertEqual(result['observed_cpu_delta_seconds_lower_bound'],4)
        self.assertEqual(len(result['sampled_owners']),3)
        self.assertEqual(result['phases']['running']['peaks'][FIELDS[0]],400)
        self.assertNotIn('pss_sum_bytes',result['phases']['running']['peaks'])
        self.assertIsNone(result['phases']['running']['last']['pss_sum_bytes'])

    def test_incomplete_or_transition_samples_do_not_fabricate_phase_growth(self):
        ledger=ResourceLedger(OWNER);ledger.accept(sample(1))
        ledger.accept(sample(2,[process(memory=9999)],False))
        row=sample(3,[process(memory=8000)]);row['phase_at_end']='draining';ledger.accept(row)
        result=ledger.summary();self.assertEqual(result['incomplete_samples'],1)
        self.assertEqual(result['phases']['running']['last'][FIELDS[0]],100)
        self.assertEqual(result['phases']['transition']['peaks'][FIELDS[0]],8000)

    def test_duplicate_root_reuse_clock_cpu_regression_and_census_bounds_rejected(self):
        bad=[sample(1,[process(),process()]),sample(1,[process(11)]),sample(1)]
        bad[-1]['tree']['status']='PID_REUSED'
        for row in bad:
            with self.assertRaises(ValueError):ResourceLedger(OWNER).accept(row)
        ledger=ResourceLedger(OWNER);ledger.accept(sample(2,[process(cpu=5)]))
        with self.assertRaises(ValueError):ledger.accept(sample(1))
        with self.assertRaises(ValueError):ledger.accept(sample(3,[process(cpu=4)]))
        with self.assertRaises(ValueError):ResourceLedger(OWNER).accept(sample(1,[process(pid=i+10) for i in range(257)]))

    def test_retained_reparented_children_are_included_once(self):
        root,child=process(),process(11,101.,memory=500)
        def tree(pid,created):
            return dict(status='ALIVE',processes=[root] if pid==10 else [child])
        with patch('application_resources.process_tree',side_effect=tree):
            row=observe(OWNER,[(10,100.),(11,101.)])
        self.assertEqual(row['rss_sum_bytes_not_unique_physical'],600)
        self.assertEqual(len(row['processes']),2)
        with patch('application_resources.process_tree',return_value=dict(status='ALIVE',processes=[root,child])):
            row=observe(OWNER,[(10,100.),(11,101.)])
        self.assertEqual(row['rss_sum_bytes_not_unique_physical'],600)

    def test_storage_failure_preserves_prefix_and_cannot_become_success(self):
        output=CONTEXT['output']/'overflow';monitor=ApplicationResources(output,interval=.1,max_bytes=1024)
        large=sample(1)['tree'];large['unused_padding']='x'*2000
        try:
            with patch('application_resources.observe',return_value=large):
                monitor.start();monitor.thread.join(3)
        finally:result=monitor.close()
        self.assertEqual(result['status'],'FAILED_PRESERVED');self.assertTrue(result['observer_thread_exited'])
        self.assertLessEqual(result['observer_bytes'],1024)
        self.assertIn('byte bound',result['error']);self.assertEqual(monitor.close(),result)

    def test_phase_and_deadline_failures_remain_explicit(self):
        monitor=ApplicationResources(CONTEXT['output']/'deadline',interval=.1,max_seconds=.15).start()
        try:
            with self.assertRaises(ValueError):monitor.mark('running')
            monitor.thread.join(3)
        finally:result=monitor.close()
        self.assertEqual(result['status'],'FAILED_PRESERVED');self.assertIn('deadline',result['error'])
        self.assertFalse(result['all_lifecycle_marks_present'])

    def test_actual_current_process_hidden_child_and_shutdown(self):
        output=CONTEXT['output']/'actual-tree';monitor=ApplicationResources(output,interval=.1).start();child=None
        try:
            monitor.mark('gui_ready');monitor.mark('gallery_ready')
            # Model-free allocation fixture. No app/audio/GUI code is imported.
            child=subprocess.Popen([sys.executable,'-B','-c','import sys; a=bytearray(16*1024*1024); sys.stdin.buffer.read(1)'],
                stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            p=psutil.Process(child.pid);p.cpu_affinity([14]);owned=dict(pid=p.pid,create_time=p.create_time())
            monitor.mark('starting');monitor.mark('running');deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                with monitor.lock:
                    seen=monitor.ledger.owners.get((owned['pid'],owned['create_time']))
                    enough=seen is not None and seen['samples']>=3
                if enough:break
                time.sleep(.03)
            self.assertTrue(enough,'Actual child was not sampled')
            child.communicate(b'x',timeout=5);self.assertEqual(child.returncode,0)
            monitor.mark('draining');monitor.mark('closed')
        finally:
            if child is not None and child.poll() is None:child.communicate(b'x',timeout=5)
            result=monitor.close()
        self.assertEqual(result['status'],'OBSERVED_HOST_RESOURCES');self.assertTrue(result['all_lifecycle_marks_present'])
        self.assertTrue(result['observer_thread_exited']);self.assertFalse(result['controlled_whole_stack_qualified'])
        self.assertFalse(result['target_qualified']);self.assertEqual(result['integrated_N4_cells'],0)
        sampled=next(p for p in result['sampled_owners'] if p['pid']==owned['pid'] and p['create_time']==owned['create_time'])
        self.assertEqual(sampled['last_observation'],'EXITED')
        raw=[json.loads(line) for line in (output/'SAMPLES.jsonl').read_text().splitlines()]
        rows=[r for r in raw if r['kind']=='sample'];self.assertGreaterEqual(len(rows),3)
        self.assertTrue(any(len(r['tree']['processes'])>=2 for r in rows))
        self.assertTrue(any(p.get('unique_set_size_bytes',0)>8*1024**2 for r in rows for p in r['tree']['processes'] if p['pid']==owned['pid']))
        CONTEXT['actual']=dict(result=bind(output/'RESULT.json'),child=owned,child_exit_code=child.returncode,
            user_desktop_not_accessed=True,complete_application_run=False)
