"""Isolated Sherpa then A2 phases; README_SEQUENTIAL_ASR_V1.md."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import wave


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main(phase):
    root=Path(__file__).resolve().parent;d=root/phase;a=json.loads((root/'ADMISSION.json').read_text());mib=1024**2
    resource.setrlimit(resource.RLIMIT_AS,((768 if phase=='sherpa' else 1536)*mib,)*2);signal.alarm(175)
    assert resource.getrlimit(resource.RLIMIT_STACK)==(mib,mib) and sorted(os.sched_getaffinity(0))==[2,3]
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();assert boot==a['boot_id']
    owner=dict(pid=os.getpid(),boot_id=boot,start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))
    with (d/'CHILD_OWNER.json').open('x') as f:json.dump(owner,f)
    for row in a['files']:assert sha(row['path'])==row['sha256']
    import numpy as np
    with wave.open(a['source_wav'],'rb') as w:
        assert (w.getframerate(),w.getnchannels(),w.getsampwidth(),w.getnframes())==(16000,1,2,715127)
        samples=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(np.float32)/32768
    result=dict(status='FAILED_PRESERVED',phase=phase,owner=owner,source_sha256=sha(a['source_wav']),source_samples=len(samples),model_closed=False)
    events=[];model=None;stream=None;began=time.monotonic();cpu=time.process_time()
    def publish(event):
        events.append(event)
        data=(json.dumps(dict(event=event,available_monotonic_ns=time.monotonic_ns()),separators=(',',':'))+'\n').encode()
        p=d/'EVENTS.jsonl';assert (p.stat().st_size if p.exists() else 0)+len(data)<2*mib
        with p.open('ab') as f:f.write(data)
    try:
        if phase=='sherpa':
            import sherpa_onnx
            model=sherpa_onnx.OnlineRecognizer.from_transducer(**a['sherpa_models'],num_threads=1,provider='cpu',sample_rate=16000,feature_dim=80,decoding_method='greedy_search',max_active_paths=4,blank_penalty=0,enable_endpoint_detection=True,rule1_min_trailing_silence=2.4,rule2_min_trailing_silence=1.2,rule3_min_utterance_length=20)
            result['load_seconds']=time.monotonic()-began;stream=model.create_stream();start=time.monotonic();last='';utterance=0;accepted=0
            for offset in range(0,len(samples),1600):
                chunk=samples[offset:offset+1600];end=(offset+len(chunk))/16000;wait=start+end-time.monotonic()
                if wait>0:time.sleep(wait)
                stream.accept_waveform(16000,chunk)
                while model.is_ready(stream):model.decode_stream(stream)
                text=model.get_result(stream);endpoint=model.is_endpoint(stream);accepted+=len(chunk)
                if text!=last or endpoint:publish(dict(source_end_seconds=end,text=text,endpoint=endpoint,utterance=utterance));last=text
                if endpoint:model.reset(stream);utterance+=1;last=''
            eof=time.monotonic();stream.accept_waveform(16000,np.zeros(10560,np.float32));stream.input_finished()
            while model.is_ready(stream):model.decode_stream(stream)
            result.update(final_text=model.get_result(stream),endpoint_count=utterance,accepted_samples=accepted,drain_seconds=time.monotonic()-eof,source_elapsed_seconds=time.monotonic()-start)
            reference=json.loads(Path(a['sherpa_reference']).read_text())
            assert events==[{k:v for k,v in e.items() if k!='available_seconds'} for e in reference['events']] and result['final_text']==reference['final_text']
        else:
            sys.path.insert(0,a['a2_parent']);import n3_asr_native
            binding=json.loads((Path(a['a2_parent'])/'BINDING.json').read_text());model=n3_asr_native.NativeRecognizer(binding)
            result['load_seconds']=time.monotonic()-began;stream=model.stream();start=time.monotonic()
            for offset in range(0,len(samples),1280):
                for event in stream.feed(samples[offset:offset+1280]):publish({k:v for k,v in event.items() if k!='available_at_monotonic'})
            eof=time.monotonic()
            for event in stream.finish_events():publish({k:v for k,v in event.items() if k!='available_at_monotonic'})
            assert stream.finish_events()==[] and stream.input_samples==len(samples)
            result.update(accepted_samples=stream.input_samples,drain_seconds=time.monotonic()-eof,source_elapsed_seconds=time.monotonic()-start)
            assert events==json.loads(Path(a['a2_reference']).read_text())
        assert any((e.get('text') or e.get('raw_text','')).strip() for e in events)
        result.update(status='PHASE_COLLECTED',canonical_reference_exact=True,event_count=len(events))
    except Exception as exc:result['error']=type(exc).__name__+': '+str(exc)
    finally:
        if phase=='a2':
            if stream is not None:stream.close()
            if model is not None:model.close();assert not bool(model.handle)
        stream=None;model=None;gc.collect();result['model_closed']=True
        result.update(elapsed_seconds=time.monotonic()-began,cpu_seconds=time.process_time()-cpu,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,ended_monotonic_ns=time.monotonic_ns(),address_space=resource.getrlimit(resource.RLIMIT_AS),stack=resource.getrlimit(resource.RLIMIT_STACK),affinity=sorted(os.sched_getaffinity(0)))
        with (d/'RESULT.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    return int(result['status']!='PHASE_COLLECTED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['sherpa','a2'],required=True)
    raise SystemExit(main(p.parse_args().phase))
