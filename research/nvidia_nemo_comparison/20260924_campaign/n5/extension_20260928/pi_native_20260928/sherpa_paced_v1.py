"""Original-pacing saved-file ASR passage on CM5; no accuracy scoring. README_SHERPA.md."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import time
from datetime import datetime, timezone

for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['MALLOC_ARENA_MAX']='2'

MODELS={
    'encoder':('32c98281c7bd8b63e3e142d007251b37f120572e8fdea9a4f5a79ce22b10ec4f','encoder-epoch-99-avg-1.int8.onnx'),
    'decoder':('9da02b77cb08826756ec6a88635f35a40374e4164e7c6359121a9145958a6ceb','decoder-epoch-99-avg-1.onnx'),
    'joiner':('831477d390e59a61f1b6a6f763b9903e6c6366ff6034f1ddba613be82637122f','joiner-epoch-99-avg-1.int8.onnx'),
    'tokens':('49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb','tokens.txt'),
}


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    root=Path(__file__).resolve().parent
    a=json.loads((root/'ADMISSION.json').read_text())
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot!=a['boot_id'] or sorted(os.sched_getaffinity(0))!=[2,3] or os.getuid()==0:
        raise RuntimeError('Wrong target/user/CPU identity')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(a['expires_utc']):raise RuntimeError('Expired admission')
    for n,h in a['files'].items():
        if sha(root/n)!=h:raise RuntimeError('Changed bound input')
    if shutil.disk_usage(root).free<5*1024**3:raise RuntimeError('Storage floor')
    available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
    if available<850*1024**2:raise RuntimeError('RAM floor')
    resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=boot,admission_sha256=sha(root/'ADMISSION.json'))
    with (root/'OWNER.json').open('x') as f:json.dump(owner,f)
    result=dict(status='FAILED_PRESERVED',owner=owner,saved_audio_accuracy_scored=False,scope='ASR component functional original-1x-pacing only; existing app remains active',integrated_mode_qualified=False,events=[])
    try:
        import numpy as np
        import soundfile as sf
        import sherpa_onnx
        base=Path('/home/peachyprototype/JustPeachy/install/models')
        paths={}
        for k,(digest,name) in MODELS.items():
            path=base/digest/name
            if sha(path)!=digest:raise RuntimeError('Installed model hash differs')
            paths[k]=str(path)
        source=root.parent/'d1-generic-v1/source.wav'
        if sha(source)!='0ee26e8aa6f815d8b202419aafb71ff5bc25093d193e95e972036f488c5040b8':raise RuntimeError('Saved source hash differs')
        audio,sr=sf.read(source,dtype='float32')
        if sr!=16000 or audio.ndim!=1 or len(audio)!=715127:raise RuntimeError('Saved source shape')
        t=time.perf_counter()
        recognizer=sherpa_onnx.OnlineRecognizer.from_transducer(**paths,num_threads=1,provider='cpu',sample_rate=sr,feature_dim=80,decoding_method='greedy_search',max_active_paths=4,blank_penalty=0,enable_endpoint_detection=True,rule1_min_trailing_silence=2.4,rule2_min_trailing_silence=1.2,rule3_min_utterance_length=20)
        result['load_seconds']=time.perf_counter()-t
        stream=recognizer.create_stream();accepted=0;calls=0;decode=0;lag=0;utterance=0;last=''
        start=time.perf_counter();cpu=time.process_time()
        for offset in range(0,len(audio),1600):
            chunk=audio[offset:offset+1600];source_end=(offset+len(chunk))/sr
            wait=start+source_end-time.perf_counter()
            if wait>0:time.sleep(wait)
            t=time.perf_counter();stream.accept_waveform(sr,chunk)
            while recognizer.is_ready(stream):recognizer.decode_stream(stream);calls+=1
            text=recognizer.get_result(stream)
            endpoint=recognizer.is_endpoint(stream)
            decode+=time.perf_counter()-t
            available=time.perf_counter()-start;lag=max(lag,available-source_end);accepted+=len(chunk)
            if text!=last or endpoint:
                result['events'].append(dict(source_end_seconds=source_end,available_seconds=available,text=text,endpoint=endpoint,utterance=utterance));last=text
            if endpoint:recognizer.reset(stream);utterance+=1;last=''
        input_done=time.perf_counter();t=input_done
        stream.accept_waveform(sr,np.zeros(round(.66*sr),np.float32));stream.input_finished()
        while recognizer.is_ready(stream):
            recognizer.decode_stream(stream);calls+=1
            if calls>100000:raise RuntimeError('Unbounded drain')
        result['final_text']=recognizer.get_result(stream);decode+=time.perf_counter()-t
        if accepted!=len(audio) or not any(e['text'].strip() for e in result['events']) and not result['final_text'].strip():raise RuntimeError('No complete audio/text passage')
        result.update(status='NATIVE_SHERPA_PACED_COLLECTED_REQUIRES_REVIEW',source_samples=accepted,source_seconds=len(audio)/sr,decode_calls=calls,decode_seconds=decode,decode_rtf=decode/(len(audio)/sr),paced_elapsed_seconds=time.perf_counter()-start,drain_seconds=time.perf_counter()-input_done,maximum_processing_lag_seconds=lag,cpu_seconds=time.process_time()-cpu,endpoint_count=utterance)
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
    result['peak_process_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    result['ended_utc']=datetime.now(timezone.utc).isoformat()
    with (root/'RESULT.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('events','final_text')}),flush=True)
    return int(result['status']=='FAILED_PRESERVED')


if __name__=='__main__':raise SystemExit(main())
