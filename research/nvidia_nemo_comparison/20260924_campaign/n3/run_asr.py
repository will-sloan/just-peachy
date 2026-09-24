"""Actual saved-audio streaming ASR with immutable per-cell receipts."""
from __future__ import annotations
import argparse
from dataclasses import asdict, replace
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import string
import threading
import time

os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=str,allow_nan=False).encode()).hexdigest()


def atomic(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')
    for attempt in range(20):
        try:temporary.replace(path);return
        except PermissionError:
            if attempt==19:raise
            time.sleep(.1)


class SherpaOwner:
    def __init__(self,config):
        from edge_speech_pipeline.models import SherpaStream
        self.config=config
        self.model=SherpaStream(config)
    def stream(self):
        from edge_speech_pipeline.models import SherpaStream
        return SherpaEvents(SherpaStream(self.config,resident=self.model))
    def close(self):pass


class SherpaEvents:
    padding_seconds=.66
    def __init__(self,stream):
        self.stream=stream;self.input_samples=0;self.finished=False;self.decode_ms=0.
    def event(self,text,final,utterance):
        return dict(raw_text=text,final=final,utterance=utterance,input_samples=self.input_samples,
            input_end_sec=self.input_samples/16000,available_at_monotonic=time.perf_counter(),
            words=[],word_time_kind='UNAVAILABLE_IN_RETAINED_BASELINE_ADAPTER')
    def feed(self,samples):
        if self.finished:raise RuntimeError('Stream finished')
        self.input_samples+=len(samples)
        text,endpoint=self.stream.accept(samples);self.decode_ms=self.stream.decode_ms
        index=self.stream.utterance_index
        if endpoint:return [self.event(self.stream.reset_endpoint(),True,index)]
        return [self.event(text,False,index)] if text else []
    def finish_events(self):
        if self.finished:return []
        began=time.perf_counter();text=self.stream.finish();self.finished=True
        self.decode_ms=(time.perf_counter()-began)*1000
        return [self.event(text,True,self.stream.utterance_index)]
    def close(self):pass


def source_binding(root):
    # Bind all prototype Python/config source, not an editable branch name.
    files={}
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix in ('.py','.json') and '__pycache__' not in path.parts:
            files[path.relative_to(root).as_posix()]=sha(path)
    for path in (Path(__file__),Path(__file__).with_name('reference_asr.py'),
                 Path(__file__).with_name('a1_service.py'),Path(__file__).with_name('a1_features.py')):
        files['n3/'+path.name]=sha(path)
    return files


def reference_binding(root):
    if root is None:return None
    return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
        if p.is_file() and p.suffix in ('.py','.yaml','.yml') and '__pycache__' not in p.parts}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prototype',type=Path,required=True)
    p.add_argument('--audio-manifest',type=Path,required=True)
    p.add_argument('--models-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--variant',choices=['A0','A1','A2','A3'],required=True)
    p.add_argument('--runtime',choices=['sherpa','native','reference'],required=True)
    p.add_argument('--binding',type=Path)
    p.add_argument('--reference-model',type=Path)
    p.add_argument('--reference-source',type=Path)
    p.add_argument('--right-context',type=int,default=1)
    p.add_argument('--cpu',type=int,choices=[4,14],default=4)
    p.add_argument('--paced',action='store_true')
    p.add_argument('--job-id',action='append')
    p.add_argument('--limit',type=int)
    args=p.parse_args()
    import psutil
    process=psutil.Process();process.cpu_affinity([args.cpu])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    import numpy as np
    import soundfile as sf
    sys.path[:0]=[str(args.prototype),str(args.prototype/'vendor')]
    from app.paths import pipeline_config
    from app.buffers import MemoryJournal
    args.output.mkdir(parents=True,exist_ok=True)
    document=json.loads(args.audio_manifest.read_text(encoding='utf-8'))
    allowed={'job_id','audio_path','audio_sha256','frames','sample_rate_hz','gain','reset_between_scenes','tap'}
    jobs=document['jobs']
    if any(set(row)!=allowed for row in jobs):raise ValueError('Inference accepts strict audio-only fields')
    if len({row['job_id'] for row in jobs})!=len(jobs):raise ValueError('Duplicate audio job')
    if args.job_id:
        if not set(args.job_id)<={row['job_id'] for row in jobs}:raise ValueError('Requested job absent')
        jobs=[row for row in jobs if row['job_id'] in args.job_id]
    if args.limit is not None:jobs=jobs[:args.limit]
    if not jobs:raise ValueError('Empty job selection')
    source=source_binding(args.prototype)
    reference_source=reference_binding(args.reference_source)
    config=replace(pipeline_config(args.output,args.models_root),asr_threads=1,speaker_threads=1,punctuation_threads=1)
    binding=json.loads(args.binding.read_text(encoding='utf-8')) if args.binding else None
    lock=dict(schema='just-peachy.n3.asr-run.v1',variant=args.variant,runtime=args.runtime,
        model_binding=binding,reference_model_sha256=sha(args.reference_model) if args.reference_model else None,
        reference_source=str(args.reference_source),reference_source_files=reference_source,right_context=args.right_context,
        source_sha256=fingerprint(source),audio_manifest_sha256=sha(args.audio_manifest),
        source_files=source,baseline_config=asdict(config) if args.variant=='A0' else None,
        delivery='source_paced_independent_producer' if args.paced else 'accelerated_causal_not_live_latency',
        numerical_threads=1,cpu_affinity=[args.cpu],interpreter=str(Path(sys.executable)),
        interpreter_sha256=sha(sys.executable),chunk_samples=1600 if args.variant=='A0' else 1280,
        reset_policy='between_independent_scenes_no_truth_boundaries',gain_policy='manifest_gain_once')
    contract=fingerprint(lock)
    lock_path=args.output/'RUN_LOCK.json'
    if lock_path.exists() and fingerprint(json.loads(lock_path.read_text()))!=contract:
        raise ValueError('Existing run was made with different state/model/source; choose a fresh directory')
    if not lock_path.exists():atomic(lock_path,lock)
    result=dict(schema='just-peachy.n3.asr-result.v1',status='RUNNING',contract_sha256=contract,
        variant=args.variant,runtime=args.runtime,total=len(jobs),completed=0,cells=[],errors=[],
        started_utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),create_time=process.create_time())
    atomic(args.output/'RESULT.json',result)
    owner=None
    try:
        load_started=time.perf_counter()
        if args.runtime=='sherpa':
            if args.variant!='A0':raise ValueError('Only A0 uses Sherpa')
            owner=SherpaOwner(config)
        elif args.runtime=='native':
            if not binding or binding['variant']!=args.variant:raise ValueError('Explicit matching native binding required')
            from edge_speech_pipeline.n3_asr_native import NativeRecognizer
            owner=NativeRecognizer(binding)
        else:
            from reference_asr import ReferenceRecognizer
            owner=ReferenceRecognizer(args.variant,args.reference_model,args.reference_source,right_context=args.right_context)
            atomic(args.output/'REFERENCE_CONFIG.json',getattr(owner,'config',dict(
                variant='A1',device='cpu',precision='float32',context=[70,1],chunk_seconds=.08,
                state='official NemoStreamingASRService recurrent caches and hypotheses',
                endpoint='predicted EOU/EOB with official cache reset',flush='partial chunk padding plus 16 zero steps')))
        result.update(model_load_seconds=time.perf_counter()-load_started,
            rss_after_model_load_bytes=process.memory_info().rss,model_load_peak_rss='NOT_SAMPLED')
        atomic(args.output/'RESULT.json',result)
        for job in jobs:
            if shutil.disk_usage(args.output).free<75*2**30:raise RuntimeError('Work disk reserve reached')
            cell_id=job['job_id'].replace('N2_','N3_',1)
            cell_dir=args.output/'cells'/cell_id
            cell_dir.mkdir(parents=True,exist_ok=True)
            cell_path=cell_dir/'RESULT.json'
            cache=fingerprint(dict(run=contract,job=job))
            if cell_path.exists():
                cached=json.loads(cell_path.read_text())
                if cached.get('cache_key')!=cache or cached.get('status')!='COMPLETE':
                    raise ValueError('Preserve failed/different cell; use fresh output directory')
                if sha(cell_dir/'events.jsonl')!=cached['events_sha256']:raise ValueError('Cached events changed')
                result['cells'].append(dict(id=cell_id,path=str(cell_path),sha256=sha(cell_path),cached=True))
                result['completed']+=1;atomic(args.output/'RESULT.json',result);continue
            if sha(job['audio_path'])!=job['audio_sha256']:raise ValueError('Audio hash changed')
            audio,rate=sf.read(job['audio_path'],dtype='float32',always_2d=False)
            if rate!=16000 or audio.ndim!=1 or len(audio)!=job['frames'] or job['reset_between_scenes'] is not True:
                raise ValueError('Audio shape/rate/reset admission failed')
            if job['gain']!=1.:raise ValueError('Prepared paired bank must already contain admitted gain')
            stream=owner.stream()
            started=time.perf_counter();cpu_start=process.cpu_times();peak=process.memory_info().rss
            producer=None;producer_error=[];journal=None;stop=threading.Event()
            if args.paced:
                journal=MemoryJournal(sample_rate=16000,reserve_sec=120)
                def deliver():
                    try:
                        for at in range(0,len(audio),320):
                            end=min(at+320,len(audio))
                            if stop.wait(max(0.,started+end/16000-time.perf_counter())):return
                            journal.append(audio[at:end])
                    except Exception as exc:producer_error.append(str(exc))
                    finally:journal.finish(producer_error[0] if producer_error else None)
                producer=threading.Thread(target=deliver,name='n3-saved-source',daemon=True);producer.start()
            samples=0;events=0;finals=[];previous={};churn=0;first_text=None;last_final=None;compute=0.
            path=cell_dir/'events.jsonl'
            if path.exists():raise ValueError('Preserve partial cell event evidence')
            def record(rows,output):
                nonlocal events,churn,first_text,last_final
                for row in rows:
                    row['normalized_lexical_score_text']=' '.join(row['raw_text'].lower().translate(str.maketrans('','',string.punctuation)).split())
                    row['formatted_text']=row['raw_text'] if args.variant in ('A2','A3') else None
                    row['manual_corrections']=[]
                    row['available_elapsed_sec']=row['available_at_monotonic']-started
                    if args.paced and row['available_elapsed_sec']+1e-6<row['input_end_sec']:
                        raise RuntimeError('Text available before actual source support')
                    output.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');events+=1
                    text=row['raw_text']
                    if text and first_text is None:first_text=row['available_elapsed_sec']
                    old=previous.get(row['utterance'],'');prefix=0
                    for left,right in zip(old.split(),text.split()):
                        if left!=right:break
                        prefix+=1
                    churn+=max(0,len(old.split())-prefix)
                    if row['final']:
                        finals.append(text);last_final=row['available_elapsed_sec'];previous.pop(row['utterance'],None)
                    else:previous[row['utterance']]=text
            try:
                with path.open('x',encoding='utf-8',newline='\n') as output:
                    while samples<len(audio):
                        count=lock['chunk_samples']
                        if journal is None:
                            block=audio[samples:samples+count]
                        else:
                            block=np.empty(0,np.float32)
                            while len(block)<count and samples+len(block)<len(audio):
                                part=journal.read(samples+len(block),count-len(block))
                                if not len(part) and journal.finished:
                                    raise RuntimeError('Source ended before complete audio')
                                block=np.concatenate((block,part))
                        if not len(block):
                            if journal is not None and journal.finished:raise RuntimeError('Source ended before complete audio')
                            continue
                        samples+=len(block);record(stream.feed(block),output);compute+=stream.decode_ms
                        peak=max(peak,process.memory_info().rss)
                    record(stream.finish_events(),output);compute+=stream.decode_ms
                    if stream.input_samples!=len(audio):raise RuntimeError('Incomplete input accounting')
                    if stream.finish_events():raise RuntimeError('Flush replay produced duplicate output')
                if producer is not None:
                    producer.join(5)
                    if producer.is_alive() or producer_error:raise RuntimeError('Source closure failed')
                elapsed=time.perf_counter()-started;cpu_end=process.cpu_times()
                cell=dict(status='COMPLETE',cache_key=cache,job_id=cell_id,audio_sha256=job['audio_sha256'],
                    input_samples=samples,source_seconds=len(audio)/16000,delivery=lock['delivery'],
                    elapsed_seconds=elapsed,compute_ms=compute,cpu_seconds=cpu_end.user+cpu_end.system-cpu_start.user-cpu_start.system,
                    peak_process_rss_bytes=peak,resource_scope='this process sampled RSS; includes resident model; no total-system/Pi claim',
                    first_text_elapsed_sec=first_text,last_final_elapsed_sec=last_final,word_revision_removals=churn,
                    finalization_after_source_sec=(last_final-len(audio)/16000 if last_final is not None and args.paced else None),
                    event_count=events,raw_final_text=' '.join(text.strip() for text in finals if text.strip()),
                    final_utterances=finals,events_sha256=sha(path),flush_padding_seconds=stream.padding_seconds,
                    flush_padding_scope='adapter_added_only; native_internal_flush_not_exposed' if args.runtime=='native' else 'explicit_adapter_padding')
                atomic(cell_path,cell)
            except Exception as exc:
                atomic(cell_path,dict(status='FAILED',cache_key=cache,error=f'{type(exc).__name__}: {exc}',input_samples=samples))
                raise
            finally:
                stop.set()
                if producer is not None:producer.join(5)
                stream.close()
            result['cells'].append(dict(id=cell_id,path=str(cell_path),sha256=sha(cell_path),cached=False))
            result['completed']+=1
            atomic(args.output/'RESULT.json',result)
            print(f'{args.variant}/{args.runtime}: {result["completed"]}/{len(jobs)}',flush=True)
        if source_binding(args.prototype)!=source:raise RuntimeError('Source changed during run')
        if reference_binding(args.reference_source)!=reference_source:raise RuntimeError('NeMo reference source changed during run')
        result['status']='COMPLETE'
    except Exception as exc:
        result['status']='FAILED';result['errors'].append(f'{type(exc).__name__}: {exc}')
        raise
    finally:
        try:
            if owner is not None:owner.close()
        except Exception as exc:
            result['status']='FAILED';result['errors'].append('Owner close: '+repr(exc))
            raise
        finally:
            result['updated_utc']=datetime.now(timezone.utc).isoformat()
            atomic(args.output/'RESULT.json',result)


if __name__=='__main__':main()
