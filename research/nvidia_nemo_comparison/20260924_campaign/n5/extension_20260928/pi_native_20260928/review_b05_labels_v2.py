"""Read native anonymous-label provenance without inference. See README_B05_LABELS_V2.md."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',choices=['b05-stop-restart-lru1-v1','b05-native-stack-v1'],required=True)
    args=parser.parse_args();psutil.Process().cpu_affinity([14])
    code=r'''
import os,json,hashlib
from pathlib import Path
os.sched_setaffinity(0,{3});d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/RUN
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text());r=json.loads((d/'RESULT.json').read_text());review=json.loads((d/'REVIEW.json').read_text())
assert review['status'] in ('PASS_B05_EARLY_STOP_AND_FULL_RESTART_ONLY','PASS_B05_NATIVE_STACK_STOP_RESTART_ONLY')
assert review['bindings']['RESULT.json']==sha(d/'RESULT.json')
for item in a['files']:assert sha(Path(item['path']))==item['sha256']
owner=json.loads((d/'OWNER.json').read_text());p=Path('/proc',str(owner['pid']),'stat')
ticks=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
assert not(ticks==owner['start_ticks'] and owner['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip())
sessions=[];bindings={n:sha(d/n) for n in ['RESULT.json','ADMISSION.json','REVIEW.json','FINAL_SNAPSHOT.json']}
for item in r['sessions']:
 s=Path(item['session_dir']);assert s.parent==d/'data/sessions'
 ev=[json.loads(line) for line in (s/'events.jsonl').read_text().splitlines()]
 keep=[e for e in ev if e['event_type'] in ['source_started','s6d_text_ready','transcript_label_revision']]
 sessions.append(dict(session_id=s.name,events=keep))
 bindings[str((s/'events.jsonl').relative_to(d))]=sha(s/'events.jsonl')
print(json.dumps(dict(sessions=sessions,snapshot=json.loads((d/'FINAL_SNAPSHOT.json').read_text()),bindings=bindings)))
'''
    x=remote('RUN='+repr(args.run_id)+'\n'+code)
    rows=x['snapshot']['rows'];session_ids={s['session_id'] for s in x['sessions']}
    assert len(session_ids)==2 and rows and not x['snapshot']['error']
    summaries=[];revision_by_id={};all_tokens={};token_state={};tokens_at_revision={}
    for session in x['sessions']:
        sid=session['session_id'];texts={};revisions=[];origin=None
        for event in session['events']:
            p=event['payload'];assert p['session_id']==sid
            if event['event_type']=='source_started':origin=p['source_epoch_monotonic_sec']
            elif event['event_type']=='s6d_text_ready':
                key=(p['utterance_id'],p['text_revision_id']);texts[key]=p
                # Upstream untimed hypothesis IDs differ from presentation span IDs.
                # Independently reconstruct the documented stable-prefix span sequence.
                caption=sid+'/'+p['utterance_id'];words=re.findall(r'\S+',p['text'])
                old_words,old_ids,serial=token_state.get(caption,([],[],0));prefix=0
                while prefix<min(len(old_words),len(words)) and old_words[prefix]==words[prefix]:prefix+=1
                ids=list(old_ids[:prefix])
                for word in words[prefix:]:
                    serial+=1;token=caption+'/token:'+str(serial);ids.append(token);all_tokens[token]=word
                token_state[caption]=(words,ids,serial)
                tokens_at_revision[(sid,*key)]=set(ids)
            else:
                assert origin is not None
                prior=texts[(p['utterance_id'],p['target_text_revision_id'])]
                assert prior['publication_sequence']<p['publication_sequence']
                assert prior['publication_monotonic_sec']<=p['publication_monotonic_sec']
                assert p['changes_raw_words'] is False
                assert p['publication_freshness']=='historical_caption_annotation_only'
                assert p['latest_known_profile_id'] is None and p['latest_known_name'] is None
                assert p['evidence_ids']==[] and p['timing_kind']=='ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT'
                assert p['target_span_ids'] and all(t.startswith(sid+'/'+p['utterance_id']+'/') and t in tokens_at_revision[(sid,p['utterance_id'],p['target_text_revision_id'])] for t in p['target_span_ids'])
                slot=p['association']['slot']
                assert origin<=p['association']['available_at_monotonic']<=p['publication_monotonic_sec']
                expected='Unknown' if slot is None else 'Speaker '+str(slot+1)
                assert slot is None or 0<=slot<8
                assert p['latest_label']==p['latest_anonymous_label']==expected
                assert p['replacement_tracker_id']==(None if slot is None else sid+':nemotron-slot-'+str(slot))
                assert p['source_start_sec']>=0 and p['source_end_sec']>=p['source_start_sec']
                revision_by_id[(sid,p['event_id'])]=p;revisions.append(p)
        assert texts and revisions and origin is not None
        summaries.append(dict(session_id=sid,text_publications=len(texts),label_revisions=len(revisions),
                              label_revision_counts=dict(Counter(p['latest_label'] for p in revisions)),
                              first_text_seconds=min(p['publication_monotonic_sec'] for p in texts.values())-origin,
                              first_label_revision_seconds=min(p['publication_monotonic_sec'] for p in revisions)-origin))
    labels=Counter();histories=0
    for row in rows:
        assert re.fullmatch(r'Speaker [1-8]|Unknown',row['label'])
        assert row['profile_id'] is None and row['display_profile_id'] is None
        assert row['raw_asr_text'].strip()==' '.join(s['text'].strip() for s in row['word_spans']).strip()
        assert row['span_ids']==[s['id'] for s in row['word_spans']]
        labels[row['label']]+=1
        for span in row['word_spans']:
            sid=span['id'].split('/')[0];assert sid in session_ids and span['id'] in all_tokens and span['text']==all_tokens[span['id']]
            assert span['timing_kind']=='ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT'
            assert span['exact_word_start_sec'] is None and span['exact_word_end_sec'] is None
            assert span['speaker_history']
            for history in span['speaker_history']:
                assert history['profile_id'] is None
                event_id=history.get('event_id')
                if event_id and event_id.startswith('n2-caption:'):
                    p=revision_by_id[(sid,event_id)]
                    assert span['id'] in p['target_span_ids'] and history['label']==p['latest_label']
                    histories+=1
            assert span['speaker_history'][-1]['label']==row['label']
    assert histories>0
    review=dict(status='PASS_NATIVE_ANONYMOUS_LABEL_PROVENANCE_ONLY',run_id=args.run_id,bindings=x['bindings'],
                sessions=summaries,cumulative_draft_rows=len(rows),draft_row_labels=dict(labels),
                checked_native_label_history_entries=histories,raw_span_text_preserved=True,
                cross_session_revision_rejected_by_reader=True,no_personal_name_or_profile=True,
                presentation_span_ids_reconstructed_from_revision_text=True,presentation_snapshot_only=True,actual_widgets_tested=False,accuracy_scored=False,
                association_quality_validated=False,release_accepted=False)
    out=PRIVATE/(args.run_id+'-evidence')
    for name,obj in [('LABEL_AUDIT_INPUTS_V2.json',x),('LABEL_REVIEW_V2.json',review)]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2)
    remote("import json\nfrom pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/"+repr(args.run_id)+"/'LABEL_REVIEW_V2.json'\nwith p.open('x') as f:f.write("+repr(json.dumps(review,indent=2))+")\nprint('{}')")
    print(json.dumps({k:v for k,v in review.items() if k!='bindings'},indent=2))


if __name__=='__main__':main()
