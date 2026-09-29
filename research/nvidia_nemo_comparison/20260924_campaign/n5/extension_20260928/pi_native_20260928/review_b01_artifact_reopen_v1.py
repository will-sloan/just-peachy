"""Independent copied archive controller reader; README_B01_ARTIFACT_REOPEN_V1.md."""
import json,os,resource,subprocess,hashlib
from pathlib import Path

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None

def main():
    os.sched_setaffinity(0, {3})
    resource.setrlimit(resource.RLIMIT_AS, (768*1024**2,)*2)
    r = Path(__file__).resolve().parent
    a = json.loads((r/'ADMISSION.json').read_text())
    result = json.loads((r/'RESULT.json').read_text())
    dispatch = json.loads((r/'DISPATCH_RESULT.json').read_text())
    envelope = json.loads((r/'LIVE_ENVELOPE.json').read_text())
    assert result['status'] == 'NATIVE_COPIED_COMPACT_ARCHIVE_CONTROLLER_REOPEN_REVIEW_REQUIRED'
    assert dispatch['exit_code'] == 0 and not dispatch['memory_guard'] and not dispatch['log_overflow']
    for name in ('OWNER.json','DISPATCH_OWNER.json'):
        owner = json.loads((r/name).read_text())
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == owner['boot_id'] == a['boot_id']
        assert ticks(owner['pid']) != owner['start_ticks']
    assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-b01-artifact-reopen-v1*'],text=True).strip()
    assert a['address_space_max_bytes'] == envelope['address_space'][0] == envelope['address_space'][1] == 768*1024**2
    assert envelope['stack'] == [1048576]*2 and envelope['affinity'] == a['cpus'] == [2,3]
    assert envelope['properties']['TimeoutStopUSec']=='10s' and int(envelope['properties']['LimitFSIZE'])==8*1024**2
    assert a['stop_timeout_seconds'] == 10 and a['tasks_max'] == 64 and a['runtime_seconds'] == 300
    assert a['per_file_max_bytes'] == 8*1024**2 and a['capture'] is False
    assert int(envelope['properties']['MainPID']) == envelope['owner']['pid']
    assert envelope['properties']['TasksMax'] == '64' and envelope['properties']['RuntimeMaxUSec'] == '5min'
    assert int(envelope['cpu_max'][0])/int(envelope['cpu_max'][1]) == 2
    for binding in a['files']:
        assert sha(binding['path']) == binding['sha256']
    expected=json.loads((r/'FINAL_SNAPSHOT.json').read_text())['rows']
    opened=json.loads((r/'OPENED_SNAPSHOT.json').read_text())['rows']
    widgets=json.loads((r/'WIDGETS.json').read_text())
    assert len(expected)==len(opened)==len(widgets)==40
    fields=['id','caption_key','utterance_id','raw_asr_text','provisional_display_text','final_punctuated_display_text','label','final','profile_id','track_id','span_ids','source_start_sec','source_end_sec','timing_kind','word_spans','speaker_revision','first_shown_label','identity_version']
    assert result['compared_fields']==fields
    for old,new,widget in zip(expected,opened,widgets,strict=True):
        assert {k:old.get(k) for k in fields}=={k:new.get(k) for k in fields}
        assert widget['id']==str(new['id'])
        assert widget['actual_text']==(widget['label']+'\n' if widget['label'] else '')+widget['caption']+'\n\n'
        assert widget['label'] in ('Unknown','Speaker 1','Speaker 2','')
    assert result['controller_closed'] and result['Tk_destroyed'] and result['root_withdrawn'] and result['controller_save_open']
    assert not result['callback_errors'] and result['model_load_counts']['asr_loads']==result['model_load_counts']['speaker_loads']==0
    for name,digest in a['original_conversations'].items():
        assert sha(Path(a['parent_run'])/'data/conversations'/name)==digest
        if name.endswith(('.jsonl','.f32le','.wav')):assert sha(r/'data/conversations'/name)==digest
    assert ticks(1013)==569 and ticks(1130)==607
    assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
    assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
    assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    total=sum(p.stat().st_size for p in r.rglob('*') if p.is_file());assert total<a['target_output_max_bytes']
    out=dict(status='PASS_NATIVE_COMPACT_ARCHIVE_CONTROLLER_SAVE_OPEN_40_WIDGET_ROWS_ONLY',rows=40,raw_utterances=4,fields_exact=fields,zero_models=True,capture=False,playback=False,root_withdrawn=True,natural_exit=0,exact_owners_closed=True,original_unchanged=True,peak_rss_kib=result['ru_maxrss_kib'],seconds=result['seconds'],target_output_bytes=total,hashes={str(p.relative_to(r)):sha(p) for p in r.rglob('*') if p.is_file()})
    with (r/'REVIEW.json').open('x') as stream:json.dump(out,stream,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k not in ('hashes','fields_exact')}))

if __name__=='__main__':main()
