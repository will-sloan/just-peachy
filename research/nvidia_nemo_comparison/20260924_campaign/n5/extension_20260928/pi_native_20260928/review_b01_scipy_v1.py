"""Independent saved-file B01 reader. See README_B01_SCIPY_REVIEW_V1.md."""
import argparse,hashlib,json,psutil
from dispatch_geometry_v2 import remote,PRIVATE

def main():
    psutil.Process().cpu_affinity([14]);p=argparse.ArgumentParser();p.add_argument('--run-id',choices=['b01-defer-scipy-v1','b01-defer-scipy-full-v1'],required=True);args=p.parse_args()
    full='full' in args.run_id; expected=715127 if full else 192000
    out=PRIVATE/(args.run_id+'-evidence');assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    x=remote('RUN='+repr(args.run_id)+'\nEXPECTED='+str(expected)+'\n'+r"""
import os,json,hashlib,subprocess,math,ast
from pathlib import Path
os.sched_setaffinity(0,{3});root=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928');d=root/RUN

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text());r=json.loads((d/'RESULT.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
assert a['address_space_max_bytes']==768*1024**2 and r['startup_stack_rlimit_bytes']==[1048576,1048576]
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/n).read_text());pp=Path('/proc',str(o['pid']),'stat');t=int(pp.read_text().rsplit(')',1)[1].split()[19]) if pp.exists() else None
 assert not(boot==o['boot_id'] and t==o['start_ticks']) and o['admission_sha256']==sha(d/'ADMISSION.json')
u=dict(l.split('=',1) for l in subprocess.check_output(['systemctl','--user','show','jp-'+RUN,'-p','MainPID','-p','ActiveState','-p','Result','-p','ExecMainStatus'],text=True).splitlines())
assert u['MainPID']=='0' and u['Result']=='success' and u['ExecMainStatus']=='0'
assert r['controller_closed'] and r['redim_encoder_loaded'] and r['mode']=='open_with_names' and r['empty_gallery']
assert r['model_load_counts']['asr_loads']==r['model_load_counts']['speaker_loads']==1
assert not r['scipy_modules_at_import'] and not r['scipy_modules_at_completion'] and len(r['e0_session_loads'])==1
assert r['status'].endswith('COLLECTED_REQUIRES_REVIEW')
sessions=list((d/'data/sessions').iterdir());assert len(sessions)==1;s=sessions[0]
ev=[json.loads(l) for l in (s/'events.jsonl').read_text().splitlines()];f=json.loads((s/'session_finalization_v3.json').read_text());c=json.loads((s/'s6d_consumer_closure.json').read_text())
assert f['state']=='COMPLETED' and not f['live_lanes_at_finalization'] and f['event_and_transcript_handles_closed'] and not f['finalization_error']
assert f['source_samples']==f['identity_samples']==EXPECTED and c['full_event_consumer_drained']
for k in ['journal','policy','punctuation']:
 q=c['queues'][k];assert not q['error'] and not q['thread_alive'] and q['closed'] and q['depth']==0 and q['accepted']==q['completed']
assert not any(v['event_type']=='failure' for v in ev)
def payloads(name):return [v['payload'] for v in ev if v['event_type']==name]
completed=payloads('session_completed');assert len(completed)==1;tel=completed[0]['telemetry']
assert tel['paired_audio_samples']==tel['identity_audio_samples']==EXPECTED and tel['asr_cursor_sec']==EXPECTED/16000 and not tel['punctuation_inference_failures'] and not tel['audio_frames_dropped']
probs=payloads('n2_diarization_frames');rows=[]
for v in probs:
 assert v['frame_start']==len(rows);rows.extend(v['probabilities'])
assert len(rows)==(4470 if EXPECTED==715127 else 1201) and all(len(v)==8 and all(math.isfinite(x) for x in v) for v in rows)
ref_run='b05-native-stack-v1' if EXPECTED==715127 else 'b05-anonymous-v1'
refs=list((root/ref_run/'data/sessions').iterdir());reference=None
for ss in refs:
 ee=[json.loads(l) for l in (ss/'events.jsonl').read_text().splitlines()]
 rr=[v['payload'] for v in ee if v['event_type']=='n2_diarization_frames'];arr=[v for entry in rr for v in entry['probabilities']]
 if len(arr)==len(rows):reference=arr;ref_path=ss/'events.jsonl'
assert reference is not None
error=max(abs(a-b) for x,y in zip(rows,reference) for a,b in zip(x,y));assert error<=1e-5
emb=payloads('research_embedding');assert emb and len(emb)==tel['n2_embedding_calls']
for v in emb:
 a0,b0=v['source_start_sec'],v['source_end_sec'];vec=v['normalized_embedding']
 assert 0<=a0<b0<=EXPECTED/16000 and .5-1e-6<=b0-a0<=2+1e-6 and v['left_padding_sec']==0 and v['actual_selected_window'] and len(vec)==192 and all(math.isfinite(x) for x in vec) and abs(sum(x*x for x in vec)-1)<1e-5
 assert v['receptive_start_sec']==a0 and v['receptive_end_sec']==b0
 assert v['model_namespace']['model_sha256']=='5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609'
final=json.loads((d/'FINAL_SNAPSHOT.json').read_text());assert final['rows'] and not final['error']
assert not any(v.get('latest_known_profile_id') or v.get('latest_known_name') for v in payloads('transcript_label_revision'))
source=payloads('source_started')[0];epoch=source['source_epoch_monotonic_sec'];text=payloads('s6d_text_ready')
assert source['mode']=='file' and source['start_sample']==0 and source['gain']==1 and text
bindings={str(p.relative_to(d)):sha(p) for p in [d/'RESULT.json',d/'ADMISSION.json',d/'FINAL_SNAPSHOT.json',d/'OWNER.json',d/'DISPATCH_OWNER.json',s/'events.jsonl',s/'session_finalization_v3.json',s/'s6d_consumer_closure.json']}
memory={k:max(int(v.split()[1])*1024 for entry in r['memory_samples'] for v in entry['values'] if v.startswith(k+':')) for k in ['VmSize','VmRSS','VmPeak']}
print(json.dumps(dict(result=r,bindings=bindings,unit=u,samples=EXPECTED,frame_count=len(rows),reference_max_abs=error,reference_path=str(ref_path),reference_sha256=sha(ref_path),embeddings=emb,embedding_count=len(emb),first_text_seconds=text[0]['publication_monotonic_sec']-epoch,first_D1_seconds=probs[0]['publication_monotonic_sec']-epoch,drain_seconds=completed[0]['publication_monotonic_sec']-(epoch+EXPECTED/16000),memory=memory,source=source,finite_norm_and_window_checks=True,empty_gallery_no_personal_names=True)))
""")
    review=dict(status='PASS_B01_SAVED_FILE_PASSAGE_DRAIN_E0_REFERENCE_PENDING',run_id=args.run_id,scope='full_source' if full else 'constructed_12s_prefix',owner_closed=True,natural_exit_code=0,bindings=x['bindings'],unit=x['unit'],source_samples=x['samples'],D1_frames=x['frame_count'],D1_reference_max_abs=x['reference_max_abs'],D1_reference_sha256=x['reference_sha256'],E0_calls=x['embedding_count'],E0_finite_normalized_and_exact_source_windows=True,E0_independent_array_parity=False,first_text_seconds=x['first_text_seconds'],first_D1_seconds=x['first_D1_seconds'],EOF_drain_seconds=x['drain_seconds'],sampled_memory_bytes=x['memory'],peak_rss_bytes=x['result']['peak_rss_bytes'],scipy_loaded=False,retained_E0_loaded=True,empty_gallery_no_personal_names=True,application_archive_process_drained=True,GUI_validated=False,Stop_restart_validated=False,accuracy_scored=False,release_accepted=False)
    for name,value in [('REVIEW_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
    remote("from pathlib import Path\np=Path("+repr('/home/peachyprototype/JustPeachy/research/nemotron-20260928/'+args.run_id+'/REVIEW.json')+")\nwith p.open('x') as f:f.write("+repr(json.dumps(review,indent=2))+")\nprint('{}')")
    print(json.dumps({k:v for k,v in review.items() if k!='bindings'}))
if __name__=='__main__':main()
