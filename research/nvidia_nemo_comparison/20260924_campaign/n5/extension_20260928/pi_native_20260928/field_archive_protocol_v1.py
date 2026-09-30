"""Installed private import/quota/UI boundary; README_FIELD_ARCHIVE_V1.md."""
import hashlib
import json
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import time
import zipfile


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def inventory(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()}


def run(root,admission):
    prior=Path(admission['installed_release']);source=Path(admission['archive_source'])
    assert inventory(prior)==admission['installed_files'] and inventory(source)==admission['archive_files']
    build_source=root/'source';shutil.copytree(prior,build_source,ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['field_entry_v3.py','field_archive_v1.py']:shutil.copyfile(root/name,build_source/'native'/name)
    shutil.copyfile(root/'README_FIELD_ARCHIVE_V1.md',build_source/'docs/README_FIELD_ARCHIVE_V1.md')
    (build_source/'main.py').write_text('from native.field_entry_v3 import main\nif __name__=="__main__":raise SystemExit(main())\n')
    sys.path.insert(0,str(build_source))
    from release_tools import release
    built=release.build(build_source,root/'archives','b01-offline-20260930-v3')
    staged=release.stage(built['archive'],root/'deployment',built['sha256']);installed=Path(staged['path'])
    (root/'CANDIDATE_BUILD.json').write_text(json.dumps(dict(built=built,staged=staged),indent=2))
    sys.path[:0]=[str(installed),str(installed/'vendor'),str(installed/'native')]
    from native import field_entry_v3 as entry
    from field_archive_v1 import FieldArchiveStore,MANIFEST,SCHEMA,ZIP_MAX,validate_folder,rename_noreplace
    from app import ui as ui_module
    contract=json.loads((installed/'config/field_contract.json').read_text())
    export_data=root/'export-data';export_data.mkdir();(export_data/'conversations').mkdir()
    identifier=source.name;copied=export_data/'conversations'/identifier;shutil.copytree(source,copied)
    store=FieldArchiveStore(export_data,contract);summary=validate_folder(copied,identifier)
    assert summary['raw_rows']==4 and sum(summary['epochs'].values())==846807
    archive=root/'private-export.zip';store.export(identifier,archive,include_audio=True,consent=True)
    with zipfile.ZipFile(archive) as z:
        transfer=json.loads(z.read(MANIFEST))
        assert set(transfer['files'])==set(admission['archive_files'])
        assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in admission['archive_files'].items())
    negatives=[];bad=root/'negative-inputs';bad.mkdir()
    def reject(name,fn):
        try:fn()
        except (ValueError,OSError,RuntimeError,zipfile.BadZipFile) as exc:negatives.append(dict(case=name,type=type(exc).__name__,error=str(exc)))
        else:raise AssertionError('Expected rejection: '+name)
    def make(name,entries):
        path=bad/(name+'.zip')
        with zipfile.ZipFile(path,'x') as z:
            for key,value in entries:z.writestr(key,value)
        return path
    rejection_data=root/'rejections';rs=FieldArchiveStore(rejection_data,contract)
    base=json.dumps(dict(schema=SCHEMA,identifier=identifier,files={}))
    reject('consent_required',lambda:rs.import_archive(archive))
    for name,entries in [
        ('traversal',[(MANIFEST,base),('../escaped',b'x')]),
        ('absolute',[(MANIFEST,base),('/tmp/escaped',b'x')]),
        ('backslash',[(MANIFEST,base),('epochs\\escape',b'x')]),
        ('duplicate',[(MANIFEST,base),(MANIFEST,base)]),
        ('text_only_legacy', [('transcript.jsonl',b'{}\n')]),
        ('schema',[(MANIFEST,json.dumps(dict(schema='wrong',identifier=identifier,files={})))])]:
        path=make(name,entries);reject(name,lambda p=path:rs.import_archive(p,consent=True))
    link=zipfile.ZipInfo('conversation.json');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16
    path=make('symlink',[(MANIFEST,base),(link,b'/tmp/outside')]);reject('symlink',lambda:rs.import_archive(path,consent=True))
    # Central directory declares an oversized member. Rejected before decompression or staging.
    path=make('oversized',[(MANIFEST,base),('conversation.json',b'{}')]);blob=bytearray(path.read_bytes())
    pos=blob.find(b'PK\x01\x02',blob.find(b'PK\x01\x02')+4);assert pos>=0
    struct.pack_into('<I',blob,pos+24,9*1024**2);path.write_bytes(blob)
    reject('member_size',lambda:rs.import_archive(path,consent=True))
    # A complete membership declaration whose first file has the wrong digest.
    with zipfile.ZipFile(archive) as z:
        name='conversation.json';data=z.read(name)
    wrong=dict(schema=SCHEMA,identifier=identifier,files={name:dict(bytes=len(data),sha256='0'*64)})
    path=make('hash',[(MANIFEST,json.dumps(wrong)),(name,data)])
    reject('hash',lambda:rs.import_archive(path,consent=True))
    assert not list(rs.root.iterdir()) and len(list((rejection_data/'.archive-imports').glob('*/RECEIPT.json')))==1
    reject('collision',lambda:store.import_archive(archive,consent=True))
    rs.active['diagnostic-owner']=object()
    reject('active_archive',lambda:rs.import_archive(archive,consent=True));rs.active.clear()
    original_usage=rs.usage
    try:
        rs.usage=lambda:dict(bytes=512*1024**2,free_bytes=10*1024**3)
        reject('injected_quota',lambda:rs.require_space(1))
        rs.usage=lambda:dict(bytes=0,free_bytes=5*1024**3)
        reject('injected_free_floor',lambda:rs.require_space(1))
    finally:rs.usage=original_usage
    one=bad/'atomic-source';two=bad/'atomic-existing';one.mkdir();two.mkdir();(two/'canary').write_bytes(b'preserve')
    reject('atomic_no_replace',lambda:rename_noreplace(one,two));assert (two/'canary').read_bytes()==b'preserve' and one.is_dir()
    (root/'NEGATIVES.json').write_text(json.dumps(negatives,indent=2))
    assert len(negatives)==15
    data=root/'data';data.mkdir()
    for old,new in [('N2_RUNTIME_BACKUP.json','n2_runtime.json'),('LIVE_CONFIG_BACKUP.json','live_config.json')]:shutil.copyfile(root/old,data/new)
    (data/'private-preservation-canary').write_bytes(b'PRIVATE_SYNTHETIC_CANARY\n')
    launch=dict(release_manifest_sha256=sha(installed/'RELEASE_MANIFEST.json'),autonomous_quiet_authorized=True,
        expires_unix=time.time()+180,data_root=str(data.resolve()),scope='Installed import/quota/UI only. No capture, playback or models.')
    (root/'GUI_LAUNCH.json').write_text(json.dumps(launch,indent=2))
    original=ui_module.PrototypeUI;holder={};steps=[];errors=[];observations=[]
    expected=json.loads(Path(admission['display_reference']).read_text())['rows']
    class ScheduledUI(original):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw);holder['ui']=self
            self.root.report_callback_exception=lambda cls,value,tb:failed(value)
            self.root.after(700,advance)
    def ui():return holder['ui']
    def sync():
        u=ui();u.controller.commands.join();u.snapshot=u.controller.snapshot();u.root.update_idletasks()
        assert u.controller.engine is None and u.controller.models.asr_loads==u.controller.models.speaker_loads==0
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    def invoke(key):
        button=ui().actions[key];assert button.winfo_exists() and str(button.cget('state'))=='normal';button.invoke()
    def capture(name):
        sync();u=ui();assert u.root.winfo_viewable() and (u.root.winfo_width(),u.root.winfo_height())==(480,800)
        texts=[]
        def walk(w):
            try:texts.append(str(w.cget('text')))
            except Exception:pass
            for child in w.winfo_children():walk(child)
        walk(u.root)
        if name=='sessions':
            assert any('/ 512 MiB' in t for t in texts) and any('Nothing is deleted automatically' in t for t in texts)
            assert not any('/ 2048 MiB' in t for t in texts)
        if name=='modes':assert not any('experimental marker never blocks' in t or 'Experimental modes remain selectable' in t for t in texts)
        if name=='backends':assert not any('Manifest sha256:' in t or ' · implemented' in t for t in texts)
        shot=root/(name+'.png');subprocess.run(['grim',str(shot)],check=True,timeout=10)
        observations.append(dict(name=name,sha256=sha(shot),width=480,height=800,texts=texts))
    def import_ui():
        invoke('session_import');assert ui().page=='consent';invoke('confirm')
        ui().keyboard_value.delete('1.0','end');ui().keyboard_value.insert('1.0',str(archive));invoke('keyboard_done');sync()
        assert not ui().controller.error and ui().controller.opened_conversation==identifier
        assert inventory(data/'conversations'/identifier)==admission['archive_files']
        u=ui().controller.session_store.usage()
        assert u['quota_bytes']==512*1024**2 and u['policy']['free_floor_mib']==5120 and not u['automatic_cleanup']
        assert u['bytes']==sum(p.stat().st_size for p in data.rglob('*') if p.is_file())
        ui().home();ui()._render_rows(ui().snapshot['rows'],force=True)
    def check_rows():
        capture('imported_captions');current=ui().snapshot['rows'];assert len(current)==len(expected)==40
        fields=['id','caption_key','utterance_id','raw_asr_text','provisional_display_text','final_punctuated_display_text','label','final','profile_id','track_id','span_ids','source_start_sec','source_end_sec','timing_kind','word_spans','speaker_revision','first_shown_label','identity_version']
        for row,old in zip(current,expected):assert {k:row.get(k) for k in fields}=={k:old.get(k) for k in fields}
        assert len(ui()._row_cache)==40
        (root/'OPENED_SNAPSHOT.json').write_text(json.dumps(ui().snapshot,indent=2))
    def export_ui():
        ui()._session_export(identifier,True);invoke('confirm')
        ui().keyboard_value.delete('1.0','end');ui().keyboard_value.insert('1.0',str(root/'roundtrip.zip'));invoke('keyboard_done');sync()
        assert not ui().controller.error
        with zipfile.ZipFile(root/'roundtrip.zip') as z:
            assert json.loads(z.read(MANIFEST))==transfer
            for name,digest in admission['archive_files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    def controller_busy():
        c=ui().controller;c.engine=object()
        try:reject('controller_busy',lambda:c._do_session_action('import',dict(path=str(archive),consent=True)))
        finally:c.engine=None
        assert len(negatives)==16
        (root/'NEGATIVES.json').write_text(json.dumps(negatives,indent=2))
    def failed(exc):
        import traceback
        errors.append(type(exc).__name__+': '+str(exc));(root/'CALLBACK_FAILURE.txt').write_text(traceback.format_exc());ui().close()
    def advance():
        if errors:return
        try:
            if not steps:ui().close();return
            name,fn=steps.pop(0);fn();sync()
            with (root/'ACTIONS.jsonl').open('a') as f:f.write(json.dumps(dict(action=name,complete=True))+'\n')
            ui().root.after(600,advance)
        except Exception as exc:failed(exc)
    steps.extend([('sessions',lambda:ui().show_sessions()),('quota_visible',lambda:capture('sessions')),
        ('import_actual_UI',import_ui),('exact_reopened_rows',check_rows),('full_export_actual_UI',export_ui),
        ('controller_busy_import',controller_busy),('modes',lambda:ui().show_modes()),('product_wording',lambda:capture('modes')),
        ('backends',lambda:ui().show_backends()),('backend_wording',lambda:capture('backends'))])
    ui_module.PrototypeUI=ScheduledUI;argv=sys.argv[:]
    try:
        sys.argv=[str(installed/'main.py'),'gui','--data-root',str(data),'--launch-admission',str(root/'GUI_LAUNCH.json')]
        code=entry.main()
    finally:sys.argv=argv;ui_module.PrototypeUI=original
    if errors:raise RuntimeError('; '.join(errors))
    assert code==0 and not steps and ui().controller.closed and not ui().controller.worker.is_alive()
    assert inventory(source)==admission['archive_files'] and inventory(copied)==admission['archive_files'] and inventory(prior)==admission['installed_files']
    result=dict(status='PASS_INSTALLED_PRIVATE_IMPORT_QUOTA_AND_UI_BOUNDARY_ONLY',installed_release=str(installed),observations=observations,
        negatives=negatives,summary=summary,source_unchanged=True,prior_release_unchanged=True,controller_closed=True,
        model_loads=0,capture_opened=False,physical_touch=False,field_release_accepted=False,imported_files=inventory(data/'conversations'/identifier),
        installed_hashes=inventory(installed),quota_bytes=512*1024**2,minimum_free_bytes=5*1024**3)
    (root/'ARCHIVE_RESULT.json').write_text(json.dumps(result,indent=2));return result
