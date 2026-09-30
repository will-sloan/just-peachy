"""New metadata and prepublication consumer checks; README_FIELD_ARCHIVE_V2.md."""
import copy
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


def inventory(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()}


def run(root,a):
    prior=Path(a['installed_release']);original_archive=Path(a['transfer_source'])
    assert inventory(prior)==a['installed_files'] and sha(original_archive)==a['transfer_source_sha256']
    source=root/'source';shutil.copytree(prior,source,ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['field_entry_v4.py','field_archive_v2.py','field_archive_schema_v2.py']:shutil.copyfile(root/name,source/'native'/name)
    shutil.copyfile(root/'README_FIELD_ARCHIVE_V2.md',source/'docs/README_FIELD_ARCHIVE_V2.md')
    (source/'main.py').write_text('from native.field_entry_v4 import main\nif __name__=="__main__":raise SystemExit(main())\n')
    sys.path.insert(0,str(source))
    from release_tools import release
    built=release.build(source,root/'archives','b01-offline-20260930-v4');staged=release.stage(built['archive'],root/'deployment',built['sha256'])
    installed=Path(staged['path']);(root/'CANDIDATE_BUILD.json').write_text(json.dumps(dict(built=built,staged=staged),indent=2))
    sys.path[:0]=[str(installed),str(installed/'vendor'),str(installed/'native')]
    from field_archive_v2 import FieldArchiveStore,MANIFEST,SCHEMA
    from field_archive_schema_v2 import caption_row,bounded_json
    from native import field_entry_v4 as entry
    from app import ui as ui_module
    from app.bounded_live_artifacts_v1 import CompactJournal
    contract=json.loads((installed/'config/field_contract.json').read_text())
    with zipfile.ZipFile(original_archive) as z:original_meta=json.loads(z.read('conversation.json'))
    identifier=original_meta['id'];bad=root/'negative-inputs';bad.mkdir();negative=[]
    rejection_data=root/'rejections';store=FieldArchiveStore(rejection_data,contract)
    def reject(name,fn,expected):
        try:fn()
        except (ValueError,TypeError,KeyError,RuntimeError) as exc:
            assert expected in str(exc),(name,str(exc));negative.append(dict(case=name,error=type(exc).__name__+': '+str(exc),expected=expected))
        else:raise AssertionError('Missing rejection: '+name)
    def malformed(name,mutation):
        m=copy.deepcopy(original_meta);m['id']='1'*32;mutation(m)
        raw=json.dumps(m).encode();binding=dict(schema=SCHEMA,identifier=m['id'],files={'conversation.json':dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())})
        path=bad/(name+'.zip')
        with zipfile.ZipFile(path,'x') as z:z.writestr(MANIFEST,json.dumps(binding));z.writestr('conversation.json',raw)
        reject(name,lambda:store.import_archive(path,consent=True),'Conversation metadata:')
        assert not list(store.root.iterdir()) and not (rejection_data/'.archive-imports').exists()
        return path
    bad_missing=malformed('missing_created_utc',lambda m:m.pop('created_utc'))
    for name,mutation in [
        ('created_utc_type',lambda m:m.update(created_utc=[])),
        ('created_utc_naive',lambda m:m.update(created_utc='2026-09-30T00:00:00')),
        ('missing_updated_utc',lambda m:m.pop('updated_utc')),
        ('missing_audio_requested',lambda m:m.pop('audio_requested')),
        ('audio_requested_string',lambda m:m.update(audio_requested='true')),
        ('notes_not_list',lambda m:m.update(notes={})),
        ('note_not_object',lambda m:m.update(notes=['bad'])),
        ('correction_missing_fields',lambda m:m.update(corrections=[{}])),
        ('correction_bad_text',lambda m:m.update(corrections=[dict(id='2'*32,utc='2026-09-30T00:00:00Z',row_id='row',corrected_text={})])),
        ('audio_reviews_unsupported',lambda m:m.update(audio_reviews=[{}])),
        ('epochs_not_strings',lambda m:m.update(epochs=[[]]))]:malformed(name,mutation)
    raw_path=Path(a['raw_reference']);assert sha(raw_path)==a['raw_reference_sha256']
    raw=json.loads(raw_path.read_text());assert len(raw)==4
    for name,mutate,message in [
        ('segments_not_objects',lambda r:r.update(segments=['bad']),'Caption segments'),
        ('text_not_string',lambda r:r.update(text=[]),'text must'),
        ('missing_utterance_id',lambda r:r.pop('utterance_id'),'utterance_id'),
        ('assistance_not_object',lambda r:r.update(text_assistance=[]),'Text assistance object'),
        ('token_range_type',lambda r:r['segments'][0].update(token_range=['0',1]),'token range')]:
        row=copy.deepcopy(raw[-1]);mutate(row)
        (bad/(name+'.json')).write_text(json.dumps(row,indent=2))
        reject(name,lambda row=row:caption_row(row,715127),message)
    nonfinite={'value':float('nan')};(bad/'nonfinite.json').write_text(json.dumps(nonfinite))
    reject('nonfinite',lambda:bounded_json(nonfinite),'Nonfinite')
    reject('consumer_hook_required',lambda:store.import_archive(original_archive,consent=True),'Controller consumer validation required')
    # One crafted full archive keeps original audio, but duplicates two visible IDs.
    # Its new manifest is internally consistent: failure must be the real consumer gate.
    full_epoch=raw[-1]['archive_epoch_id'];full_rows=[copy.deepcopy(r) for r in raw if r['archive_epoch_id']==full_epoch]
    assert len(full_rows[0]['segments'])>1
    full_rows[0]['segments'][1]['segment_id']=full_rows[0]['segments'][0]['segment_id']
    events=bad/'duplicate-projection-events.jsonl';journal=CompactJournal(events,1024**2)
    for row in full_rows:journal.append(dict(kind='s6d_display',payload=row))
    journal.close('COMPLETE')
    member=f'epochs/{full_epoch}/events.jsonl';bad_duplicate=bad/'duplicate-projection.zip'
    with zipfile.ZipFile(original_archive) as src,zipfile.ZipFile(bad_duplicate,'x',zipfile.ZIP_DEFLATED) as dst:
        manifest=json.loads(src.read(MANIFEST));manifest['files'][member]=dict(bytes=events.stat().st_size,sha256=sha(events))
        dst.writestr(MANIFEST,json.dumps(manifest))
        for name in manifest['files']:
            if name==member:dst.write(events,name)
            else:
                with src.open(name) as f,dst.open(name,'w') as out:shutil.copyfileobj(f,out,65536)
    assert len(negative)==19
    (root/'NEGATIVES.json').write_text(json.dumps(negative,indent=2))
    data=root/'data';data.mkdir()
    for old,new in [('N2_RUNTIME_BACKUP.json','n2_runtime.json'),('LIVE_CONFIG_BACKUP.json','live_config.json')]:shutil.copyfile(root/old,data/new)
    (data/'private-preservation-canary').write_bytes(b'PRIVATE_SYNTHETIC_CANARY\n')
    launch=dict(release_manifest_sha256=sha(installed/'RELEASE_MANIFEST.json'),autonomous_quiet_authorized=True,
        expires_unix=time.time()+180,data_root=str(data.resolve()),scope='Changed schema/consumer gate and installed import only; no capture/model/playback')
    (root/'GUI_LAUNCH.json').write_text(json.dumps(launch,indent=2))
    original=ui_module.PrototypeUI;holder={};steps=[];errors=[];observations=[]
    expected=json.loads(Path(a['display_reference']).read_text())['rows']
    class ScheduledUI(original):
        def __init__(self,*args,**kw):
            super().__init__(*args,**kw);holder['ui']=self
            self.root.report_callback_exception=lambda cls,value,tb:failed(value)
            self.root.after(700,advance)
    def ui():return holder['ui']
    def sync():
        u=ui();u.controller.commands.join();u.snapshot=u.controller.snapshot();u.root.update_idletasks()
        assert u.controller.engine is None and u.controller.models.asr_loads==u.controller.models.speaker_loads==0
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    def invoke(key):
        button=ui().actions[key];assert button.winfo_exists() and str(button.cget('state'))=='normal';button.invoke()
    def import_path(path):
        ui().show_sessions();invoke('session_import');invoke('confirm')
        ui().keyboard_value.delete('1.0','end');ui().keyboard_value.insert('1.0',str(path));invoke('keyboard_done');sync()
    def reject_ui(path,message,name):
        import_path(path);assert message in ui().controller.error
        assert not list((data/'conversations').iterdir()) and not ui().controller.session_listing and not ui().snapshot['rows']
        negative.append(dict(case=name,error=ui().controller.error,no_publication=True))
        (root/'NEGATIVES.json').write_text(json.dumps(negative,indent=2))
    def valid_ui():
        import_path(original_archive);assert not ui().controller.error and ui().controller.opened_conversation==identifier
        assert inventory(data/'conversations'/identifier)==a['archive_files']
        receipts=[json.loads(p.read_text()) for p in (data/'.archive-imports').glob('*/RECEIPT.json')]
        published=[r for r in receipts if r['status']=='PUBLISHED'];rejected=[r for r in receipts if r['status']=='REJECTED_PRESERVED']
        assert len(published)==len(rejected)==1 and 'Duplicate projected caption ID' in rejected[0]['error']
        assert published[0]['consumer_validation']['display_rows']==40 and published[0]['consumer_validation']['raw_rows']==4
        (root/'CONSUMER_VALIDATION.json').write_text(json.dumps(published[0]['consumer_validation'],indent=2))
        ui().home();ui()._render_rows(ui().snapshot['rows'],force=True)
    def visible():
        sync();u=ui();current=u.snapshot['rows'];assert len(current)==len(expected)==40 and len(u._row_cache)==40
        fields=['id','caption_key','utterance_id','raw_asr_text','provisional_display_text','final_punctuated_display_text','label','final','profile_id','track_id','span_ids','source_start_sec','source_end_sec','timing_kind','word_spans','speaker_revision','first_shown_label','identity_version']
        for row,old in zip(current,expected):assert {k:row.get(k) for k in fields}=={k:old.get(k) for k in fields}
        assert u.root.winfo_viewable() and (u.root.winfo_width(),u.root.winfo_height())==(480,800)
        shot=root/'imported-captions.png';subprocess.run(['grim',str(shot)],check=True,timeout=10)
        observations.append(dict(name='imported-captions',sha256=sha(shot),width=480,height=800))
        (root/'OPENED_SNAPSHOT.json').write_text(json.dumps(u.snapshot,indent=2))
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
    steps.extend([('metadata_rejected_in_actual_UI',lambda:reject_ui(bad_missing,'Conversation metadata:','UI_missing_metadata')),
        ('projection_rejected_before_publish',lambda:reject_ui(bad_duplicate,'Duplicate projected caption ID','UI_duplicate_projection')),
        ('changed_valid_import_actual_UI',valid_ui),('exact_reopened_widgets',visible)])
    ui_module.PrototypeUI=ScheduledUI;argv=sys.argv[:]
    try:
        sys.argv=[str(installed/'main.py'),'gui','--data-root',str(data),'--launch-admission',str(root/'GUI_LAUNCH.json')]
        code=entry.main()
    finally:sys.argv=argv;ui_module.PrototypeUI=original
    if errors:raise RuntimeError('; '.join(errors))
    assert code==0 and not steps and ui().controller.closed and not ui().controller.worker.is_alive() and len(negative)==21
    assert sha(original_archive)==a['transfer_source_sha256'] and inventory(prior)==a['installed_files']
    result=dict(status='PASS_INSTALLED_PREPUBLICATION_METADATA_AND_CONSUMER_GATE_ONLY',installed_release=str(installed),observations=observations,
        negatives=negative,source_unchanged=True,prior_release_unchanged=True,controller_closed=True,model_loads=0,capture_opened=False,
        physical_touch=False,field_release_accepted=False,imported_files=inventory(data/'conversations'/identifier),installed_hashes=inventory(installed),
        quota_bytes=512*1024**2,minimum_free_bytes=5*1024**3)
    (root/'ARCHIVE_RESULT.json').write_text(json.dumps(result,indent=2));return result
