"""Independently review closed Windows startup/control evidence. README_UI_ERROR_V1.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import bind,freeze,load,verify
from metric_process import pin,exact_process

def require(ok,message):
    if not ok:raise ValueError(message)

def review(run,output):
    pin();require(not output.exists(),'Fresh receipt required')
    a=load(run/'ADMISSION.json');r=load(run/'RESULT.json')
    require(a['scope']=='EXTENDED_WINDOWS_CONTROLS_V2' and r['status']=='PASS_WINDOWS_CONTROLS_SMOKE' and r['error'] is None,'Run incomplete')
    require(r['admission']==bind(run/'ADMISSION.json'),'Admission differs')
    for b in a['code']+a['release_files']+a['assets']+a['runtime_configs']+[a['source_receipt'],a['acceptance'],a['audio'],a['census'],a['window']]:verify(b)
    d=load(a['source_receipt']['path']);require(d['schema']=='extended-ui-error-priority-v1' and d['changed_code']==['app/ui.py'],'Unexpected GUI derivative')
    verify(d['parent_source_receipt'])
    owners=[a['owner'],{k:a['supervisor'][k] for k in ('pid','create_time')}]
    require(len(r['phases'])==1 and r['phases'][0]['phase']=='controls','Wrong phases')
    p=r['phases'][0];verify(p['result']);verify(p['lifetime'])
    c=load(p['result']['path']);life=load(p['lifetime']['path']);owners += [c['owner'],life['owner']]
    require(all(exact_process(o) is None for o in owners),'Live owner remains')
    require(c['status']=='PASS_CONTROLS_PHASE' and not c['errors'],'Phase failed')
    require(c['controller_closed'] and not c['worker_alive'] and c['lock_released'],'Controller closure absent')
    require(life['status']=='OWNED_PROCESS_LIFETIME_CLOSED' and not life['forced'] and life['job_empty_verified']
        and life['root_exit_code']==0 and life['observed_members_exited'],'Process closure failed')
    require([x['case'] for x in c['cases']]==['invalid_runtime_selection','missing_d1_at_start'],'Fault cases missing')
    for x in c['cases']:require(x['state']=='ERROR' and x['error'] and x['error'][:120] in x['rendered_error'],'Hidden startup fault')
    require(c['cases'][1]['backend_id']==c['backend_id'],'Fallback occurred')
    require([x['control'] for x in c['controls']]==['mode_caption_only','mode_anonymous_conversation','recipe_patient','recipe_balanced'],'Control coverage differs')
    s=c['recovery'];require(s['source_samples']>=128000 and s['source_samples']==s['asr_samples']==s['identity_samples']
        and s['embedding_calls']>0 and s['caption_rows']>0 and s['cleanup']['owned_threads_joined'],'Recovery incomplete')
    require(c['baseline_rollback'] and c['sentinel_preserved'] and c['saved_audio_only'],'Rollback/isolation absent')
    require(all(x.get('status')=='DISABLED_SAVED_AUDIO_ONLY' for x in c['output_observations']),'Hardware access not suppressed')
    summary=dict(status='PASS_WINDOWS_CONTROLS_STARTUP_RECOVERY_ONLY',utc=datetime.now(timezone.utc).isoformat(),
        admission=bind(run/'ADMISSION.json'),terminal=bind(run/'RESULT.json'),phase=p,backend_key=a['backend_key'],
        controls=c['controls'],cases=c['cases'],recovery=s,closed_owners=owners,all_owners_exited=True,
        source_files_verified=len(a['release_files']),N4_accepted=False,N5_complete=False,CM5_tested=False)
    freeze(output,summary);print(dict(status=summary['status'],output=str(output)))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();review(args.run,args.output)
