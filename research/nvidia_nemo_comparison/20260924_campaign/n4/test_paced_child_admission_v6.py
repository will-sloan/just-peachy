"""Pure and live-refusal child gate tests. Use the guarded probe entry point."""
from copy import deepcopy
from pathlib import Path
import os
import time
import tempfile
import unittest

import psutil
from common import bind, freeze
from metric_process import identity
from paced_child_admission_v6 import (ChildAdmission, EXECUTION_POLICY, INPUT_FIELDS, LEASE_SCHEMA, SCHEMA,
    assert_plain_path, bounded_json, validate_input, validate_lease, validate_permit, write_lease, replace_lease_file, shared_reader)


def fixture_permit():
    return dict(schema=SCHEMA, status='ADMITTED_SINGLE_APPLICATION_CHILD', nonce='a'*64,
        coordinator=dict(pid=20, create_time=100.), application=dict(pid=30, create_time=101.),
        supervisor=dict(pid=10, create_time=99.), supervised_run='synthetic-test-not-production',
        coordinator_argv_sha256='b'*64, application_argv_sha256='c'*64, desktop='codex-n1-n4-'+'d'*32,
        plan_sha256='e'*64, input={}, output='unused', state='unused', code=[{}])


def fixture_input():
    return dict(schema='n4-paced-cell-input-v1', cell_id='fixture_only',
        job=dict(job_id='fixture', audio_path='not-opened.wav', audio_sha256='0'*64, frames=16000,
            sample_rate_hz=16000, gain=1, reset_between_scenes=True, tap='O0'),
        contract=dict(mode='open_with_names'), execution=deepcopy(EXECUTION_POLICY), source_receipt={}, catalog={},
        runtimes=[dict(path='n2_runtime.json'),dict(path='n3_runtime.json')], gallery_preparation={},
        models_root='NO_MODEL_PAYLOAD', assets=[{}], source_execution_authorized=False, remaining_gate='Fixture only')


def fixture_lease(permit):
    return dict(schema=LEASE_SCHEMA, status='ADMITTED', nonce=permit['nonce'], permit_sha256='f'*64,
        coordinator=permit['coordinator'], application=permit['application'], supervised_run=permit['supervised_run'],
        sequence=3, issued_monotonic=100.)


class ChildAdmissionTests(unittest.TestCase):
    def test_atomic_initial_publish_and_missing_source_preserve_target(self):
        with tempfile.TemporaryDirectory() as folder:
            pending=Path(folder)/'LEASE.pending'; target=Path(folder)/'LEASE.json'
            pending.write_bytes(b'{"sequence":0}');replace_lease_file(pending,target)
            self.assertEqual(bounded_json(target,4096),{'sequence':0});self.assertFalse(pending.exists())
            with self.assertRaises(OSError):replace_lease_file(pending,target)
            self.assertEqual(bounded_json(target,4096),{'sequence':0})

    def test_atomic_refuses_different_directory_and_identical_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);pending=root/'LEASE.pending';pending.write_bytes(b'preserve')
            other=root/'other';other.mkdir()
            for target in (pending,other/'LEASE.json'):
                with self.assertRaisesRegex(ValueError,'same directory'):replace_lease_file(pending,target)
                self.assertEqual(pending.read_bytes(),b'preserve')

    def test_atomic_respects_readonly_target_without_attribute_override(self):
        import ctypes as C
        from ctypes import wintypes as W
        self.assertEqual(os.name,'nt')
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.SetFileAttributesW.argtypes=[W.LPCWSTR,W.DWORD];kernel.SetFileAttributesW.restype=W.BOOL
        with tempfile.TemporaryDirectory() as folder:
            pending=Path(folder)/'LEASE.pending';target=Path(folder)/'LEASE.json'
            pending.write_bytes(b'new');target.write_bytes(b'old')
            self.assertTrue(kernel.SetFileAttributesW(str(target),1))
            try:
                with self.assertRaises(PermissionError):replace_lease_file(pending,target)
                self.assertEqual(target.read_bytes(),b'old');self.assertEqual(pending.read_bytes(),b'new')
            finally:self.assertTrue(kernel.SetFileAttributesW(str(target),0x80))

    def test_ordinary_windows_reader_blocks_for_entire_bounded_retry(self):
        self.assertEqual(os.name, 'nt')
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'LEASE.json'; pending = Path(folder)/'LEASE.pending'
            target.write_bytes(b'{"sequence":1}'); pending.write_bytes(b'{"sequence":2}')
            with target.open('rb') as reader:
                with self.assertRaises(PermissionError): replace_lease_file(pending, target)
                self.assertEqual(reader.read(), b'{"sequence":1}')
            self.assertEqual(bounded_json(target,4096), {'sequence':1})
            self.assertEqual(bounded_json(pending,4096), {'sequence':2})

    def test_shared_windows_reader_survives_repeated_atomic_replacement(self):
        self.assertEqual(os.name, 'nt')
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'LEASE.json'; pending = Path(folder)/'LEASE.pending'
            target.write_bytes(b'{"sequence":0}')
            with shared_reader(target) as original:
                for sequence in range(1,101):
                    with shared_reader(target) as previous:
                        pending.write_text('{"sequence":'+str(sequence)+'}', encoding='utf-8')
                        replace_lease_file(pending,target)
                        self.assertEqual(previous.read(), ('{"sequence":'+str(sequence-1)+'}').encode())
                        self.assertEqual(bounded_json(target,4096), {'sequence':sequence})
                self.assertEqual(original.read(), b'{"sequence":0}')

    def test_shared_reader_conversion_failures_close_owned_handle(self):
        import msvcrt
        from unittest.mock import patch
        import paced_child_admission_v6 as gate
        self.assertEqual(os.name, 'nt')
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'record.json'; target.write_bytes(b'{}')
            # Windows cannot reopen exclusively if a conversion failure leaks a handle.
            import ctypes as C
            from ctypes import wintypes as W
            kernel=C.WinDLL('kernel32',use_last_error=True)
            kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE]
            kernel.CreateFileW.restype=W.HANDLE;kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
            for module, name in ((msvcrt,'open_osfhandle'),(gate.os,'fdopen')):
                with patch.object(module,name,side_effect=OSError('conversion fixture')):
                    with self.assertRaisesRegex(OSError,'conversion fixture'):shared_reader(target)
                handle=kernel.CreateFileW(str(target),0x80000000,0,None,3,0x80,None)
                self.assertNotEqual(handle,C.c_void_p(-1).value)
                self.assertTrue(kernel.CloseHandle(handle))

    def test_shared_json_errors_preserve_bounds_and_close_stream(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'record.json'; pending=Path(folder)/'replacement.json'
            for data,maximum in ((b'{broken}',4096),(b'{"too_big":true}',2),(b'\xff',4096)):
                target.write_bytes(data)
                with self.assertRaises(ValueError):bounded_json(target,maximum)
                pending.write_bytes(b'{}'); replace_lease_file(pending,target)
                self.assertEqual(bounded_json(target,4096),{})
            with self.assertRaises(OSError):bounded_json(Path(folder)/'missing.json',4096)
            self.assertFalse((Path(folder)/'missing.json').exists())

    def permit_check(self, value):
        baseline=fixture_permit()
        return validate_permit(value, nonce=baseline['nonce'], application=baseline['application'],
            parent=baseline['coordinator'], desktop=baseline['desktop'])

    def lease_check(self, value, *, now=102., previous=2):
        return validate_lease(value, fixture_permit(), 'f'*64, now_monotonic=now, previous_sequence=previous)

    def test_input_truth_and_policy_firewall(self):
        self.assertEqual(set(fixture_input()), INPUT_FIELDS); validate_input(fixture_input())
        for field in ('truth', 'transcript', 'selection', 'report', 'speaker_positions'):
            value=fixture_input(); value[field]={}
            with self.assertRaises(ValueError): validate_input(value)
        for change in ('execution','source_execution_authorized','gain','mode','assets'):
            value=fixture_input()
            if change=='execution': value['execution']['cells_concurrent']=2
            elif change=='gain': value['job']['gain']=1.4125
            elif change=='mode': value['contract']['mode']='selected_closed'
            elif change=='assets': value['assets']=[]
            else:value[change]=True
            with self.assertRaises(ValueError): validate_input(value)

    def test_permit_exact_identity_and_desktop(self):
        self.permit_check(fixture_permit())
        for change in ('application','coordinator','desktop','nonce','role_alias'):
            value=fixture_permit()
            if change in ('application','coordinator'):value[change]['create_time']+=.001
            elif change=='desktop':value['desktop']='Default'
            elif change=='nonce':value['nonce']='9'*64
            else:value['supervisor']=deepcopy(value['coordinator'])
            with self.assertRaises(ValueError):self.permit_check(value)

    def test_permit_bounds_and_digests(self):
        for change in ('code','digest','extra','nan'):
            value=fixture_permit()
            if change=='code':value['code']=[{}]*513
            elif change=='digest':value['plan_sha256']='bad'
            elif change=='extra':value['truth']=True
            else:value['supervisor']['create_time']=float('nan')
            with self.assertRaises(ValueError):self.permit_check(value)

    def test_lease_monotonic_expiry_and_future(self):
        value=fixture_lease(fixture_permit())
        self.assertEqual(self.lease_check(value,now=105.),3)
        for now in (105.001,99.,float('nan')):
            with self.assertRaises(ValueError):self.lease_check(value,now=now)
        for issued in (float('inf'),float('nan'),True):
            changed=deepcopy(value);changed['issued_monotonic']=issued
            with self.assertRaises(ValueError):self.lease_check(changed)

    def test_lease_owner_nonce_run_and_rollback(self):
        value=fixture_lease(fixture_permit()); self.assertEqual(self.lease_check(value,previous=3),3)
        with self.assertRaises(ValueError):self.lease_check(value,previous=4)
        for field,new in [('nonce','0'*64),('status','REVOKED'),('supervised_run','other'),('permit_sha256','0'*64),
                          ('coordinator',dict(pid=20,create_time=999.)),('application',dict(pid=30,create_time=999.)),('sequence',True)]:
            changed=deepcopy(value);changed[field]=new
            with self.assertRaises(ValueError):self.lease_check(changed)

    def test_record_read_bounds(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'record.json';path.write_text('{"okay":true}',encoding='utf-8')
            self.assertEqual(bounded_json(path,100),{'okay':True})
            with self.assertRaises(ValueError):bounded_json(path,2)

    def test_output_containment(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.assertEqual(assert_plain_path(root/'fresh/application',root),(root/'fresh/application').resolve())
            with self.assertRaises(ValueError):assert_plain_path(root.parent/'outside',root)

    def test_actual_helper_refused_before_source_or_input_reads(self):
        process=psutil.Process();self.assertEqual(process.cpu_affinity(),[14])
        with tempfile.TemporaryDirectory() as temp:
            value=fixture_permit();value['application']=identity(process);value['coordinator']=identity(process.parent())
            value['supervisor']=dict(pid=2147483647,create_time=1.)
            path=Path(temp)/'PERMIT.json';freeze(path,value)
            with self.assertRaisesRegex(ValueError,'already be pinned to CPU4'):
                ChildAdmission(path,nonce=value['nonce'],desktop=value['desktop'],expected_code=[])
            self.assertEqual({p.name for p in Path(temp).iterdir()},{'PERMIT.json'})

    def test_foreign_helper_cannot_renew(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'LEASE.json'
            with self.assertRaisesRegex(ValueError,'Only exact CPU14 coordinator'):
                write_lease(path,fixture_permit(),'f'*64,0)
            self.assertFalse(path.exists())

    def test_replace_succeeds_without_retry(self):
        calls=[]
        replace_lease_file('pending','target',replace=lambda a,b:calls.append((a,b)),sleep=lambda _:self.fail('Unexpected retry'))
        self.assertEqual(calls,[('pending','target')])

    def test_transient_errors_retry_same_complete_file_without_reissuing(self):
        from unittest.mock import patch
        import paced_child_admission_v6 as gate
        for number in (5,32,33):
            calls=[]; sleeps=[]; error=PermissionError('sharing'); error.winerror=number
            def replacement(a,b):
                calls.append((a,b))
                if len(calls)<3: raise error
            with patch.object(gate.os,'name','nt'):
                replace_lease_file('pending','target',replace=replacement,clock=lambda:10.,sleep=sleeps.append)
            self.assertEqual(calls,[('pending','target')]*3);self.assertEqual(sleeps,[.02,.02])

    def test_unrelated_replace_errors_fail_immediately(self):
        for error in (PermissionError('no Windows sharing code'), FileNotFoundError('missing'), OSError('disk failure')):
            calls=[]
            def replacement(a,b):calls.append(1);raise error
            with self.assertRaises(type(error)):
                replace_lease_file('pending','target',replace=replacement,sleep=lambda _:self.fail('Wrong retry'))
            self.assertEqual(calls,[1])

    def test_replace_deadline_preserves_pending_and_old_lease(self):
        with tempfile.TemporaryDirectory() as folder:
            pending=Path(folder)/'LEASE.pending'; target=Path(folder)/'LEASE.json'
            pending.write_bytes(b'complete replacement');target.write_bytes(b'previous lease')
            ticks=iter((10.,10.26)); error=PermissionError('sharing');error.winerror=32
            def replacement(a,b):raise error
            with self.assertRaises(PermissionError):
                replace_lease_file(pending,target,replace=replacement,clock=lambda:next(ticks),sleep=lambda _:self.fail('Expired retry'))
            self.assertEqual(pending.read_bytes(),b'complete replacement');self.assertEqual(target.read_bytes(),b'previous lease')

    def test_replace_attempt_cap_even_if_clock_stalls(self):
        calls=[];sleeps=[];error=PermissionError('sharing');error.winerror=5
        def replacement(a,b):calls.append(1);raise error
        with self.assertRaises(PermissionError):
            replace_lease_file('pending','target',replace=replacement,clock=lambda:10.,sleep=sleeps.append)
        self.assertEqual(len(calls),13);self.assertEqual(sleeps,[.02]*12)

    def test_actual_windows_reader_sharing_race_then_atomic_renewal(self):
        import ctypes as C
        from ctypes import wintypes as W
        import threading
        self.assertEqual(os.name,'nt','This qualification must reproduce Windows replacement sharing')
        kernel=C.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE]
        kernel.CreateFileW.restype=W.HANDLE;kernel.CloseHandle.argtypes=[W.HANDLE];kernel.CloseHandle.restype=W.BOOL
        with tempfile.TemporaryDirectory() as folder:
            pending=Path(folder)/'LEASE.pending';target=Path(folder)/'LEASE.json'
            pending.write_bytes(b'complete replacement');target.write_bytes(b'previous lease')
            # Explicitly deny delete sharing, just as a brief ordinary reader can.
            handle=kernel.CreateFileW(str(target),0x80000000,3,None,3,0x80,None)
            self.assertNotEqual(handle,C.c_void_p(-1).value)
            released=threading.Event();lock=threading.Lock();failures=[]
            def release():
                with lock:
                    if not released.is_set():kernel.CloseHandle(handle);released.set()
            timer=threading.Timer(.06,release)
            def replacement(a,b):
                try:os.replace(a,b)
                except PermissionError as error:failures.append(error.winerror);raise
            try:
                with self.assertRaises(PermissionError):os.replace(pending,target)
                timer.start();replace_lease_file(pending,target,replace=replacement)
                self.assertTrue(failures);self.assertTrue(all(n in (5,32,33) for n in failures))
                self.assertEqual(target.read_bytes(),b'complete replacement');self.assertFalse(pending.exists())
            finally:release();timer.join(timeout=1) if timer.ident is not None else None
