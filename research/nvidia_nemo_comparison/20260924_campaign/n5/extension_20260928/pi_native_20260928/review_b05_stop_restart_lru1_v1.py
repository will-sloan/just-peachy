"""Independent two-session native reader. See README_B05_STOP_RESTART_LRU1_REVIEW_V1.md."""
import hashlib
import json
from pathlib import Path
import re
import numpy as np
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    run = 'b05-stop-restart-lru1-v1'
    code = r'''
import hashlib,json,os,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3})
d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/RUN
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
owner=json.loads((d/'OWNER.json').read_text())
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
try:start=int(Path('/proc',str(owner['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])
except FileNotFoundError:start=None
assert not(boot==owner['boot_id'] and start==owner['start_ticks'])
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
r=json.loads((d/'RESULT.json').read_text())
assert len(r['sessions'])==2
assert len(list((d/'data/sessions').iterdir()))==2
sessions=[];bindings={n:sha(d/n) for n in ['RESULT.json','ADMISSION.json','EARLY_STOP.json','STOP_SNAPSHOT.json','FINAL_SNAPSHOT.json']}
for item in r['sessions']:
 s=Path(item['session_dir']);assert s.parent==d/'data/sessions'
 names=['session_summary.json','session_finalization_v3.json','s6d_consumer_closure.json']
 documents={n:json.loads((s/n).read_text()) for n in names}
 events=[json.loads(line) for line in (s/'events.jsonl').read_text().splitlines()]
 relevant=[e for e in events if e['event_type'] in ('source_started','s6d_text_ready','n2_diarization_frames','session_completed')]
 assert all(e['payload']['session_id']==s.name for e in relevant)
 sources=[e['payload'] for e in events if e['event_type']=='source_started'];assert len(sources)==1
 completions=[e['payload'] for e in events if e['event_type']=='session_completed'];assert len(completions)==1
 sessions.append(dict(item=item,documents=documents,source=sources[0],done=completions[0],
   prob=[e['payload'] for e in events if e['event_type']=='n2_diarization_frames'],
   punct=[e['payload']['punctuation'] for e in events if e['event_type']=='s6d_punctuation_revision'],
   text_times=[e['payload']['publication_monotonic_sec'] for e in events if e['event_type']=='s6d_text_ready']))
 for path in [s/'events.jsonl',*[s/n for n in names]]:bindings[str(path.relative_to(d))]=sha(path)
print(json.dumps(dict(result=r,sessions=sessions,bindings=bindings,owner_closed=True,
 stop_snapshot=json.loads((d/'STOP_SNAPSHOT.json').read_text()),final_snapshot=json.loads((d/'FINAL_SNAPSHOT.json').read_text()))))
'''
    x = remote('RUN='+repr(run)+'\n'+code)
    out = PRIVATE/(run+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code'] == 0
    r = x['result']
    assert r['status'] == 'B05_STOP_RESTART_COLLECTED_REQUIRES_REVIEW'
    assert r['harness_retains_early_engine'] is False
    assert r['controller_closed'] and not r['redim_encoder_loaded']
    assert r['model_load_counts']['asr_loads'] == 1 and r['model_load_counts']['speaker_loads'] == 0
    assert r['sessions'][1]['epoch'] > r['sessions'][0]['epoch']
    assert x['stop_snapshot']['metrics']['last_worker_cleanup']['owned_threads_joined']
    rows=[];arrays=[]
    for index, session in enumerate(x['sessions']):
        item=session['item']; samples=item['source_samples']
        if index == 0:
            assert item['kind']=='early_stop' and 128000 <= samples < 715127
            assert item['samples_at_stop_request'] <= samples
        else:
            assert item['kind']=='full_restart' and samples == 715127
        snapshot=x['stop_snapshot'] if index == 0 else x['final_snapshot']
        assert not snapshot['error'] and snapshot['rows']
        d=session['documents']; f=d['session_finalization_v3.json']
        assert f['state']=='COMPLETED' and not f['finalization_error'] and not f['live_lanes_at_finalization']
        assert f['event_and_transcript_handles_closed'] and not f['resident_bundle_lease_retained']
        assert f['source_samples']==f['identity_samples']==samples
        c=d['s6d_consumer_closure.json']
        assert c['state']=='COMPLETED' and c['full_event_consumer_drained']
        assert c['queues']['event_consumer']['depth']==0
        for name in ('journal','punctuation','policy'):
            q=c['queues'][name]
            assert q['closed'] and not q['thread_alive'] and not q['error'] and q['depth']==0
            assert q['accepted']==q['completed']
        summary=d['session_summary.json']; t=summary['telemetry']
        assert summary['state']=='COMPLETED' and t['audio_frames_dropped']==0
        assert t['identity_audio_samples']==t['paired_audio_samples']==samples
        assert t['n2_embedding_calls']==0 and t['n2_embedding_policy']=='BYPASSED_ANONYMOUS_NATIVE_SLOTS'
        costs=t['component_costs']['rows']
        for name in ('asr_accept','diarizer_push'):assert costs[name]['successful_samples']==samples
        for row in costs.values():assert row['errors']==row['in_flight']==0 and row['started']==row['completed']
        assert costs['embedding']['started']==0 and t['punctuation_inference_failures']==0
        assert session['punct'] and all(p['status']=='learned' and p['error'] is None for p in session['punct'])
        origin=session['source']['source_epoch_monotonic_sec']
        assert session['source']['start_sample']==0 and session['source']['pacing']=='absolute'
        assert session['text_times'] and min(session['text_times'])>=origin
        if index:assert origin>x['sessions'][0]['done']['publication_monotonic_sec']
        chunks=[];cursor=0
        for payload in session['prob']:
            a=np.asarray(payload['probabilities'],dtype=np.float32)
            assert payload['frame_start']==cursor and a.ndim==2 and a.shape[1]==8 and len(a)>0
            assert np.isfinite(a).all() and (a>=0).all() and (a<=1).all()
            assert payload['available_at_monotonic']>=origin
            assert abs(payload['frame_step_sec']-.01)<1e-8
            chunks.append(a);cursor+=len(a)
        assert cursor>0 and cursor==costs['diarizer_push']['output_frames']+costs['diarizer_finish']['output_frames']
        probabilities=np.concatenate(chunks);arrays.append(probabilities)
        parity=None
        if index:
            reference=PRIVATE/'d1-geometry-delayed-metadata2-v1-evidence'
            prior=json.loads((reference/'REVIEW.json').read_text())
            assert hashlib.sha256((reference/'RESULT.json').read_bytes()).hexdigest()==prior['result_sha256']
            ref=np.load(reference/'saved_full.npy',allow_pickle=False)
            assert probabilities.shape==ref.shape==(4470,8)
            parity=float(np.max(np.abs(probabilities-ref)));assert parity<=1e-5
        archive=snapshot['sessions']['last_archive']
        assert archive['closed'] and not archive['worker_alive'] and not archive['archive_error'] and not archive['loss']
        assert archive['source_samples']==samples and archive['queue_items']==archive['queue_bytes']==0
        rows.append(dict(kind=item['kind'],samples=samples,probability_frames=cursor,probability_windows=len(chunks),
                         reference_max_abs=parity,caption_rows=len(snapshot['rows']),
                         first_text_seconds=min(session['text_times'])-origin,
                         first_probability_seconds=session['prob'][0]['available_at_monotonic']-origin,
                         source_end_to_completed_seconds=session['done']['publication_monotonic_sec']-origin-samples/16000,
                         model_call_costs=costs,terminal_punctuation_fallbacks=t['punctuation_terminal_fallbacks']))
    early=r['sessions'][0]
    review=dict(status='PASS_B05_EARLY_STOP_AND_FULL_RESTART_ONLY',bindings=x['bindings'],sessions=rows,
                stop_request_to_controller_return_seconds=early['stop_completed_monotonic']-early['stop_requested_monotonic'],
                same_process=True,asr_model_loads=1,encoder_loaded=False,source_offsets_reset=True,
                session_event_identity_and_probability_frame_origin_checked=True,
                reference_tolerance=1e-5,peak_rss_bytes=r['peak_rss_bytes'],
                sampled_peak_virtual_bytes=max(int(re.search(r'VmPeak:\s+(\d+)',v).group(1))*1024 for m in r['memory_samples'] for v in m['values'] if v.startswith('VmPeak:')),
                natural_process_exit=True,owner_closed=True,application_finalization=True,consumer_archive_drained=True,
                robust_memory_fit=False,UI_tested=False,stage_acceptance=False,persistent_naming=False,accuracy_scored=False)
    for name,value in [('RESULT.json',r),('AUDIT_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)
    for index,a in enumerate(arrays):np.save(out/('session_'+str(index)+'_probabilities.npy'),a,allow_pickle=False)
    remote("import json\nfrom pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/"+repr(run)+"/'REVIEW.json'\nassert not p.exists()\np.write_text("+repr(json.dumps(review,indent=2))+")\nprint(json.dumps({'saved':True}))")
    print(json.dumps({k:v for k,v in review.items() if k not in ('bindings','sessions')},indent=2))


if __name__=='__main__':main()
