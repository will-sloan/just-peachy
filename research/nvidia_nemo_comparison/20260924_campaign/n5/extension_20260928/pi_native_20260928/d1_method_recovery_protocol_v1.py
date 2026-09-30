"""One actual installed UI selection/Start/Stop passage; README_D1_METHOD_RECOVERY_V1.md."""
import hashlib
import json
from pathlib import Path
import sys
import time


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f, 'sha256').hexdigest()


def run(root, admission):
    from field_sidecar_budget_v1 import GroupWriter
    from d1_method_recovery_v1 import controller_class, ui_class
    from d1_method_controls_v1 import MethodCatalog, canonical
    root = Path(root)
    spec = json.loads((root/'code/D1_METHOD_RECOVERY_INPUT_V1.json').read_bytes())
    for pin in spec['method_binding'].values():
        assert Path(pin['path']).stat().st_size==pin['bytes'] and sha(pin['path'])==pin['sha256']
    assert json.loads(Path(spec['method_binding']['native_result']['path']).read_bytes())['status']=='PASS_D1_METHOD_CONTRACT_AND_WITHDRAWN_CONTROLS_ONLY'
    catalog=MethodCatalog(spec['method_binding']['contract']['path'],spec['method_binding']['evidence']['path'])
    prototype = Path(spec['prototype'])
    for rel, h in spec['installed_files'].items():assert sha(prototype/rel) == h
    for name, pin in spec['pins'].items():
        if name != 'REVIEW.json':
            p = root.parent/spec['retained_run']/name
            assert p.stat().st_size == pin['bytes'] and sha(p) == pin['sha256']
    for item in spec['availability'].values():
        receipt = root/'code'/item['receipt']
        assert sha(receipt) == item['sha256']
        assert json.loads(receipt.read_bytes())['status'] == item['status']
    assert spec['mode'] == 'chunk52' and spec['prefix_samples'] == 70327 and spec['stop_after_samples'] == 68800
    for item in spec['saved_application_evidence'].values():
        receipt = root/'code'/item['receipt']
        assert sha(receipt) == item['sha256'] and json.loads(receipt.read_bytes())['status'] == item['status']
    # Explicit selected layout and quotas, independent of the unadmitted full V3 plan.
    for name in ('passage', 'passage_closure', 'app_receipts', 'app_failure', 'data'):(root/name).mkdir()
    writer = GroupWriter(root/'passage', admission['passage_limits'])
    closer = GroupWriter(root/'passage_closure', admission['passage_closure_limits'])
    receipts = GroupWriter(root/'app_receipts', admission['app_receipt_limits'])
    failure = GroupWriter(root/'app_failure', admission['app_failure_limits'])
    GroupWriter(root/'data', admission['app_receipt_limits']).json('DATA_SCHEMA.json', {'schema_version': 1})
    sys.path[:0] = [str(prototype), str(prototype/'vendor'), str(prototype/'native')]
    import app.controller as cm
    import app.ui as um
    import app.paths as paths
    assert Path(cm.__file__).resolve() == prototype/'app/controller.py'
    assert Path(um.__file__).resolve() == prototype/'app/ui.py'
    assert Path(paths.ROOT).resolve() == prototype
    manifest = json.loads((prototype/'RELEASE_MANIFEST.json').read_bytes())
    installed = {row['path']:row for row in manifest['files']}
    def verify_loaded():
        names = []
        for name, module in tuple(sys.modules.items()):
            if name.split('.')[0] not in ('app', 'edge_speech_pipeline', 'release_tools', 'field_artifact_limits_v1'):
                continue
            origin = getattr(module, '__file__', None)
            if origin is None:continue
            path = Path(origin).resolve()
            rel = path.relative_to(prototype).as_posix()
            assert path.stat().st_size == installed[rel]['bytes'] and sha(path) == installed[rel]['sha256']
            names.append(name)
        return sorted(names)
    verify_loaded()
    original_atomic = cm.atomic_json
    def bounded_close(path, value):
        if Path(path).resolve() != root/'data/last_application.json':
            raise RuntimeError('Undeclared application metadata writer')
        return receipts.json('last_application.json', value)
    cm.atomic_json = bounded_close
    C = controller_class(cm.Controller, root, spec, writer, closer, failure, catalog)
    controller = tkroot = ui = None
    result = {};began = time.monotonic();errors = []
    try:
        controller = C(root/'data', Path.home()/'JustPeachy/install/models', saved_audio_only=True)
        assert controller.owner._ownership.owned
        assert (root/'data/runtime.lock').stat().st_size <= 1024
        assert controller.models.asr_loads == controller.models.speaker_loads == 0
        import tkinter
        tkroot = tkinter.Tk(screenName=':0');tkroot.withdraw()
        tkroot.tk.eval('rename wm jp_original_wm; proc wm {args} {if {[lindex $args 0] eq "deiconify" || ([lindex $args 0] eq "state" && [llength $args] > 2 && [lindex $args 2] ne "withdrawn")} {error "visible windows forbidden"}; return [uplevel 1 [linsert $args 0 jp_original_wm]]}')
        tkroot.report_callback_exception = lambda k, v, t:errors.append(k.__name__+': '+str(v))
        ui = ui_class(um.PrototypeUI)(tkroot, controller, allow_auto_start=False)
        ui.show_modes();ui.actions['d1_saved_open'].invoke()
        def pump():
            tkroot.update();ui._page_update()
            assert tkroot.state() == 'withdrawn' and not tkroot.winfo_ismapped() and not errors, errors
            if time.monotonic()-began > 90:raise TimeoutError('Saved app protocol deadline')
        def commands_done(expect_error=False):
            deadline = time.monotonic()+65
            while controller.commands.unfinished_tasks:
                pump()
                if time.monotonic() > deadline:raise TimeoutError('Application command did not complete')
                time.sleep(.005)
            if not expect_error:assert not controller.error, controller.error
        pump();assert controller.d1_snapshot()['selected'] is None
        ui.d1_buttons[spec['mode']].invoke();commands_done();pump()
        selection = controller.d1_snapshot()
        assert selection['selected']['selection']['id'] == spec['mode'] and selection['start_available']
        assert selection['selected']['schema'] == 'd1-saved-mode-selection.v1'
        assert 'reason' not in selection['selected'] and 'launchable' not in selection['selected']
        assert selection['admitted_mode'] == spec['mode'] and selection['live_start_available'] is False
        assert spec['mode_label'] in ui.d1_status.cget('text')
        assert str(ui.d1_buttons['start'].cget('state')) == 'normal'
        cases=[]
        def observe(name):
            snap=controller.d1_snapshot();generic=controller.snapshot()
            assert snap['application_state']==generic['state']
            assert snap['application_status']==generic['status']
            assert snap['application_error']==generic['error']
            assert controller.d1_thread is None and not snap['owned'] and not snap['used']
            assert snap['samples']==snap['frames']==0 and not (root/'passage/START_REQUEST.json').exists()
            cases.append(dict(case=name,phase=snap['phase'],state=generic['state'],status=generic['status'],
                error=generic['error'],d1_error=snap['error'],start_available=snap['start_available'],
                recovery_available=snap['validation_recovery_available'],
                start_button=str(ui.d1_buttons['start'].cget('state')),source_samples=0,model_worker_created=False))
            return snap
        with controller.d1_lock:controller.d1_method_profile['resources']['gpu']=True
        ui.d1_buttons['start'].invoke();commands_done(expect_error=True);pump()
        snap=observe('queued_profile_reject')
        assert snap['application_state']=='ERROR' and snap['phase']=='METHOD_ERROR'
        assert snap['validation_recovery_available'] and not snap['start_available']
        assert str(ui.d1_buttons['start'].cget('state'))=='disabled'
        retained=snap['application_error']
        controller.d1_stop();commands_done(expect_error=True);pump()
        snap=observe('stop_retains_validation_error')
        assert snap['application_error']==retained and snap['validation_recovery_available']
        controller.d1_select('unavailable');commands_done(expect_error=True);pump()
        snap=observe('invalid_reselection_stays_error')
        assert snap['application_state']=='ERROR' and snap['validation_recovery_available']
        ui.d1_buttons[spec['mode']].invoke();commands_done();pump()
        snap=observe('explicit_valid_selection_recovers_both')
        assert snap['application_state']=='IDLE' and snap['application_error'] is None
        assert snap['phase']=='READY' and snap['error'] is None and snap['start_available']
        assert not snap['validation_recovery_available']
        assert snap['application_status']=='Saved diarizer ready. Microphone is off.'
        assert str(ui.d1_buttons['start'].cget('state'))=='normal'
        assert canonical(snap['implemented_methods'])==canonical(catalog.request(spec['mode']))
        # Declared source-kind sentinel only; no physical/model owner is created.
        controller.source_kind='declared-owner-sentinel'
        ui.d1_buttons[spec['mode']].invoke();commands_done(expect_error=True);pump()
        snap=observe('source_kind_sentinel_blocks_selection')
        assert snap['application_state']=='ERROR' and not snap['validation_recovery_available']
        assert not snap['start_available'] and 'existing operation' in snap['application_error']
        controller.source_kind=None
        ui.d1_buttons[spec['mode']].invoke();commands_done(expect_error=True);pump()
        snap=observe('unrelated_error_not_cleared_after_sentinel_removed')
        assert snap['application_state']=='ERROR' and not snap['validation_recovery_available']
        assert 'cannot clear another failure' in snap['application_error'] and not snap['start_available']
        assert controller.models.asr_loads==controller.models.speaker_loads==0
        assert controller.engine is None and controller.consumer is None and not controller.session_store.active
        assert not list((root/'passage').glob('*.json')) and not list((root/'passage').glob('*.npy'))
        receipts.json('RECOVERY.json',dict(cases=cases,mode=spec['mode'],scope='pre-owner validation only',
            actual_command_queue=True,actual_controller_constructor=True,actual_ui_constructor=True,
            source_kind_sentinel=True,source_or_model_failure_tested=False,successful_start_tested=False,
            root_withdrawn=True,physical_touch=False,profile_sha256=hashlib.sha256(canonical(catalog.request(spec['mode'])).encode()).hexdigest()))
        receipts.json('LOADED_MODULES.json',dict(installed_manifest_sha256=sha(prototype/'RELEASE_MANIFEST.json'),
            verified_loaded_modules=verify_loaded(),all_origins_inside_exact_release=True))
        result=dict(status='PASS_INSTALLED_D1_PREOWNER_VALIDATION_RECOVERY_ONLY',changed_cases=len(cases),
            actual_controller_constructor=True,actual_ui_constructor=True,actual_command_queue=True,
            generic_state_status_error_checked=True,method_failure_recovers=True,unknown_failure_not_cleared=True,
            model_worker_created=False,source_samples=0,output_frames=0,successful_start_tested=False,
            live_start_available=False,capture=False,ASR=False,visible_rendering=False,physical_touch=False,
            native_failure_stress=False,new_speedup_claim=False,accuracy_claim=False,original_rc5_concurrent=True)
    finally:
        if controller is not None:
            controller.d1_cancel.set()
            controller.close()
            deadline = time.monotonic()+65
            while controller.commands.unfinished_tasks and time.monotonic() < deadline:time.sleep(.01)
            controller.worker.join(1)
            assert controller.closed and not controller.worker.is_alive() and not controller.d1_owned
            assert not controller.owner._ownership.owned and not (root/'data/runtime.lock').exists()
            result.update(controller_closed=True, command_worker_joined=True, application_lease_released=True)
        if ui is not None:ui._closed = True
        if tkroot is not None:tkroot.destroy();result['Tk_destroyed'] = True
        cm.atomic_json = original_atomic
    directories = sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_dir())
    allowed = sorted(['code', 'control', 'outer', 'outer/logs', 'outer/telemetry', 'outer/receipts',
        'outer/failure', 'outer/closure_reserve', 'passage', 'passage_closure', 'app_receipts', 'app_failure',
        'data', 'data/people', 'data/conversations'])
    assert directories == allowed, directories
    dirs = [root/n for n in ['passage', 'passage_closure', 'app_receipts', 'app_failure', 'data', 'data/people', 'data/conversations']]
    assert sum(max(p.stat().st_size, p.stat().st_blocks*512) for p in dirs) <= admission['application_directory_reserve_bytes']
    assert {p.name for p in (root/'data').iterdir()} == {'DATA_SCHEMA.json', '.budget.guard', '.runtime.guard', 'people', 'conversations'}
    assert not list((root/'data/people').iterdir()) and not list((root/'data/conversations').iterdir())
    receipts.json('APPLICATION_CLOSURE.json', dict(controller_closed=True, command_worker_joined=True,
        model_worker_created=False, source_samples=0, application_lease_released=True, Tk_destroyed=True, directories=directories))
    return result
