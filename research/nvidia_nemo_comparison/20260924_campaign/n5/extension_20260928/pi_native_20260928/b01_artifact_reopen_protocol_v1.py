"""Copied archive controller/widget protocol; README_B01_ARTIFACT_REOPEN_V1.md."""
import hashlib
import json
import sys
import time
from pathlib import Path


def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run_protocol(root, admission):
    for name,digest in admission['original_conversations'].items():
        assert sha(root/'data/conversations'/name)==digest
    source=Path(admission['prototype']);sys.path[:0]=[str(source),str(source/'vendor')]
    from app.controller import Controller
    from app.backends import backend_catalog
    from app.ui import PrototypeUI
    import tkinter
    from dataclasses import replace
    controller=None;tkroot=None;result={}
    try:
        controller=Controller(root/'data',Path.home()/'JustPeachy/install/models',saved_audio_only=True)
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        selected=next(x['id'] for x in backend_catalog() if x['key']=='nemotron_hybrid')
        controller.select_backend(selected);controller.commands.join()
        controller.switch(mode='open_with_names',recipe='balanced',tap='O0');controller.commands.join()
        assert not controller.error,controller.error
        identifier=next((root/'data/conversations').iterdir()).name
        tkroot=tkinter.Tk(screenName=':0');tkroot.withdraw()
        tkroot.tk.eval('rename wm jp_original_wm; proc wm {args} {if {[lindex $args 0] eq "deiconify" || ([lindex $args 0] eq "state" && [llength $args] > 2 && [lindex $args 2] ne "withdrawn")} {error "visible windows forbidden"}; return [uplevel 1 [linsert $args 0 jp_original_wm]]}')
        errors=[];tkroot.report_callback_exception=lambda kind,value,trace:errors.append(kind.__name__+': '+str(value))
        ui=PrototypeUI(tkroot,controller,allow_auto_start=False)
        controller.session_action('open',identifier=identifier);controller.commands.join()
        assert not controller.error,controller.error
        controller.session_action('save',identifier=identifier);controller.commands.join()
        assert not controller.error and controller.session_store.metadata(identifier)['pinned']
        controller.session_action('open',identifier=identifier);controller.commands.join()
        assert not controller.error,controller.error
        until=time.monotonic()+1.4
        while time.monotonic()<until:
            tkroot.update();assert tkroot.state()=='withdrawn' and not tkroot.winfo_ismapped();time.sleep(.03)
        opened=controller.snapshot();expected=json.loads((root/'FINAL_SNAPSHOT.json').read_text())
        assert len(opened['rows'])==len(expected['rows'])==40
        # Stable row fields are the user-visible/history contract. Runtime clocks and review annotations differ.
        fields=['id','caption_key','utterance_id','raw_asr_text','provisional_display_text','final_punctuated_display_text',
                'label','final','profile_id','track_id','span_ids','source_start_sec','source_end_sec','timing_kind',
                'word_spans','speaker_revision','first_shown_label','identity_version']
        for old,new in zip(expected['rows'],opened['rows'],strict=True):
            assert {k:old.get(k) for k in fields}=={k:new.get(k) for k in fields},old['id']
        ui.poll();ui._flush_rows();ui._render_rows(opened['rows'],force=True);tkroot.update()
        widgets=[]
        for row in opened['rows']:
            rid=str(row['id']);label,caption,_=ui._row_cache[rid]
            actual=ui.caption_text.get(*ui._marks[rid]);assert actual==(label+'\n' if label else '')+caption+'\n\n'
            widgets.append(dict(id=rid,label=label,caption=caption,actual_text=actual))
        assert not errors and controller.engine is None and controller.consumer is None
        loads={k:getattr(controller.models,k,None) for k in ('asr_loads','speaker_loads','punctuation_loads')}
        assert loads['asr_loads']==loads['speaker_loads']==0
        for name,digest in admission['original_conversations'].items():
            assert sha(Path(admission['parent_run'])/'data/conversations'/name)==digest
            if name.endswith(('.jsonl','.f32le','.wav')):assert sha(root/'data/conversations'/name)==digest
        with (root/'OPENED_SNAPSHOT.json').open('x') as stream:json.dump(opened,stream,indent=2)
        with (root/'WIDGETS.json').open('x') as stream:json.dump(widgets,stream,indent=2)
        result.update(status='NATIVE_COPIED_COMPACT_ARCHIVE_CONTROLLER_REOPEN_REVIEW_REQUIRED',rows=40,raw_utterances=4,
                      compared_fields=fields,model_load_counts=loads,callback_errors=errors,original_unchanged=True,
                      capture=False,models=False,root_withdrawn=True,controller_save_open=True)
    finally:
        if controller is not None:
            controller.close();controller.commands.join();controller.worker.join(10)
            assert controller.closed and not controller.worker.is_alive()
            result['controller_closed']=True
        if tkroot is not None:tkroot.destroy();result['Tk_destroyed']=True
    return result
