"""Independent closed-run review; see README_D1_ANONYMOUS_REVIEW_V1.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'n4'))
from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, pin
from d1_anonymous_lifecycle_v4 import acceptance, bypass_acceptance, checked_inputs, require


def review(parent, candidate, output):
    pin()
    arms=[]; owners=[]
    for name,root in [('parent',parent),('candidate',candidate)]:
        result=load(root/'RESULT.json'); a=checked_inputs(root/'ADMISSION.json')
        require(result['admission']==bind(root/'ADMISSION.json') and
                result['status']=='PASS_NEMOTRON_WINDOWS_LIFECYCLE_SMOKE' and
                result['error'] is None and a['arm']==name, 'Incomplete or mismatched arm')
        require([p['phase'] for p in result['phases']]==['infer','reopen'], 'Missing lifecycle phase')
        require(result['owner']==a['owner'], 'Driver identity mismatch')
        owners += [a['owner'],{k:a['supervisor'][k] for k in ('pid','create_time')}]
        phases=[]
        for p in result['phases']:
            verify(p['result']);verify(p['lifetime'])
            r=load(p['result']['path']); life=load(p['lifetime']['path'])
            acceptance(r,life)
            semantics=load(root/p['phase']/'CAPTION_SEMANTICS.json')
            require(fingerprint(semantics['display'])==r['caption_fingerprint'], 'Display evidence changed')
            require(fingerprint([{k:row.get(k) for k in ('text','display_text','source_start_sec','source_end_sec')}
                    for row in semantics['stored']])==r['stored_caption_fingerprint'], 'Stored evidence changed')
            require(len(semantics['display'])==r['rendered_rows'] and
                    len(semantics['stored'])==r['stored_rows'], 'Semantic evidence counts differ')
            require(load(root/(p['phase']+'-OWNER.json'))['owner']==r['owner'], 'GUI owner mismatch')
            owners.append(r['owner'])
            phases.append(dict(phase=p['phase'],result=p['result'],lifetime=p['lifetime'],
                rendered_rows=r['rendered_rows'],stored_rows=r['stored_rows'],
                semantics=bind(root/p['phase']/'CAPTION_SEMANTICS.json')))
        infer=load(root/'infer/RESULT.json')
        bypass_acceptance(infer,name,arms[0]['infer'] if name=='candidate' else None)
        arms.append(dict(arm=name,admission=bind(root/'ADMISSION.json'),result=bind(root/'RESULT.json'),
            source_receipt=a['source_receipt'],source_files_verified=len(a['release_files']),
            assets_verified=len(a['assets']),application_cpus=a['application_cpus'],numerical_threads_per_model=a['numerical_threads_per_model'],phases=phases,infer=infer))
    pa=load(parent/'ADMISSION.json');ca=load(candidate/'ADMISSION.json')
    require(ca['reference_inputs'][0]==bind(parent/'RESULT.json') and
            ca['reference_inputs'][1]==bind(parent/'infer/RESULT.json'), 'Reference join mismatch')
    for key in ('audio','runtime_configs','assets','models','backend_key','mode','application_cpus','numerical_threads_per_model','accepted_source_receipt','parent_source_receipt'):
        require(pa[key]==ca[key], 'Paired input differs: '+key)
    require(all(exact_process(o) is None for o in owners), 'An exact admitted owner remains active')
    for arm in arms:
        r=arm.pop('infer')
        arm.update(model_cache=r['model_cache'],embedding_calls=r['telemetry']['n2_embedding_calls'],
            seen_slots=r['telemetry']['n2_seen_slots'],expected_samples=r['expected_samples'],
            asr_samples=r['asr_samples'],identity_samples=r['identity_samples'],speaker_lag_sec=r['speaker_lag_sec'],
            activity_frame_count=r['activity_frame_count'],activity_fingerprint=r['activity_fingerprint'],
            caption_fingerprint=r['caption_fingerprint'],stored_caption_fingerprint=r['stored_caption_fingerprint'],
            elapsed_wall_sec=r['telemetry']['elapsed_wall_sec'])
    candidate_result=load(candidate/'infer/RESULT.json')
    receipt=dict(status='PASS_D1_ANONYMOUS_WINDOWS_PAIRED_LIFECYCLE',utc=datetime.now(timezone.utc).isoformat(),
        arms=arms,private_admission=bind(candidate/'ADMISSION.json'),private_result=bind(candidate/'RESULT.json'),
        backend_id=candidate_result['backend_id'],exact_closed_owners=owners,
        candidate_encoder_loads=0,candidate_embedding_calls=0,paired_semantic_parity=True,
        scope='One saved O0 file, A2/D1 anonymous mode; thresholded activity and caption parity, not raw posterior or accuracy/latency qualification',
        microphone=False,playback=False,CM5_tested=False,N4_accepted=False,N5_complete=False,
        reviewer_code=[bind(__file__),bind(HERE/'README_D1_ANONYMOUS_REVIEW_V1.md'),bind(HERE/'d1_anonymous_lifecycle_v4.py')])
    freeze(output,receipt)
    print(dict(status=receipt['status'],output=str(output),arms=[{k:a[k] for k in
        ('arm','model_cache','embedding_calls','activity_frame_count','asr_samples','identity_samples','elapsed_wall_sec')} for a in arms]))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    review(args.parent,args.candidate,args.output)
