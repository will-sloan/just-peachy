"""Host-only raw release evidence gates; see README_RAW_RELEASE.md."""
import argparse
import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
import uuid


def register(output_root):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,1<<14):raise ctypes.WinError(ctypes.get_last_error())
    clocks=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in clocks)):raise ctypes.WinError(ctypes.get_last_error())
    root=Path(output_root)/('raw-release-checks-'+uuid.uuid4().hex);root.mkdir(parents=True,exist_ok=False)
    with (root/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
            affinity_mask=1<<14,creation_filetime=clocks[0].value,
            create_time=(clocks[0].value-116444736000000000)/10000000),stream)
        stream.flush();os.fsync(stream.fileno())
    return root


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root',required=True)
    parser.add_argument('--closed-mirror',type=Path,help='Optional exact prior closed raw mirror; readback only, never enables a release')
    parser.add_argument('--relocation-package',type=Path,help='Explicit actual frozen package for pure path-only relocation refusal fixtures')
    parser.add_argument('--checks',nargs='+')
    args=parser.parse_args();root=register(args.output_root);sys.dont_write_bytecode=True
    import prepare_package as package

    def fixture(directory,mutate=None):
        runtime={name:('fixture '+name).encode() for name in ('installed_source.py','raw_capture.py','source_batch.py')}
        factory=package.sha(b'fixture retained factory')
        owner=dict(pid=123,start_ticks=456,boot_id='fixture-boot')
        native=package.TARGET_PARENT+'/live-runtime-tests-20261003/raw-qualification-01'
        unit='jp-v29-raw-qualification-01.service';invocation='a'*32;cgroup='/user.slice/'+unit
        job=dict(schema='just-peachy.native-component-job.v1',boot_id=owner['boot_id'],owner=owner,
                 output_root=native,unit=unit,invocation_id=invocation,control_group=cgroup)
        proof=dict(status='RAW_NATIVE_QUALIFICATION_PASSED',native_executed=True,duration_seconds=5,
            owner=owner,unit=unit,unit_invocation=invocation,raw_channels=4,raw_samples=80000,
            processed_samples=80000,raw_bytes=1280000,processed_bytes=320000,
            source_clock_checked=True,raw_readback_checked=True,processed_readback_checked=True,
            route_restored=True,stream_closed=True,lease_released=True,source_owner_closed=True,
            physical=dict(kind='CLOSED',error=None,stream_closed=True,lease_released=True,source_batch_ms=100,
                integrity=dict(ok=True,restoration_ok=True),status=dict(dropped_frames=0),
                raw_capture=dict(derivation=dict(factory_sha256=factory),channel_order=['MIC0','MIC1','MIC2','MIC3'])))
        for filename,key in (('installed_source.py','installed_source_sha256'),('raw_capture.py','raw_capture_sha256'),('source_batch.py','source_batch_sha256')):
            proof[key]=package.sha(runtime[filename])
        closure=dict(closed=True,exact_owner_gone=True,cgroup_empty=True,owner=owner,
            owner_recaptured=True,unit=unit,invocation_id=invocation,control_group=cgroup,
            job_exit=dict(owner=owner,unit=unit,invocation_id=invocation,natural_returncode=0,
                          error=None,leases_released=True,output_budget_failure=None))
        if mutate:mutate(proof,job,closure)
        contents={'qualification/RAW_QUALIFICATION.json':package.encoded(proof),'JOB.json':package.encoded(job)}
        rows=[dict(path=name,identity=dict(bytes=len(raw)),sha256=package.sha(raw)) for name,raw in sorted(contents.items())]
        completion=dict(kind='COMPLETE',files=len(rows),bytes=sum(len(raw) for raw in contents.values()),
            mirror_scope='all_regular_output_files',manifest_sha256=package.sha(package.encoded(rows)),closure=closure)
        for name,raw in contents.items():package.write(directory/'closed-output'/name,raw)
        package.write(directory/'MIRROR_MANIFEST.json',package.encoded(rows))
        package.write(directory/'MIRROR_COMPLETE.json',package.encoded(completion))
        reference,documents=package.raw_reference_input(native+'/qualification/RAW_QUALIFICATION.json',
            package.sha(contents['qualification/RAW_QUALIFICATION.json']),directory)
        return reference,documents,runtime,factory

    class Checks(unittest.TestCase):
        @unittest.skipUnless(args.relocation_package,'No exact source package requested')
        def test_relocation_keeps_actual_source_identity_and_all_nonpath_behavior(self):
            import time
            from install_candidate import verify_tree
            source=args.relocation_package.resolve(strict=True)
            manifest_raw=package.read_regular(source/'PACKAGE_MANIFEST.json',262144)
            manifest_sha=package.sha(manifest_raw);verify_tree(source,manifest_sha)
            raw=package.read_regular(source/'BINDING.json',65536);old=package.strict(raw)
            new=copy.deepcopy(old);before=old['target'];after=package.TARGET_PARENT+'/field-runtime-v29-build-09'
            mappings=[]
            for field in ('target','reference_code','raw_factory_path'):
                new[field]=after+old[field][len(before):]
                mappings.append(dict(field=field,source=old[field],destination=new[field]))
            for key,row in new['profiles'].items():
                prior=row['path'];row['path']=after+prior[len(before):]
                mappings.append(dict(field='profiles.'+key+'.path',source=prior,destination=row['path']))
            mappings.sort(key=lambda row:row['field'])
            certificate=dict(schema='just-peachy.reviewed-runtime-relocation.v1',reviewed=True,
                reviewer='synthetic guard fixture only; never issued',reviewed_unix=time.time(),
                source_target=before,destination_target=after,source_manifest_sha256=manifest_sha,
                source_binding_sha256=package.sha(raw),candidate_content_sha256=old['candidate_content_sha256'],
                installed_manifest_sha256=old['installed_manifest_sha256'],
                source_operational_binding_sha256=package.sha(package.encoded(package.operational_binding(old))),
                destination_operational_binding_sha256=package.sha(package.encoded(package.operational_binding(new))),
                relocations=mappings,runtime_behavior_changed=False,measurement_reuse_requires_separate_review=True)
            self.assertEqual(package.validate_relocation(certificate,old,new,manifest_sha,raw),certificate)
            changed=copy.deepcopy(new);changed.update(native_launch_enabled=True,authorization_kind='production',production_acceptance_sha256='a'*64)
            package.validate_relocation(certificate,old,changed,manifest_sha,raw)
            for key,value in (('native_qualified',True),('source_batch_ms',0),('raw_adapter_enabled',False)):
                changed=copy.deepcopy(new);changed[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):package.validate_relocation(certificate,old,changed,manifest_sha,raw)
            changed=copy.deepcopy(new);changed['profiles'][next(iter(changed['profiles']))]['sha256']='0'*64
            with self.assertRaises(ValueError):package.validate_relocation(certificate,old,changed,manifest_sha,raw)
            for delta in (dict(source_manifest_sha256='0'*64),dict(source_binding_sha256='0'*64),
                          dict(relocations=mappings[:-1]),dict(runtime_behavior_changed=True),dict(reviewed=False)):
                with self.subTest(delta=delta),self.assertRaises(ValueError):
                    package.validate_relocation(dict(certificate,**delta),old,new,manifest_sha,raw)

        def test_exact_closed_reference_is_immutable_and_module_bound(self):
            ref,docs,runtime,factory=fixture(root/'valid')
            evidence=package.verify_raw_reference(ref,docs,runtime,100,factory)
            self.assertTrue(evidence['qualified']);self.assertTrue(evidence['adapter_native_qualified'])
            self.assertEqual(evidence['evidence_sha256'],ref['sha256'])
            options=dict(schema='just-peachy.v29.build-options.v1',source_batch_ms=100,raw_qualification_reference=ref)
            self.assertEqual(package.select_options(options),options)
            with self.assertRaisesRegex(ValueError,'Frozen'):package.select_options(options,0)
            for filename in runtime:
                with self.subTest(module=filename):
                    changed=dict(runtime);changed[filename]+=b' changed'
                    with self.assertRaisesRegex(ValueError,'module differs'):package.verify_raw_reference(ref,docs,changed,100,factory)
            for batch,sha in ((0,factory),(100,'0'*64)):
                with self.assertRaisesRegex(ValueError,'batch/factory'):package.verify_raw_reference(ref,docs,runtime,batch,sha)
            changed=dict(docs);changed[package.RAW_REFERENCE_FILES[0]]+=b' '
            with self.assertRaisesRegex(ValueError,'documents changed'):package.verify_raw_reference(ref,changed,runtime,100,factory)

        def test_success_flag_cannot_replace_owner_physical_or_route_closure(self):
            mutations=[
                lambda p,j,c:c.update(cgroup_empty=False),
                lambda p,j,c:c.update(owner=dict(pid=999,start_ticks=456,boot_id='fixture-boot')),
                lambda p,j,c:c['job_exit'].update(natural_returncode=1),
                lambda p,j,c:c['job_exit'].update(leases_released=False),
                lambda p,j,c:p.update(source_owner_closed=False),
                lambda p,j,c:p.update(status='RAW_NATIVE_QUALIFICATION_FAILED'),
                lambda p,j,c:p['physical'].update(stream_closed=False),
                lambda p,j,c:p['physical']['integrity'].update(restoration_ok=False),
                lambda p,j,c:p['physical']['status'].update(dropped_frames=1),
                lambda p,j,c:p.update(processed_samples=79999),
                lambda p,j,c:p.update(owner=None),
            ]
            for index,mutate in enumerate(mutations):
                with self.subTest(index=index):
                    ref,docs,runtime,factory=fixture(root/('refuse-'+str(index)),mutate)
                    with self.assertRaises(ValueError):package.verify_raw_reference(ref,docs,runtime,100,factory)

        def test_full_mirror_membership_and_readback_required(self):
            directory=root/'readback';ref,docs,runtime,factory=fixture(directory)
            proof=directory/'closed-output/qualification/RAW_QUALIFICATION.json'
            original=proof.read_bytes();proof.write_bytes(original.replace(b'80000',b'70000',1))
            with self.assertRaisesRegex(ValueError,'readback'):package.raw_reference_input(ref['path'],ref['sha256'],directory)
            proof.write_bytes(original)
            extra=directory/'closed-output/unlisted.txt';extra.write_bytes(b'not listed')
            with self.assertRaisesRegex(ValueError,'membership'):package.raw_reference_input(ref['path'],ref['sha256'],directory)
            extra.unlink()
            complete=package.strict((directory/'MIRROR_COMPLETE.json').read_bytes());complete['kind']='INCOMPLETE'
            (directory/'MIRROR_COMPLETE.json').write_bytes(package.encoded(complete))
            with self.assertRaisesRegex(ValueError,'complete raw mirror'):package.raw_reference_input(ref['path'],ref['sha256'],directory)

        def test_late_owner_requires_actual_recapture(self):
            ref,docs,runtime,factory=fixture(root/'late-owner',lambda p,j,c:j.update(owner=None))
            self.assertTrue(package.verify_raw_reference(ref,docs,runtime,100,factory)['qualified'])
            ref,docs,runtime,factory=fixture(root/'late-owner-missing',lambda p,j,c:(j.update(owner=None),c.update(owner_recaptured=False)))
            with self.assertRaises(ValueError):package.verify_raw_reference(ref,docs,runtime,100,factory)

        @unittest.skipUnless(args.closed_mirror,'No explicit historical mirror requested')
        def test_explicit_historical_mirror_readback_only(self):
            mirror=args.closed_mirror.resolve(strict=True)
            job=package.strict(package.read_regular(mirror/'closed-output/JOB.json',65536))
            proof=package.read_regular(mirror/'closed-output/qualification/RAW_QUALIFICATION.json',1024**2)
            ref,docs=package.raw_reference_input(job['output_root']+'/qualification/RAW_QUALIFICATION.json',package.sha(proof),mirror)
            self.assertEqual(ref['sha256'],package.sha(proof));self.assertEqual(len(docs),4)
            # Deliberately do not substitute hashes for candidate bytes or call
            # build: this confirms the reader protocol, not qualification08.

    suite=unittest.TestSuite(Checks(name) for name in args.checks) if args.checks else unittest.defaultTestLoader.loadTestsFromTestCase(Checks)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    receipt=dict(tests=result.testsRun,errors=len(result.errors),failures=len(result.failures),
        skipped=len(result.skipped),native_executed=False,package_built=False,evidence=str(root))
    package.write(root/'TEST_RESULT.json',package.encoded(receipt));print(package.encoded(receipt).decode())
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
