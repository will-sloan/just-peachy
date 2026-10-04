"""Host-only package-origin, installer transaction and receipt tests; README_GUARDED_ACTIVATION.md."""
import base64
from pathlib import Path, PurePosixPath
import sys
import tempfile
import types
import time
import unittest
from unittest.mock import patch

import desktop_activation_action as action
import launch_production_idle_action as idle
import production_idle_control as controller

PACKAGE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/package-preparation-3b8ec5e1d68d406ea1f126e834c16288/package')


class ActivationTests(unittest.TestCase):
    def fixture(self, directory):
        root=Path(directory); package=root/'package'; package.mkdir()
        desktop=root/'Desktop';desktop.mkdir();desktop=desktop/'existing.desktop'
        old=b'[Desktop Entry]\nName=Retained fixture\n';desktop.write_bytes(old)
        files={name+'.py':(PACKAGE/(name+'.py')).read_bytes() for name in (*action.IMPORTS,'install_candidate')}
        row=dict(path='selected.desktop',source=str(desktop),identity=dict(bytes=len(old)),sha256=action.sha(old))
        rows=action.encoded([row]);complete=action.encoded(dict(kind='COMPLETE',files=1,manifest_sha256=action.sha(rows),
            closure=dict(closed=True,exact_owner_gone=True,cgroup_empty=True)))
        selection=dict(diarizer='pyannote',embedding='redimnet',input_source='saved',nemotron_profile=None,
            allow_experimental=False,provisional_correction=False,refinement_profile='current_delayed',
            revision_window_seconds=30,refinement_period_seconds=5,embedding_schedule='continuous',
            embedding_refresh_seconds=2.0,speaker_attribution='retained',optional_d1_refiner=False)
        accepted=dict(schema='just-peachy.v29.production-acceptance.v1',accepted=True,reviewer='synthetic host fixture',
            accepted_unix=1,target=str(package),candidate_content_sha256='a'*64,installed_manifest_sha256='b'*64,
            previous_desktop_sha256=action.sha(old),allowed_selections=[selection],optional_refiner_admissions=[],
            limits=dict(maximum_session_seconds=300,maximum_developer_seconds=3600,max_drain_seconds=120,max_backlog_seconds=120),
            assets=[dict(path='/home/peachyprototype/JustPeachy/install/model.onnx',resolved='/home/peachyprototype/JustPeachy/install/model.onnx',bytes=1,sha256='c'*64)],
            full_backup=dict(scope='selected-release-and-user-data',root='fixture',manifest_path='fixture',completion_path='fixture',
                manifest_sha256=action.sha(rows),completion_sha256=action.sha(complete)))
        acceptance=action.encoded(accepted)
        binding=dict(target=str(package),native_launch_enabled=True,authorization_kind='production',
            production_acceptance_sha256=action.sha(acceptance),candidate_content_sha256='a'*64,installed_manifest_sha256='b'*64,
            python='/usr/bin/python3')
        files.update({'BINDING.json':action.encoded(binding),'PRODUCTION_ACCEPTANCE.json':acceptance,
            'PRODUCTION_BACKUP_MANIFEST.json':rows,'PRODUCTION_BACKUP_COMPLETE.json':complete})
        for name,raw in files.items():(package/name).write_bytes(raw)
        manifest=dict(schema='just-peachy.v29.package.v1',target=str(package),files=[dict(path=name,bytes=len(raw),sha256=action.sha(raw)) for name,raw in files.items()])
        raw=action.encoded(manifest);(package/'PACKAGE_MANIFEST.json').write_bytes(raw)
        payload=dict(desktop=str(desktop),previous_desktop_sha256=action.sha(old),production_acceptance_sha256=action.sha(acceptance),
            backup_manifest_sha256=action.sha(rows),backup_completion_sha256=action.sha(complete))
        return root,package,desktop,old,manifest,action.sha(raw),payload

    def test_exact_imports_enable_unchanged_installer_and_preserve_old_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root,package,desktop,old,manifest,manifest_sha,payload=self.fixture(directory)
            action.inventory(package,manifest_sha)
            with patch.dict(sys.modules):
                for name in action.IMPORTS:sys.modules.pop(name,None)
                with action.VerifiedImports(package,manifest) as imported:
                    action.production_evidence(package,manifest,payload)
                    self.assertEqual(set(imported.origins),set(action.IMPORTS))
                    namespace=dict(__name__='actual_installer_fixture',__file__=str(package/'install_candidate.py'))
                    exec(compile((package/'install_candidate.py').read_bytes(),namespace['__file__'],'exec'),namespace)
                    # Only platform/path/fsync-directory adapters differ on the host.
                    namespace['check_native']=lambda:None
                    namespace['allowed_target']=lambda path:Path(path)==package
                    namespace['fsync_dir']=lambda path:None
                    class HostPath(type(Path())):
                        def __str__(self):return super().__str__().replace('\\','/')
                        @classmethod
                        def home(cls):return cls(root)
                    namespace['Path']=HostPath
                    baseline=root/'BASELINE.json';baseline.write_bytes(b'{"fixture":true}')
                    result=namespace['activate'](package,manifest_sha,desktop,action.sha(old),baseline,action.sha(baseline.read_bytes()))
                    backup=Path(result['backup'])
                    self.assertEqual((backup/(desktop.name+'.backup')).read_bytes(),old)
                    self.assertEqual((backup/(desktop.name+'.restore')).read_bytes(),old)
                    self.assertEqual(action.sha(desktop.read_bytes()),result['current_sha256'])
                    self.assertIn(b'native_scope.py',desktop.read_bytes())
                    self.assertFalse(result['autostart'])
                self.assertNotIn('profiles',sys.modules)

    def test_alien_import_and_qualification_receipts_refused_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            _,package,desktop,old,manifest,_,payload=self.fixture(directory)
            fake=types.ModuleType('profiles');fake.__file__=str(package/'alien.py')
            with patch.dict(sys.modules,profiles=fake):
                with self.assertRaisesRegex(ValueError,'different origin'):
                    with action.VerifiedImports(package,manifest):pass
            with patch.dict(sys.modules):
                for name in action.IMPORTS:sys.modules.pop(name,None)
                with action.VerifiedImports(package,manifest):
                    payload['backup_completion_sha256']='0'*64
                    with self.assertRaisesRegex(ValueError,'backup pins'):
                        action.production_evidence(package,manifest,payload)
            self.assertEqual(desktop.read_bytes(),old)
            self.assertEqual(list(package.parent.glob('field-runtime-v29-desktop-backup-*')),[])

    def test_closed_outer_readback_recovers_baseline_and_refuses_changed_bytes(self):
        baseline=dict(utility_owner=dict(pid=1,start_ticks=2,boot_id='fixture'),boot_id='fixture')
        raw=action.encoded(baseline);campaign=PurePosixPath(action.CAMPAIGN.as_posix());root=str(campaign/('field-runtime-v29-activation-'+'1'*32))
        result=dict(status='DESKTOP_ACTIVATED_NOT_STARTED',inspector_reference=baseline['utility_owner'],
            baseline_fields=sorted(baseline),baseline_bytes=len(raw),baseline_sha256=action.sha(raw),evidence_root=root,
            backup=str(campaign/('field-runtime-v29-desktop-backup-'+'2'*32)),desktop='/home/peachyprototype/Desktop/fixture.desktop',readback_files=[])
        names=[result['backup']+'/fixture.desktop.backup',result['backup']+'/fixture.desktop.restore',
            result['backup']+'/ACTIVATION_PLAN.json',result['desktop']]
        names.extend(root+'/'+name for name in ('INSPECTOR_REFERENCE.json','IMPORTS.json','ACTIVATION_INTENT.json'))
        result['readback_files']=[dict(path=name,bytes=2,sha256=action.sha(b'{}'),base64=base64.b64encode(b'{}').decode()) for name in names]
        native=action.encoded(result);result['activation_result_record']=dict(bytes=len(native),sha256=action.sha(native))
        outer=dict(baseline,action_result=result,native_writes=True,utility_pid_absent_after_ssh=True,prior_failed_inspector_checked_dead=[])
        files=action.readback_payload(outer)
        self.assertEqual(files[root+'/BASELINE.json'],raw)
        self.assertEqual(files[root+'/BASELINE.restore.json'],raw)
        outer['boot_id']='changed'
        with self.assertRaisesRegex(ValueError,'transport'):action.readback_payload(outer)

    def test_idle_wrapper_is_exact_frozen_wrapper_and_has_no_capture_path(self):
        source=(PACKAGE/'launch_raw_qualification_action.py').read_bytes();helper={}
        exec(compile(source,'<actual10wrapper>','exec'),helper)
        settings=dict(output='/fixture',package='/package',unit='jp-v29-production-idle-01.service',
            budget=dict(file_limit_bytes=32*1024**2,maximum_output_bytes=16*1024**2,runtime_seconds=90,stop_seconds=30))
        wrapper=helper['wrapper_source'](settings)
        compile(wrapper,'<idle-owned-wrapper>','exec');compile(idle.CONTROL_SOURCE,'<production-idle-controller>','exec')
        self.assertLess(wrapper.index("put('OWNER.json'"),wrapper.index('scope.verified_inventory'))
        self.assertEqual(idle.CONTROL_SOURCE,Path(controller.__file__).read_text())
        self.assertIn("subprocess.Popen(request['command']",idle.CONTROL_SOURCE)
        self.assertIn("control.tk.call('send',candidate,'pid')",idle.CONTROL_SOURCE)
        self.assertIn('actual_native_scope_outer_executed=True',idle.CONTROL_SOURCE)
        self.assertEqual((PACKAGE/'launch_raw_qualification_action.py').read_bytes(),source)

    def test_watchdog_refuses_changed_invocation_and_only_closes_owned_unit(self):
        owner=dict(pid=1,start_ticks=2,boot_id='fixture')
        receipt=dict(unit='jp-v29-fixture.service',invocation_id='a'*32,control_group='/user.slice/fixture',owner=owner)
        live=[True]
        state=dict(InvocationID='b'*32,ControlGroup=receipt['control_group'])
        scope=types.SimpleNamespace(properties=lambda unit:dict(state),alive=lambda value:live[0],cgroup_empty=lambda group:not live[0])
        with patch.object(controller.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'identity changed'):
                controller.close_owned_nested(scope,dict(receipt=receipt),time.monotonic()+5)
            run.assert_not_called()
            with self.assertRaisesRegex(RuntimeError,'acknowledged'):
                controller.close_owned_nested(scope,dict(receipt=None),time.monotonic()+5)
            run.assert_not_called()
        state['InvocationID']=receipt['invocation_id']
        def terminate(*args,**kwargs):live[0]=False;return types.SimpleNamespace(returncode=0)
        with patch.object(controller.subprocess,'run',side_effect=terminate) as run:
            result=controller.close_owned_nested(scope,dict(receipt=receipt),time.monotonic()+5)
            self.assertTrue(result['closed']);self.assertTrue(result['forced'])
            self.assertEqual(run.call_args.args[0][-1],receipt['unit'])
            self.assertIn('--signal=TERM',run.call_args.args[0])
            self.assertEqual(run.call_count,1)

    def test_nested_registration_requires_actual7200scope_and_exact_main_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'unit-owners'/'fixture';(root/'main').mkdir(parents=True)
            owner=dict(pid=1,start_ticks=2,boot_id='fixture');main=dict(pid=3,start_ticks=4,boot_id='fixture')
            def write(name,value):(root/name).write_bytes(action.encoded(value))
            write('REGISTERED_OWNER.json',owner)
            write('SERVICE_REQUEST.json',dict(owner=owner,unit='jp-v29-fixture.service'))
            write('main/REGISTERED_OWNER.json',main)
            request=dict(data_root=str(base),boot_id='fixture')
            self.assertIsNone(controller.nested_registration(request)['receipt'])
            receipt=dict(unit='jp-v29-fixture.service',owner=main,runtime_max_seconds=90)
            write('UNIT_OWNERSHIP.json',receipt)
            with self.assertRaisesRegex(ValueError,'7200'):controller.nested_registration(request)
            receipt['runtime_max_seconds']=7200;write('UNIT_OWNERSHIP.json',receipt)
            self.assertEqual(controller.nested_registration(request)['receipt']['owner'],main)

    def test_actual_baseline_settings_membership_and_closed_capture_are_required(self):
        path=PACKAGE.parents[2]/'operation-production-scope-06/dispatch/RESULT.json'
        baseline=action.strict(path.read_bytes())
        request=idle.baseline_state(baseline,Path('/fixture/current.desktop'),b'fixture')
        self.assertEqual(len(request['unchanged_files']),7)
        self.assertEqual(request['capture_status'],baseline['capture'])
        baseline['capture_started']=True
        with self.assertRaisesRegex(ValueError,'closed capture'):idle.baseline_state(baseline,Path('/fixture/current.desktop'),b'fixture')
        baseline['capture_started']=False;baseline['files']=baseline['files'][:-1]
        with self.assertRaisesRegex(ValueError,'settings membership'):idle.baseline_state(baseline,Path('/fixture/current.desktop'),b'fixture')

    def test_idle_state_readback_refuses_changed_settings_or_display(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'settings.json';file.write_bytes(b'{"stable":true}')
            shown=types.SimpleNamespace(returncode=0,stdout='Enabled: yes\nTransform: 270\n',stderr='')
            request=dict(unchanged_files=[dict(path=str(file),bytes=file.stat().st_size,sha256=action.sha(file.read_bytes()))],
                capture_status={},display_stdout_sha256=action.sha(shown.stdout.encode()))
            with patch.object(controller.subprocess,'run',return_value=shown) as run:
                before=controller.unchanged_state(request)
                self.assertTrue(before['settings_unchanged']);self.assertEqual(run.call_args.args[0],['wlr-randr'])
                file.write_bytes(b'{"stable":false}')
                with self.assertRaisesRegex(ValueError,'settings or desktop changed'):controller.unchanged_state(request)
                file.write_bytes(b'{"stable":true}')
                shown.stdout='Enabled: yes\nTransform: 90\n'
                with self.assertRaisesRegex(ValueError,'display270 changed'):controller.unchanged_state(request)


if __name__=='__main__':unittest.main()
