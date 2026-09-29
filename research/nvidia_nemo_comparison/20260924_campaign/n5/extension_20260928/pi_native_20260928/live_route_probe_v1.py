"""Bounded source-only quiet route probe. See README_LIVE_READY_V1.md."""
import time

def probe(L,config,seconds=12.,pump=None):
    source=L.XVFLiveSource(config);result={'status':'FAILED_PRESERVED','audio_saved':False,'models_loaded':False,'seconds_requested':seconds};blocks=0;samples=0;native=0;peak=0.;began=time.monotonic()
    try:
        metadata=source.start(consent=True);result['metadata']=metadata;started=time.monotonic()
        while samples<round(seconds*16000):
            if time.monotonic()-started>seconds+3:raise TimeoutError('Source count did not reach bounded quiet interval')
            if pump is not None:pump(source)
            block=source.read(.25)
            if block is None:continue
            assert block.model_start_sample==samples and block.native_start_frame==native
            assert block.native_frames==len(block.audio)*3 and block.resampler_delay_seconds==.001
            blocks+=1;samples+=len(block.audio);native+=block.native_frames
            if len(block.audio):peak=max(peak,float(abs(block.audio).max()))
        result['status']='SOURCE_COUNTS_COLLECTED_REQUIRES_REVIEW'
    except BaseException as exc:result['error']=type(exc).__name__+': '+str(exc)
    finally:
        for attempt in range(2):
            try:
                result['stop_receipt']=source.stop();break
            except BaseException as exc:
                result.setdefault('stop_failures',[]).append(type(exc).__name__+': '+str(exc));time.sleep(.05)
        result['integrity']=L.summarize_live_integrity(source)
        if not result['integrity']['ok'] or result.get('stop_failures'):result['status']='FAILED_PRESERVED'
        result.update(samples=samples,native_frames=native,blocks=blocks,maximum_absolute_amplitude=peak,elapsed_seconds=time.monotonic()-began,lease_released=source.lease is None or source.lease.handle is None)
    return result
