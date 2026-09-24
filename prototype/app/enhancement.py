"""One optional stateful post-XVF 16k branch. See README_NOISE.md."""
from pathlib import Path
from functools import lru_cache
import threading,time
import numpy as np
from .paths import ROOT,read_json,sha256
from .buffers import MemoryJournal
from .noise_coordination import NoiseCoordinator

RATE=16000
ROUTES={'bypass':'Bypass','asr':'Enhance for ASR','identity':'Enhance for identity','both':'Enhance for both'}

@lru_cache(maxsize=1)
def specification():return read_json(ROOT/'config/enhancement.json')
def identity_domain(route):return specification()['id'] if route in ('identity','both') else None
def identity_binding(route):
    return dict(enhancement=identity_domain(route),enhancement_sha256=specification()['sha256']) if identity_domain(route) else {}
def route_binding(route):
    if route not in ROUTES:raise ValueError('Unknown enhancement route')
    spec=specification()
    return dict(route=route,model_sha256=spec['sha256'] if route!='bypass' else None,
        asr_stream='enhanced' if route in ('asr','both') else 'input',
        identity_stream='enhanced' if route in ('identity','both') else 'input',experimental=route!='bypass')


class DpdfStream:
    """Sherpa 1.13.4 streaming API, never an offline denoiser in a chunk loop."""
    def __init__(self,models_root):
        import sherpa_onnx as sherpa
        spec=specification();path=Path(models_root)/spec['sha256']/spec['filename']
        if sherpa.__version__!=spec['runtime_version']:raise ValueError('Enhancement runtime is not the checked 1.13.4 version')
        if not path.is_file() or path.stat().st_size!=spec['size_bytes'] or sha256(path)!=spec['sha256']:raise ValueError('Optional DPDFNet model is missing or hash differs; select Bypass')
        config=sherpa.OnlineSpeechDenoiserConfig(model=sherpa.OfflineSpeechDenoiserModelConfig(
            dpdfnet=sherpa.OfflineSpeechDenoiserDpdfNetModelConfig(model=str(path)),num_threads=1,provider='cpu'))
        self.native=sherpa.OnlineSpeechDenoiser(config)
        if (self.native.sample_rate,self.native.frame_shift_in_samples)!=(16000,160):raise ValueError('Unexpected enhancement frame contract')
        self.reset()
    def reset(self):
        self.native.reset();self.input_samples=self.output_samples=0;self.closed=False;self.compute_sec=0.;self.max_call_sec=0.
    def _result(self,result,elapsed):
        y=np.asarray(result.samples,np.float32)
        if result.sample_rate!=RATE or y.ndim!=1 or not np.isfinite(y).all():raise ValueError('Invalid enhancer output')
        self.output_samples+=len(y);self.compute_sec+=elapsed;self.max_call_sec=max(self.max_call_sec,elapsed)
        if self.output_samples>self.input_samples:raise ValueError('Enhancer output exceeds source; no trimming allowed')
        return y
    def run(self,samples):
        x=np.asarray(samples,np.float32)
        if self.closed or x.ndim!=1 or len(x)>160000 or not np.isfinite(x).all():raise ValueError('Invalid enhancer source or closed stream')
        self.input_samples+=len(x);started=time.perf_counter()
        result=self.native.run(x,RATE)
        return self._result(result,time.perf_counter()-started)
    def flush(self):
        if self.closed:return np.empty(0,np.float32)
        started=time.perf_counter();result=self.native.flush();y=self._result(result,time.perf_counter()-started)
        self.closed=True
        if self.output_samples!=self.input_samples:raise ValueError('Enhancer flush length mismatch; no padding allowed')
        return y


class IdentityView:
    """On helper failure, stop enhanced identity; raw ASR keeps all source audio."""
    def __init__(self,router):self.router=router;self.journal=router.enhanced;self.sample_rate=RATE;self.path=self.journal.path
    @property
    def committed_samples(self):return self.journal.committed_samples if self.router.identity_limit is None else self.router.identity_limit
    @property
    def finished(self):return self.router.identity_limit is not None or self.journal.finished
    @property
    def fatal_error(self):return self.journal.fatal_error
    @property
    def duration_sec(self):return self.committed_samples/RATE
    def read(self,cursor,size,wait_sec=.25):
        if self.router.identity_limit is not None:size=min(size,max(0,self.router.identity_limit-cursor))
        result=self.journal.read(cursor,size,wait_sec=0 if self.finished else wait_sec)
        if self.router.identity_limit is not None:result=result[:max(0,self.router.identity_limit-cursor)]
        return result
    def finish(self,error=None):self.router.finish(error)


class EnhancementRouter:
    """One capture writer; optional worker reads a bounded raw ring off callback."""
    def __init__(self,path,reserve_sec,route,helper,archive=None,emit=None,coordinator=None):
        self.path=Path(path);self.sample_rate=RATE;self.route=route;self.helper=helper;self.archive=archive;self.emit=emit or (lambda *a:None)
        self.coordinator=coordinator or NoiseCoordinator(route);self.guard=threading.RLock()
        self.raw=MemoryJournal(path,RATE,reserve_sec,observer=archive.audio_block if archive else None)
        self.enhanced=MemoryJournal(path.with_name('enhanced_ram'),RATE,reserve_sec,
            observer=archive.enhanced_block if archive else None)
        self.asr=self.enhanced if route in ('asr','both') else self.raw
        self.identity_limit=None;self.identity=IdentityView(self) if route in ('identity','both') else self.raw
        self.active=True;self.finishing=False;self.thread=None;self.finish_timer=None;self.cursor=0;self.next_quality=0
        self.helper.reset()
    @property
    def committed_samples(self):return self.raw.committed_samples
    @property
    def finished(self):return self.raw.finished
    @property
    def fatal_error(self):return self.raw.fatal_error
    @property
    def duration_sec(self):return self.raw.duration_sec
    def start(self):
        self.thread=threading.Thread(target=self._run,name='proto-optional-enhancement',daemon=True);self.thread.start()
    def append(self,samples):
        start=self.raw.committed_samples;self.raw.append(samples)
        end=self.raw.committed_samples
        if end>=self.next_quality:
            x=np.asarray(samples,np.float32)
            self.coordinator.observe('waveform',start/RATE,end/RATE,dict(rms=float(np.sqrt(np.mean(x.astype(np.float64)**2))),clipped_fraction=float(np.mean(np.abs(x)>=.999))),
                'actual unenhanced post-XVF mono samples; no SNR/voice inference')
            self.next_quality=end+8000
        if self.active and (end-self.enhanced.committed_samples)>RATE//2:self._fallback('optional worker backlog >0.5s')
        if not self.active:self._copy_pending_raw()
    def _copy_pending_raw(self):
        with self.guard:
            while self.enhanced.committed_samples<self.raw.committed_samples:
                start=self.enhanced.committed_samples
                x=self.raw.read(start,min(3200,self.raw.committed_samples-start),wait_sec=0)
                self.enhanced.append(x)
                if self.archive:self.archive.enhancement_transform(start,len(x),'raw_fallback',self.raw.committed_samples,0.)
    def _fallback(self,reason):
        with self.guard:
            if not self.active:return
            self.active=False
            if self.route in ('identity','both'):self.identity_limit=self.enhanced.committed_samples
            if self.archive and self.identity_limit is not None:self.archive.metadata['identity_stopped_at_sample']=self.identity_limit
            record=dict(reason=str(reason),source_start_sample=self.enhanced.committed_samples,available_monotonic_sec=time.perf_counter(),
                policy='Raw source resumes at exact next sample; enhanced identity ends, no cross-domain matching. Select route at a fresh Start.')
            self.coordinator.fallback=record;self.emit('enhancement_fallback',self.enhanced.duration_sec,record)
            self._copy_pending_raw()
    def _publish(self,y,available_source,compute):
        with self.guard:
            if not self.active:return
            if len(y):
                start=self.enhanced.committed_samples;self.enhanced.append(y)
                if self.archive:self.archive.enhancement_transform(start,len(y),'dpdfnet_stateful',available_source,compute)
    def _run(self):
        try:
            while self.active:
                x=self.raw.read(self.cursor,320)
                if len(x):
                    self.cursor+=len(x);started=time.perf_counter();y=self.helper.run(x)
                    self._publish(y,self.cursor,time.perf_counter()-started)
                elif self.raw.finished:break
            if self.active:
                started=time.perf_counter();tail=self.helper.flush()
                self._publish(tail,self.cursor,time.perf_counter()-started)
        except Exception as exc:self._fallback(str(exc))
        finally:
            if not self.active:
                # Source append copies future raw blocks; finish waits for capture.
                while not self.raw.finished:
                    with self.raw._condition:self.raw._condition.wait(.1)
                self._copy_pending_raw()
            self.enhanced.finish(self.raw.fatal_error)
            if self.finish_timer is not None:self.finish_timer.cancel()
    def finish(self,error=None):
        with self.guard:
            self.raw.finish(error)
            if self.finishing:return
            self.finishing=True
            if not self.active:
                self._copy_pending_raw();self.enhanced.finish(error)
            elif self.thread is None:self.enhanced.finish(error)
            elif not self.enhanced.finished:
                # At EOF no further source append can detect backlog. A bounded
                # flush deadline releases ASR even if a native call is stalled.
                # The worker still retains ownership until join succeeds.
                def expired():
                    with self.guard:
                        if self.enhanced.finished:return
                        self._fallback('optional helper did not finish within0.5s of source closure')
                        self.enhanced.finish(self.raw.fatal_error)
                self.finish_timer=threading.Timer(.5,expired);self.finish_timer.daemon=True;self.finish_timer.start()
    def join(self,timeout=10):
        if self.thread:self.thread.join(timeout)
        if self.thread and self.thread.is_alive():raise RuntimeError('Enhancement worker remains active; do not reuse model')
    def snapshot(self):
        return self.coordinator.snapshot(self.raw.committed_samples,max(0,self.raw.committed_samples-self.enhanced.committed_samples)/RATE)
