"""Sixteen sealed ASR/D1 anonymous replay checks. README_COMPONENT_D1_REPLAY.md."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''

from common import audio_only,bind,fingerprint,freeze,load,verify
from component_commands import asr_commands
from component_d1_replay import replay_d1_anonymous
from probe_component_s7 import read_events,save_private


def main(args):
    import psutil
    import soundfile as sf
    p=psutil.Process();p.cpu_affinity([14])
    if os.name=='nt':p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if args.output.exists():raise ValueError('Preserve existing probes; select a fresh output')
    for drive,floor in [('C:\\',50),('G:\\',75)]:
        if shutil.disk_usage(drive).free < floor*1024**3 + 256*1024**2:
            raise ValueError('Insufficient space for bounded probe under existing floors')
    ar,dr=load(args.asr_review),load(args.d1_review)
    if (ar['status']!='PASS_ASR_COMPONENT_SMOKE' or ar['component_cells']!=8
            or dr['status']!='PASS_D1_COMPONENT_SMOKE' or dr['component_cells']!=4):
        raise ValueError('Both complete smoke reviews required')
    for b in (ar['admission'],ar['final_result'],dr['admission'],dr['terminal']):verify(b)
    ac,dc=load(ar['admission']['path']),load(dr['admission']['path'])
    source_binding=ac['component_contract']['source_receipt']
    if dc['component_contract']['source_receipt']!=source_binding:
        raise ValueError('Different accepted application sources')
    verify(source_binding);source_receipt=load(source_binding['path']);source=Path(source_receipt['prototype'])
    for rel,b in source_receipt['files'].items():verify(dict(path=str((source/rel).resolve()),**b))
    sys.path[:0]=[str(source),str(source/'vendor')]
    import onnxruntime
    with patch.object(onnxruntime,'InferenceSession',side_effect=AssertionError('No models in D1 replay')):
        from app.pipeline import effective_profile
        args.output.mkdir(parents=True,exist_ok=False)
        summaries=[]
        try:
            for de in dr['rows']:
                verify(de['result']);d=load(de['result']['path']);job=audio_only(d['job'])
                if (d['status']!='COMPLETE' or d['encoder']!=de['encoder']
                        or d['admission_sha256']!=dr['admission']['sha256']):
                    raise ValueError('D1 result/admission/encoder mismatch')
                if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Source waveform changed')
                wave,rate=sf.read(job['audio_path'],dtype='float32')
                if rate!=16000 or wave.ndim!=1 or len(wave)!=job['frames']:raise ValueError('Source waveform shape changed')
                drows=read_events(d)
                for ae in ar['cells']:
                    verify(ae['result']);a=load(ae['result']['path'])
                    if a['job']['job_id']!=job['job_id']:continue
                    if (a['status']!='COMPLETE' or a['job']!=job or a['variant']!=ae['variant']
                            or a['admission_sha256']!=ar['admission']['sha256']):
                        raise ValueError('ASR/D1 paired source or admission mismatch')
                    profile=effective_profile('balanced','anonymous_conversation',job['tap'])
                    if d['profile_sha256']!=fingerprint(profile.to_dict()) or a['profile_sha256']!=d['profile_sha256']:
                        raise ValueError('Source component profile mismatch')
                    if sum(p.stat().st_size for p in args.output.iterdir() if p.is_file())+33*1024**2>256*1024**2:
                        raise ValueError('Private probe allocation exhausted')
                    arows=read_events(a);duration=len(wave)/16000
                    result=replay_d1_anonymous(asr_commands(arows,variant=ae['variant'],duration=duration),
                        drows,wave=wave,summary=d['summary'],namespace=d['namespace'],profile=profile,
                        session_id=job['job_id'],formatting=[r['payload'] for r in arows if r['event_type']=='component_final_punctuation'])
                    if result['presentation']['raw_observations']!=ae['scan']['raw_observations']:
                        raise ValueError('Raw ASR census changed')
                    if result['presentation']['formatting_revisions']!=ae['scan']['final_utterances']:
                        raise ValueError('Exact final formatting census changed')
                    artifact=save_private(args.output/(ae['variant']+'-'+de['encoder']+'-'+job['job_id']+'.json.gz'),result)
                    summaries.append(dict(variant=ae['variant'],encoder=de['encoder'],job_id=job['job_id'],
                        inputs=[ae['result'],de['result'],a['events'],d['events']],private_output=artifact,
                        commands=result['commands'],native_event_counts=result['native_event_counts'],
                        raw_observations=result['presentation']['raw_observations'],final_utterances=result['presentation']['final_utterances'],
                        rejected=result['presentation']['rejected'],worker_counts=result['worker_counts'],
                        d1_worker_alive=result['d1_worker_alive'],query_census=result['scan']))
            if len(summaries)!=16:raise ValueError('Expected all four ASRs, both encoders and both taps')
            receipt=dict(status='PASS_SIXTEEN_MODELED_D1_ANONYMOUS_DEVELOPMENT_REPLAYS',
                utc=datetime.now(timezone.utc).isoformat(),source_receipt=source_binding,
                review_inputs=[bind(args.asr_review),bind(args.d1_review)],
                code=[bind(Path(__file__).with_name(n)) for n in ('component_d1_replay.py','test_component_d1_replay.py',
                    'probe_component_d1.py','README_COMPONENT_D1_REPLAY.md','component_commands.py','component_s7_replay.py',
                    'component_presentation.py','probe_component_s7.py','review_d1_components.py')],
                cells=summaries,models_loaded=0,integrated_N4_cells=0,observed_Controller_parity=False,
                physical_widget_observed=False,live_latency_qualified=False,
                scope='Modeled anonymous application-method replay; real cooperative D1 lock, activity/window/name/span code. No named gallery, full Controller, GUI or hardware claim.')
            freeze(args.output/'RESULT.json',receipt)
            print(json.dumps(dict(status=receipt['status'],cells=len(summaries),receipt=bind(args.output/'RESULT.json')),indent=2))
        except BaseException as exc:
            freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc),completed=len(summaries)))
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('asr-review','d1-review','output'):parser.add_argument('--'+key,type=Path,required=True)
    main(parser.parse_args())
