"""Installed visible GUI/archive diagnostic; see README_FIELD_VISIBLE_V1.md."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def inventory(root):
    return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()}


def run(root,admission):
    installed=Path(admission['installed_release']);source=Path(admission['archive_source'])
    before=inventory(source);code_before=inventory(installed)
    assert before==admission['archive_files'] and code_before==admission['installed_files']
    data=root/'data';data.mkdir();(data/'conversations').mkdir()
    identifier=source.name;copied=data/'conversations'/identifier
    shutil.copytree(source,copied)
    assert inventory(copied)==before
    for name in ['N2_RUNTIME_BACKUP.json','LIVE_CONFIG_BACKUP.json']:
        shutil.copyfile(root/name,data/('n2_runtime.json' if name.startswith('N2') else 'live_config.json'))
    canary=data/'people-preservation-canary.bin';canary.write_bytes(b'PRIVATE_SYNTHETIC_CANARY_NO_ENROLLMENT\n')
    launch=dict(release_manifest_sha256=sha(installed/'RELEASE_MANIFEST.json'),autonomous_quiet_authorized=True,
                expires_unix=time.time()+180,data_root=str(data.resolve()),scope='Visible GUI/archive only; no Start confirmation or audio playback')
    (root/'GUI_LAUNCH.json').write_text(json.dumps(launch,indent=2))
    sys.path[:0]=[str(installed),str(installed/'vendor'),str(installed/'native')]
    from native import field_entry_v1 as entry
    from app import ui as ui_module
    from app.sessions import SessionStore
    import tkinter as tk
    expected=SessionStore(data).rows(identifier)
    assert len(expected)==40
    observations=[];steps=[];issues=[];errors=[];holder={}
    original=ui_module.PrototypeUI

    class DiagnosticUI(original):
        # Only schedules the diagnostic. Production construction/rendering/actions remain inherited.
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);holder['ui']=self
            self.root.report_callback_exception=lambda cls,value,tb:failed(RuntimeError(str(value)))
            self.root.after(700,advance)

    def ui():return holder['ui']
    def sync():
        u=ui();u.controller.commands.join();u.snapshot=u.controller.snapshot();u.root.update_idletasks()
        assert u.controller.engine is None and u.controller.models.asr_loads==u.controller.models.speaker_loads==0
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    def invoke(key):
        button=ui().actions[key];assert button.winfo_exists() and str(button.cget('state'))=='normal'
        button.invoke()
    def capture(name):
        sync();u=ui();u.root.update_idletasks()
        controls={k:dict(text=str(v.cget('text')),state=str(v.cget('state')),mapped=bool(v.winfo_ismapped()))
                  for k,v in u.actions.items() if v.winfo_exists()}
        record=dict(stage=name,page=u.page,mapped=bool(u.root.winfo_ismapped()),viewable=bool(u.root.winfo_viewable()),
                    window_state=u.root.state(),geometry=u.root.winfo_geometry(),x=u.root.winfo_rootx(),y=u.root.winfo_rooty(),
                    width=u.root.winfo_width(),height=u.root.winfo_height(),screen=[u.root.winfo_screenwidth(),u.root.winfo_screenheight()],
                    error=u.snapshot.get('error'),state=u.snapshot['state'],controls=controls)
        assert record['mapped'] and record['viewable']
        if [record['width'],record['height']]!=[480,800]:
            issues.append(dict(kind='client_size_not_480x800',stage=name,width=record['width'],height=record['height']))
        if record['x']<0 or record['y']<0 or record['x']+480>record['screen'][0] or record['y']+800>record['screen'][1]:
            issues.append(dict(kind='client_extends_outside_display',stage=name,geometry=record['geometry'],x=record['x'],y=record['y']))
        shot=root/(name+'.png')
        subprocess.run(['scrot','--overwrite',str(shot)],check=True,timeout=10)
        assert shot.stat().st_size<4*1024**2
        record.update(screenshot=shot.name,screenshot_sha256=sha(shot));observations.append(record)
    def failed(exc):
        errors.append(type(exc).__name__+': '+str(exc));ui().close()
    def advance():
        if errors:return
        try:
            if not steps:ui().close();return
            name,action=steps.pop(0);action();sync()
            with (root/'ACTIONS.jsonl').open('a') as f:f.write(json.dumps(dict(action=name,complete=True))+'\n')
            ui().root.after(350,advance)
        except Exception as exc:failed(exc)
    def mode_check():
        capture('modes');u=ui()
        issues.extend(dict(kind='unavailable_mode_button_enabled',key=k,text=str(v.cget('text')))
                      for k,v in u.actions.items() if k.startswith('mode_') and k!='mode_open_with_names' and v.winfo_exists() and str(v.cget('state'))=='normal')
    def backend_check():
        capture('backends');u=ui()
        for b in u.snapshot['backends']:
            key='backend_'+b['key']
            if not b['available'] and key in u.actions:
                widget=u.actions[key]
                if 'implemented' in str(widget.cget('text')) or str(widget.cget('state'))=='normal':
                    issues.append(dict(kind='unavailable_backend_label_or_enabled_control',key=key,text=str(widget.cget('text')),state=str(widget.cget('state'))))
    def negative_mode():
        invoke('mode_caption_only');sync()
        assert ui().controller.mode=='open_with_names' and ui().controller.error
        capture('mode_rejected')
    def open_copied():
        ui().show_session(identifier);invoke('session_open');sync()
        assert ui().controller.session_rows==expected
        ui().home();ui()._render_rows(ui().snapshot['rows'],force=True)
    def check_rows():
        capture('reopened_captions')
        assert len(ui()._row_cache)==40
    def rename():
        ui().show_session(identifier);invoke('session_rename')
        ui().keyboard_value.delete('1.0','end');ui().keyboard_value.insert('1.0','Private visible archive control copy')
        invoke('keyboard_done');sync()
        assert ui().controller.session_store.metadata(identifier)['title']=='Private visible archive control copy'
    def pin():
        ui().show_session(identifier);invoke('session_pin');sync()
        assert ui().controller.session_store.metadata(identifier)['pinned']
    def export_text():
        ui()._session_export(identifier,False);invoke('confirm')
        ui().keyboard_value.delete('1.0','end');ui().keyboard_value.insert('1.0',str(root/'private-text-export.zip'))
        invoke('keyboard_done');sync()
        with zipfile.ZipFile(root/'private-text-export.zip') as z:
            assert set(z.namelist())=={'transcript.jsonl','user_annotations.json','EXPORT_NOTICE.txt'}
            rows=[json.loads(x) for x in z.read('transcript.jsonl').splitlines()]
            assert len(rows)==len(expected)
            for actual,ref in zip(rows,expected):
                assert actual['raw_asr']==ref.get('text') and actual['formatted']==ref.get('display_text')
                assert actual['source_start_sample']==ref['source_start_sample'] and actual['source_end_sample']==ref['source_end_sample']
    def delete_copy():
        # Preserve the exact pre-delete copy as a private ZIP; only the diagnostic store is deleted.
        ui().controller.session_store.export(identifier,root/'pre-delete-copy.zip',include_audio=True,consent=True)
        ui().show_session(identifier);invoke('session_delete');assert ui().page=='consent';invoke('confirm');sync()
        assert not copied.exists() and canary.read_bytes()==b'PRIVATE_SYNTHETIC_CANARY_NO_ENROLLMENT\n'
        assert inventory(source)==before
    def start_cancel():
        ui().home();invoke('start_stop');assert ui().page=='consent';capture('start_consent');invoke('cancel')
        assert ui().controller.engine is None
    steps.extend([
        ('idle_visible',lambda:capture('idle')),('Start_consent_cancel',start_cancel),
        ('modes_visible',lambda:ui().show_modes()),('modes_inventory',mode_check),('unavailable_mode_rejected',negative_mode),
        ('backends_visible',lambda:ui().show_backends()),('backend_inventory',backend_check),
        ('open_copied_archive',open_copied),('visible_40_rows',check_rows),('rename_copy',rename),('save_pin_copy',pin),
        ('export_private_text',export_text),('delete_copied_archive',delete_copy),('post_delete_visible',lambda:capture('after_delete'))])
    issues.append(dict(kind='conversation_import_unavailable',evidence='SessionUI has no import action; no import receipt claimed'))
    ui_module.PrototypeUI=DiagnosticUI
    prior_argv=sys.argv[:]
    try:
        sys.argv=[str(installed/'main.py'),'gui','--data-root',str(data),'--launch-admission',str(root/'GUI_LAUNCH.json')]
        code=entry.main()
    finally:
        sys.argv=prior_argv;ui_module.PrototypeUI=original
    assert inventory(source)==before and inventory(installed)==code_before
    if errors:raise RuntimeError('; '.join(errors))
    assert code==0 and not steps and ui().controller.closed and not ui().controller.worker.is_alive()
    result=dict(status='INSTALLED_VISIBLE_GUI_ARCHIVE_OBSERVATIONS_ONLY',observations=observations,issues=issues,
                archive_rows=40,source_unchanged=True,installed_code_unchanged=True,model_loads=0,capture_opened=False,
                physical_touch=False,field_release_accepted=False,actual_installed_gui_entry=True,production_ui_overrides='constructor scheduling only',
                controller_closed=True,source_hashes=before,installed_hashes=code_before)
    (root/'VISIBLE_RESULT.json').write_text(json.dumps(result,indent=2))
    return result
