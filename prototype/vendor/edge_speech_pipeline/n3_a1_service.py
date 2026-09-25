"""CPU A1 service using NumPy/SciPy and ONNX Runtime; README_N3_A1.md."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
import numpy as np


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


@dataclass
class Result:
    text: str
    is_final: bool
    eou_prob: float | None = None
    eob_prob: float | None = None


class FeatureBuffer:
    """Exact pinned inference frontend and official 80-ms cache scheduling."""
    def __init__(self, config, window, filterbank):
        self.config=config
        expected=dict(sample_rate=16000,features=128,n_fft=512,hop_length=160,
            win_length=400,normalize='NA',pad_to=0,frame_splicing=1,log=True,
            log_zero_guard_type='add',log_zero_guard_value=2**-24,
            preemph=.97,mag_power=2.,exact_pad=False,use_grads=False)
        if any(config.get(k)!=v for k,v in expected.items()):
            raise ValueError('Frontend differs from the reviewed pinned A1 contract')
        self.chunk=1280;self.lookback=160
        self.window=np.pad(np.asarray(window,np.float32),(56,56))
        self.filterbank=np.asarray(filterbank,np.float32).reshape(128,257)
        if self.window.shape!=(512,):raise ValueError('Unexpected exported window')
        self.reset()

    def reset(self):
        self.samples=np.zeros(4000,np.float32)
        self.features=np.full((128,25),-16.635,np.float32)

    def update(self, audio):
        from scipy.fft import rfft
        audio=np.asarray(audio,np.float32)
        if audio.shape!=(self.chunk,) or not np.all(np.isfinite(audio)):
            raise ValueError('Service requires one finite 1280-sample chunk')
        self.samples[:-self.chunk]=self.samples[self.chunk:].copy()
        self.samples[-self.chunk:]=audio
        samples=self.samples[-(self.lookback+self.chunk):].copy()
        emphasized=np.concatenate((samples[:1],samples[1:]-np.float32(.97)*samples[:-1]))
        padded=np.pad(emphasized,(256,256))
        frames=np.lib.stride_tricks.sliding_window_view(padded,512)[::160]
        spectrum=rfft(frames*self.window,axis=-1,workers=1)
        magnitude=np.sqrt(spectrum.real**2+spectrum.imag**2)
        power=magnitude**2
        mel=np.log(self.filterbank@power.T+np.float32(2**-24))
        # NeMo's dense preprocessor masks the extra centered terminal frame.
        mel[:,len(samples)//160:]=0.
        diff=mel.shape[1]-8-1
        if diff>0:mel=mel[:,:-diff]
        self.features[:,:-8]=self.features[:,8:].copy()
        self.features[:,-8:]=mel[:,-8:]
        return self.features.copy()


class OnnxService:
    """One resident encoder/decoder pair, explicit recurrent states and EOU reset."""
    def __init__(self, bundle, *, audit=False):
        bundle=Path(bundle).resolve(strict=True)
        manifest=json.loads((bundle/'BUNDLE.json').read_text(encoding='utf-8'))
        if manifest['schema']!='n3-a1-onnx-service-bundle-v1':raise ValueError('Unsupported A1 bundle')
        for row in manifest['files']:
            path=bundle/row['name']
            if path.parent!=bundle or digest(path)!=row['sha256'] or path.stat().st_size!=row['bytes']:
                raise ValueError('Portable asset binding changed')
        config=json.loads((bundle/'service_config.json').read_text(encoding='utf-8'))
        if config['model_sha256']!='6603a22a53b7c1a4bac4736cb24628fb568a7102ba931a28c799e2e72f109893':
            raise ValueError('Unadmitted A1 model')
        if config['streaming']['cache_drop_size']!=1 or config['streaming']['valid_out_len']!=1:
            raise ValueError('Service requires its actual 80-ms cache advance')
        self.config=config;self.audit=audit;self.last_step=None
        with np.load(bundle/'frontend_buffers.npz',allow_pickle=False) as buffers:
            self.frontend=FeatureBuffer(config['frontend'],buffers['window'],buffers['filterbank'])
        self.vocabulary=config['vocabulary'];self.blank=len(self.vocabulary)
        if self.blank!=1026 or self.vocabulary[-2:]!=['<EOU>','<EOB>']:
            raise ValueError('Unexpected token/control inventory')
        import onnxruntime as ort
        options=ort.SessionOptions();options.intra_op_num_threads=options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        self.encoder=ort.InferenceSession(str(bundle/'encoder-service.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        self.decoder=ort.InferenceSession(str(bundle/'decoder_joint-service.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
        if [x.name for x in self.encoder.get_inputs()]!=['audio_signal','length','cache_last_channel','cache_last_time','cache_last_channel_len']:
            raise ValueError('Unexpected encoder interface')
        if [x.name for x in self.decoder.get_inputs()]!=['encoder_outputs','targets','target_length','input_states_1','input_states_2']:
            raise ValueError('Unexpected decoder interface')
        if [x.type for x in self.decoder.get_inputs()]!=['tensor(float)','tensor(int32)','tensor(int32)','tensor(float)','tensor(float)']:
            raise ValueError('Unexpected decoder input dtypes')
        self.reset_state()

    def reset_state(self,stream_id='default'):
        self.frontend.reset()
        self.channel=np.zeros((1,17,70,512),np.float32)
        self.time_cache=np.zeros((1,17,512,8),np.float32)
        self.cache_len=np.zeros(1,np.int64)
        self.hidden=np.zeros((1,1,640),np.float32);self.cell=np.zeros_like(self.hidden)
        self.last_token=self.blank

    def transcribe(self,audio,stream_id='default'):
        if len(audio)!=2560:raise ValueError('One PCM16 80-ms chunk is required')
        features=self.frontend.update(np.frombuffer(audio,dtype='<i2').astype(np.float32)/32768.)
        outputs=self.encoder.run(None,dict(audio_signal=features[None],length=np.array([25],np.int64),
            cache_last_channel=self.channel,cache_last_time=self.time_cache,cache_last_channel_len=self.cache_len))
        encoded,length,self.channel,self.time_cache,self.cache_len=outputs
        tokens=[];probabilities=[]
        for t in range(int(length[0])):
            for _ in range(10):
                logits,_,h,c=self.decoder.run(None,dict(encoder_outputs=encoded[:,:,t:t+1],
                    targets=np.array([[self.last_token]],np.int32),target_length=np.ones(1,np.int32),
                    input_states_1=self.hidden,input_states_2=self.cell))
                scores=logits[0,0,0];token=int(np.argmax(scores))
                if token==self.blank:break
                p=np.exp(scores-np.max(scores));p/=p.sum()
                tokens.append(token);probabilities.append(float(p[token]))
                self.hidden,self.cell=h,c;self.last_token=token
        pieces=[self.vocabulary[t] for t in tokens]
        text=''.join(p.replace('\u2581',' ') if p.startswith('\u2581') else p for p in pieces)
        controls={control:probabilities[pieces.index(control)] if control in pieces else None for control in ('<EOU>','<EOB>')}
        final=any(p is not None for p in controls.values())
        if self.audit:
            self.last_step=dict(features=features,encoder=[x.copy() for x in outputs],
                decoder=[self.hidden.copy(),self.cell.copy()],tokens=tokens)
        if final:self.reset_state(stream_id)
        return Result(text,final,controls['<EOU>'],controls['<EOB>'])


class OnnxRecognizer:
    """Reuse the already reviewed sample accounting, event splitting and tail policy."""
    variant='A1'
    pipeline=None
    def __init__(self,bundle):
        self.service=OnnxService(bundle);self.active=None;self.serial=0
    def stream(self):
        from .n3_a1_stream import ReferenceStream
        if self.active is not None and not self.active.closed:raise RuntimeError('Close the previous stream')
        self.serial+=1;self.active=ReferenceStream(self,self.serial);return self.active
    def close(self):
        if self.active is not None:self.active.close()
