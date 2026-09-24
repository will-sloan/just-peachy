"""Small consented live lifecycle and native file check; see README_LIVE_TIMING.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import os

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(key,'1')
import psutil
import soundfile as sf
from app.controller import Controller
from app.paths import atomic_json,default_models_root


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consent',action='store_true')
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--wav',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if not args.consent or output.exists() or ROOT in output.parents:
        parser.error('Require consent and a new private output directory outside app')
    output.mkdir(parents=True)
    atomic_json(output/'live_config.json',json.loads(args.config.read_text(encoding='utf-8-sig')))
    # Existing speech, no gain/resampling/mixing; short exact final partial block.
    with sf.SoundFile(args.wav) as handle:
        if handle.samplerate!=16000 or handle.channels!=1 or handle.subtype!='PCM_16':
            raise ValueError('Prepared O0 PCM16 mono16k required')
        audio=handle.read(96073,dtype='int16')
    wav=output/'O0.wav';sf.write(wav,audio,16000,subtype='PCM_16')
    del audio
    proc=psutil.Process();cpu0=proc.cpu_times();start=time.perf_counter();peak=proc.memory_info().rss
    result=dict(utc=datetime.now(timezone.utc).isoformat(),checks=[],
        scope='Consented real input lifecycle plus existing prerecorded speech. No saved microphone WAV or enrollment; no human speech accuracy claim.')
    c=Controller(output,default_models_root())
    def finish_command():
        c.commands.join()
        if c.error:raise RuntimeError(c.error)
    def collect(engine,label):
        source=engine._source
        receipt=dict(label=label,state=engine.state,source_error=getattr(source,'error',None),
            samples=source.sent,session=str(engine.session_dir),
            finalization_error=str(engine._finalization_error) if engine._finalization_error else None)
        if hasattr(source,'live'):
            receipt.update(integrity=source.integrity,timing=source.timing.snapshot() if source.timing else None,
                output_defaults=source.stop_receipt.get('default_output_comparison') if source.stop_receipt else None,
                source_thread_alive=source.thread.is_alive() if source.thread else False)
        receipt['status']='PASS' if (receipt['state']=='COMPLETED' and not receipt['source_error']
            and not receipt['finalization_error'] and (not hasattr(source,'live') or
                source.integrity['ok'] and not receipt['source_thread_alive'])) else 'FAIL'
        result['checks'].append(receipt)
        print(json.dumps({key:receipt[key] for key in ('label','status','state','samples')}),flush=True)
    def receive(seconds):
        nonlocal peak
        deadline=time.perf_counter()+seconds+15
        while c.engine._source.sent<round(seconds*16000):
            if c.error or c.engine.state=='FAILED':raise RuntimeError(c.error or 'Native engine failed')
            if time.perf_counter()>deadline:raise TimeoutError('Capture made insufficient progress')
            peak=max(peak,proc.memory_info().rss)
            time.sleep(.05)
    try:
        c.switch(mode='anonymous_conversation',recipe='balanced',tap='O0');finish_command()
        c.start_live(consent=True);finish_command();receive(6)
        first=c.engine
        c.switch(mode='strongly_spatial_assisted',recipe='balanced',tap='O1');finish_command()
        collect(first,'O0 balanced to O1 spatial transition')
        receive(6);second=c.engine;c.stop();finish_command();collect(second,'O1 spatial Stop')
        c.switch(mode='caption_only',recipe='fast',tap='O0');finish_command()
        for i in range(2):
            c.start_live(consent=True);finish_command();engine=c.engine
            c.stop();finish_command();collect(engine,'Immediate Start Stop '+str(i+1))
        c.start_file(wav);finish_command();engine=c.engine
        deadline=time.perf_counter()+30
        while c.state in ('RUNNING','STARTING','STOPPING'):
            if time.perf_counter()>deadline:raise TimeoutError('Short native file did not finish')
            peak=max(peak,proc.memory_info().rss);time.sleep(.05)
        if c.error:raise RuntimeError(c.error)
        c.stop();finish_command();collect(engine,'Prepared speech with 73-sample final partial block')
        result['model_cache']=dict(asr_loads=c.models.asr_loads,speaker_loads=c.models.speaker_loads,streams=c.models.streams)
        result['status']='PASS' if all(r['status']=='PASS' for r in result['checks']) else 'FAIL'
    except Exception as exc:
        result.update(status='FAIL',error=repr(exc))
    finally:
        c.close();c.commands.join();c.worker.join(15)
        result['closed']=c.closed
        if not c.closed:result.update(status='FAIL',close_error=c.error)
        cpu=proc.cpu_times()
        result['resources']=dict(elapsed_sec=time.perf_counter()-start,
            process_cpu_sec=cpu.user+cpu.system-cpu0.user-cpu0.system,
            observed_peak_rss_bytes=peak,scope='desktop process; not CM5 qualification')
        atomic_json(output/'TIMING_LIFECYCLE_CHECK.json',result)
    print(json.dumps({key:result.get(key) for key in ('status','error','closed','model_cache','resources')}))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
