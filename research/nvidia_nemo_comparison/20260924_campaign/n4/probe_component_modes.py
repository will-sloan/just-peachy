"""160 sealed-component naming-mode checks. See README_COMPONENT_MODES.md."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_key]='1'
os.environ['CUDA_VISIBLE_DEVICES']=''

from common import audio_only,bind,fingerprint,freeze,load,verify
from component_commands import asr_commands,d0_commands
from component_mode_replay import replay_d0_mode,replay_d1_mode
from mode_galleries import CONDITIONS,backend_contract
from probe_component_s7 import read_events,save_private


def main(args):
    import psutil
    import soundfile as sf
    process=psutil.Process();process.cpu_affinity([14])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if args.output.exists():raise ValueError('Preserve prior probes; select a fresh output')
    for drive,floor in [('C:\\',50),('G:\\',75)]:
        if shutil.disk_usage(drive).free<floor*1024**3+512*1024**2:
            raise ValueError('Insufficient space under campaign floors and 512-MiB probe reservation')
    ar,d0r,d1r,gr=map(load,(args.asr_review,args.d0_review,args.d1_review,args.gallery_review))
    if (ar['status']!='PASS_ASR_COMPONENT_SMOKE' or ar['component_cells']!=8
            or d0r['status']!='PASS_MATCHED_FULL_BANK_COMPONENTS_ONLY' or d0r['encoder_clip_cells']!=960
            or d1r['status']!='PASS_D1_COMPONENT_SMOKE' or d1r['component_cells']!=4
            or gr['status']!='PASS_FIXED_GALLERIES_AND_ACTUAL_MODE_BEGIN_METHODS_ONLY' or gr['checks_count']!=160):
        raise ValueError('All component and gallery reviews are required')
    for b in [ar['admission'],ar['final_result'],d1r['admission'],d1r['terminal'],gr['preparation'],*gr['code'],*d0r['inputs']]:verify(b)
    ac,dc=load(ar['admission']['path']),load(d1r['admission']['path'])
    d0ad=next(b for b in d0r['inputs'] if Path(b['path']).name=='ADMISSION.json')
    d0c=load(d0ad['path']);source_binding=ac['component_contract']['source_receipt']
    if dc['component_contract']['source_receipt']!=source_binding or d0c['source_receipt']!=source_binding or gr['source_receipt']!=source_binding:
        raise ValueError('Different accepted application sources')
    verify(source_binding);s=load(source_binding['path']);source=Path(s['prototype'])
    for rel,b in s['files'].items():verify(dict(path=str((source/rel).resolve()),**b))
    prepared=load(gr['preparation']['path']);verify(prepared['catalog']);catalog=load(prepared['catalog']['path'])
    for b in prepared['inputs']:verify(b)
    indexes={e:load(next(b['path'] for b in d0r['inputs'] if Path(b['path']).name=='RESULT_INDEX.json' and Path(b['path']).parent.name==e)) for e in ('E0','E1')}
    d1index={(r['encoder'],load(r['result']['path'])['job']['job_id']):r['result'] for r in d1r['rows']}
    sys.path[:0]=[str(source),str(source/'vendor')]
    import onnxruntime
    with patch.object(onnxruntime,'InferenceSession',side_effect=AssertionError('No neural model in mode probe')):
        from app.pipeline import effective_profile
        args.output.mkdir(parents=True,exist_ok=False);summaries=[];sealed={};waves={};written=0
        try:
            for ae in ar['cells']:
                verify(ae['result']);a=load(ae['result']['path']);job=audio_only(a['job']);jid=job['job_id'];duration=job['frames']/16000
                if a['status']!='COMPLETE' or a['variant']!=ae['variant'] or a['admission_sha256']!=ar['admission']['sha256']:
                    raise ValueError('ASR cell differs from review')
                if jid not in waves:
                    if bind(job['audio_path'])['sha256']!=job['audio_sha256']:raise ValueError('Original waveform changed')
                    wave,rate=sf.read(job['audio_path'],dtype='float32')
                    if rate!=16000 or wave.ndim!=1 or len(wave)!=job['frames']:raise ValueError('Waveform shape changed')
                    waves[jid]=wave
                arows=read_events(a);commands=asr_commands(arows,variant=ae['variant'],duration=duration)
                formatting=[r['payload'] for r in arows if r['event_type']=='component_final_punctuation']
                profile_hash=fingerprint(effective_profile('balanced','anonymous_conversation',job['tap']).to_dict())
                if a['profile_sha256']!=profile_hash:raise ValueError('ASR component profile changed')
                for backend in catalog['backends']:
                    if not backend['implemented']:continue
                    base=backend_contract(catalog,backend['key'],'anonymous_conversation')
                    if base['variant']!=ae['variant']:continue
                    d,e=base['diarization'],base['encoder'];cache=(d,e,jid)
                    if cache not in sealed:
                        b=indexes[e]['cells'][jid] if d=='D0' else d1index[e,jid]
                        verify(b);cell=load(b['path'])
                        admission=d0ad if d=='D0' else d1r['admission']
                        if (cell['status']!='COMPLETE' or cell.get('error') is not None or cell['job']!=job
                                or cell['encoder']!=e or cell['admission_sha256']!=admission['sha256']
                                or cell['profile_sha256']!=profile_hash):raise ValueError('Paired speaker component differs')
                        sealed[cache]=(b,cell,read_events(cell))
                    b,cell,rows=sealed[cache]
                    for mode in CONDITIONS:
                        if written+33*1024**2>512*1024**2:raise ValueError('Mode probe allocation exhausted')
                        kwargs=dict(preparation=gr['preparation'],backend=backend['key'],mode=mode,tap=job['tap'],
                            namespace=cell['namespace'],session_id=jid,formatting=formatting)
                        result=(replay_d0_mode(commands,d0_commands(rows,duration=duration),duration=duration,**kwargs) if d=='D0'
                            else replay_d1_mode(commands,rows,wave=waves[jid],summary=cell['summary'],**kwargs))
                        if (result['presentation']['raw_observations']!=ae['scan']['raw_observations'] or
                                result['presentation']['formatting_revisions']!=ae['scan']['final_utterances']):
                            raise ValueError('Raw/final text census changed')
                        decisions=([r['decision'] for r in result['policy_events'] if r['event_type']=='speaker_decision'] if d=='D0'
                            else [r['payload'] for r in result['native_events'] if r['event_type']=='speaker_decision'])
                        if base['uses_n2'] and mode!='selected_closed' and any(p.get('known_profile_id') is not None for p in decisions):
                            raise ValueError('Uncalibrated N2 open or absent gallery published a known name')
                        artifact=save_private(args.output/(backend['key']+'-'+mode+'-'+jid+'.json.gz'),result)
                        written+=artifact['compressed']['bytes']
                        summaries.append(dict(backend=backend['key'],mode=mode,job_id=jid,inputs=[ae['result'],b],
                            output=artifact,commands=result['commands'],raw_observations=result['presentation']['raw_observations'],
                            final_utterances=result['presentation']['final_utterances'],display_events=len(result['display_events']),
                            diagnostic_decision_states=dict(Counter(p.get('naming_state','missing') for p in decisions)),
                            diagnostic_known_decisions=sum(p.get('known_profile_id') is not None for p in decisions),
                            worker_counts=result['worker_counts'],d1_worker_alive=result.get('d1_worker_alive'),
                            integrated_N4_cells=0,modeled_not_visible_name_metrics=True))
                print(json.dumps(dict(completed=len(summaries),total=160,variant=ae['variant'])),flush=True)
            if len(summaries)!=160:raise ValueError('Expected 16 tuples x 5 modes x 2 taps')
            receipt=dict(status='PASS_160_MODELED_CATALOG_MODE_DEVELOPMENT_REPLAYS',utc=datetime.now(timezone.utc).isoformat(),
                source_receipt=source_binding,gallery_preparation=gr['preparation'],review_inputs=[bind(p) for p in (
                    args.asr_review,args.d0_review,args.d1_review,args.gallery_review)],
                code=[bind(Path(__file__).with_name(n)) for n in ('component_mode_replay.py','probe_component_modes.py',
                    'test_component_modes.py','README_COMPONENT_MODES.md','mode_galleries.py','component_d1_replay.py',
                    'component_s7_replay.py','component_presentation.py','component_commands.py','probe_component_s7.py','common.py')],
                checks=summaries,checks_count=len(summaries),private_compressed_bytes=written,models_loaded=0,integrated_N4_cells=0,
                observed_Controller_parity=False,physical_widget_observed=False,
                scope='Modeled actual resolver/activity/span/display-annotation methods; missing-voice baseline/N2 behavior preserved; no Controller projection, GUI, first-visible timing or accuracy acceptance')
            freeze(args.output/'RESULT.json',receipt)
            print(json.dumps(dict(status=receipt['status'],receipt=bind(args.output/'RESULT.json')),indent=2))
        except BaseException as exc:
            freeze(args.output/'FAILED.json',dict(status='FAILED_PRESERVED',error=repr(exc),completed=len(summaries)))
            raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('asr-review','d0-review','d1-review','gallery-review','output'):p.add_argument('--'+key,required=True,type=Path)
    main(p.parse_args())
