"""One actual installed UI selection/Start/Stop passage; README_D1_PROCESS_LAUNCH_V1.md."""
import hashlib
import json
from pathlib import Path
import sys
import time


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f, 'sha256').hexdigest()


def run(root, admission, request, registry):
    from field_sidecar_budget_v1 import GroupWriter
    from d1_process_entry_v1 import controller_class
    from d1_recovery_process_v1 import ui_class
    from d1_method_controls_v1 import MethodCatalog, canonical
    root = Path(root)
    spec = registry.specification(request)
    spec['stop_after_samples'] = admission['stop_after_samples']
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
    assert spec['mode'] == admission['admitted_mode'] == 'streaming' and spec['stop_after_samples'] == 19200
    for item in spec['saved_application_evidence'].values():
        receipt = Path(item['path'])
        assert sha(receipt) == item['sha256'] and json.loads(receipt.read_bytes())['status'] == 'PASS_INSTALLED_D1_SAVED_SELECTION_START_STOP_ONLY'
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
    C = controller_class(cm.Controller, root, request, registry, writer, closer, failure, catalog)
    from d1_process_entry_v1 import claim_process
    try:claim_process(request, registry)
    except RuntimeError as exc:assert str(exc)=='Start a fresh process for another diarizer run'
    else:raise AssertionError('Process binding was not latched')
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
        assert selection['application_state']=='IDLE' and selection['application_error'] is None
        assert canonical(selection['implemented_methods'])==canonical(catalog.request(spec['mode']))
        ui.d1_buttons['start'].invoke();commands_done()
        while controller.d1_snapshot()['samples'] < spec['stop_after_samples']:
            pump();s = controller.d1_snapshot()
            assert not s['error'], s
            time.sleep(.005)
        before = controller.d1_snapshot()
        assert before['application_state'] == before['phase'] == 'RUNNING'
        assert before['owned'] and controller.owner._ownership.owned and controller.d1_thread.is_alive()
        assert str(ui.d1_buttons['stop'].cget('state')) == 'normal'
        ui.d1_buttons['stop'].invoke()
        # Public Stop requests cancellation; the command thread must join before release.
        commands_done();pump()
        after = controller.d1_snapshot()
        assert not after['owned'] and after['phase'] == after['application_state'] == 'STOPPED' and not after['error'] and after['application_error'] is None
        phases=[x['phase'] for x in controller.d1_transitions]
        assert phases == ['STARTING','RUNNING','STOPPING','AWAITING_JOIN','STOPPED'], phases
        assert all(x['phase']==x['application_state'] for x in controller.d1_transitions)
        assert all(x['owned'] for x in controller.d1_transitions[:-1]) and not controller.d1_transitions[-1]['owned']
        assert not controller.d1_thread.is_alive() and controller.owner._ownership.owned
        assert ui.d1_status.cget('text').startswith('STOPPED / ')
        assert str(ui.d1_buttons['start'].cget('state')) == str(ui.d1_buttons['stop'].cget('state')) == 'disabled'
        out = controller.d1_outcome
        assert spec['stop_after_samples'] <= out['source_samples'] < spec['prefix_samples'] and out['stop_requested']
        assert out['source_position'] == out['source_samples'] and out['pre_eof_frames'] > 0
        assert out['pre_eof_max_abs'] <= spec['tolerance'] and out['session_id'] == spec['session_id']
        assert out['native_checks'].count('actual_c_abi_before_create') == 1
        assert out['native_checks'].count('actual_mapped_libraries') == 2
        assert out['native_checks'].count('actual_asset_bytes') == 1
        assert controller.models.asr_loads == controller.models.speaker_loads == 0
        assert controller.engine is None and controller.consumer is None and not controller.session_store.active
        # Store one complete profile and exact hashes of the other two snapshots.
        def compact_snapshot(snapshot):
            value=dict(snapshot);profile=value.pop('implemented_methods')
            assert canonical(profile)==canonical(selection['implemented_methods'])
            value['implemented_methods_sha256']=hashlib.sha256(canonical(profile).encode()).hexdigest()
            return value
        receipts.json('GUI_STOP.json', dict(selection=selection, before_stop=compact_snapshot(before), after_stop=compact_snapshot(after),
            status_text=ui.d1_status.cget('text'), model_worker_joined=True, application_lease_still_owned=True,
            root_withdrawn=True, physical_touch=False, transitions=controller.d1_transitions, entry_request=request))
        receipts.json('LOADED_MODULES.json', dict(installed_manifest_sha256=sha(prototype/'RELEASE_MANIFEST.json'),
            verified_loaded_modules=verify_loaded(), all_origins_inside_exact_release=True))
        result = dict(status='PASS_FRESH_PROCESS_STREAMING_ENTRY_START_STOP_ONLY', mode=spec['mode'], passage=out,
            actual_controller_constructor=True, actual_ui_constructor=True, actual_buttons=True,
            method_profile_bound=True, generic_state_transitions=controller.d1_transitions, mode_entry_request=request, method_base_fixture=False, second_process_binding_rejected=True,
            saved_source_closed=True, model_worker_joined=True, request_is_fixture=False,
            live_start_available=False, capture=False, ASR=False, visible_rendering=False, physical_touch=False,
            native_failure_stress=False, new_speedup_claim=False, accuracy_claim=False, original_rc5_concurrent=True)
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
        'data', 'data/people', 'data/conversations', 'launch_meta', 'launch_logs'])
    assert directories == allowed, directories
    dirs = [root/n for n in ['passage', 'passage_closure', 'app_receipts', 'app_failure', 'data', 'data/people', 'data/conversations']]
    assert sum(max(p.stat().st_size, p.stat().st_blocks*512) for p in dirs) <= admission['application_directory_reserve_bytes']
    assert {p.name for p in (root/'data').iterdir()} == {'DATA_SCHEMA.json', '.budget.guard', '.runtime.guard', 'people', 'conversations'}
    assert not list((root/'data/people').iterdir()) and not list((root/'data/conversations').iterdir())
    receipts.json('APPLICATION_CLOSURE.json', dict(controller_closed=True, command_worker_joined=True,
        model_worker_joined=True, application_lease_released=True, Tk_destroyed=True, directories=directories))
    return result
