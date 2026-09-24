"""Meaningful process/lock/failure/resume contracts; see README.md."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

SCRIPT=Path(__file__).with_name('supervisor.py')
spec=importlib.util.spec_from_file_location('n1_supervisor',SCRIPT)
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='jp-n1-supervisor-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        s.init(self.root,'fixture-session',None)

    def call(self,*args):
        return subprocess.run([sys.executable,'-B',str(SCRIPT),*args,'--root',str(self.root)],capture_output=True,text=True,
            timeout=20,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)

    def wait_terminal(self):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            row=s.read(self.root/'worker.json',{})
            if row.get('status') in ('FAILED','COMPLETED'):
                while s.same_process(row) and time.monotonic()<deadline:time.sleep(.05)
                return row
            time.sleep(.05)
        self.fail('Worker did not finish')

    def test_cross_process_overlap_prevention(self):
        with s.lock(self.root/'writer.lock'):
            result=self.call('probe')
        self.assertEqual(result.returncode,0)
        self.assertIn('OVERLAP_PREVENTED',result.stdout)
        self.assertFalse((self.root/'status.json').exists())

    def test_atomic_reader_sharing_denial_recovers_without_losing_prior_value(self):
        target=self.root/'atomic-retry.json';s.atomic(target,{'version':1})
        original=s.os.replace;calls=[]
        def temporary_denial(source,destination):
            calls.append(1)
            self.assertEqual(s.read(target),{'version':1})
            if len(calls)==1:
                error=PermissionError('simulated Windows reader sharing');error.winerror=32;raise error
            return original(source,destination)
        with patch.object(s.os,'replace',side_effect=temporary_denial):s.atomic(target,{'version':2})
        self.assertEqual(len(calls),2);self.assertEqual(s.read(target),{'version':2})

    def test_atomic_unrelated_permission_error_is_not_retried(self):
        target=self.root/'atomic-denied.json'
        with patch.object(s.os,'replace',side_effect=PermissionError('unrelated denial')) as replace:
            with self.assertRaises(PermissionError):s.atomic(target,{'version':1})
        self.assertEqual(replace.call_count,1);self.assertFalse(target.exists())
        self.assertEqual(len(list(self.root.glob('.atomic-denied.json.*.tmp'))),1)

    def test_unchanged_healthy_check_does_not_enqueue_or_invoke_llm(self):
        s.probe(self.root)
        first=list((self.root/'review_requests').glob('*.json'))
        result=s.probe(self.root)
        self.assertFalse(result['changed']);self.assertFalse(result['llm_invoked'])
        self.assertEqual(first,list((self.root/'review_requests').glob('*.json')))

    def test_starting_and_running_watchdogs_detect_dead_or_stale_host(self):
        for status in ('STARTING','RUNNING'):
            with self.subTest(status=status):
                s.atomic(self.root/'worker.json',dict(status=status,pid=99999,create_time=1,
                    heartbeat_unix=time.time()-3600,run_id='fixture'))
                with patch.object(s,'same_process',return_value=False),patch.object(s,'stop_owned_tree') as stop:
                    self.assertEqual(s.probe(self.root)['meaningful']['worker_health'],'WORKER_LOST')
                    stop.assert_not_called()
                with patch.object(s,'same_process',return_value=True),patch.object(s,'stop_owned_tree') as stop:
                    self.assertEqual(s.probe(self.root)['meaningful']['worker_health'],'WATCHDOG_HEARTBEAT_STALE')
                    stop.assert_not_called()

    def test_terminal_host_or_orphan_child_prevents_resume_without_launch(self):
        def observed_process(pid):
            process=Mock()
            process.is_running.return_value=True
            process.create_time.return_value=100 if pid==501 else 200
            return process
        cases=[
            ('terminal-host',dict(status='COMPLETED',pid=501,create_time=100),'host still active'),
            ('orphan-child',dict(status='RUNNING',pid=501,create_time=99,
                child_pid=502,child_create_time=200),'child still active'),
            ('legacy-child',dict(status='FAILED',pid=501,create_time=99,
                child_pid=502),'child identity unverified'),
            ('legacy-host',dict(status='COMPLETED',pid=501),'host identity unverified'),
        ]
        for label,record,message in cases:
            with self.subTest(case=label):
                s.atomic(self.root/'worker.json',record)
                with patch.object(s.psutil,'Process',side_effect=observed_process),patch.object(s.subprocess,'Popen') as launch:
                    with self.assertRaisesRegex(RuntimeError,message):
                        s.start(self.root,self.root/'absent-spec.json',resume=True)
                    launch.assert_not_called()
                self.assertFalse((self.root/'worker_spec.json').exists())
                self.assertEqual(s.read(self.root/'worker.json'),record)

    def test_pid_reuse_absence_and_identity_uncertainty_are_distinct(self):
        reused=Mock()
        reused.is_running.return_value=True;reused.create_time.return_value=300
        with patch.object(s.psutil,'Process',return_value=reused):
            s.require_no_active_worker(dict(pid=501,create_time=100,child_pid=502,child_create_time=200))
        with patch.object(s.psutil,'Process',side_effect=s.psutil.NoSuchProcess(501)):
            s.require_no_active_worker(dict(pid=501,create_time=100,child_pid=502))
        with patch.object(s.psutil,'Process',side_effect=s.psutil.AccessDenied(501)):
            with self.assertRaisesRegex(RuntimeError,'identity unverified'):
                s.require_no_active_worker(dict(child_pid=501,child_create_time=100))
        with self.assertRaisesRegex(RuntimeError,'launch outcome unverified'):
            s.require_no_active_worker(dict(child_launch_pending=True))

    def test_worker_failure_checkpoint_resume_and_lock_cleanup(self):
        checkpoint=self.root/'checkpoint.txt'
        worker_spec=self.root/'test-spec.json'
        code="from pathlib import Path; import sys; p=Path(sys.argv[1]); old=p.exists(); p.write_text('resumed' if old else 'checkpoint'); sys.exit(0 if old else 7)"
        s.atomic(worker_spec,dict(argv=[sys.executable,'-c',code,str(checkpoint)],cwd=str(self.root)))
        s.start(self.root,worker_spec)
        failed=self.wait_terminal()
        self.assertEqual(failed['status'],'FAILED');self.assertIn('exit_code',failed,failed)
        self.assertEqual(failed['exit_code'],7)
        if failed['child_pid'] is not None:self.assertIsInstance(failed['child_create_time'],(int,float))
        else:self.assertIsNone(failed['child_create_time'])
        self.assertFalse(failed['child_launch_pending'])
        self.assertEqual(checkpoint.read_text(),'checkpoint')
        s.start(self.root,worker_spec,resume=True)
        done=self.wait_terminal()
        self.assertEqual(done['status'],'COMPLETED');self.assertTrue(done['resumed'])
        self.assertEqual(checkpoint.read_text(),'resumed')
        with s.lock(self.root/'worker-owner.lock'):pass
        self.assertTrue(any(json.loads(p.read_text())['delta']['worker_health']=='FAILED' for p in (self.root/'review_requests').glob('*.json')))

    def test_phase_gates_and_target_survives_reinitialization(self):
        before=s.read(self.root/'campaign.json')
        s.phase(self.root,'inference')
        self.assertEqual(s.probe(self.root,'setup')['status'],'PHASE_NOT_DUE')
        self.assertEqual(s.probe(self.root,'inference')['interval_minutes'],15)
        after=s.init(self.root,'different-session',None)
        self.assertEqual(after['session_id'],before['session_id'])
        self.assertEqual(after['target_utc'],before['target_utc'])

    def test_disk_reserve_prevents_new_worker(self):
        state=s.read(self.root/'campaign.json')
        state['resource_policy']['minimum_free_gib']={self.root.drive:10**9}
        s.atomic(self.root/'campaign.json',state)
        with self.assertRaisesRegex(RuntimeError,'Disk reserve'):s.start(self.root,self.root/'absent-spec.json')
        self.assertFalse((self.root/'worker.json').exists())

    def test_eta_uses_only_new_cells_after_resume(self):
        s.atomic(self.root/'panel_progress.json',dict(pid=91,completed=80,total=100,elapsed_seconds=5))
        self.assertIsNone(s.probe(self.root)['eta_seconds'])
        s.atomic(self.root/'panel_progress.json',dict(pid=91,completed=82,total=100,elapsed_seconds=25))
        self.assertEqual(s.probe(self.root)['eta_seconds'],180)
        s.atomic(self.root/'panel_progress.json',dict(pid=92,completed=82,total=100,elapsed_seconds=2))
        self.assertIsNone(s.probe(self.root)['eta_seconds'])
        s.atomic(self.root/'panel_progress.json',dict(pid=92,completed=100,total=100,elapsed_seconds=202))
        self.assertEqual(s.probe(self.root)['eta_seconds'],0)

    def test_disk_reserve_stops_only_owned_worker_tree(self):
        spec_path=self.root/'sleep-spec.json'
        s.atomic(spec_path,dict(argv=[sys.executable,'-c','import time; time.sleep(30)'],cwd=str(self.root)))
        record=s.start(self.root,spec_path)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            worker=s.read(self.root/'worker.json')
            if worker.get('child_pid'):break
            time.sleep(.05)
        self.assertTrue(worker.get('child_pid'))
        self.assertIsInstance(worker['child_create_time'],(int,float))
        state=s.read(self.root/'campaign.json')
        state['resource_policy']['minimum_free_gib']={self.root.drive:10**9}
        s.atomic(self.root/'campaign.json',state)
        result=s.probe(self.root)
        self.assertEqual(result['meaningful']['worker_health'],'DISK_RESERVE_LOW')
        self.assertEqual(s.read(self.root/'worker.json')['status'],'FAILED_DISK_RESERVE')
        self.assertFalse(s.same_process(record))
        with s.lock(self.root/'worker-owner.lock'):pass


if __name__=='__main__':unittest.main()
