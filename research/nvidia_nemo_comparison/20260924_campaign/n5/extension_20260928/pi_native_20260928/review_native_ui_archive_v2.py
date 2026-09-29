"""Independent native Tk/archive evidence reader. See README_REVIEW_NATIVE_UI_ARCHIVE_V2.md."""
import hashlib
import json
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    out = PRIVATE/'b05-ui-archive-v4-evidence'
    assert json.loads((out/'LAUNCH_RESULT.json').read_text(encoding='utf-8'))['exit_code'] == 0
    x = remote(r'''
import json,hashlib,os
from pathlib import Path
os.sched_setaffinity(0,{3});d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b05-ui-archive-v4')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text());r=json.loads((d/'RESULT.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
o=json.loads((d/'OWNER.json').read_text());assert o==r['owner'] and o['admission_sha256']==sha(d/'ADMISSION.json')
p=Path('/proc',str(o['pid']),'stat');ticks=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
assert not(o['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and ticks==o['start_ticks'])
assert not (d/'data/conversations'/a['conversation_id']).exists()
source=Path(a['source_final_snapshot']);parent_review=json.loads((source.parent/'LABEL_REVIEW_V2.json').read_text())
assert parent_review['bindings']['FINAL_SNAPSHOT.json']==sha(source)
bindings={n:sha(d/n) for n in ('ADMISSION.json','RESULT.json','OWNER.json','OPENED_SNAPSHOT.json')}
bindings['source_final_snapshot']=sha(source)
print(json.dumps(dict(result=r,source=json.loads(source.read_text()),opened=json.loads((d/'OPENED_SNAPSHOT.json').read_text()),bindings=bindings,owner_closed=True)))
''')
    r = x['result'];original = x['source']['rows'];opened = x['opened']['rows']
    assert r['status'] == 'WITHDRAWN_TK_ARCHIVE_COLLECTED_REQUIRES_REVIEW'
    assert r['checks'] == ['backend_nemotron_hybrid','mode_anonymous_conversation','session_pin','session_open',
                           'session_delete','cancel','session_delete','confirm','backend_baseline']
    for key in ('controller_closed','controller_worker_closed','Tk_destroyed','source_archive_unchanged',
                'copied_archive_deleted','delete_cancel_preserves_archive','punctuation_unloaded_by_asr_absence'):
        assert r[key], key
    assert r['observed_settling_seconds']>=1.35 and len(r['initial_widget_labels'])==40
    assert r['root_state']=='withdrawn' and r['root_mapped'] is False and not r['callback_errors']
    assert not r['inference_run'] and not r['capture'] and not r['playback']
    assert all(v==0 for v in r['hybrid_model_loads'].values()) and all(v==0 for v in r['model_loads'].values())
    assert len(original)==len(opened)==len(r['widget_rows'])==40
    fields=['id','raw_asr_text','provisional_display_text','final_punctuated_display_text','label','final',
            'caption_key','span_ids','source_start_sec','source_end_sec','timing_kind','word_spans',
            'speaker_revision','speaker_history','token_range','profile_id','display_profile_id']
    for old,new,widget in zip(original,opened,r['widget_rows']):
        assert {k:old[k] for k in fields}=={k:new[k] for k in fields}
        assert widget['id']==old['id'] and old['profile_id'] is None and old['display_profile_id'] is None
        assert widget['label'] in ('','Speaker 1','Speaker 2','Unknown')
        expected = old['final_punctuated_display_text'] if old['final'] and old['final_punctuated_display_text'] else old['provisional_display_text']
        assert expected is not None and widget['caption']==expected
        assert widget['actual_text']==(widget['label']+'\n' if widget['label'] else '')+expected+'\n\n'
    review=dict(status='PASS_NATIVE_WITHDRAWN_WIDGETS_AND_ARCHIVE_ONLY',run_id='b05-ui-archive-v4',bindings=x['bindings'],
                observed_settling_seconds=r['observed_settling_seconds'],initial_collecting_count=sum(v.startswith('•••') for v in r['initial_widget_labels']),checked_rows=40,checked_fields=fields,controls=r['checks'],archive_raw_text_labels_spans_preserved=True,
                actual_Tk_text_widgets_checked=True,root_withdrawn=True,physical_layout_qualified=False,
                save_open_delete_cancel_confirm=True,baseline_rollback=True,model_inference_run=False,
                natural_process_exit=True,owner_closed=True,controller_and_Tk_closed=True,
                original_archive_unchanged=True,peak_rss_bytes=r['peak_rss_bytes'],accuracy_scored=False,
                live_UI_latency_qualified=False,release_accepted=False)
    for name,doc in [('AUDIT_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(doc,f,indent=2)
    remote("from pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b05-ui-archive-v4/REVIEW.json')\nwith p.open('x') as f:f.write("+repr(json.dumps(review,indent=2))+")\nprint('{}')")
    print(json.dumps({k:v for k,v in review.items() if k!='bindings'},indent=2))


if __name__=='__main__':main()
