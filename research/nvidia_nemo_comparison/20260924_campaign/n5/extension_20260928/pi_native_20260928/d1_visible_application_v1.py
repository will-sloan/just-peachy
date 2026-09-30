"""Actual installed controls, visible without source/model Start. See README_D1_VISIBLE_ENTRY_V1.md."""
import hashlib
import json
from pathlib import Path
import sys
import time


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def run(root,admission,request,registry):
    from field_sidecar_budget_v1 import GroupWriter
    from d1_process_entry_v1 import controller_class
    from d1_method_controls_v1 import MethodCatalog,canonical
    from d1_visible_controls_v1 import preview_ui,visible,check_box,snapshot
    root=Path(root);spec=registry.specification(request)
    for pin in spec['method_binding'].values():
        assert Path(pin['path']).stat().st_size==pin['bytes'] and sha(pin['path'])==pin['sha256']
    catalog=MethodCatalog(spec['method_binding']['contract']['path'],spec['method_binding']['evidence']['path'])
    prototype=Path(spec['prototype'])
    for rel,h in spec['installed_files'].items():assert sha(prototype/rel)==h
    for item in spec['saved_application_evidence'].values():
        assert sha(item['path'])==item['sha256']
        assert json.loads(Path(item['path']).read_bytes())['status']=='PASS_INSTALLED_D1_SAVED_SELECTION_START_STOP_ONLY'
    for name in ('passage','passage_closure','app_receipts','app_failure','data'):(root/name).mkdir()
    writer=GroupWriter(root/'passage',admission['passage_limits'])
    closer=GroupWriter(root/'passage_closure',admission['passage_closure_limits'])
    receipts=GroupWriter(root/'app_receipts',admission['app_receipt_limits'])
    failure=GroupWriter(root/'app_failure',admission['app_failure_limits'])
    images=GroupWriter(root/'visual_images',admission['visual_image_limits'])
    metadata=GroupWriter(root/'visual_meta',admission['visual_metadata_limits'])
    GroupWriter(root/'data',admission['app_receipt_limits']).json('DATA_SCHEMA.json',{'schema_version':1})
    sys.path[:0]=[str(prototype),str(prototype/'vendor'),str(prototype/'native')]
    import app.controller as cm
    import app.ui as um
    import app.paths as paths
    assert Path(cm.__file__).resolve()==prototype/'app/controller.py'
    assert Path(um.__file__).resolve()==prototype/'app/ui.py' and Path(paths.ROOT).resolve()==prototype
    installed={row['path']:row for row in json.loads((prototype/'RELEASE_MANIFEST.json').read_bytes())['files']}
    def verify_loaded():
        names=[]
        for name,module in tuple(sys.modules.items()):
            if name.split('.')[0] not in ('app','edge_speech_pipeline','release_tools','field_artifact_limits_v1'):continue
            origin=getattr(module,'__file__',None)
            if origin is None:continue
            path=Path(origin).resolve();rel=path.relative_to(prototype).as_posix()
            assert path.stat().st_size==installed[rel]['bytes'] and sha(path)==installed[rel]['sha256']
            names.append(name)
        return sorted(names)
    verify_loaded()
    original_atomic=cm.atomic_json
    def bounded_close(path,value):
        if Path(path).resolve()!=root/'data/last_application.json':raise RuntimeError('Undeclared metadata writer')
        return receipts.json('last_application.json',value)
    cm.atomic_json=bounded_close
    Base=controller_class(cm.Controller,root,request,registry,writer,closer,failure,catalog)
    class InspectionController(Base):
        def d1_start(self):raise RuntimeError('This visible inspection admission cannot start a model')
        def _do_d1_start(self):raise RuntimeError('This visible inspection admission cannot start a model')
        def d1_snapshot(self):
            value=super().d1_snapshot();value['start_available']=False
            value['inspection_only']=True;return value
    controller=tkroot=ui=None;errors=[];result={};closed_by_button=False
    try:
        controller=InspectionController(root/'data',Path.home()/'JustPeachy/install/models',saved_audio_only=True)
        assert controller.owner._ownership.owned
        import tkinter as tk
        tkroot=tk.Tk(screenName=':0');tkroot.withdraw()
        tkroot.report_callback_exception=lambda k,v,t:errors.append(k.__name__+': '+str(v))
        ui=preview_ui(um.PrototypeUI,spec['mode'])(tkroot,controller,allow_auto_start=False)
        controller.d1_select(spec['mode'])
        deadline=time.monotonic()+10
        while controller.commands.unfinished_tasks:
            tkroot.update();assert not errors
            if time.monotonic()>deadline:raise TimeoutError('Selection did not finish')
            time.sleep(.005)
        selection=controller.d1_snapshot()
        assert selection['selected']['selection']['id']==spec['mode'] and not selection['start_available']
        assert canonical(selection['implemented_methods'])==canonical(catalog.request(spec['mode']))
        assert not selection['owned'] and selection['samples']==selection['frames']==0 and controller.d1_thread is None
        ui.show_preview();visible(tkroot)
        began=time.monotonic()
        while time.monotonic()-began<.6:tkroot.update();time.sleep(.01)
        boxes={n:check_box(tkroot,w) for n,w in {'notice':ui.preview_notice,'start':ui.preview_start.button,'return':ui.preview_close.button}.items()}
        assert str(ui.preview_start.button.cget('state'))=='disabled'
        assert all(str(ui.actions[k].cget('state'))=='disabled' for k in ('start_stop','mode','people','settings','rescue','backend') if k in ui.actions)
        ui.preview_start.button.invoke()
        assert controller.d1_thread is None and not controller.d1_used
        shot=snapshot(tkroot,'child',images,metadata)
        receipts.json('VISIBLE_CONTROLS.json',dict(selection=selection,rectangles=boxes,screenshot=shot,
            model_start_disabled=True,application_lease_owned=True,physical_touch=False))
        ui.preview_close.button.invoke();closed_by_button=True
        deadline=time.monotonic()+10
        while not ui._closed:
            tkroot.update()
            assert not errors,errors
            if time.monotonic()>deadline:raise TimeoutError('Return did not close actual installed UI')
            time.sleep(.005)
        controller.worker.join(1)
        assert controller.closed and not controller.worker.is_alive() and not controller.owner._ownership.owned
        assert controller.d1_thread is None and not controller.d1_used and not controller.d1_owned
        assert controller.models.asr_loads==controller.models.speaker_loads==0
        assert controller.engine is None and controller.consumer is None and not controller.session_store.active
        assert not (root/'passage/START_REQUEST.json').exists() and not (root/'data/runtime.lock').exists()
        assert 'libnemo_speech_' not in Path('/proc/self/maps').read_text() and 'libggml' not in Path('/proc/self/maps').read_text()
        receipts.json('LOADED_MODULES.json',dict(verified_loaded_modules=verify_loaded(),all_origins_inside_exact_release=True))
        result=dict(status='PASS_VISIBLE_D1_ENTRY_INSPECTION_AND_RETURN_ONLY',mode=spec['mode'],mode_entry_request=request,
            actual_controller_constructor=True,actual_ui_constructor=True,visible_rendering=True,physical_touch=False,
            source_samples=0,frames=0,model_start_available=False,model_loaded=False,capture=False,ASR=False,
            selected_profile_sha256=hashlib.sha256(canonical(selection['implemented_methods']).encode()).hexdigest(),
            actual_return_button=True,Tk_destroyed=ui._closed,command_worker_joined=True,application_lease_released=True,
            child_screenshot=shot,native_failure_stress=False,new_speedup_claim=False,accuracy_claim=False)
    finally:
        if controller is not None and not controller.closed:
            controller.close();controller.worker.join(5)
            assert controller.closed and not controller.worker.is_alive() and not controller.owner._ownership.owned
        if tkroot is not None and (ui is None or not ui._closed):
            if ui is not None:ui._closed=True
            tkroot.destroy()
        cm.atomic_json=original_atomic
    directories=sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_dir())
    allowed=sorted(['code','control','outer','outer/logs','outer/telemetry','outer/receipts','outer/failure','outer/closure_reserve',
        'passage','passage_closure','app_receipts','app_failure','data','data/people','data/conversations','launch_meta','launch_logs','visual_images','visual_meta'])
    assert directories==allowed,directories
    assert not list((root/'data/people').iterdir()) and not list((root/'data/conversations').iterdir())
    receipts.json('APPLICATION_CLOSURE.json',dict(controller_closed=True,command_worker_joined=True,
        no_model_worker_created=True,application_lease_released=True,Tk_destroyed=True,actual_return_button=closed_by_button,directories=directories))
    return result
