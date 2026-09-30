"""Installed visible GUI/archive diagnostic; see README_FIELD_VISIBLE_V3.md."""
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
    prior=Path(admission['installed_release']);source=Path(admission['archive_source'])
    assert inventory(prior)==admission['installed_files']
    build_source=root/'source';shutil.copytree(prior,build_source,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copyfile(root/'field_entry_v2.py',build_source/'native/field_entry_v2.py')
    shutil.copyfile(root/'README_FIELD_VISIBLE_V3.md',build_source/'docs/README_FIELD_VISIBLE_V3.md')
    (build_source/'main.py').write_text('from native.field_entry_v2 import main\nif __name__=="__main__":raise SystemExit(main())\n')
    sys.path.insert(0,str(build_source))
    from release_tools import release
    built=release.build(build_source,root/'archives','b01-offline-20260930-v2')
    staged=release.stage(built['archive'],root/'deployment',built['sha256'])
    installed=Path(staged['path'])
    (root/'CANDIDATE_BUILD.json').write_text(json.dumps(dict(built=built,staged=staged),indent=2))
    before=inventory(source);code_before=inventory(installed)
    assert before==admission['archive_files']
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
    from native import field_entry_v2 as entry
    from app import ui as ui_module
    from app.sessions import SessionStore
    import tkinter as tk
    expected=SessionStore(data).rows(identifier)
    assert len(expected)==4  # Four raw utterances expand into40 displayed segments.
    reference=Path(admission['display_reference']);assert sha(reference)==admission['display_reference_sha256']
    display_reference=json.loads(reference.read_text())['rows']
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
        subprocess.run(['grim',str(shot)],check=True,timeout=10)
        assert shot.stat().st_size<4*1024**2
        record.update(screenshot=shot.name,screenshot_sha256=sha(shot));observations.append(record)
        (root/('VISUAL_'+name+'.json')).write_text(json.dumps(record,indent=2))
    def failed(exc):
        import traceback
        errors.append(type(exc).__name__+': '+str(exc))
        (root/'CALLBACK_FAILURE.txt').write_text(traceback.format_exc())
        ui().close()
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
        button=ui().actions['mode_caption_only'];assert str(button.cget('state'))=='disabled'
        button.invoke();sync();assert ui().controller.mode=='open_with_names' and not ui().controller.error
        capture('mode_disabled')
    def other_availability():
        u=ui();u.show_advanced()
        for key,button in u.actions.items():
            if key.startswith('mode_') and key!='mode_open_with_names' and button.winfo_exists():assert str(button.cget('state'))=='disabled'
        u.show_recipes();capture('recipes')
        for key,button in u.actions.items():
            if ((key.startswith('recipe_') and key!='recipe_balanced') or (key.startswith('tap_') and key!='tap_O0')) and button.winfo_exists():assert str(button.cget('state'))=='disabled'
        u.enrollment_form('Diagnostic unused name');assert u.page!='enrollment' and 'unavailable' in u._notice
    def open_copied():
        ui().show_session(identifier);invoke('session_open');sync()
        actual=list(ui().controller.rows.values());assert len(actual)==len(expected)==4
        for row,raw in zip(actual,expected):
            for key in ['caption_key','text','display_text','source_start_sample','source_end_sample','archive_epoch_id']:
                assert row.get(key)==raw.get(key),key
        assert len(ui().controller.session_rows)==4
        for link,raw in zip(ui().controller.session_rows,expected):
            assert link['start']==raw['source_start_sample'] and link['end']==raw['source_end_sample']
        ui().home();ui()._render_rows(ui().snapshot['rows'],force=True)
    def check_rows():
        capture('reopened_captions')
        assert len(ui()._row_cache)==40
        fields=['id','caption_key','utterance_id','raw_asr_text','provisional_display_text','final_punctuated_display_text','label','final','profile_id','track_id','span_ids','source_start_sec','source_end_sec','timing_kind','word_spans','speaker_revision','first_shown_label','identity_version']
        current=ui().snapshot['rows'];assert len(current)==len(display_reference)==40
        for row,ref in zip(current,display_reference):assert {k:row.get(k) for k in fields}=={k:ref.get(k) for k in fields}
        widgets=[]
        for row in current:
            rid=str(row['id']);label,caption,selected=ui()._row_cache[rid]
            start,end=ui()._marks[rid];actual=ui().caption_text.get(start,end)
            assert caption in actual
            widgets.append(dict(id=rid,label=label,caption=caption,actual=actual))
        (root/'WIDGET_ROWS.json').write_text(json.dumps(widgets,indent=2))
        (root/'OPENED_SNAPSHOT.json').write_text(json.dumps(ui().snapshot,indent=2))
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
        ('modes_visible',lambda:ui().show_modes()),('modes_inventory',mode_check),('unavailable_mode_disabled',negative_mode),
        ('backends_visible',lambda:ui().show_backends()),('backend_inventory',backend_check),
        ('advanced_recipe_enrollment_unavailable',other_availability),
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
                physical_touch=False,field_release_accepted=False,actual_installed_gui_entry=True,installed_release=str(installed),prior_release_unchanged=inventory(prior)==admission['installed_files'],production_ui_overrides='constructor scheduling only',
                controller_closed=True,source_hashes=before,installed_hashes=code_before)
    (root/'VISIBLE_RESULT.json').write_text(json.dumps(result,indent=2))
    return result
