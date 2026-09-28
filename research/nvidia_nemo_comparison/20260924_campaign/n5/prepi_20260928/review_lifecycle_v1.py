"""Independent closed saved-file check review. See README_REVIEW.md."""
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
    require(a['scope']=='PREPI_WINDOWS_LIFECYCLE_V1','Wrong source scope')
    require(r['status']=='PASS_NEMOTRON_WINDOWS_LIFECYCLE_SMOKE' and r['error'] is None,'Run failed')
    require(r['admission']==bind(run/'ADMISSION.json'),'Admission/terminal mismatch')
    require(a['backend_key'] in ('nemotron_hybrid','nemotron_600m'),'Unadmitted backend')
    require(a['application_cpus']==[4,14] and a['numerical_threads_per_model']==1,'Resource binding differs')
    owners=[a['owner'],{k:a['supervisor'][k] for k in ('pid','create_time')}]
    for who in owners:require(exact_process(who) is None,'Run owner is still present')
    for b in a['code']+a['release_files']+a['assets']+a['runtime_configs']+[a['source_receipt'],a['acceptance'],a['audio'],a['census'],a['window']]:verify(b)
    require([p['phase'] for p in r['phases']]==['infer','reopen'],'Missing lifecycle phases')
    phases=[]
    for phase in r['phases']:
        verify(phase['result']);verify(phase['lifetime'])
        result=load(phase['result']['path']);life=load(phase['lifetime']['path'])
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
            t=result['telemetry']
            require(result['expected_samples']>0 and result['source_samples']==result['asr_samples']==result['identity_samples']==result['expected_samples'],'Incomplete audio')
            require(result['writers_drained'] and result['speaker_lag_sec']==0,'Undrained inference')
            require(result['model_cache']['asr_loads']==1 and result['model_cache']['speaker_loads']==1 and t['n2_embedding_calls']>0,'E0 or ASR not exercised')
            require(result['activity_frame_count']>0 and len(t['n2_seen_slots'])>=2,'Native speaker activity missing')
            require(not t.get('live_lanes_at_finalization') and not t.get('bundle_retained_due_live_lanes'),'Inference finalization retained workers')
            summary=dict(expected_samples=result['expected_samples'],asr_samples=result['asr_samples'],
                identity_samples=result['identity_samples'],activity_frame_count=result['activity_frame_count'],
                activity_fingerprint=result['activity_fingerprint'],caption_fingerprint=result['caption_fingerprint'],
                stored_caption_fingerprint=result['stored_caption_fingerprint'],embedding_calls=t['n2_embedding_calls'],
                model_cache=result['model_cache'])
        else:require(result['test_session_deleted'],'Delete not verified')
        phases.append(dict(phase=phase['phase'],result=phase['result'],lifetime=phase['lifetime'],
            rendered_rows=result['rendered_rows'],stored_rows=result['stored_rows']))
    for who in owners:require(exact_process(who) is None,'Closed owner changed')
    result=dict(status='PASS_PREPI_ONE_FILE_WINDOWS_LIFECYCLE_ONLY',utc=datetime.now(timezone.utc).isoformat(),
        admission=bind(run/'ADMISSION.json'),terminal=bind(run/'RESULT.json'),source_receipt=a['source_receipt'],
        backend_key=a['backend_key'],phases=phases,summary=summary,closed_owners=owners,
        source_files_verified=len(a['release_files']),assets_verified=len(a['assets']),
        all_owners_exited=True,N4_accepted=False,N5_complete=False,CM5_tested=False,
        scope='One saved source, actual private-desktop Windows render/save/reopen/delete; not full bank or sustained realtime')
    freeze(output,result)
    print(dict(status=result['status'],backend=a['backend_key'],output=str(output),summary=summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();review(args.run,args.output)
