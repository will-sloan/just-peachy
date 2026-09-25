"""Closed-cell native policy/activity development probe. README_D0_ACTIVITY.md."""
import argparse
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''

from common import bind, fingerprint, freeze, load, verify
from d0_bank_components import verify_contract
from review_d0_bank import check_cell, scan_events, exact_path
from d0_activity_evidence import D0ActivityEvidence


def replay(cell, profile, build_policy, *, incremental):
    """Same genuine native tracker, with two schedules and no ASR/gallery.

    The incremental path releases only strictly earlier availability groups.
    The batched control closes the same causal scheduler after all inputs arrive.
    Equality establishes anonymous policy ordering only, not Controller parity.
    """
    observer=D0ActivityEvidence(cell['job']['frames'],clock_kind='modeled_component_availability') if incremental else None
    observations={};decisions=[];seg_serial=0
    def emitted(row):
        if row['event_type'] != 'speaker_decision':
            return
        event=observations[row['input_event_id']];decision=row['decision']
        # Naming's measured compute is not an anonymous tracking outcome.
        anonymous={k:v for k,v in decision.items() if k not in ('identity','identity_compute_sec')}
        decisions.append(dict(input_event_id=row['input_event_id'],decision=deepcopy(anonymous)))
        if observer is not None:
            observer.track(row['event_id'],source_start_sec=event['source_start_sec'],
                source_end_sec=event['source_end_sec'],available_at_sec=row['available_at_sec'],
                track_id=decision['tracker_id'],clean_intervals=event['clean_intervals'],
                observation_id=event['event_id'],committed=decision['committed'])
    scheduler=build_policy(profile,gallery=None,spatial_provider=None,emit=emitted)
    scheduler.advance({'asr':float('inf')})
    with gzip.open(cell['events']['path'],'rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);kind=row['event_type'];p=row['payload']
            if kind not in ('research_segmentation','research_embedding'):
                continue
            if incremental:
                scheduler.advance({'speaker':p['modeled_available_at_sec']})
            if kind=='research_segmentation':
                seg_serial+=1;eid=f'seg:{seg_serial:08d}'
                if observer is not None:
                    observer.segmentation(eid,p)
                event=dict(kind='segmentation',event_id=eid,source_start_sec=p['source_start_sec'],
                    source_end_sec=p['source_end_sec'],available_at_sec=p['modeled_available_at_sec'],
                    speech=p['speech'],overlap=p['overlap'])
            else:
                event={k:p[k] for k in ('kind','event_id','observation_id','source_start_sec','source_end_sec',
                    'receptive_start_sec','receptive_end_sec','available_at_sec','speech','overlap',
                    'evidence_kind','clean_intervals','rms','clipping_fraction','clean_fraction')}
                event['vector']=p['normalized_embedding']
                observations[event['event_id']]=event
            scheduler.push(event,'speaker')
    scheduler.finish()
    if len(decisions)!=len(cell['vectors']) or scheduler.snapshot()['pending_events']:
        raise ValueError('Native policy replay did not consume every actual observation')
    return dict(decisions=decisions,anonymous_decisions_sha256=fingerprint(decisions),
        snapshot=scheduler.snapshot(),activity=None if observer is None else observer.snapshot())


def main(args):
    import psutil
    process=psutil.Process();process.cpu_affinity([14])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    import numpy as np
    import soundfile as sf
    if args.output.exists():raise ValueError('Preserve probe evidence; select a fresh output')
    contract=verify_contract(args.run/'ADMISSION.json');admission=bind(args.run/'ADMISSION.json')
    if contract['schema']!='n4-d0-bank-components-v1' or Path(contract['output']).resolve()!=args.run.resolve():
        raise ValueError('Different full-bank collection contract')
    jobs={row['job_id']:row for row in load(contract['manifest']['path'])['jobs']}
    if len(args.job)!=len(set(args.job)) or not 1 <= len(args.job) <= 4:
        raise ValueError('One to four unique closed jobs required for development probe')
    source=Path(contract['source']);sys.path[:0]=[str(source),str(source/'vendor')]
    import onnxruntime
    with patch.object(onnxruntime,'InferenceSession',side_effect=AssertionError('Probe may not load a model')):
        from app.pipeline import effective_profile
        from edge_speech_pipeline.research_scheduler_v3 import build_s6c_policy
        index=load(args.run/args.encoder/'RESULT_INDEX.json');outputs=[]
        args.output.mkdir(parents=True,exist_ok=False)
        try:
            for jid in args.job:
                binding=index['cells'][jid];exact_path(binding,args.run/args.encoder/jid/'RESULT.json')
                cell=load(binding['path']);job=jobs[jid]
                if cell['status']!='COMPLETE' or cell['error'] is not None:
                    raise ValueError('Only complete closed cells may be probed')
                profile=effective_profile('balanced','anonymous_conversation',job['tap'])
                check_cell(cell,job,args.encoder,dict(profiles={job['tap']:profile.to_dict()},namespace=cell['namespace']),admission['sha256'])
                if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Audio changed')
                wave,rate=sf.read(job['audio_path'],dtype='float32')
                if rate!=16000 or wave.ndim!=1 or len(wave)!=job['frames']:raise ValueError('Audio shape changed')
                for row in cell['vectors']:
                    v=np.asarray(row['normalized_embedding'])
                    if v.shape!=(192,) or not np.isfinite(v).all() or abs(np.linalg.norm(v)-1)>1e-4:
                        raise ValueError('Invalid actual model vector')
                scan=scan_events(cell,wave)
                streamed=replay(cell,profile,build_s6c_policy,incremental=True)
                control=replay(cell,profile,build_s6c_policy,incremental=False)
                if streamed['decisions']!=control['decisions']:
                    raise ValueError('Native anonymous policy streaming/batched parity failed')
                verify(binding);verify(cell['events'])
                path=args.output/(jid+'.json')
                freeze(path,dict(source_result=binding,event_scan=scan,incremental=streamed,
                    batched_anonymous_decisions_sha256=control['anonymous_decisions_sha256'],status='PASS_POLICY_ORDERING_ONLY'))
                activity=streamed['activity']
                outputs.append(dict(source_result=binding,private_output=bind(path),
                    actual_embedding_decisions=len(streamed['decisions']),
                    anonymous_decisions_sha256=streamed['anonymous_decisions_sha256'],
                    activity_coverage={k:activity[k] for k in ('duration_sec','mask_seconds','supported_single_speech_sec',
                        'unassigned_single_speech_sec','conflicting_single_speech_sec','overlap_without_global_source_assignment_sec')}))
            receipt=dict(status='PASS_CLOSED_CELL_DEVELOPMENT_PROBE',scope='No ASR, no gallery, modeled component clocks; no Controller parity',
                encoder=args.encoder,cells=outputs,admission=admission,code=[bind(Path(__file__).with_name(n)) for n in
                    ('probe_d0_activity.py','d0_activity_evidence.py','review_d0_bank.py','test_d0_activity.py','README_D0_ACTIVITY.md')],
                models_loaded=0,integrated_N4_cells=0,full_bank_review_complete=False,global_D0_DER_qualified=False)
            freeze(args.output/'RESULT.json',receipt);print(json.dumps(receipt,indent=2))
        except BaseException as exc:
            freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc),admission=admission))
            raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('run','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--encoder',choices=['E0','E1'],required=True)
    p.add_argument('--job',action='append',required=True)
    main(p.parse_args())
