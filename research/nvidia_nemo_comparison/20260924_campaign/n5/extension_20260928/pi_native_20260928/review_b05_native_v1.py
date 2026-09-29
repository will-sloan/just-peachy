"""Independent native B05 passage/closure reader. See README_B05_REVIEW_V1.md."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--samples', type=int, required=True)
    args = parser.parse_args()
    assert args.run_id in ('b05-anonymous-v1', 'b05-anonymous-full-v1')
    assert args.samples == (192000 if args.run_id == 'b05-anonymous-v1' else 715127)
    psutil.Process().cpu_affinity([14])
    code = r'''
import hashlib,json,os,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3})
root=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928');d=root/RUN
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
r=json.loads((d/'RESULT.json').read_text());owner=json.loads((d/'OWNER.json').read_text())
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
try:start=int(Path('/proc',str(owner['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])
except FileNotFoundError:start=None
assert not(boot==owner['boot_id'] and start==owner['start_ticks'])
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
sessions=list((d/'data/sessions').iterdir());assert len(sessions)==1;s=sessions[0]
names=['session_summary.json','session_finalization_v3.json','s6d_consumer_closure.json']
documents={n:json.loads((s/n).read_text()) for n in names}
events=[json.loads(x) for x in (s/'events.jsonl').read_text().splitlines()]
prob=[e['payload'] for e in events if e['event_type']=='n2_diarization_frames']
punct=[e['payload']['punctuation'] for e in events if e['event_type']=='s6d_punctuation_revision']
source=next(e['payload'] for e in events if e['event_type']=='source_started')
text_times=[e['payload'].get('publication_monotonic_sec') for e in events if e['event_type']=='s6d_text_ready']
done=next(e['payload'] for e in events if e['event_type']=='session_completed')
snapshot=json.loads((d/'FINAL_SNAPSHOT.json').read_text())
print(json.dumps(dict(result=r,documents=documents,prob=prob,punct=punct,source=source,done=done,
 text_times=text_times,snapshot=snapshot,owner_closed=True,bindings={str(p.relative_to(d)):sha(p) for p in [d/'RESULT.json',d/'ADMISSION.json',s/'events.jsonl',*[s/n for n in names]]})))
'''
    x = remote('RUN='+repr(args.run_id)+'\n'+code)
    out = PRIVATE/(args.run_id+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code'] == 0
    r = x['result']; documents = x['documents']
    assert r['status'] == 'B05_SHORT_SHARED_CONTROLLER_COLLECTED_REQUIRES_REVIEW'
    assert r['controller_closed'] and not r['redim_encoder_loaded']
    assert r['model_load_counts']['speaker_loads'] == 0 and r['model_load_counts']['asr_loads'] == 1
    assert not x['snapshot']['error'] and r['row_count'] > 0
    f = documents['session_finalization_v3.json']
    assert f['state'] == 'COMPLETED' and not f['finalization_error'] and not f['live_lanes_at_finalization']
    assert f['event_and_transcript_handles_closed'] and not f['resident_bundle_lease_retained']
    assert f['source_samples'] == f['identity_samples'] == args.samples
    c = documents['s6d_consumer_closure.json']
    assert c['state'] == 'COMPLETED' and c['full_event_consumer_drained']
    assert c['queues']['event_consumer']['depth'] == 0
    for name in ('journal', 'punctuation', 'policy'):
        q = c['queues'][name]
        assert q['closed'] and not q['thread_alive'] and not q['error'] and q['depth'] == 0
        assert q['accepted'] == q['completed']
    summary = documents['session_summary.json']; t = summary['telemetry']
    assert summary['state'] == 'COMPLETED' and t['audio_frames_dropped'] == 0
    assert t['n2_embedding_calls'] == 0 and t['n2_embedding_policy'] == 'BYPASSED_ANONYMOUS_NATIVE_SLOTS'
    assert t['identity_audio_samples'] == t['paired_audio_samples'] == args.samples
    costs = t['component_costs']['rows']
    for name in ('asr_accept', 'diarizer_push'):
        assert costs[name]['successful_samples'] == args.samples and costs[name]['errors'] == 0
    for row in costs.values():
        assert row['errors'] == 0 and row['in_flight'] == 0 and row['started'] == row['completed']
    assert costs['embedding']['started'] == 0
    assert t['punctuation_inference_failures'] == 0
    assert x['punct'] and all(p['status'] == 'learned' and p['error'] is None for p in x['punct'])
    # Terminal-period fallback is separately visible; it is not model failure.
    arrays=[]; cursor=0
    for payload in x['prob']:
        a=np.asarray(payload['probabilities'],dtype=np.float32)
        assert payload['frame_start'] == cursor and a.ndim == 2 and a.shape[1] == 8
        assert len(a)>0 and np.isfinite(a).all() and (a>=0).all() and (a<=1).all()
        arrays.append(a);cursor+=len(a)
    assert cursor == costs['diarizer_push']['output_frames']+costs['diarizer_finish']['output_frames']
    assert cursor>0
    probabilities=np.concatenate(arrays)
    parity=None
    if args.samples == 715127:
        reference=PRIVATE/'d1-geometry-delayed-metadata2-v1-evidence'
        prior=json.loads((reference/'REVIEW.json').read_text())
        assert hashlib.sha256((reference/'RESULT.json').read_bytes()).hexdigest()==prior['result_sha256']
        ref=np.load(reference/'saved_full.npy',allow_pickle=False)
        assert probabilities.shape == ref.shape == (4470,8)
        parity=float(np.max(np.abs(probabilities-ref)))
        assert parity <= 1e-5
    archive=x['snapshot']['sessions']['last_archive']
    assert archive['closed'] and not archive['worker_alive'] and not archive['archive_error'] and not archive['loss']
    assert archive['source_samples'] == args.samples and archive['queue_items'] == archive['queue_bytes'] == 0
    origin=x['source']['source_epoch_monotonic_sec'];assert x['source']['pacing']=='absolute'
    drain=x['done']['publication_monotonic_sec']-origin-args.samples/16000
    first_text=min(x['text_times'])-origin
    first_prob=x['prob'][0].get('available_at_monotonic')
    review=dict(status='PASS_B05_NATIVE_PASSAGE_AND_CLOSURE_ONLY',run_id=args.run_id,bindings=x['bindings'],
                samples=args.samples,probability_frames=cursor,probability_windows=len(arrays),
                component_reference_max_abs=parity,reference_tolerance=1e-5 if parity is not None else None,
                source_pacing='original_1x',first_text_seconds=first_text,
                first_probability_seconds=first_prob-origin if first_prob is not None else None,
                source_eof_to_session_completed_seconds=drain,caption_rows=r['row_count'],
                model_call_costs=costs,peak_rss_bytes=r['peak_rss_bytes'],
                sampled_peak_virtual_bytes=max(int(re.search(r'VmPeak:\s+(\d+)',v).group(1))*1024 for m in r['memory_samples'] for v in m['values'] if v.startswith('VmPeak:')),
                embedding_calls=0,encoder_loaded=False,punctuation_inference_failures=0,
                terminal_punctuation_fallbacks=t['punctuation_terminal_fallbacks'],
                all_input_samples_retained=True,natural_process_exit=True,owner_closed=True,
                application_finalization=True,consumer_archive_drained=True,
                UI_tested=False,stage_acceptance=False,persistent_naming=False,accuracy_scored=False)
    for name,value in [('RESULT.json',r),('AUDIT_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)
    np.save(out/'probabilities.npy',probabilities,allow_pickle=False)
    remote("import json\nfrom pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/"+repr(args.run_id)+"/'REVIEW.json'\nassert not p.exists()\np.write_text("+repr(json.dumps(review,indent=2))+")\nprint(json.dumps({'saved':True}))")
    print(json.dumps(review,indent=2))


if __name__ == '__main__':main()
