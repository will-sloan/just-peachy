"""Pure dispatch admission/wrapper checks; README_QUALIFICATION_DISPATCH.md."""
import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

import launch_raw_qualification_action as action


class DispatchTests(unittest.TestCase):
    def output_guard(self, folder, maximum_files=256):
        import ast,json,stat
        source=action.wrapper_source(dict(kind='full_app_hour',budget={}))
        function=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='bounded_output')
        context=dict(Path=Path,os=os,json=json,stat=stat,out=folder,
            SETTINGS=dict(budget=dict(maximum_files=maximum_files,maximum_output_bytes=1024**2)))
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<host-only-output-guard>','exec'),context)
        return context['bounded_output']

    def test_output_guard_exact_pending_pair_and_external_alias_refusal(self):
        folder=self.root/'guard';folder.mkdir();pending=folder/'receipt.json.pending';final=folder/'receipt.json'
        pending.write_bytes(b'payload');os.link(pending,final)
        guard=self.output_guard(folder)
        self.assertEqual(guard(),14)
        outside=self.root/'outside-alias';os.link(final,outside)
        with self.assertRaisesRegex(ValueError,'unrecognized_hardlink') as caught:guard()
        self.assertIn('"nlink":3',str(caught.exception));self.assertIn('"path":',str(caught.exception))
        outside.unlink();pending.unlink();self.assertEqual(guard(),7)
        alias=self.root/'outside-other';os.link(final,alias)
        with self.assertRaisesRegex(ValueError,'unrecognized_hardlink'):guard()

    def test_output_guard_publication_unlink_races_are_rechecked(self):
        folder=self.root/'race';folder.mkdir();pending=folder/'receipt.json.pending';final=folder/'receipt.json'
        pending.write_bytes(b'payload');os.link(pending,final)
        original=Path.lstat;observed=original(final);pending.unlink();seen=False
        def stale_first(path,*args,**kwargs):
            nonlocal seen
            if path==final and not seen:seen=True;return observed
            return original(path,*args,**kwargs)
        with mock.patch.object(Path,'lstat',stale_first):self.assertEqual(self.output_guard(folder)(),7)
        vanished=folder/'history.sqlite3-journal';vanished.write_bytes(b'old');seen=False
        def unlinked_zero(path,*args,**kwargs):
            nonlocal seen
            if path==vanished and not seen:
                seen=True;value=list(original(path));value[3]=0;path.unlink();return os.stat_result(value)
            return original(path,*args,**kwargs)
        with mock.patch.object(Path,'lstat',unlinked_zero):self.assertEqual(self.output_guard(folder)(),7)

    def test_output_guard_count_has_exact_failure_details(self):
        folder=self.root/'count';folder.mkdir();(folder/'one').write_bytes(b'1');(folder/'two').write_bytes(b'22')
        with self.assertRaisesRegex(ValueError,'file_count') as caught:self.output_guard(folder,1)()
        self.assertIn('"count":2',str(caught.exception));self.assertIn('"maximum_files":1',str(caught.exception))

    def setUp(self):
        parent=Path(os.environ['LIVE_QUALIFICATION_TEST_ROOT'])
        parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for name in ('installed_source.py','raw_capture.py','native_scope.py','source_batch.py'):
            (self.root/name).write_text('# synthetic source-only fixture\n')
        rows=[dict(path=p.name,bytes=p.stat().st_size,sha256=action.sha(p)) for p in self.root.iterdir()]
        manifest=dict(schema='just-peachy.v29.package.v1',files=rows,target=str(self.root))
        (self.root/'PACKAGE_MANIFEST.json').write_bytes(action.encoded(manifest))
        self.manifest_sha=action.sha(self.root/'PACKAGE_MANIFEST.json')

    def test_complete_inventory_rejects_extra_changed_and_traversal_members(self):
        self.assertEqual(len(action.inventory(self.root,self.manifest_sha)['files']),4)
        (self.root/'unlisted').write_bytes(b'x')
        with self.assertRaises(ValueError):action.inventory(self.root,self.manifest_sha)
        (self.root/'unlisted').unlink()
        (self.root/'raw_capture.py').write_bytes(b'x')
        with self.assertRaises(ValueError):action.inventory(self.root,self.manifest_sha)
        manifest=dict(schema='just-peachy.v29.package.v1',files=[dict(path='../outside',bytes=1,sha256='0'*64)])
        (self.root/'PACKAGE_MANIFEST.json').write_bytes(action.encoded(manifest))
        with self.assertRaises(ValueError):action.inventory(self.root,action.sha(self.root/'PACKAGE_MANIFEST.json'))

    def test_five_second_review_template_requires_exact_pins_and_expiry(self):
        now=time.time()
        payload=dict(boot_id='synthetic-boot',expires_unix=now+60,package_manifest_sha256=self.manifest_sha)
        template=dict(schema='just-peachy.raw-qualification-template.v1',reviewed=True,duration_seconds=5,
            target=str(self.root),binding_sha256='a'*64,package_manifest_sha256=self.manifest_sha,
            boot_id=payload['boot_id'],expires_unix=now+30,
            installed_source_sha256=action.sha(self.root/'installed_source.py'),raw_capture_sha256=action.sha(self.root/'raw_capture.py'),
            source_batch_sha256=action.sha(self.root/'source_batch.py'))
        payload['raw_admission_template_sha256']=hashlib.sha256(action.encoded(template)).hexdigest()
        self.assertEqual(action.validate_template(template,payload,'a'*64,self.root),template)
        with self.assertRaises(ValueError):action.validate_template(template,payload,'b'*64,self.root)
        with mock.patch.object(action.time,'time',return_value=now+31):
            with self.assertRaises(ValueError):action.validate_template(template,payload,'a'*64,self.root)
        changed=dict(template,source_batch_sha256='0'*64)
        changed_payload=dict(payload,raw_admission_template_sha256=hashlib.sha256(action.encoded(changed)).hexdigest())
        with self.assertRaises(ValueError):action.validate_template(changed,changed_payload,'a'*64,self.root)

    def test_raw_envelope_and_wrapper_are_finite_without_executing(self):
        budget=action.budget_plan(self.root,{},dict(maximum_output_bytes=16*1024**2),'raw')
        self.assertEqual((budget['runtime_seconds'],budget['stop_seconds'],budget['file_limit_bytes']),(180,30,32*1024**2))
        source=action.wrapper_source(dict(kind='raw',budget=budget))
        compile(source,'<not-executed-native-wrapper>','exec')
        self.assertLess(source.index("put('OWNER.json',owner)"),source.index("scope_path.read_bytes()"))
        self.assertIn("open(SETTINGS['research_lock'],'rb')",source)
        self.assertNotIn("open('/home/peachyprototype/JustPeachy/data/xvf-hardware.lock'",source)
        self.assertIn("'JOB_EXIT.json'",source)
        self.assertIn('scope.verified_inventory',source)
        self.assertIn("'--owner-directory',str(out/'qualification')",source)
        with self.assertRaises(ValueError):action.budget_plan(self.root,{},dict(maximum_output_bytes=1),'raw')

    def test_pipeline_inherited_file_ceiling_covers_newly_initialized_history(self):
        import profiles
        import storage
        from worker import file_size_plan
        disk=storage.StoragePolicy(reserve_bytes=0,reserve_fraction=0)
        policy=profiles.SessionPolicy(maximum_session_seconds=5)
        selection=profiles.RuntimeSelection(input_source='saved')
        metadata=16*action.MIB+5*256*1024
        spec=dict(duration_seconds=5,sample_rate=16000,mode='processed',metadata_reserve_bytes=metadata)
        required=disk.estimate_bytes(spec)+metadata+disk.metadata_allowance_bytes+10*action.MIB
        import dataclasses
        payload=dict(selection=dataclasses.asdict(selection),policy=dataclasses.asdict(policy),maximum_output_bytes=required)
        with mock.patch.object(action,'load_pure',side_effect=lambda package,name:dict(profiles=profiles,storage=storage)[name]):
            budget=action.budget_plan(self.root,dict(storage_policy=dataclasses.asdict(disk)),payload,'pipeline')
        store=storage.SessionStore(self.root/'fresh-history',disk)
        self.addCleanup(store.close)
        plan=file_size_plan(store.root,metadata,disk)
        old_ceiling=2*(metadata+disk.metadata_allowance_bytes)+8*action.MIB
        self.assertGreater(plan['existing_history_bytes'],0)
        self.assertGreater(plan['file_limit_bytes'],old_ceiling)
        self.assertLessEqual(plan['file_limit_bytes'],budget['file_limit_bytes'])
        self.assertEqual(budget['file_limit_bytes'],required)
        self.assertEqual(budget['maximum_output_bytes'],required)

    def test_gui_reserves_two_full_operator_sessions_and_second_start_room(self):
        import dataclasses
        import profiles
        import storage
        policy=profiles.SessionPolicy();disk=storage.StoragePolicy()
        metadata=16*action.MIB+300*256*1024
        processed=dict(duration_seconds=300,sample_rate=16000,mode='processed',metadata_reserve_bytes=metadata)
        raw=dict(processed,mode='raw_processed',raw=dict(sample_rate=16000,channels=4,sample_width_bytes=4,
            encoding='PCM_S32LE',qualification=dict(qualified=True,evidence='synthetic budget only')))
        extra=metadata+disk.metadata_allowance_bytes+10*action.MIB
        required=disk.estimate_bytes(raw)+disk.estimate_bytes(processed)+2*extra+24*action.MIB
        payload=dict(selection=profiles.RuntimeSelection().validate(),policy=policy.validate(),
            workflow='capture-save-replay-discard',stop_after_seconds=45,maximum_output_bytes=required,runtime_seconds=1500)
        with mock.patch.object(action,'load_pure',side_effect=lambda package,name:dict(profiles=profiles,storage=storage)[name]):
            budget=action.budget_plan(self.root,dict(raw_adapter_enabled=True),payload,'gui')
            self.assertEqual(budget['session_seconds'],300)
            self.assertEqual([row['mode'] for row in budget['session_allocations']],['raw_processed','processed'])
            self.assertEqual(budget['maximum_output_bytes'],required)
            self.assertGreaterEqual(budget['runtime_seconds']-policy.total_deadline_seconds,policy.total_deadline_seconds+150)
            self.assertEqual(budget['maximum_files'],1024)
            complete=action.budget_plan(self.root,dict(raw_adapter_enabled=True),
                dict(payload,stop_after_seconds=300,stop_mode='policy',save_raw=True),'gui')
            self.assertEqual(complete['maximum_output_bytes'],required)
            self.assertEqual(complete['stop_mode'],'policy');self.assertTrue(complete['save_raw'])
            manual=action.budget_plan(self.root,dict(raw_adapter_enabled=True),
                dict(payload,stop_after_seconds=300,stop_mode='button'),'gui')
            self.assertEqual(manual['stop_after_seconds'],300)
            for delta in (dict(stop_after_seconds=299,stop_mode='policy'),dict(stop_after_seconds=301),
                          dict(save_raw=1),dict(stop_mode='guess')):
                with self.subTest(delta=delta),self.assertRaises(ValueError):
                    action.budget_plan(self.root,dict(raw_adapter_enabled=True),dict(payload,**delta),'gui')
            with self.assertRaisesRegex(ValueError,'separately qualified'):
                action.budget_plan(self.root,{},dict(payload,save_raw=True),'gui')
            for delta in (dict(maximum_output_bytes=16*action.MIB),dict(runtime_seconds=900),
                          dict(policy=dict(policy.validate(),maximum_session_seconds=45))):
                with self.subTest(delta=delta),self.assertRaises(ValueError):
                    action.budget_plan(self.root,dict(raw_adapter_enabled=True),dict(payload,**delta),'gui')


if __name__=='__main__':unittest.main()
