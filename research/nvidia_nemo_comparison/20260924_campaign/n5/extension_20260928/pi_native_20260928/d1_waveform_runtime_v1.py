"""Bounded ordered waveform-to-D1 candidate; README_D1_WAVEFORM_V1.md."""
import threading
import time
import numpy as np
from d1_numpy_frontend_v1 import Frontend
from d1_ort_state_v1 import OrtState

class WaveformD1:
    """One 16kHz stream, delayed264/1/1/0/264/188; no capture or label UI."""
    def __init__(self, graph, compression, coefficients, silence_embedding, max_samples=715127):
        import onnxruntime as ort
        if type(max_samples) is not int or not 0 < max_samples <= 715127:
            raise ValueError('Candidate bound is at most715127samples')
        self.thread=threading.get_ident();self.max_samples=max_samples
        self.frontend=Frontend(coefficients)
        self.state=OrtState(silence_embedding,compression,fifo_capacity=0,refresh=188)
        options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        options.add_session_config_entry('session.intra_op.allow_spinning','0')
        options.add_session_config_entry('session.inter_op.allow_spinning','0')
        self.model=ort.InferenceSession(str(graph),options,providers=['CPUExecutionProvider'])
        if self.model.get_providers()!=['CPUExecutionProvider']:raise RuntimeError('Unexpected provider')
        self.names=['chunk','chunk_lengths','spkcache','spkcache_lengths','fifo','fifo_lengths']
        self.outputs=['spkcache_fifo_chunk_preds','chunk_pre_encode_embs','chunk_pre_encode_lengths','high_resolution_preds']
        if [x.name for x in self.model.get_inputs()]!=self.names or [x.name for x in self.model.get_outputs()]!=self.outputs:
            raise RuntimeError('Wrong four-output graph contract')
        self.reset()

    def _owner(self):
        if threading.get_ident()!=self.thread:raise RuntimeError('One ordered owning thread required')
        if self.model is None:raise RuntimeError('Runtime released')

    def reset(self):
        self._owner();self.frontend.reset();self.state.reset()
        self.features=np.empty((0,128),np.float32)
        self.base=self.available=self.position=self.samples=0
        self.closed=False;self.trace=[];self.peak_feature_rows=0
        self.frontend_seconds=self.model_seconds=self.state_seconds=0.0

    def _append(self, features):
        self.features=np.concatenate((self.features,features));self.available+=len(features)
        self.peak_feature_rows=max(self.peak_feature_rows,len(self.features))
        if len(self.features)>2112+16+206:raise RuntimeError('Feature buffer exceeded')

    def _pump(self, eof):
        rows=[]
        while self.position<self.available:
            if not eof and self.available<self.position+2112+8:break
            end=min(self.position+2112,self.available)
            left=min(8,self.position);right=min(8,self.available-end)
            chunk=self.features[self.position-left-self.base:end+right-self.base].copy()
            assert len(chunk)==end-self.position+left+right and chunk.shape[1]==128
            before_cache=len(self.state.cache);before_fifo=len(self.state.fifo)
            feed=dict(chunk=chunk[None],chunk_lengths=np.array([len(chunk)],np.int64),
                spkcache=self.state.cache[None],spkcache_lengths=np.array([before_cache],np.int64),
                fifo=self.state.fifo[None],fifo_lengths=np.array([before_fifo],np.int64))
            start=time.perf_counter();coarse,emb,lengths,high=self.model.run(self.outputs,feed)
            self.model_seconds+=time.perf_counter()-start
            if int(lengths[0])!=(len(chunk)+7)//8 or emb.shape!=(1,int(lengths[0]),512):
                raise RuntimeError('Encoded length mismatch')
            if coarse.shape!=(1,before_cache+before_fifo+len(emb[0]),8) or high.shape!=(1,coarse.shape[1]*8,8):
                raise RuntimeError('Graph probability shape mismatch')
            if not all(np.isfinite(x).all() for x in (coarse,emb,high)):raise RuntimeError('Nonfinite graph output')
            lc=left//8;rc=(right+7)//8;count=len(emb[0])-lc-rc
            # Keep the original learned output. Never reconstruct it from coarse probabilities.
            first=(before_cache+before_fifo+lc)*8
            emitted=high[0,first:first+count*8][:end-self.position].copy()
            assert len(emitted)==end-self.position
            start=time.perf_counter();self.state.update(emb[0],coarse[0],offset=self.state.offset,left=lc,right=rc)
            self.state_seconds+=time.perf_counter()-start
            self.trace.append(dict(feature_start=self.position,feature_end=end,left_features=left,right_features=right,
                graph_feature_rows=len(chunk),encoded_rows=len(emb[0]),highres_offset=first,
                emitted_rows=len(emitted),trimmed_coarse_padding=count*8-len(emitted),
                coarse_offset=self.state.offset,cache_rows=len(self.state.cache),fifo_rows=len(self.state.fifo)))
            rows.append(emitted);self.position=end
            keep=max(0,self.position-8);self.features=self.features[keep-self.base:].copy();self.base=keep
        return np.concatenate(rows) if rows else np.empty((0,8),np.float32)

    def push(self, audio, *, source_start):
        self._owner()
        if self.closed:raise RuntimeError('Stream already finished')
        if type(source_start) is not int or source_start!=self.samples:raise ValueError('Noncontiguous source samples')
        x=np.asarray(audio)
        if x.ndim!=1 or x.dtype!=np.float32 or len(x)>32768 or not np.isfinite(x).all():
            raise ValueError('Need finite mono float32 <=32768samples')
        if self.samples+len(x)>self.max_samples:raise ValueError('Admitted sample bound exceeded')
        start=time.perf_counter();features=self.frontend.push(x);self.frontend_seconds+=time.perf_counter()-start
        self.samples+=len(x);self._append(features)
        return self._pump(False)

    def finish(self):
        self._owner()
        if self.closed:raise RuntimeError('Stream already finished')
        start=time.perf_counter();self._append(self.frontend.finish());self.frontend_seconds+=time.perf_counter()-start
        result=self._pump(True);self.state.finish();self.closed=True
        if self.position!=self.samples//160 or self.available!=self.position:raise RuntimeError('Incomplete valid feature passage')
        self.features=np.empty((0,128),np.float32);self.base=self.available
        return result

    def close(self):
        self._owner();self.closed=True;self.state.close();self.model=None
        self.features=np.empty((0,128),np.float32)

    def process(self, audio, sizes=(3200,)):
        self.reset();parts=[];offset=0;index=0
        while offset<len(audio):
            n=sizes[index%len(sizes)]
            if type(n) is not int or not 0<n<=32768:raise ValueError('Invalid push size')
            x=audio[offset:offset+n];parts.append(self.push(x,source_start=offset));offset+=len(x);index+=1
        parts.append(self.finish())
        return np.concatenate(parts)
