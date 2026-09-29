"""Independent actual app artifact review; README_APP_BOUNDED_ARTIFACTS_V1.md."""
import json,os,resource,subprocess,hashlib,wave,struct,copy
from pathlib import Path
from review_live_artifacts_v1 import sha,ticks,decode,canonical

def main():
    os.sched_setaffinity(0, {3})
    resource.setrlimit(resource.RLIMIT_AS, (768*1024**2,)*2)
    r = Path(__file__).resolve().parent
    a = json.loads((r/'ADMISSION.json').read_text())
    result = json.loads((r/'RESULT.json').read_text())
    dispatch = json.loads((r/'DISPATCH_RESULT.json').read_text())
    envelope = json.loads((r/'LIVE_ENVELOPE.json').read_text())
    assert result['status'] == 'NATIVE_APP_ARTIFACT_INTEGRATION_REVIEW_REQUIRED'
    assert dispatch['exit_code'] == 0 and not dispatch['memory_guard'] and not dispatch['log_overflow']
    for name in ('OWNER.json','DISPATCH_OWNER.json'):
        owner = json.loads((r/name).read_text())
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == owner['boot_id'] == a['boot_id']
        assert ticks(owner['pid']) != owner['start_ticks']
    assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-app-artifact-integration-v1*'],text=True).strip()
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
    for binding in result['derivative_files'].items():
        assert sha(r/'prototype'/binding[0])==binding[1]
    manifest=json.loads((r/'prototype'/'ARTIFACT_DERIVATIVE.json').read_text())
    changed=[]
    for name,digest in manifest['files'].items():
        parent=Path(manifest['parent'])/name
        if not parent.exists() or sha(parent)!=digest:changed.append(name)
    assert sorted(changed)==sorted(manifest['changed']+manifest['added'])
    targets=[r/result['event_journal'],r/result['archive_path']/'events.jsonl']
    events=[]
    for source,target in zip(a['journals'],targets,strict=True):
        iterator=decode(target);count=0;h=hashlib.sha256()
        for line in Path(source['path']).open():
            original=json.loads(line);stored=next(iterator);assert original==stored
            h.update(canonical(stored)+b'\n');count+=1
        try:next(iterator)
        except StopIteration:pass
        else:raise AssertionError('Extra stored event')
        assert count==source['events']
        events.append(dict(events=count,bytes=target.stat().st_size,canonical_sha256=h.hexdigest()))
    folder=r/result['archive_path'];m=json.loads((folder/'epoch.json').read_text())
    assert m['state']=='CLOSED' and m['closed'] and not m['archive_error']
    assert m['recorded_samples']==m['source_samples']==715127
    assert m['accepted_items']==m['completed_items'] and m['queue_items']==m['queue_bytes']==0
    assert m['artifact_metrics']['events']['status']=='COMPLETE' and m['artifact_metrics']['audio']['status']=='COMPLETE'
    with wave.open(a['source_wav'],'rb') as old,wave.open(str(folder/'model_input.wav'),'rb') as new:
        assert new.getparams()==old.getparams();raw=old.readframes(715127);assert new.readframes(715127)==raw
    floats=(folder/'model_input.f32le').read_bytes()
    assert len(floats)==4*715127
    for (expected,),(actual,) in zip(struct.iter_unpack('<h',raw),struct.iter_unpack('<f',floats),strict=True):assert actual==expected/32768
    assert m['audio_sha256']==sha(folder/'model_input.f32le') and m['audio_bytes']==6*715127+44
    captions={};formats={}
    for line in Path(a['journals'][1]['path']).open():
        event=json.loads(line);kind=event.get('kind')
        if kind not in ('s6d_display','prototype_formatted_text'):continue
        value=event['payload'];key=value.get('caption_key') or str(value.get('utterance_id'))
        (captions if kind=='s6d_display' else formats)[key]=copy.deepcopy(value)
    expected=[]
    for key,row in captions.items():
        row.update(archive_epoch_id=result['epoch'],archive_conversation_id=result['conversation_id'],source_start_sample=round(float(row.get('source_start_sec',0))*16000),source_end_sample=round(float(row.get('source_end_sec',0))*16000),audio_link_quality='coarse utterance interval; not phonetic word alignment')
        f=formats.get(key)
        if f and f.get('text_revision_id')==row.get('text_revision_id'):
            row.update(archived_provisional_display_text=f['provisional_display_text'],archived_final_formatted_text=f['final_formatted_text'],text_assistance=f.get('text_assistance'))
        expected.append(row)
    assert expected==json.loads((r/'ROWS.json').read_text()) and len(expected)==result['rows']
    assert result['row_digest']==result['legacy_row_digest']
    assert result['partial_archive']['archive_error']=='ARCHIVE_RECORD_OVERSIZE' and result['partial_archive']['closed']
    assert result['async_limit']['status']=='BYTE_LIMIT' and result['async_limit']['closed'] and result['async_limit']['bytes']<=1024
    assert result['engine_writer']['accepted']==result['engine_writer']['completed']==2628 and result['engine_writer']['closed']
    assert ticks(1013)==569 and ticks(1130)==607
    assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
    assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
    assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    total=sum(x.stat().st_size for x in r.rglob('*') if x.is_file());assert total<a['target_output_max_bytes']
    out=dict(status='PASS_NATIVE_APP_ARTIFACT_WRITER_REOPEN_PCM_ONLY',journals=events,rows=len(expected),all_row_fields_exact=True,pcm_frames=715127,exact_float_master=True,legacy_reader_equal=True,partial_and_async_failure_visible=True,peak_rss_kib=result['ru_maxrss_kib'],seconds=result['seconds'],target_bytes=total,target_cap=a['target_output_max_bytes'],natural_exit=0,owners_closed=True,capture=False,models=False,callback_repaired=False,live_combined_qualified=False,files={p.relative_to(r).as_posix():sha(p) for p in r.rglob('*') if p.is_file()})
    with (r/'REVIEW.json').open('x') as stream:json.dump(out,stream,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k!='files'}))

if __name__=='__main__':main()
