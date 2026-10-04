"""Synthetic owned-process/storage integration; README_INTEGRATION_TESTS.md."""
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from launcher import CaptionView, Manager, request_current_stop, run_headless
from profiles import RuntimeSelection, SessionPolicy
from runtime_support import DiskBudget, SegmentedText, strict, owner_status, kill_owned_unit
from storage import SessionStore, StoragePolicy
from worker import run_owned_session, file_size_plan
import runtime_support


class FakeOwnedProcess:
    def __init__(self, output=b"synthetic worker\n"):
        self.pid = 123456
        self.stdout = io.BytesIO(output)
        self.returncode = None
        self.waited = False

    def poll(self):
        return self.returncode

    def wait(self):
        if self.returncode is None:
            raise AssertionError("must not wait for a live fixture")
        self.waited = True
        return self.returncode


CHILD_FIXTURE = r'''
import os,sys,ctypes
if os.name == 'nt':
 k=ctypes.windll.kernel32
 k.GetCurrentProcess.restype=ctypes.c_void_p
 k.SetProcessAffinityMask.argtypes=(ctypes.c_void_p,ctypes.c_size_t)
 assert k.SetProcessAffinityMask(k.GetCurrentProcess(),16384)
else:
 os.sched_setaffinity(0,{14})
import psutil,json,time,struct
from pathlib import Path
owner=Path(sys.argv[2]); owner.mkdir()
me=psutil.Process()
assert me.cpu_affinity()==[14]
identity=dict(status='REGISTERED_OWNER',pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity(),purpose='synthetic subprocess fixture')
def receipt(name,value):
 with (owner/name).open('x',encoding='utf-8') as f:
  json.dump(value,f); f.flush(); os.fsync(f.fileno())
receipt('REGISTERED_OWNER.json',identity)
from storage import SessionStore,StoragePolicy
request=json.loads(Path(sys.argv[1]).read_text())
store=SessionStore(request['data_root'],StoragePolicy(**request['storage_policy']))
spool=store.begin(dict(duration_seconds=1,sample_rate=16000))
spool.append_processed(0,struct.pack('<ff',.25,-.25))
receipt('SESSION.json',dict(session_id=spool.session_id))
deadline=time.monotonic()+10
while not (owner/'STOP').exists():
 if time.monotonic()>deadline: raise RuntimeError('fixture stop timeout')
 time.sleep(.01)
spool.stop(final_sample=2)
receipt('RESULT.json',dict(session_id=spool.session_id,failure=None,synthetic=True,logical_cleanup_complete=True,physical_process_closed=False))
store.close()
'''


class RuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get('LIVE_INTEGRATION_TEST_ROOT')
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='runtime-integration-', dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.binding = self.base/'binding.json'
        self.binding.write_text(json.dumps(dict(python=sys.executable, native_launch_enabled=True,
            storage_policy=dict(reserve_bytes=0, reserve_fraction=0, segment_samples=8))))

    def manager(self, factory):
        manager = Manager(self.binding, self.base/'data', 'synthetic-test.scope', process_factory=factory,
                          session_authorizer=lambda *args: dict(synthetic=True),
                          service_room_check=lambda *args: 10000)
        def cleanup():
            if manager.process is not None:
                if isinstance(manager.process, FakeOwnedProcess):
                    manager.process.returncode = 1
                else:
                    manager.stop()
                    try:
                        manager.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        manager.process.terminate()
                        manager.process.wait(timeout=3)
                manager.poll()
            if not manager.closed:
                manager.close()
        self.addCleanup(cleanup)
        return manager

    def test_real_owned_child_stop_drain_reap_and_restart_history(self):
        def fixture_factory(command, **kwargs):
            request = command[command.index('--request')+1]
            owner = command[command.index('--owner-directory')+1]
            return subprocess.Popen([sys.executable, '-c', CHILD_FIXTURE, request, owner],
                                    cwd=Path(__file__).parent, **kwargs)
        manager = self.manager(fixture_factory)
        ids = []
        for _ in range(2):
            manager.start(RuntimeSelection(), SessionPolicy(maximum_session_seconds=1))
            # Deliberately request Stop before the worker has registered its owner.
            manager.stop()
            deadline = time.monotonic()+8
            while manager.poll() is None:
                if time.monotonic() > deadline:
                    self.fail('synthetic child did not close')
                time.sleep(.01)
            closure = manager.last
            self.assertEqual(closure['returncode'], 0, closure)
            self.assertTrue(closure['direct_child_reaped'])
            self.assertTrue(closure['stdout_reader_joined'])
            self.assertEqual(closure['registered_owner']['affinity'], [14])
            self.assertEqual(closure['receipt_errors'], [])
            session_id = closure['result']['session_id']
            ids.append(session_id)
            self.assertEqual(manager.store.read(session_id)['processed_samples'], 2)
            manager.store.keep(session_id)
        self.assertEqual(len(set(ids)), 2)
        manager.close()
        reopened = SessionStore(self.base/'data'/'recordings', StoragePolicy(reserve_bytes=0, reserve_fraction=0))
        self.assertEqual(len(reopened.history()['items']), 2)

    def test_manager_single_owner_close_pending_and_malformed_receipt(self):
        process = FakeOwnedProcess()
        manager = self.manager(lambda *args, **kwargs: process)
        manager.start(RuntimeSelection(), SessionPolicy())
        with self.assertRaises(RuntimeError):
            manager.start(RuntimeSelection(), SessionPolicy())
        with self.assertRaises(RuntimeError):
            manager.close()
        self.assertFalse(manager.closed)
        manager.owner_dir.mkdir()
        manager.poll()
        self.assertTrue((manager.owner_dir/'STOP').exists())
        (manager.owner_dir/'RESULT.json').write_text('{broken')
        process.returncode = 1
        closure = manager.poll()
        self.assertTrue(process.waited)
        self.assertTrue(closure['receipt_errors'])
        self.assertIsNone(manager.process)
        manager.close()

    def test_gui_snapshot_stays_in_memory_and_allocator_is_set_before_exec(self):
        from runtime_ui_channel import spatial_message
        wire=spatial_message(dict(state='RUNNING',coordinate_frame='device',
            arrows=[],associations=[],motion=dict(valid=True,yaw_deg=15)))
        process=FakeOwnedProcess(b'diagnostic before\n'+wire+b'diagnostic after\n')
        factory=mock.Mock(return_value=process)
        manager=self.manager(factory)
        manager.show_spatial(True)
        manager.start(RuntimeSelection(),SessionPolicy())
        manager.reader.join(timeout=2)
        self.assertFalse(manager.reader.is_alive())
        self.assertEqual(manager.latest_spatial['spatial']['motion']['yaw_deg'],15)
        self.assertEqual((manager.run_dir/'WORKER.log').read_bytes(),b'diagnostic before\ndiagnostic after\n')
        env=factory.call_args.kwargs['env']
        for key,value in dict(MALLOC_ARENA_MAX='1',MALLOC_MMAP_THRESHOLD_='131072',MALLOC_TRIM_THRESHOLD_='131072').items():
            self.assertEqual(env[key],value)
        manager.owner_dir.mkdir()
        manager.poll()
        self.assertTrue((manager.owner_dir/'GUI_SPATIAL_ON').is_file())
        manager.show_spatial(False)
        self.assertFalse((manager.owner_dir/'GUI_SPATIAL_ON').exists())
        process.returncode=1

    def test_manager_disabled_admission_and_start_failure_receipt(self):
        binding = json.loads(self.binding.read_text())
        binding['native_launch_enabled'] = False
        self.binding.write_text(json.dumps(binding))
        factory = mock.Mock(side_effect=OSError('synthetic launch error'))
        manager = self.manager(factory)
        with self.assertRaisesRegex(RuntimeError, 'pending'):
            manager.start(RuntimeSelection(), SessionPolicy())
        factory.assert_not_called()
        manager.binding['native_launch_enabled'] = True
        with self.assertRaises(OSError):
            manager.start(RuntimeSelection(), SessionPolicy())
        self.assertIsNone(manager.process)
        self.assertTrue((manager.run_dir/'START_FAILURE.json').exists())

    def test_manager_deadline_requests_stop_without_claiming_closure(self):
        process = FakeOwnedProcess()
        manager = self.manager(lambda *args, **kwargs: process)
        manager.start(RuntimeSelection(), SessionPolicy())
        manager.owner_dir.mkdir()
        manager.started -= SessionPolicy().total_deadline_seconds + 1
        self.assertIsNone(manager.poll())
        self.assertTrue((manager.owner_dir/'STOP').exists())
        self.assertIs(manager.process, process)
        self.assertFalse((manager.run_dir/'HOST_CLOSURE.json').exists())
        process.returncode = 1
        self.assertIn('deadline', manager.poll()['output_error'])

    def test_nested_live_source_blocks_reuse_until_exact_owner_closed(self):
        process = FakeOwnedProcess()
        manager = self.manager(lambda *args, **kwargs: process)
        manager.start(RuntimeSelection(), SessionPolicy())
        manager.owner_dir.mkdir()
        spool = manager.store.begin(dict(duration_seconds=1))
        session_id = spool.session_id
        spool.cancel()
        (manager.owner_dir/'SESSION.json').write_text(json.dumps(dict(session_id=session_id)))
        source = spool.directory/'work'/'source'; source.mkdir(parents=True)
        identity = dict(pid=4321, start_ticks=789, boot_id='fixture-boot')
        (source/'REGISTERED_OWNER.json').write_text(json.dumps(dict(owner=identity)))
        (source/'SOURCE_CLOSE.json').write_text(json.dumps(dict(owner=identity, stream_closed=True, lease_released=True)))
        manager.owner_probe = mock.Mock(return_value=dict(closed=False, state='ALIVE'))
        process.returncode = 1
        self.assertIsNone(manager.poll())
        self.assertFalse((manager.run_dir/'HOST_CLOSURE.json').exists())
        with self.assertRaises(RuntimeError):
            manager.start(RuntimeSelection(), SessionPolicy())
        manager.owner_probe.assert_called_with(identity)
        manager.owner_probe.return_value = dict(closed=True, state='ABSENT')
        closure = manager.poll()
        self.assertTrue(closure['nested_source']['closed'])

    def test_exact_linux_owner_absence_reuse_and_historical_boot(self):
        proc = self.base/'proc'
        boot = proc/'sys/kernel/random/boot_id'; boot.parent.mkdir(parents=True)
        boot.write_text('current-boot')
        directory = proc/'22'; directory.mkdir()
        def write_stat(ticks, state='S'):
            fields = [state]+['0']*18+[str(ticks)]+['0']*3
            (directory/'stat').write_text('22 (owned fixture) '+' '.join(fields))
        identity = dict(pid=22, start_ticks=10, boot_id='current-boot')
        write_stat(10)
        self.assertFalse(owner_status(identity, proc)['closed'])
        write_stat(11)
        self.assertEqual(owner_status(identity, proc)['state'], 'PID_REUSED')
        old = dict(identity, boot_id='previous-boot')
        self.assertEqual(owner_status(old, proc)['state'], 'HISTORICAL_DIFFERENT_BOOT')
        (directory/'stat').unlink()
        self.assertEqual(owner_status(identity, proc)['state'], 'ABSENT')
        boot.unlink()
        self.assertFalse(owner_status(identity, proc)['closed'])

    def test_owned_unit_watchdog_refuses_changed_invocation(self):
        receipt = self.base/'UNIT_OWNERSHIP.json'
        unit = 'jp-v29-'+'a'*32+'.service'
        receipt.write_text(json.dumps(dict(unit=unit, invocation_id='first', control_group='/owned/unit',
            main_pid=123, owner=dict(pid=123, start_ticks=456, boot_id='fixture'))))
        runner = mock.Mock(return_value=type('Result', (), dict(stdout='InvocationID=changed\nControlGroup=/owned/unit\nMainPID=123\nActiveState=active\n'))())
        with mock.patch('runtime_support.owner_status', return_value=dict(closed=False, state='ALIVE')):
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                kill_owned_unit(unit, receipt, runner=runner)
        self.assertEqual(runner.call_count, 1)
        self.assertIn('show', runner.call_args[0][0])

    def test_manager_watchdog_requests_only_bound_unit_without_claiming_exit(self):
        process = FakeOwnedProcess()
        manager = self.manager(lambda *args, **kwargs: process)
        manager.unit_ownership = self.base/'synthetic-unit.json'
        manager.unit_killer = mock.Mock(return_value=dict(requested=True))
        manager.start(RuntimeSelection(), SessionPolicy())
        manager.started -= SessionPolicy().total_deadline_seconds+1
        self.assertIsNone(manager.poll())
        manager.unit_killer.assert_called_once_with(manager.unit, manager.unit_ownership)
        self.assertFalse(strict((manager.run_dir/'WATCHDOG_REQUEST.json').read_bytes())['closure_claimed'])
        self.assertIs(manager.process, process)
        process.returncode = 1

    def test_headless_saved_or_live_run_stop_and_keep(self):
        process = FakeOwnedProcess()
        manager = self.manager(lambda *args, **kwargs: process)
        original_start = manager.start
        def start(selection, policy, saved_path=None, **kwargs):
            original_start(selection, policy, saved_path, **kwargs)
            manager.owner_dir.mkdir()
            spool = manager.store.begin(dict(duration_seconds=1))
            spool.append_processed(0, struct.pack('<f', .25)); spool.stop(1)
            (manager.owner_dir/'SESSION.json').write_text(json.dumps(dict(session_id=spool.session_id)))
            (manager.owner_dir/'RESULT.json').write_text(json.dumps(dict(session_id=spool.session_id, failure=None)))
            request_current_stop(manager.data_root)
            process.returncode = 0
        manager.start = start
        closure = run_headless(manager, RuntimeSelection(input_source='saved'),
            SessionPolicy(maximum_session_seconds=1), saved_path=self.base/'synthetic.wav', keep_processed=True)
        self.assertTrue(manager.closed)
        self.assertEqual(manager.store.read(closure['result']['session_id'])['status'], 'kept')

    def test_provisional_correction_is_explicitly_blocked_before_launch(self):
        factory = mock.Mock()
        manager = self.manager(factory)
        selection = RuntimeSelection('nemotron', 'anonymous', 'live', 'current_delayed', True, True)
        with self.assertRaisesRegex(RuntimeError, 'pending native admission'):
            manager.start(selection, SessionPolicy())
        factory.assert_not_called()

    def test_complete_recording_request_is_distinct_from_single_wav(self):
        process=FakeOwnedProcess()
        manager=self.manager(lambda *args,**kwargs:process)
        prior=manager.store.begin(dict(duration_seconds=1))
        prior.append_processed(0,struct.pack('<ff',.125,-.125));prior.stop(2);prior.keep()
        selection=RuntimeSelection(input_source='saved')
        with self.assertRaises(ValueError):
            manager.start(selection,SessionPolicy(),self.base/'one.wav',saved_session_id=prior.session_id)
        with self.assertRaises(ValueError):
            manager.start(selection,SessionPolicy(),saved_session_id=prior.session_id,saved_store_root=self.base/'unrelated')
        manager.start(selection,SessionPolicy(),saved_session_id=prior.session_id)
        self.assertIsNone(manager.request['saved_path'])
        self.assertEqual(manager.request['saved_session_id'],prior.session_id)
        self.assertEqual(manager.request['saved_store_root'],str(manager.store.root))

    def test_history_file_limit_is_derived_and_retains_free_floor(self):
        root = self.base/'size-plan'; root.mkdir()
        (root/'history.sqlite3').write_bytes(bytes(1234))
        policy = StoragePolicy(reserve_bytes=5000, reserve_fraction=0)
        usage = type('Usage', (), dict(total=2*1024**3, free=1024**3))()
        plan = file_size_plan(root, 64*1024**2, policy, usage)
        self.assertEqual(plan['existing_history_bytes'], 1234)
        self.assertGreater(plan['file_limit_bytes'], 32*1024**2)
        self.assertLess(plan['file_limit_bytes'], usage.free-policy.reserve_bytes)
        usage.free = 5000
        with self.assertRaises(OSError):
            file_size_plan(root, 64*1024**2, policy, usage)

    def test_caption_tail_beyond_100_and_stable_id_revision(self):
        store = SessionStore(self.base/'captions', StoragePolicy(reserve_bytes=0, reserve_fraction=0))
        spool = store.begin(dict(duration_seconds=1))
        for index in range(125):
            store.write_caption(spool.session_id, str(index), index, index+1,
                                'caption '+str(index), 'A', True, {})
        view = CaptionView(store, limit=40)
        self.assertTrue(view.refresh(spool.session_id))
        self.assertEqual((view.rows[0]['caption_id'], view.rows[-1]['caption_id']), ('85', '124'))
        self.assertFalse(view.refresh(spool.session_id))
        store.write_caption(spool.session_id, '124', 124, 125, 'corrected', 'B', False, {})
        self.assertTrue(view.refresh(spool.session_id))
        self.assertEqual(len(view.rows), 40)
        self.assertEqual((view.rows[-1]['text'], view.rows[-1]['revision']), ('corrected', 2))
        self.assertFalse(view.rows[-1]['provisional'])
        spool.cancel()

    def test_authorization_and_unit_time_gate_before_worker_creation(self):
        factory = mock.Mock()
        manager = self.manager(factory)
        manager.session_authorizer = mock.Mock(side_effect=PermissionError('not admitted'))
        with self.assertRaises(PermissionError):
            manager.start(RuntimeSelection(), SessionPolicy())
        factory.assert_not_called()
        self.assertFalse((manager.data_root/'CURRENT_LAUNCH.json').exists())
        manager.session_authorizer = mock.Mock(return_value={'synthetic': True})
        manager.unit_ownership = self.base/'synthetic-owned-unit.json'
        manager.service_room_check = mock.Mock(side_effect=TimeoutError('insufficient unit lifetime'))
        with self.assertRaises(TimeoutError):
            manager.start(RuntimeSelection(), SessionPolicy())
        manager.service_room_check.assert_called_once()
        factory.assert_not_called()

    def test_process_memory_details_cache_and_unavailable_metrics(self):
        readings = []
        def read(path, *args, **kwargs):
            readings.append(str(path).replace('\\', '/'))
            if readings[-1].endswith('/status'):
                return 'VmSize:\t100 kB\nVmPeak:\t120 kB\nVmSwap:\t3 kB\n'
            return 'Pss:\t40 kB\nSwapPss:\t2 kB\n'
        initial = dict(sampled=-float('inf'), pid=None, values={})
        with mock.patch.object(runtime_support, '_memory_details', initial), mock.patch.object(Path, 'read_text', read):
            first = runtime_support._extended_memory(10)
            cached = runtime_support._extended_memory(10.9)
            self.assertEqual(len(readings), 2)
            self.assertEqual(first['virtual_bytes'], 100*1024)
            self.assertEqual(first['peak_virtual_bytes'], 120*1024)
            self.assertEqual(first['swap_bytes'], 3*1024)
            self.assertEqual(first['pss_bytes'], 40*1024)
            self.assertAlmostEqual(cached['pss_sample_age_seconds'], .9)
            self.assertEqual(cached['pss_sampled_monotonic_sec'], 10)
            runtime_support._extended_memory(11.01)
            self.assertEqual(len(readings), 4)
        with mock.patch.object(runtime_support, '_memory_details', dict(sampled=-float('inf'), pid=None, values={})), mock.patch.object(Path, 'read_text', side_effect=PermissionError):
            missing = runtime_support._extended_memory(12)
            self.assertIsNone(missing['pss_bytes'])
            self.assertIsNone(missing['pss_sample_age_seconds'])
            self.assertIsNone(missing['swap_bytes'])
        snapshot = runtime_support.resource_snapshot()
        self.assertEqual(snapshot['scope'], 'current_process')
        self.assertFalse(snapshot['whole_unit_aggregate'])
        self.assertEqual(snapshot['pid'], os.getpid())

    def synthetic_session(self, spool, failure=None):
        class Session:
            def __init__(self):
                self.work = spool.directory/'work'
                self.work.mkdir()
                self.stop_event = threading.Event()
                self.closed = False
            def run(self):
                spool.append_processed(0, struct.pack('<ff', .1, -.1))
                (self.work/'native.json').write_text('{"synthetic":true}')
                if failure == 'run':
                    raise RuntimeError('synthetic run fault')
                return {'synthetic': True}
            def fail(self, reason):
                self.stop_event.set()
            def close(self):
                self.closed = True
                if failure == 'close':
                    raise RuntimeError('synthetic close fault')
        return Session()

    def test_worker_success_and_cleanup_faults_publish_owned_results(self):
        for failure in (None, 'run', 'close', 'register'):
            with self.subTest(failure=failure):
                store = SessionStore(self.base/('worker-'+str(failure)), StoragePolicy(reserve_bytes=0, reserve_fraction=0))
                spool = store.begin(dict(duration_seconds=1))
                owner = self.base/('owner-'+str(failure)); owner.mkdir()
                session = self.synthetic_session(spool, failure)
                patch = mock.patch.object(store, 'register_artifact', side_effect=OSError('synthetic register fault')) if failure == 'register' else context_noop()
                with patch:
                    code = run_owned_session(store, spool, session, owner)
                result = strict((owner/'RESULT.json').read_bytes())
                self.assertEqual(code, 0 if failure is None else 1)
                self.assertEqual(result['post_stop_choice_pending'], failure is None)
                self.assertFalse(result['physical_process_closed'])
                self.assertTrue(session.closed)
                self.assertTrue(spool.closed)
                self.assertEqual(store.read(spool.session_id)['status'], 'stopped' if failure is None else 'failed')
                store.begin(dict(duration_seconds=1)).cancel()

    def test_segmented_output_boundaries_and_shared_disk_budget(self):
        first = SegmentedText(self.base/'first', maximum_bytes=100, reserve_bytes=0, segment_bytes=5)
        first.write('abc'); first.write('de'); first.write('fgh')
        first.close()
        index = strict((self.base/'first.index.json').read_bytes())
        self.assertTrue(index['complete'])
        self.assertEqual(index['segment_count'], 2)
        self.assertEqual((self.base/'first.000000').read_bytes(), b'abcde')
        self.assertEqual((self.base/'first.000001').read_bytes(), b'fgh')
        self.assertNotIn('segments', index)
        budget = DiskBudget(10, reserve_bytes=0)
        left = SegmentedText(self.base/'left', maximum_bytes=20, budget=budget)
        right = SegmentedText(self.base/'right', maximum_bytes=20, budget=budget)
        left.write('123456')
        with self.assertRaises(BufferError):
            right.write('12345')
        left.close()
        with self.assertRaises(RuntimeError):
            right.close()
        self.assertEqual(budget.accepted, 6)

    def test_queue_fault_drains_previously_accepted_text(self):
        entered, release = threading.Event(), threading.Event()
        faults = []
        budget = DiskBudget(100, reserve_bytes=0)
        original = budget.check_free
        def blocked(path, count):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('fixture release')
            original(path, count)
        with mock.patch.object(budget, 'check_free', side_effect=blocked):
            writer = SegmentedText(self.base/'queue', maximum_bytes=100, queue_bytes=3,
                                   segment_bytes=10, budget=budget, fail=faults.append)
            writer.write('abc')
            self.assertTrue(entered.wait(2))
            with self.assertRaises(BufferError):
                writer.write('x')
            release.set()
            with self.assertRaises(RuntimeError):
                writer.close()
        index = strict((self.base/'queue.index.json').read_bytes())
        self.assertEqual((index['accepted_bytes'], index['completed_bytes']), (3, 3))
        self.assertFalse(index['complete'])
        self.assertEqual((self.base/'queue.000000').read_bytes(), b'abc')
        self.assertTrue(faults)

    def test_final_fsync_fault_cannot_publish_complete(self):
        faults = []
        writer = SegmentedText(self.base/'flush', maximum_bytes=100, reserve_bytes=0, fail=faults.append)
        writer.write('data')
        original = os.fsync
        first = True
        def fail_once(fd):
            nonlocal first
            if first:
                first = False
                raise OSError('synthetic final fsync failure')
            return original(fd)
        with mock.patch('runtime_support.os.fsync', side_effect=fail_once):
            with self.assertRaises(RuntimeError):
                writer.close()
        index = strict((self.base/'flush.index.json').read_bytes())
        self.assertFalse(index['complete'])
        self.assertIn('fsync', index['error'])
        self.assertTrue(faults)


class context_noop:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


if __name__ == '__main__':
    unittest.main()
