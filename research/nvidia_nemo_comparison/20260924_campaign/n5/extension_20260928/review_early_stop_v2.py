"""Independent paired shadow review. See README_EARLY_STOP_V2.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import bind, freeze, load, verify
from metric_process import pin, exact_process


def require(ok,message):
    if not ok:raise ValueError(message)


def review(run,output):
    pin();run=run.resolve(strict=True)
    a=load(run/'ADMISSION.json');r=load(run/'RESULT.json')
    require(not output.exists(),'Fresh review receipt required')
    require(a['scope']=='EXTENDED_WINDOWS_STOP_NEW_RESTART_V2','Wrong source scope')
    require(r['status']=='PASS_NEMOTRON_WINDOWS_LIFECYCLE_SMOKE' and r['error'] is None,'Run failed')
    require(r['admission']==bind(run/'ADMISSION.json'),'Admission/terminal mismatch')
    require(a['backend_key'] in ('nemotron_hybrid','nemotron_600m'),'Unadmitted backend')
    require(a['application_cpus']==[4,14] and a['numerical_threads_per_model']==1,'Resource binding differs')
    runtime=next(row for row in a['runtime_configs'] if Path(row['path']).name=='n2_runtime.json')
    require(not {'titanet_manifest','titanet_manifest_sha256','embedding_namespace'} & set(load(runtime['path'])),'Retired E1 fields remain')
    require(load(a['source_receipt']['path'])['schema']=='prepi-e0-runtime-derivative-v1','Wrong source derivative')
    owners=[a['owner'],{k:a['supervisor'][k] for k in ('pid','create_time')}]
    for who in owners:require(exact_process(who) is None,'Run owner is still present')
    for b in a['code']+a['release_files']+a['assets']+a['runtime_configs']+[a['source_receipt'],a['acceptance'],a['audio'],a['census'],a['window']]:verify(b)
    require([p['phase'] for p in r['phases']]==['infer','reopen'],'Missing lifecycle phases')
    phases=[]
    for phase in r['phases']:
        verify(phase['result']);verify(phase['lifetime'])
        result=load(phase['result']['path']);life=load(phase['lifetime']['path'])
        require(exact_process(result['owner']) is None and exact_process(life['owner']) is None,'Phase owner remains active')
        require(Path(phase['result']['path'])==run/phase['phase']/'RESULT.json','Foreign phase')
        require(result['status']=='PASS_NEMOTRON_PHASE' and not result['errors'],'Phase failed')
        require(result['controller_closed'] and result['worker_alive'] is False and result['lock_released'],'Controller ownership retained')
        require(result.get('controller_error') is None,'Controller error was not cleared by successful execution')
        require(result['rendered_rows']>0 and result['stored_rows']>0 and result['sentinel_preserved'],'Missing display/storage/preservation evidence')
        require(result['saved_audio_only'] and all(x.get('status')=='DISABLED_SAVED_AUDIO_ONLY' for x in result['output_observations']),'Device suppression absent')
        require(life['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and life['forced'] is False
            and life['job_empty_verified'] and life['root_exit_code']==0 and life['observed_members_exited'],'Process closure failed')
        require(result['pages']==[dict(requested=p,actual=p) for p in ('modes','backends','sessions','settings')],'Navigation coverage missing')
        require(result['mode']=='anonymous_conversation','Mode scope differs')
        if phase['phase']=='infer':
            e=result['early_stop']
            require(e.get('explicit_new_transcript') and e.get('earlier_draft_preserved'),'New-transcript boundary absent')
            require(0<e['requested_after_samples']<=e['source_samples']<e['full_file_samples'],'Not an early Stop')
            require(e['source_samples']==e['asr_samples']==e['identity_samples'],'Early accepted-prefix drain differs')
            require(e['speaker_lag_sec']==0 and e['workers_joined'] and e['actually_skipped_samples']==0,'Early drain/ownership failure')
            require(e['cleanup']['owned_threads_joined'],'Early cleanup missing')
            import hashlib,wave
            with wave.open(a['audio']['path'],'rb') as wav:
                require(hashlib.sha256(wav.readframes(e['source_samples'])).hexdigest()==e['accepted_prefix_sha256'],'Early source prefix hash differs')
            require(result['model_cache']['streams']==2,'Not two resident-model streams')
            t=result['telemetry']
            require(result['expected_samples']>0 and result['source_samples']==result['asr_samples']==result['identity_samples']==result['expected_samples'],'Incomplete audio')
            require(result['writers_drained'] and result['speaker_lag_sec']==0,'Undrained inference')
            require(result['model_cache']['asr_loads']==1 and result['model_cache']['speaker_loads']==1 and t['n2_embedding_calls']>0,'E0 or ASR not exercised')
            require(result['activity_frame_count']>0 and len(t['n2_seen_slots'])>=2,'Native speaker activity missing')
            require(not t.get('live_lanes_at_finalization') and not t.get('bundle_retained_due_live_lanes'),'Inference finalization retained workers')
            verify(result['shadow']);shadow=load(result['shadow']['path'])
            verify(a['shadow_reference_review']);verify(a['shadow_reference_result'])
            reference_review=load(a['shadow_reference_review']['path']);reference=load(a['shadow_reference_result']['path'])
            require(reference_review['status']=='PASS_PREPI_ONE_FILE_WINDOWS_LIFECYCLE_ONLY' and reference_review['backend_key']==a['backend_key'],'Reference review invalid')
            require(reference_review['phases'][0]['result']==a['shadow_reference_result'],'Reference binding differs')
            for key in ('expected_samples','source_samples','asr_samples','identity_samples','activity_frame_count',
                        'activity_fingerprint','caption_fingerprint','stored_caption_fingerprint'):
                require(result[key]==reference[key],'Matched shadow output differs: '+key)
            require(result['shadow_parity_passed'] and shadow['status']=='SHADOW_ONLY_ALL_AUDIO_RETAINED','Shadow parity absent')
            require(shadow['samples']==result['expected_samples'] and shadow['actually_skipped_samples']==0,'Shadow dropped audio')
            import hashlib,wave
            with wave.open(a['audio']['path'],'rb') as wav:
                require(hashlib.sha256(wav.readframes(wav.getnframes())).hexdigest()==shadow['source_pcm_sha256'],'Observed PCM hash differs')
            cursor=0;counts=dict(G01=0,G02=0,G03=0)
            for row in shadow['rows']:
                require(row['start_sample']==cursor and cursor<row['end_sample']<=cursor+320,'Shadow mapping is discontinuous')
                require(row['actually_skipped'] is False and set(row['proposed_skip'])==set(counts),'Unexpected applied gate')
                for name in counts:
                    require(type(row['proposed_skip'][name]) is bool,'Invalid proposal flag')
                    if row['proposed_skip'][name]:counts[name]+=row['end_sample']-cursor
                cursor=row['end_sample']
            require(cursor==shadow['samples'] and len(shadow['rows'])==shadow['blocks'],'Incomplete shadow map')
            for name,count in counts.items():
                method=shadow['proposed_methods'][name]
                require(method['proposed_skip_samples']==count,'Proposal aggregation differs')
                require(abs(method['proposed_skip_fraction']-count/cursor)<1e-12,'Proposal fraction differs')
                require(count<=method['below_threshold_samples']<=cursor,'Proposal exceeds below-threshold samples')
            shadow_summary={k:v for k,v in shadow.items() if k!='rows'}
            summary=dict(early_stop=e,shadow=shadow_summary,expected_samples=result['expected_samples'],asr_samples=result['asr_samples'],
                identity_samples=result['identity_samples'],activity_frame_count=result['activity_frame_count'],
                activity_fingerprint=result['activity_fingerprint'],caption_fingerprint=result['caption_fingerprint'],
                stored_caption_fingerprint=result['stored_caption_fingerprint'],embedding_calls=t['n2_embedding_calls'],
                model_cache=result['model_cache'])
        else:require(result['test_session_deleted'] and result.get('early_test_session_deleted'),'Both test session deletions unverified')
        phases.append(dict(phase=phase['phase'],result=phase['result'],lifetime=phase['lifetime'],
            rendered_rows=result['rendered_rows'],stored_rows=result['stored_rows']))
    for who in owners:require(exact_process(who) is None,'Closed owner changed')
    result=dict(status='PASS_STOP_NEW_TRANSCRIPT_FULL_RESTART_WINDOWS_ONLY',utc=datetime.now(timezone.utc).isoformat(),
        admission=bind(run/'ADMISSION.json'),terminal=bind(run/'RESULT.json'),source_receipt=a['source_receipt'],
        backend_key=a['backend_key'],phases=phases,summary=summary,closed_owners=owners,
        source_files_verified=len(a['release_files']),assets_verified=len(a['assets']),
        all_owners_exited=True,N4_accepted=False,N5_complete=False,CM5_tested=False,
        scope='One early stopped prefix drained then same full saved file restarted; exact full reference parity and resident model reuse; Windows only, no sustained performance qualification')
    freeze(output,result)
    print(dict(status=result['status'],backend=a['backend_key'],output=str(output),summary=summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();review(args.run,args.output)
