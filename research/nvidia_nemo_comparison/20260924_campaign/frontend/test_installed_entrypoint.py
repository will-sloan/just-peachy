"""Real installed main.py idle/close audit on a private desktop. See README.md."""
from contextlib import ExitStack
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import time
import unittest
from unittest.mock import patch


INSTALLED = Path('G:/Just_Peachy_N1/20260924_campaign/local/Installed Baseline/releases/n1-common-20260924-v1')
MODELS = Path('C:/Users/amiri/JustPeachy/shared/models')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


class InstalledEntrypointTests(unittest.TestCase):
    def test_real_main_stays_idle_and_closes_with_saved_autostart(self):
        if not os.environ.get('N1_UI_RECEIPT_DIR'):
            self.skipTest('Requires the private desktop test launcher')
        from prototype.tests.run_private_desktop import desktop_name, setup_api
        user32 = setup_api()
        desktop = desktop_name(user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId()))
        self.assertTrue(desktop.startswith('codex-n1-'))
        source = INSTALLED.resolve(strict=True)
        output = Path(os.environ['N1_UI_RECEIPT_DIR']).resolve()
        data = output/'isolated_app_data'; data.mkdir()
        preferences = {'microphone_preapproved':True,'auto_start_listening':True,
                       'caption_size':'Compact','preview_zoom':1.0}
        (data/'settings.json').write_text(json.dumps(preferences)+'\n',encoding='utf-8')
        bound_files = [path for folder in ('app','config','vendor','release_tools') for path in (source/folder).rglob('*')
                       if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.pyo')]
        bound_files.append(source/'main.py')
        before = {str(path.relative_to(source)):digest(path) for path in bound_files}
        sys.path[:0] = [str(source),str(source/'vendor')]
        from app.ui import PrototypeUI
        from app.controller import Controller
        from app.pipeline import ResidentModels
        from app import windows_audio, session_playback, live_audio
        from release_tools.runtime_lock import RuntimeLock
        self.assertEqual(Path(sys.modules['app.ui'].__file__).resolve(),source/'app/ui.py')
        self.assertEqual(Path(sys.modules['app.controller'].__file__).resolve(),source/'app/controller.py')
        capture_helper=Path(__file__).resolve().parents[4]/'prototype/tests/test_n1_capture.py'
        spec=importlib.util.spec_from_file_location('_installed_capture_helper',capture_helper)
        helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
        calls=[]; observed={}; failures=[]; original=PrototypeUI.__init__
        def forbidden(name):
            def fail(*args,**kwargs):
                calls.append(name)
                raise AssertionError('Idle startup attempted forbidden call: '+name)
            return fail
        def instrumented(window,root,controller,**kwargs):
            self.assertIsInstance(controller,Controller)
            observed['allow_auto_start_argument']=kwargs.get('allow_auto_start')
            observed['controller']=controller
            started=time.monotonic()
            original(window,root,controller,**kwargs)
            def verify_and_close():
                try:
                    snapshot=controller.snapshot()
                    observed.update(idle_observation_seconds=time.monotonic()-started,
                        idle_state=snapshot['state'],saved_audio_only=controller.saved_audio_only,
                        saved_preferences=dict(controller.settings),root_pixels=[root.winfo_width(),root.winfo_height()],
                        model_counts=dict(asr_loads=controller.models.asr_loads,speaker_loads=controller.models.speaker_loads,
                                          streams=controller.models.streams,enhancer_loads=controller.models.enhancer_loads),
                        runtime_lock_exists_during_ui=(data/'runtime.lock').exists(),
                        endpoint_observations=list(controller.output_defaults),imu_is_none=controller.imu is None,
                        engine_is_none=controller.engine is None,ui_pending_auto_start=window._auto_start_pending)
                    self.assertEqual(snapshot['state'],'IDLE')
                    self.assertTrue(controller.saved_audio_only)
                    self.assertEqual(observed['root_pixels'],[480,800])
                    self.assertTrue(all(value==0 for value in observed['model_counts'].values()))
                    self.assertFalse(window._auto_start_pending)
                    self.assertFalse(calls)
                    self.assertTrue(observed['runtime_lock_exists_during_ui'])
                    observed['screenshot']=helper.render_client(root,output/'INSTALLED_IDLE.png')
                except BaseException as exc:
                    failures.append(type(exc).__name__+': '+str(exc))
                finally:
                    observed['normal_ui_close_called']=True
                    window.close()
            root.after(900,verify_and_close)
            def emergency():
                failures.append('UI close exceeded the bounded eight-second deadline')
                root.quit()
            root.after(8000,emergency)
        result_code=None
        try:
            with ExitStack() as stack:
                stack.enter_context(patch.object(PrototypeUI,'__init__',instrumented))
                for target,name in ((windows_audio,'endpoint_snapshot'),(session_playback,'outputs'),
                    (live_audio.HostControl,'query'),(ResidentModels,'acquire'),
                    (ResidentModels,'enrollment_models'),(ResidentModels,'enhancement_model'),
                    (Controller,'start_live'),(Controller,'start_file'),(Controller,'enrollment_start')):
                    stack.enter_context(patch.object(target,name,side_effect=forbidden(target.__name__+'.'+name)))
                stack.enter_context(patch.object(sys,'argv',[str(source/'main.py'),'gui','--data-root',str(data),'--models',str(MODELS)]))
                try:
                    runpy.run_path(str(source/'main.py'),run_name='__main__')
                except SystemExit as exc:
                    result_code=exc.code
            controller=observed.pop('controller')
            controller.worker.join(2)
            observed.update(main_exit_code=result_code,closed=controller.closed,final_state=controller.state,
                controller_worker_alive=controller.worker.is_alive(),runtime_lock_exists_after_close=(data/'runtime.lock').exists(),
                endpoint_observations=list(controller.output_defaults),guarded_forbidden_calls=calls)
            self.assertEqual(result_code,0)
            self.assertTrue(controller.closed)
            self.assertEqual(controller.state,'CLOSED')
            self.assertFalse(controller.worker.is_alive())
            self.assertFalse((data/'runtime.lock').exists())
            next_owner=RuntimeLock(data,'post-close-verification'); next_owner.close()
            observed['runtime_lock_reacquired_and_released']=True
            self.assertFalse(calls)
            self.assertFalse(failures)
            self.assertEqual({str(path.relative_to(source)):digest(path) for path in bound_files},before)
            observed['installed_source_unchanged']=True
        finally:
            observed.pop('controller',None)
            receipt=dict(schema='n1-installed-main-idle-audit.v1',scope='Actual installed main.py, real Controller, private desktop, no inference/hardware',
                installed_source=str(source),main_sha256=digest(source/'main.py'),bound_file_count=len(before),
                capture_helper_sha256=digest(capture_helper),
                private_desktop=desktop,isolated_data_root=str(data),failures=failures,**observed)
            (output/'INSTALLED_MAIN_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':unittest.main()
