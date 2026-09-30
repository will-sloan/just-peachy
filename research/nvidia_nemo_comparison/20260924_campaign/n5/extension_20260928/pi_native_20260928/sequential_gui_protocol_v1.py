"""Actual controller/withdrawn GUI plus model cancellation protocol; README_SEQUENTIAL_GUI_V1.md."""
import json
from pathlib import Path
import sys
import time


def run(root,admission):
    prototype=Path(admission['prototype']);sys.path[:0]=[str(prototype),str(prototype/'vendor')]
    from app.controller import Controller
    from app.ui import PrototypeUI
    from sequential_controller_v1 import controller_class,sha,write
    from sequential_ui_v1 import ui_class
    import tkinter
    C=controller_class(Controller,root,admission);controller=None;tkroot=None;result={};began=time.monotonic()
    try:
        controller=C(root/'data',Path.home()/'JustPeachy/install/models',saved_audio_only=True)
        tkroot=tkinter.Tk(screenName=':0');tkroot.withdraw()
        tkroot.tk.eval('rename wm jp_original_wm; proc wm {args} {if {[lindex $args 0] eq "deiconify" || ([lindex $args 0] eq "state" && [llength $args] > 2 && [lindex $args 2] ne "withdrawn")} {error "visible windows forbidden"}; return [uplevel 1 [linsert $args 0 jp_original_wm]]}')
        errors=[];tkroot.report_callback_exception=lambda k,v,t:errors.append(k.__name__+': '+str(v))
        ui=ui_class(PrototypeUI)(tkroot,controller,allow_auto_start=False)
        ui.actions['sequential_open'].invoke()
        def pump():
            tkroot.update();ui._page_update()
            assert tkroot.state()=='withdrawn' and not tkroot.winfo_ismapped() and not errors,errors
            if time.monotonic()-began>245:raise TimeoutError('GUI protocol deadline')
        def wait(predicate):
            while True:
                pump();value=controller.seq_snapshot()
                if predicate(value):return value
                if not value['owned'] and value['phase'].endswith('_FAILED'):raise RuntimeError(str(value))
                time.sleep(.02)
        def invoke(action):
            pump();button=ui.seq_widgets['controls'][action];assert str(button.cget('state'))=='normal'
            button.invoke();controller.commands.join();assert not controller.error,controller.error;pump()
        # Real queued controller rejects refinement without a completed primary.
        controller.seq_action('refine');controller.commands.join();assert 'primary transcript' in controller.error
        assert not any(x.is_dir() for x in controller.seq_root.iterdir())
        invoke('start');wait(lambda s:s['publications']>=2)
        controller.seq_action('start');controller.commands.join();assert 'owns a model' in controller.error
        controller.switch(mode='caption_only');controller.commands.join();assert 'owns a model' in controller.error
        primary=wait(lambda s:not s['owned'] and s['phase']=='PRIMARY_READY')
        controller.seq_thread.join(2);assert not controller.seq_thread.is_alive()
        # Terminal success clears prior rejected-control notices, without a second model job.
        assert controller.error is None
        invoke('save');saved_primary=controller.seq_snapshot()['saved'];primary_artifact=primary['primary']
        primary_hashes={key:sha(primary_artifact[key]) for key in ['result','events']}
        invoke('refine');wait(lambda s:s['publications']>=1)
        cancel_start=time.monotonic();invoke('cancel')
        cancelling=dict(controller.seq_cancel_receipts[-1]);assert cancelling['phase']=='CANCELLING' and cancelling['owned']
        cancelled=wait(lambda s:not s['owned'] and s['phase']=='REFINEMENT_CANCELLED');controller.seq_thread.join(2)
        assert cancelled['primary']==primary_artifact and cancelled['refined'] is None and not cancelled['refined_text']
        cancel_seconds=time.monotonic()-cancel_start
        invoke('save');saved_cancelled=controller.seq_snapshot()['saved']
        invoke('refine');complete=wait(lambda s:not s['owned'] and s['phase']=='COMPLETE');controller.seq_thread.join(2)
        assert complete['primary']==primary_artifact and complete['refined'] and complete['primary_text'] and complete['refined_text']
        assert not controller.seq_thread.is_alive();invoke('save');saved_complete=controller.seq_snapshot()['saved']
        before=controller.seq_snapshot();invoke('open');after=controller.seq_snapshot();assert before==after
        assert ui.seq_widgets['primary'].cget('text')=='Primary (Sherpa):\n'+after['primary_text']
        assert ui.seq_widgets['refined'].cget('text')=='Refinement (Nemotron):\n'+after['refined_text']
        # New malformed copy is rejected; preserved valid archives remain unchanged.
        bad=controller.seq_root/'bad-source';bad.mkdir();bad_value=json.loads(Path(saved_complete).read_text());bad_value['source_sha256']='0'*64
        write(bad/'SAVED.json',bad_value)
        controller.seq_action('open',path=str(bad/'SAVED.json'));controller.commands.join();assert 'mismatch' in controller.error
        assert controller.seq_snapshot()==after
        controller.seq_action('start',source_sha256='0'*64);controller.commands.join();assert 'binding changed' in controller.error
        assert controller.seq_snapshot()==after
        invoke('open')
        for key,h in primary_hashes.items():assert sha(primary_artifact[key])==h
        assert controller.engine is None and controller.consumer is None
        assert controller.models.asr_loads==controller.models.speaker_loads==0
        result=dict(status='SEQUENTIAL_CONTROLLER_GUI_COLLECTED_REVIEW_REQUIRED',history=controller.seq_history,
                    source_sha256=after['source_sha256'],saved_primary=saved_primary,saved_cancelled=saved_cancelled,saved_complete=saved_complete,
                    cancel_return_seconds=cancel_seconds,cancelling_owned_snapshot=cancelling,primary_immutable=True,
                    completed_snapshot=after,reopened_exact=True,rejected_controls=5,callback_errors=errors,
                    base_model_loads=0,models_in_separate_processes=True,root_withdrawn=True,capture=False,diarizer_loaded=False,
                    actual_controller_and_widgets=True,physical_gui=False,accuracy_scored=False)
        write(root/'GUI_SNAPSHOT.json',dict(primary_text=ui.seq_widgets['primary'].cget('text'),refined_text=ui.seq_widgets['refined'].cget('text'),phase=ui.seq_widgets['state'].cget('text')))
    finally:
        if controller is not None:
            controller.close();controller.commands.join();controller.worker.join(35)
            assert controller.closed and not controller.worker.is_alive() and (controller.seq_thread is None or not controller.seq_thread.is_alive())
            result['controller_closed']=True
        if tkroot is not None:tkroot.destroy();result['Tk_destroyed']=True
    return result
