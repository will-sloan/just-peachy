"""Host-only frame/closure mirror checks. See README_JOB_MONITOR.md."""
import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
import uuid


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-root',required=True)
    ap.add_argument('--checks',nargs='+')
    args=ap.parse_args()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess();kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    values=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in values)):raise ctypes.WinError(ctypes.get_last_error())
    root=Path(args.output_root)/('job-monitor-checks-'+uuid.uuid4().hex);root.mkdir()
    with (root/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
            affinity_mask=16384,creation_filetime=values[0].value,
            create_time=(values[0].value-116444736000000000)/10000000),stream)
        stream.flush();os.fsync(stream.fileno())
    sys.dont_write_bytecode=True
    import monitor_native_job as monitor
    compile(Path(__file__).with_name('native_job_probe.py').read_bytes(),'<native-probe-not-executed>','exec')

    class Checks(unittest.TestCase):
        def test_optional_followup_exact_derived_plan_and_no_generic_widening(self):
            import native_job_probe as probe
            for mode,audio,complete,maximum in (
                    ('raw_processed',202684712,330610984,330610984),
                    ('processed',125638952,253565224,256*1024**2)):
                plan=dict(schema='just-peachy.optional-output-plan.v1',stage='followup_policy',
                    source_kind='live',session_seconds=300,mode=mode,audio_and_metadata_bytes=audio,
                    additional_primary_allocation_bytes=106954752,optional_output_bytes=4*1024**2,
                    outer_unit_trace_bytes=16*1024**2,computed_output_bytes=complete,
                    native_maximum_output_bytes=maximum,maximum_files=256)
                job=dict(schema='just-peachy.native-component-job.v1',unit='jp-v29-optional-followup-01.service',
                    output_root=probe.ROOT+'optional-followup-01',boot_id='a'*36,invocation_id='b'*32,
                    maximum_output_bytes=maximum,maximum_output_files=256,independent_pc_copy_bytes=maximum,
                    workflow='optional-followup-live-policy',duration_seconds=300,runtime_seconds=840,
                    issued_unix=1,deadline_unix=886,package_manifest_sha256='c'*64,output_plan=plan)
                self.assertEqual(monitor.job_limits(job),(512*1024**2,256))
                self.assertEqual(probe.job_limits(job),monitor.job_limits(job));monitor.validate_job(job)
                for changes in (dict(workflow=None),dict(runtime_seconds=841),dict(duration_seconds=299),
                        dict(independent_pc_copy_bytes=maximum-1),dict(deadline_unix=887),
                        dict(output_plan=dict(plan,computed_output_bytes=complete-1)),
                        dict(output_plan=dict(plan,extra_field=True)),dict(maximum_output_files=257)):
                    for checker in (monitor.job_limits,probe.job_limits):
                        with self.assertRaises(ValueError):checker(dict(job,**changes))
            other=dict(job,output_root=probe.ROOT+'optional-first-01',unit='jp-v29-optional-first-01.service',
                maximum_output_bytes=330610984)
            with self.assertRaises(ValueError):monitor.validate_job(other)

        def test_sampled_memory_exact_members_and_reused_owner_exclusion(self):
            from unittest.mock import patch
            import native_job_probe as probe
            owner=dict(pid=123,start_ticks=456,boot_id='fixture')
            status=dict(control_group='/user.slice/fixture.service',owner=owner,closed=False,
                unit='fixture.service',invocation_id='abc')
            def read(path,maximum=16384):
                name=str(path).replace('\\','/')
                if name.endswith('/cgroup'):return '0::/user.slice/fixture.service\n'
                if name.endswith('/status'):return 'VmSize: 300 kB\nVmPeak: 350 kB\nVmSwap: 0 kB\n'
                if name.endswith('/smaps_rollup'):return 'Rss: 100 kB\nPss: 90 kB\n'
                if name.endswith('/meminfo'):return 'MemAvailable: 1000 kB\nMemTotal: 2000 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n'
                if name.endswith('/temp'):return '61000\n'
                raise AssertionError(name)
            with patch.object(probe,'memory_members',return_value={123}),patch.object(probe,'identity',return_value=owner),patch.object(probe,'bounded_text',side_effect=read):
                row=probe.sample_memory(status)
            self.assertTrue(row['complete_process_sample']);self.assertFalse(row['continuous_peak_claimed'])
            self.assertEqual((row['rss_bytes'],row['pss_bytes'],row['available_bytes']),(102400,92160,1024000))
            self.assertEqual(row['processes'][0]['owner'],owner)
            with patch.object(probe,'memory_members',return_value={123}),patch.object(probe,'identity',side_effect=[owner,owner,dict(owner,start_ticks=999),owner]),patch.object(probe,'bounded_text',side_effect=read):
                row=probe.sample_memory(status)
            self.assertFalse(row['complete_process_sample']);self.assertEqual(row['processes'],[])

        def receiver(self,name):
            receiver=monitor.Receiver(root/name,65536,mirror=True)
            receiver.feed(dict(kind='OWNER',owner=dict(pid=123,start_ticks=456,boot_id='fixture')))
            receiver.feed(dict(kind='STATUS',closed=True))
            return receiver

        def test_complete_multichunk_source_pc_readback(self):
            receiver=self.receiver('valid');raw=b'abc\x00'*9000
            row=dict(path='benchmark/probabilities.f32',identity=dict(bytes=len(raw),device=1,inode=2,
                mtime_ns=3,ctime_ns=4),sha256=hashlib.sha256(raw).hexdigest())
            receiver.feed(dict(kind='MANIFEST',files=1,bytes=len(raw)))
            receiver.feed(dict(kind='MANIFEST_ENTRY',**row));receiver.feed(dict(kind='FILE',path=row['path']))
            for offset in range(0,len(raw),16384):
                receiver.feed(dict(kind='CHUNK',path=row['path'],offset=offset,data=base64.b64encode(raw[offset:offset+16384]).decode()))
            receiver.feed(dict(kind='FILE_END',path=row['path'],bytes=len(raw),sha256=row['sha256']))
            receiver.feed(dict(kind='COMPLETE',files=1,bytes=len(raw),closure=dict(closed=True),
                manifest_sha256=hashlib.sha256(monitor.encoded([row])).hexdigest()))
            self.assertEqual((root/'valid'/row['path']).read_bytes(),raw)
            self.assertIsNotNone(receiver.complete)

        def test_traversal_rejected(self):
            receiver=self.receiver('unsafe');receiver.feed(dict(kind='MANIFEST',files=1,bytes=1))
            with self.assertRaises(ValueError):
                receiver.feed(dict(kind='MANIFEST_ENTRY',path='../escape',identity=dict(bytes=1),sha256='0'*64))

        def test_source_cursor_and_hash_failure_never_certify(self):
            receiver=self.receiver('bad');receiver.feed(dict(kind='MANIFEST',files=1,bytes=1))
            row=dict(path='data.bin',identity=dict(bytes=1),sha256=hashlib.sha256(b'x').hexdigest())
            receiver.feed(dict(kind='MANIFEST_ENTRY',**row));receiver.feed(dict(kind='FILE',path='data.bin'))
            with self.assertRaises(ValueError):
                receiver.feed(dict(kind='CHUNK',path='data.bin',offset=1,data='eA=='))
            receiver.feed(dict(kind='CHUNK',path='data.bin',offset=0,data='eQ=='))
            with self.assertRaises(ValueError):
                receiver.feed(dict(kind='FILE_END',path='data.bin',bytes=1,sha256=row['sha256']))
            self.assertIsNone(receiver.complete);receiver.close()

        def test_segmented_copy_preserves_exact_prefix_and_hash(self):
            data=b'old-and-new-offset\x00'*5000
            entry=dict(path='nested/probabilities.f32',identity=dict(bytes=len(data)),
                sha256=hashlib.sha256(data).hexdigest())
            destination=root/'segments'
            for start in range(0,len(data),65536):
                raw=data[start:start+65536]
                receiver=monitor.SegmentReceiver(destination,256*1024**2,entry,start,len(raw))
                receiver.feed(dict(kind='OWNER',owner=dict(pid=123,start_ticks=456,boot_id='fixture')))
                receiver.feed(dict(kind='STATUS',closed=True))
                receiver.feed(dict(kind='SEGMENT',entry=entry,offset=start,count=len(raw)))
                for offset in range(0,len(raw),16384):
                    receiver.feed(dict(kind='CHUNK',path=entry['path'],offset=start+offset,
                        data=base64.b64encode(raw[offset:offset+16384]).decode()))
                receiver.feed(dict(kind='SEGMENT_END',path=entry['path'],offset=start,bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),closure=dict(closed=True)))
                self.assertIsNotNone(receiver.segment_complete)
            self.assertEqual((destination/entry['path']).read_bytes(),data)
            broken=monitor.SegmentReceiver(destination,256*1024**2,entry,1,1)
            broken.feed(dict(kind='OWNER',owner=dict(pid=123,start_ticks=456,boot_id='fixture')))
            broken.feed(dict(kind='STATUS',closed=True))
            with self.assertRaises(ValueError):broken.feed(dict(kind='SEGMENT',entry=entry,offset=1,count=1))
            self.assertIsNone(broken.segment_complete)

        def test_large_reservation_is_explicit_and_capped(self):
            job=dict(schema='just-peachy.native-component-job.v1',unit='jp-v29-fixture.service',
                boot_id='a'*36,invocation_id='b'*32,maximum_output_bytes=256*1024**2,
                issued_unix=1,deadline_unix=3601,package_manifest_sha256='c'*64)
            monitor.validate_job(job)
            job['maximum_output_bytes']+=1
            with self.assertRaises(ValueError):monitor.validate_job(job)

        def test_catalog_bytes_and_source_digest_must_match(self):
            receiver=monitor.Receiver(root/'catalog',256*1024**2,mirror=True,catalog=True)
            receiver.feed(dict(kind='OWNER',owner=dict(pid=123,start_ticks=456,boot_id='fixture')))
            receiver.feed(dict(kind='STATUS',closed=True))
            row=dict(path='data',identity=dict(bytes=10),sha256='a'*64)
            receiver.feed(dict(kind='MANIFEST',files=1,bytes=11))
            receiver.feed(dict(kind='MANIFEST_ENTRY',**row))
            with self.assertRaises(ValueError):
                receiver.feed(dict(kind='CATALOG_END',files=1,bytes=11,
                    manifest_sha256=hashlib.sha256(monitor.encoded([row])).hexdigest(),closure=dict(closed=True)))
            self.assertIsNone(receiver.catalog_complete)

        def test_gui_cap_requires_exact_owned_workflow_and_finite_lifetime(self):
            import native_job_probe as probe
            job=dict(schema='just-peachy.native-component-job.v1',unit='jp-v29-gui-qualification-01.service',
                output_root=probe.ROOT+'gui-qualification-01',boot_id='a'*36,invocation_id='b'*32,
                maximum_output_bytes=567398992,issued_unix=1,deadline_unix=1501,package_manifest_sha256='c'*64)
            self.assertEqual(monitor.job_limits(job),(1024**3,1024))
            self.assertEqual(probe.job_limits(job),monitor.job_limits(job))
            monitor.validate_job(job)
            for changes in (dict(unit='jp-v29-raw-qualification-01.service'),
                    dict(output_root=probe.ROOT+'raw-qualification-01'),dict(deadline_unix=1547),
                    dict(maximum_output_bytes=1024**3+1)):
                with self.assertRaises(ValueError):monitor.validate_job(dict(job,**changes))
            for count,valid in ((1024,True),(1025,False)):
                receiver=monitor.Receiver(root/('gui-files-'+str(count)),1024**3,mirror=True,
                    catalog=True,maximum_files=1024)
                receiver.feed(dict(kind='OWNER',owner=dict(pid=123,start_ticks=456,boot_id='fixture')))
                receiver.feed(dict(kind='STATUS',closed=True))
                if valid:receiver.feed(dict(kind='MANIFEST',files=count,bytes=0))
                else:
                    with self.assertRaises(ValueError):receiver.feed(dict(kind='MANIFEST',files=count,bytes=0))

        def test_hour_caps_require_exact_separate_workflow(self):
            import native_job_probe as probe
            job=dict(schema='just-peachy.native-component-job.v1',unit='jp-v29-full-app-hour-01.service',
                output_root=probe.ROOT+'full-app-hour-01',boot_id='a'*36,invocation_id='b'*32,
                maximum_output_bytes=2300000000,maximum_output_files=2048,
                workflow='continuous-full-application-repeated-wav',duration_seconds=3600,repeat_input_seconds=3600,
                issued_unix=1,deadline_unix=4726,package_manifest_sha256='c'*64)
            self.assertEqual(monitor.job_limits(job),(3*1024**3,2048))
            self.assertEqual(probe.job_limits(job),monitor.job_limits(job));monitor.validate_job(job)
            for changes in (dict(workflow=None),dict(repeat_input_seconds=None),dict(maximum_output_files=2049),
                    dict(deadline_unix=4727),dict(maximum_output_bytes=3*1024**3+1),dict(unit='jp-v29-other.service')):
                with self.assertRaises(ValueError):monitor.validate_job(dict(job,**changes))

        def test_identity_catalog_only_for_hour_and_no_content_hash(self):
            import native_job_probe as probe
            from unittest.mock import patch
            folder=root/'identity-source';folder.mkdir();(folder/'x').write_bytes(b'large-placeholder')
            with patch.object(probe.hashlib,'sha256',side_effect=AssertionError('No whole-tree hashing')):
                rows=probe.inventory(folder,100,2048,hash_files=False)
            self.assertIsNone(rows[0]['sha256'])
            for count in (256,2048):
                receiver=monitor.Receiver(root/('identity-catalog-'+str(count)),100,mirror=True,catalog=True,maximum_files=count)
                receiver.feed(dict(kind='OWNER',owner=dict(pid=123,start_ticks=456,boot_id='fixture')))
                receiver.feed(dict(kind='STATUS',closed=True))
                manifest=dict(kind='MANIFEST',files=1,bytes=17,hash_mode='streamed_segments')
                if count==256:
                    with self.assertRaises(ValueError):receiver.feed(manifest)
                else:
                    receiver.feed(manifest);receiver.feed(dict(kind='MANIFEST_ENTRY',**rows[0]))
                    receiver.feed(dict(kind='CATALOG_END',files=1,bytes=17,
                        manifest_sha256=hashlib.sha256(monitor.encoded(rows)).hexdigest(),closure=dict(closed=True)))
                    self.assertIsNotNone(receiver.catalog_complete)

        def test_segmented_hour_manifest_has_measured_provenance(self):
            from unittest.mock import patch
            import types,time
            raw=b'exact native segment fixture'*3000
            folder=root/'hour-mirror';folder.mkdir()
            row=dict(path='data/part',identity=dict(bytes=len(raw),device=1,inode=2,mtime_ns=3,ctime_ns=4),sha256=None)
            identity_sha=hashlib.sha256(monitor.encoded([row])).hexdigest()
            catalog=types.SimpleNamespace(rows=[row],manifest=dict(bytes=len(raw),hash_mode='streamed_segments'),
                catalog_complete=dict(manifest_sha256=identity_sha,files=1,bytes=len(raw),closure=dict(closed=True)))
            def probe(source,job,mode,root,index,extra=None):
                if mode=='catalog':return catalog
                path=root/'closed-output'/row['path'];path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('ab') as stream:stream.write(raw[extra['offset']:extra['offset']+extra['count']])
            with patch.object(monitor,'run_probe',probe):
                result=monitor.segmented_mirror(b'',{'maximum_output_bytes':len(raw)},folder,0,time.time()+60)
            full=monitor.strict((folder/'MIRROR_MANIFEST.json').read_bytes())
            self.assertEqual(full[0]['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(result['manifest_sha256'],hashlib.sha256(monitor.encoded(full)).hexdigest())
            self.assertEqual(result['source_identity_manifest_sha256'],identity_sha)
            self.assertFalse(result['source_whole_file_hash_claimed'])

    suite=unittest.TestSuite(Checks(name) for name in args.checks) if args.checks else unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    receipt=dict(tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),
        evidence=str(root),ssh_executed=False,native_executed=False)
    monitor.save(root/'TEST_RESULT.json',receipt);print(monitor.encoded(receipt).decode())
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
