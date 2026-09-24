"""Finite audio-derived alternatives, no language model. See README_TRANSCRIPT_REVIEW.md."""
from copy import deepcopy
import difflib,hashlib,json,os,platform,re,threading,time,uuid
import numpy as np
from .text_assistance import PROTECTED,WORDS,tokens

MAX_SECONDS=20
MAX_TEXT=4000
TIMEOUT=8.
HELPER_STATUS='NOT_INSTALLED: no justified language-model role; no qualified Qwen/llama.cpp derivative downloaded'

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def audio_digest(x):return hashlib.sha256(np.asarray(x,dtype='<f4').tobytes()).hexdigest()
def desktop_supported():return os.name=='nt' and platform.machine().lower() in ('amd64','x86_64')
def resource_ok():
    import psutil
    return psutil.virtual_memory().available>=512*1024**2

def differences(original,alternative,vocabulary=()):
    a=original.split();b=alternative.split();changes=[];protected=[]
    names={t for v in vocabulary if v.get('kind')=='name' for t in tokens(v['text'])}|{'amir','emir'}
    for op,i,j,k,l in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if op=='equal':continue
        before=' '.join(a[i:j]);after=' '.join(b[k:l]);words=set(tokens(before+' '+after));risks=[]
        if words&(PROTECTED|{'can','could','will','must','may','positive','negative','yes'}):risks.append('pronoun / negation / meaning-sensitive words')
        if any(c.isdigit() for c in before+after):risks.append('amount / number / time')
        if words&names:risks.append('confusable or vocabulary name')
        if words-set(WORDS)-PROTECTED:risks.append('unusual or unknown vocabulary; preserve what was said')
        if op in ('insert','delete'):risks.append('missing or added speech; second decoding is not proof of recovery')
        changes.append(dict(operation=op,before=before,after=after,alternative_word_range=[k,l],original_word_range=[i,j],risks=risks))
        protected.extend(risks)
    return changes,sorted(set(protected))

def finite_review(job,decoded,stats,vocabulary=()):
    original=job['original'];decoded=str(decoded).strip()
    if len(original)>MAX_TEXT or len(decoded)>MAX_TEXT:raise ValueError('Review text exceeds bounded size')
    values=[dict(id='original',text=original,provenance='immutable original ASR',changes=[],protected=[])]
    if decoded and decoded!=original:
        changes,risks=differences(original,decoded,vocabulary)
        values.append(dict(id='redecode',text=decoded,provenance='unbiased greedy re-decode of exact archived ASR excerpt; not N-best',changes=changes,protected=risks))
    lexicon={t for entry in vocabulary for t in tokens(entry['text'])}
    for row in values:
        row['vocabulary_hits']=len(set(tokens(row['text']))&lexicon)
        row['acoustic_confidence']=None
    return dict(schema='just-peachy.audio-review.v1',id=uuid.uuid4().hex,request=deepcopy(job),candidates=values,
        ranking=['original']+[v['id'] for v in sorted(values[1:],key=lambda r:(-r['vocabulary_hits'],len(r['changes'])))],
        decision='original' if len(values)==1 and decoded else 'abstain',
        reason='Same decoder agrees; not independent corroboration' if decoded==original and decoded else 'No calibrated acoustic winner; listen and explicitly decide',
        decoder_output=decoded,language_helper=dict(status=HELPER_STATUS,selection=None),
        vocabulary_role='display ordering only; no new words, biasing, speaker access or acoustic confidence',
        resources=stats,uncertain_missing_words=True,automatic_adoption=False)

def validate_choice(raw,candidates):
    """Reserved finite-choice boundary; text can never become a command or new words."""
    if not isinstance(raw,str) or len(raw)>256:raise ValueError('Invalid bounded choice')
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError('Duplicate choice key')
            d[k]=v
        return d
    value=json.loads(raw,object_pairs_hook=unique)
    if not isinstance(value,dict) or set(value)!={'candidate_id'} or value['candidate_id'] not in ['abstain']+[c['id'] for c in candidates]:raise ValueError('Choose a supplied candidate ID or abstain')
    return value['candidate_id']

def decode_excerpt(stream,audio,guard):
    """Existing native recognizer/model, a new isolated stream; check between native calls."""
    rec=stream.recognizer;s=stream.stream;parts=[]
    def drain():
        while rec.is_ready(s):guard();rec.decode_stream(s)
    for start in range(0,len(audio),1600):
        guard();s.accept_waveform(16000,audio[start:start+1600]);drain()
        if rec.is_endpoint(s):
            parts.append(rec.get_result(s));rec.reset(s)
    guard();s.accept_waveform(16000,np.zeros(round(.66*16000),np.float32));s.input_finished();drain()
    parts.append(rec.get_result(s))
    return ' '.join(p.strip() for p in parts if p.strip())

class ReviewWorker:
    """One cancellable small optional job; generation fencing prevents stale publication."""
    def __init__(self):
        self.lock=threading.RLock();self.generation=0;self.thread=None;self.cancel_event=threading.Event();self.active_stream=None
        self.state=dict(status='OFF',result=None,reason='Enable review, then select a recorded utterance.')
    def cancel(self,reason='cancelled'):
        with self.lock:
            self.cancel_event.set();self.generation+=1;self.state=dict(status='CANCELLED',result=None,reason=reason)
    def snapshot(self):
        with self.lock:return deepcopy(dict(self.state,worker_alive=bool(self.thread and self.thread.is_alive()),generation=self.generation))
    def start(self,job,audio,stream,publish,vocabulary=(),*,timeout=TIMEOUT,resources=resource_ok):
        if self.thread and self.thread.is_alive():raise ValueError('Previous optional review is releasing its current native call; try again shortly')
        with self.lock:
            self.generation+=1;generation=self.generation;self.cancel_event=threading.Event();cancel=self.cancel_event
            self.state=dict(status='RUNNING',result=None,reason='Reviewing exact stored audio; captions are unchanged.')
        def work():
            import psutil
            proc=psutil.Process();started=time.perf_counter();cpu0=time.thread_time();rss0=proc.memory_info().rss;peak=rss0
            self.active_stream=stream
            def guard():
                nonlocal peak
                if cancel.is_set():raise InterruptedError('cancelled')
                if time.perf_counter()-started>timeout:raise TimeoutError('Review deadline; unchanged caption')
                if not resources():raise MemoryError('Resource pressure; unchanged caption')
                peak=max(peak,proc.memory_info().rss)
            try:
                if os.name=='nt':
                    import ctypes
                    kernel=ctypes.windll.kernel32;kernel.GetCurrentThread.restype=ctypes.c_void_p
                    kernel.SetThreadPriority.argtypes=[ctypes.c_void_p,ctypes.c_int]
                    kernel.SetThreadPriority(kernel.GetCurrentThread(),-1) # this worker only
                guard()
                x=np.asarray(audio,np.float32)
                if x.ndim!=1 or not 0<len(x)<=MAX_SECONDS*16000 or not np.isfinite(x).all():raise ValueError('Invalid bounded audio excerpt')
                if audio_digest(x)!=job['audio_sha256']:raise ValueError('Audio binding mismatch')
                rms=float(np.sqrt(np.mean(x.astype(np.float64)**2)))
                decoded='' if rms<.002 else decode_excerpt(stream,x,guard)
                guard()
                stats=dict(wall_sec=time.perf_counter()-started,worker_cpu_sec=time.thread_time()-cpu0,
                    rss_before=rss0,rss_after=proc.memory_info().rss,sampled_peak_increment_bytes=max(0,peak-rss0),
                    source_seconds=len(x)/16000,rms=rms,decoder_flush_s=.66,
                    measurement='Process RSS sampled between decode calls; CPU is this Python/native calling thread; resident models reused')
                result=finite_review(job,decoded,stats,vocabulary)
                with self.lock:
                    if generation!=self.generation or cancel.is_set():return
                    self.state=dict(status='DELIVERING',result=None,reason='Validating source before saving proposal')
                publish(generation,result)
            except Exception as exc:
                with self.lock:
                    if generation==self.generation:self.state=dict(status='ABSTAINED',result=None,reason=str(exc),unchanged=True)
            finally:self.active_stream=None
        self.thread=threading.Thread(target=work,name='proto-optional-transcript-review',daemon=True);self.thread.start()
