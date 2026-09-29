"""Independent two-session native reader. See README_ASR_CAUSAL_V1.md."""
import hashlib
import json
from pathlib import Path
import re
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import numpy as np
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    run = 'b01-asr-causal-v1'
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
lease=json.loads((d/'DISPATCH_OWNER.json').read_text());pp=Path('/proc',str(lease['pid']),'stat')
tick=int(pp.read_text().rsplit(')',1)[1].split()[19]) if pp.exists() else None
assert not(boot==lease['boot_id'] and tick==lease['start_ticks'])
u=dict(v.split('=',1) for v in subprocess.check_output(['systemctl','--user','show','jp-'+RUN,'-p','MainPID','-p','Result','-p','ExecMainStatus'],text=True).splitlines())
assert u['MainPID']=='0' and u['Result']=='success' and u['ExecMainStatus']=='0'
assert a['mode']=='open_with_names' and a['empty_new_gallery']
assert a['backend_manifest_id']=='sha256:f8992d25c29658428e87b0defb03c43677793f8f39a5ffa7e3bfdc2a72ab6eef'
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
r=json.loads((d/'RESULT.json').read_text())
assert len(r['sessions'])==2
assert len(list((d/'data/sessions').iterdir()))==2
sessions=[];bindings={n:sha(d/n) for n in ['RESULT.json','ADMISSION.json','EARLY_STOP.json','STOP_SNAPSHOT.json','FINAL_SNAPSHOT.json','SHADOW_EARLY.json','SHADOW_FULL.json']}
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
   emb=[e['payload'] for e in events if e['event_type']=='research_embedding'],
   labels=[e['payload'] for e in events if e['event_type']=='transcript_label_revision'],
   prob=[e['payload'] for e in events if e['event_type']=='n2_diarization_frames'],
   punct=[e['payload']['punctuation'] for e in events if e['event_type']=='s6d_punctuation_revision'],
   text_times=[e['payload']['publication_monotonic_sec'] for e in events if e['event_type']=='s6d_text_ready'],text_cues=[e['payload'] for e in events if e['event_type']=='s6d_text_ready']))
 for path in [s/'events.jsonl',*[s/n for n in names]]:bindings[str(path.relative_to(d))]=sha(path)
print(json.dumps(dict(result=r,sessions=sessions,bindings=bindings,owner_closed=True,shadow=[json.loads((d/n).read_text()) for n in ['SHADOW_EARLY.json','SHADOW_FULL.json']],
 stop_snapshot=json.loads((d/'STOP_SNAPSHOT.json').read_text()),final_snapshot=json.loads((d/'FINAL_SNAPSHOT.json').read_text()))))
'''
    x = remote('RUN='+repr(run)+'\n'+code)
    out = PRIVATE/(run+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code'] == 0
    r = x['result']
    assert r['status'] == 'B01_ASR_SHADOW_COLLECTED_REQUIRES_REVIEW'
    assert r['startup_stack_rlimit_bytes']==[1048576,1048576] and r['native_default_thread_stack_bytes']==1048576
    assert r['harness_retains_early_engine'] is False
    assert r['controller_closed'] and r['redim_encoder_loaded'] and r['no_scipy_loaded'] and r['empty_new_gallery']
    assert r['model_load_counts']['asr_loads'] == 1 and r['model_load_counts']['speaker_loads'] == 1
    assert r['sessions'][1]['epoch'] > r['sessions'][0]['epoch']
    assert x['stop_snapshot']['metrics']['last_worker_cleanup']['owned_threads_joined']
    qualified=PRIVATE/'live-decimator-numpy-v1-evidence'
    qr=json.loads((qualified/'REVIEW.json').read_text(encoding='utf-8'))
    assert qr['status']=='PASS_NATIVE_NUMPY_FIR_COMPONENT_ONLY'
    fp=qualified/'saved_full.npy';assert hashlib.sha256(fp.read_bytes()).hexdigest()==qr['bindings']['saved_full.npy']
    expected_audio=np.load(fp,allow_pickle=False)
    for key,item in zip(['early_conversion','full_conversion'],r['sessions']):
        cv=r[key];n=item['source_samples'];assert cv['model_samples']==n and cv['native_samples']==n*3
        assert cv['filter_delay_seconds']==.001 and cv['constructed_only'] and cv['no_appended_tail']
        assert cv['output_float32_sha256']==hashlib.sha256(expected_audio[:n].tobytes()).hexdigest()
    ref_dir=PRIVATE/'b01-fir-references-v1-evidence';ref_review=json.loads((ref_dir/'REVIEW.json').read_text(encoding='utf-8'))
    assert ref_review['status']=='PASS_NATIVE_FILTERED_APPLICATION_D1_E0_REFERENCES_ONLY'
    plan=json.loads((ref_dir/'AUDIT_INPUTS.json').read_text(encoding='utf-8'))['plan']
    for n,digest in ref_review['bindings'].items():
        if n.endswith('.npy'):assert hashlib.sha256((ref_dir/n).read_bytes()).hexdigest()==digest
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
        assert t['n2_embedding_calls']==len(session['emb'])>0 and t['n2_embedding_policy']=='UNCHANGED_NAMING_OR_RESEARCH'
        costs=t['component_costs']['rows']
        for name in ('asr_accept','diarizer_push'):assert costs[name]['successful_samples']==samples
        for row in costs.values():assert row['errors']==row['in_flight']==0 and row['started']==row['completed']
        assert costs['embedding']['started']==len(session['emb']) and t['punctuation_inference_failures']==0
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
            full_reference=np.load(PRIVATE/'b01-fir-references-v1-evidence/d1_1.npy',allow_pickle=False)[0]
            assert probabilities.shape==full_reference.shape==(4470,8)
            parity=float(np.max(np.abs(probabilities-full_reference)));assert parity<=1e-5
        embedding_difference=None
        for emb in session['emb']:
            a0,b0=emb['source_start_sec'],emb['source_end_sec'];vec=np.asarray(emb['normalized_embedding'],dtype=np.float32)
            assert 0<=a0<b0<=samples/16000 and .5-1e-6<=b0-a0<=2+1e-6
            assert emb['left_padding_sec']==0 and emb['receptive_start_sec']==a0 and emb['receptive_end_sec']==b0
            assert vec.shape==(192,) and np.isfinite(vec).all() and abs(float(np.linalg.norm(vec))-1)<1e-5
            assert emb['session_id']==Path(item['session_dir']).name and emb['tracker_id'].startswith(Path(item['session_dir']).name+':')
        if index:
            prior=[(i,q) for i,q in enumerate(plan['embeddings']) if q['session']==1];assert len(prior)==len(session['emb'])
            embedding_difference=0.
            for emb,(qi,q) in zip(session['emb'],prior):
                assert round(emb['source_start_sec']*16000)==q['first'] and round(emb['source_end_sec']*16000)==q['last']
                vec=np.load(ref_dir/f'e0_{qi:03d}.npy',allow_pickle=False)[0]
                err=float(np.max(np.abs(vec-np.asarray(emb['normalized_embedding'],dtype=np.float32))))
                assert err<=1e-5;embedding_difference=max(embedding_difference,err)
        assert not any(e.get('latest_known_name') or e.get('latest_known_profile_id') for e in session['labels'])
        archive=snapshot['sessions']['last_archive']
        assert archive['closed'] and not archive['worker_alive'] and not archive['archive_error'] and not archive['loss']
        assert archive['source_samples']==samples and archive['queue_items']==archive['queue_bytes']==0
        rows.append(dict(kind=item['kind'],samples=samples,probability_frames=cursor,probability_windows=len(chunks),
                         reference_max_abs=parity,E0_calls=len(session['emb']),E0_full_restart_max_abs=embedding_difference,caption_rows=len(snapshot['rows']),
                         first_text_seconds=min(session['text_times'])-origin,
                         first_probability_seconds=session['prob'][0]['available_at_monotonic']-origin,
                         source_end_to_completed_seconds=session['done']['publication_monotonic_sec']-origin-samples/16000,
                         model_call_costs=costs,terminal_punctuation_fallbacks=t['punctuation_terminal_fallbacks']))
    assert r['root_withdrawn'] and r['Tk_destroyed'] and not r['callback_errors']
    assert r['withdrawn_Tk_constructed'] and r['GUI_tested'].startswith('withdrawn widgets')
    assert len(r['widget_rows'])==r['row_count'] and r['widget_rows']
    for widget in r['widget_rows']:
        assert widget['label'] in ('','Speaker 1','Speaker 2','Unknown')
        assert widget['actual_text']==(widget['label']+'\n' if widget['label'] else '')+widget['caption']+'\n\n'
    shadows=[]
    for session,sh in zip(x['sessions'],x['shadow']):
        assert sh['samples']==session['item']['source_samples'] and sh['actual_audio_skipped']==0
        assert sh['pre_roll_seconds']==sh['post_roll_seconds']==1 and sh['decision_delay_seconds']==2
        assert sh['energy_dbfs']==-55 and sh['strict_deployable_skip_qualified'] is False
        assert not sh['ASR_watermark_available'] and sh['missing_health_would_retain'] and not sh['buffer_implemented']
        blocks=sh['blocks'];cues=sh['cues'];n=0
        for q in blocks:
            assert q['first']==n and 0<q['last']-q['first']<=320;n=q['last']
            data=expected_audio[q['first']:q['last']].astype(np.float64);rms=float(np.sqrt(np.mean(data*data)));db=20*np.log10(rms) if rms>0 else -300.
            assert abs(db-q['rms_dbfs'])<1e-9 and q['energy_positive']==(db>=-55.)
        assert n==sh['samples'] and len(sh['frames'])==len(blocks)
        byid={q['event_id']:q for q in session['text_cues']};assert len(cues)==len(byid)>0
        for q in cues:
            e=byid[q['event_id']];assert q['first_sec']==e['source_start_sec'] and q['last_sec']==e['source_end_sec']
            assert q['observed']+session['source']['source_epoch_monotonic_sec']>=e['publication_monotonic_sec']-1e-6
        def audit(rows):
            for q in rows:
                a,b=q['first_sec'],q['last_sec'];deadline=b+2
                assert q['decision_deadline_sec']==deadline and q['actual_action']=='KEEP_ALL_SHADOW'
                overlap=lambda lo,hi:hi>a and lo<b
                ap=any(c['observed']<=deadline and overlap(max(0,c['first_sec']-1),c['last_sec']+1) for c in cues)
                ep=any(e['observed']<=deadline and e['energy_positive'] and overlap(max(0,e['first']/16000-.2),e['last']/16000+.4) for e in blocks)
                late=any(overlap(max(0,c['first_sec']-1),c['last_sec']+1) for c in cues) and not ap
                assert q['asr_positive']==ap and q['energy_positive']==ep and q['late_asr_support']==late
                assert q['union_diagnostic_skip']==(not(ap or ep)) and q['asr_only_negative_control_skip']==(not ap)
        audit(sh['frames']);audit(sh['whole_chunks'])
        cursor=0.
        for q in sh['whole_chunks']:
            assert abs(q['first_sec']-cursor)<1e-9 and abs(q['last_sec']-min(cursor+21.12,sh['audio_seconds']))<1e-9;cursor=q['last_sec']
        assert abs(cursor-sh['audio_seconds'])<1e-9
        for field,key,rows2 in [('union_diagnostic_skip_seconds','union_diagnostic_skip',sh['frames']),('whole_chunk_diagnostic_skip_seconds','union_diagnostic_skip',sh['whole_chunks']),('ASR_only_negative_control_skip_seconds','asr_only_negative_control_skip',sh['frames'])]:
            assert abs(sh[field]-sum(q['last_sec']-q['first_sec'] for q in rows2 if q[key]))<1e-9
        cb=sh['causal_buffer'];assert cb['status']=='ONLINE_BOUNDED_SHADOW_ONLY'
        assert cb['capacity_samples']==48000 and cb['capacity_audio_bytes']==192000 and cb['maximum_samples']<=48000
        assert cb['pending_samples']==0 and cb['received_samples']==cb['completed_samples']==n and cb['asr_finished'] and not cb['health_failed']
        assert cb['ingress_sha256']==cb['egress_sha256']==hashlib.sha256(expected_audio[:n].tobytes()).hexdigest()
        assert cb['actual_skipped_samples']==0 and cb['progress_is_completion_not_speech_truth']
        ds=cb['decisions'];progress=cb['progress'];cursor=0
        assert len(ds)==len(blocks)
        for d in ds:
            assert d['first']==cursor and d['last']>cursor and d['actual_action']=='KEEP_ALL_SHADOW';cursor=d['last']
            a,b=d['first']/16000,d['last']/16000
            known=[v for v in progress if v['observed']<=d['decided']]
            done=known[-1]['completed_samples'] if known else 0
            failed=known[-1]['failed'] if known else False
            assert d['completed_samples']==done and d['health_failed']==failed
            ap=any(c['observed']<=d['decided'] and c['last_sec']+1>a and max(0,c['first_sec']-1)<b for c in cues)
            ep=any(e['observed']<=d['decided'] and e['energy_positive'] and e['last']/16000+.4>a and max(0,e['first']/16000-.2)<b for e in blocks)
            assert d['asr_positive']==ap and d['energy_positive']==ep
            if d['reason'] not in ('BUFFER_PRESSURE_KEEP','EOF_KEEP'):
                assert d['decided']>=b+3.
                expected='ASR_POSITIVE' if ap else 'ENERGY_POSITIVE' if ep else 'MISSING_PROGRESS_KEEP' if failed or done<d['last']+16000 else 'QUIET_CANDIDATE_UNQUALIFIED'
                assert d['reason']==expected
            late=d['reason']=='QUIET_CANDIDATE_UNQUALIFIED' and any(c['observed']>d['decided'] and c['last_sec']+1>a and max(0,c['first_sec']-1)<b for c in cues)
            assert d['late_positive_support']==late
        assert cursor==n and all(a['completed_samples']<=b['completed_samples'] for a,b in zip(progress,progress[1:]))
        assert len(r['causal_model_free_cases'])==7 and all(v['pass_case'] for v in r['causal_model_free_cases'])
        sh['causal_summary']={k:v for k,v in cb.items() if k not in ('decisions','progress')}
        sh['causal_summary']['reason_seconds']={reason:sum((d['last']-d['first'])/16000 for d in ds if d['reason']==reason) for reason in sorted(set(d['reason'] for d in ds))}
        shadows.append({k:v for k,v in sh.items() if k not in ('blocks','cues','frames','whole_chunks','causal_buffer')})
    early=r['sessions'][0]
    review=dict(startup_stack_limit_bytes=1048576,native_default_thread_stack_bytes=1048576,status='PASS_NATIVE_CAUSAL_BUFFER_SHADOW_AND_FULL_MODEL_PARITY_ONLY',causal_model_free_cases=r['causal_model_free_cases'],shadow=shadows,bindings=x['bindings'],sessions=rows,
                stop_request_to_controller_return_seconds=early['stop_completed_monotonic']-early['stop_requested_monotonic'],
                same_process=True,asr_model_loads=1,encoder_loaded=True,encoder_model_loads=1,empty_new_gallery=True,D1_E0_full_reference_qualified=True,early_numeric_repeat_qualified=False,source_offsets_reset=True,conversion=r['full_conversion'],early_conversion=r['early_conversion'],FIR_reference_review_sha256=hashlib.sha256((qualified/'REVIEW.json').read_bytes()).hexdigest(),
                session_event_identity_and_probability_frame_origin_checked=True,
                reference_tolerance=1e-5,peak_rss_bytes=r['peak_rss_bytes'],
                sampled_peak_virtual_bytes=max(int(re.search(r'VmPeak:\s+(\d+)',v).group(1))*1024 for m in r['memory_samples'] for v in m['values'] if v.startswith('VmPeak:')),
                natural_process_exit=True,owner_closed=True,application_finalization=True,consumer_archive_drained=True,
                robust_memory_fit=False,UI_tested='native withdrawn widgets with model inference',widget_rows_checked=len(r['widget_rows']),physical_layout_qualified=False,Tk_destroyed=True,stage_acceptance=False,persistent_naming=False,accuracy_scored=False)
    for name,value in [('RESULT.json',r),('AUDIT_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2)
    for index,a in enumerate(arrays):np.save(out/('session_'+str(index)+'_probabilities.npy'),a,allow_pickle=False)
    remote("import json\nfrom pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')/"+repr(run)+"/'REVIEW.json'\nassert not p.exists()\np.write_text("+repr(json.dumps(review,indent=2))+")\nprint(json.dumps({'saved':True}))")
    print(json.dumps(dict(status=review['status'],peak_rss_bytes=review['peak_rss_bytes'],shadow=[v['causal_summary'] for v in shadows]),indent=2))


if __name__=='__main__':main()
