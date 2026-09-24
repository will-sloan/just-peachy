"""Pinned NeMo CPU reference streams; see README_REFERENCE.md."""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
import sys
import time
import numpy as np

NEMO_REVISION = 'cf724ac337d1ebc7d0dda1e23fb80916f52927a5'
WEIGHTS = {
    'A1': '6603a22a53b7c1a4bac4736cb24628fb568a7102ba931a28c799e2e72f109893',
    'A2': '283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd',
    'A3': '210214ed94039bf6bfbb9a047c7fa289628db75b103e2bf6381fa78285436a74',
}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class ReferenceRecognizer:
    def __init__(self, variant, model_path, source_root, *, right_context=1):
        if variant not in WEIGHTS or sha(model_path) != WEIGHTS[variant]:
            raise ValueError('Reference model hash is not the admitted checkpoint')
        if right_context not in (0,1):
            raise ValueError('Reference screen admits only nominal/lower-buffer context')
        if variant == 'A1' and right_context != 1:
            raise ValueError('A1 was trained for [70,1]; no unsupported lower-buffer context')
        self.source_root = Path(source_root).resolve(strict=True)
        sys.path.insert(0,str(self.source_root))
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        torch.set_float32_matmul_precision('highest')
        self.variant, self.model_path = variant, str(model_path)
        import nemo
        if not Path(nemo.__file__).resolve().is_relative_to(self.source_root.resolve()):
            raise ValueError('Imported NeMo is outside the bound reviewed source tree')
        self.right_context = right_context
        self.active = None
        self.serial = 0
        if variant == 'A1':
            from a1_service import NemoStreamingASRService
            self.service = NemoStreamingASRService(model=str(model_path),device='cpu',
                att_context_size=[70,1],use_amp=False,chunk_size_in_secs=.08)
            self.pipeline = None
        else:
            from omegaconf import OmegaConf, open_dict
            from nemo.collections.asr.inference.factory.pipeline_builder import PipelineBuilder
            source_config = self.source_root / 'examples/asr/conf/asr_streaming_inference/cache_aware_rnnt.yaml'
            config = OmegaConf.load(source_config)
            with open_dict(config):
                config.asr.model_name = str(model_path)
                config.asr.device = 'cpu'
                config.asr.compute_dtype = 'float32'
                config.asr.use_amp = False
                config.asr.use_cuda_graphs = False
                config.asr.decoding.greedy.use_cuda_graph_decoder = False
                config.asr.decoding.greedy.enable_per_stream_biasing = False
                config.streaming.att_context_size = [56 if variant == 'A3' else 70,right_context]
                config.streaming.chunk_size_in_secs = None
                config.streaming.batch_size = 1
                config.streaming.num_slots = 1
                config.streaming.request_type = 'frame'
                config.enable_itn = False
                config.enable_nmt = False
                config.lang = 'en-US'
                config.matmul_precision = 'highest'
                config.asr_output_granularity = 'word'
                config.return_tail_result = True
                config.calculate_wer = False
                config.calculate_bleu = False
            self.config = OmegaConf.to_container(config,resolve=True)
            self.pipeline = PipelineBuilder.build_pipeline(config)
            self.pipeline.open_session()

    def stream(self):
        if self.active is not None and not self.active.closed:
            raise RuntimeError('Close the previous reference stream')
        self.serial += 1
        self.active = ReferenceStream(self,self.serial)
        return self.active

    def close(self):
        if self.active is not None:
            self.active.close()
        if self.pipeline is not None:
            self.pipeline.close_session()


class ReferenceStream:
    sample_rate = 16000

    def __init__(self,owner,serial):
        self.owner,self.serial = owner,serial
        self.input_samples = 0
        self.pending = np.empty(0,np.float32)
        self.decode_ms = 0.
        self.finished = self.closed = False
        self.first = True
        self.utterance_index = 0
        self.partial = ''
        self.chunk = 1280 if owner.variant == 'A1' else round((owner.right_context+1)*.08*16000)
        self.padding_seconds = 1.28 if owner.variant == 'A1' else 0.
        if owner.variant == 'A1':
            owner.service.reset_state()

    def _event(self,text,final,**metadata):
        row = dict(raw_text=text,final=final,utterance=self.utterance_index,
            input_samples=self.input_samples,input_end_sec=self.input_samples/16000,
            available_at_monotonic=time.perf_counter(),words=[],
            word_time_kind='UNAVAILABLE_IN_REFERENCE_ADAPTER',
            endpoint_reason='model_EOU_EOB_or_explicit_tail' if final else None)
        row.update(metadata)
        if final:
            self.utterance_index += 1
        return row

    def _step(self,audio,*,last=False,valid_length=None):
        if self.owner.variant == 'A1':
            # The official service accepts PCM16. This round-trip is exact for
            # the admitted PCM16 saved bank at gain=1. No floating gain is hidden.
            pcm = np.rint(audio.astype(np.float64)*32768)
            if np.any(pcm < -32768) or np.any(pcm > 32767):
                raise ValueError('A1 reference PCM16 service cannot represent this gain without clipping')
            result = self.owner.service.transcribe(pcm.astype('<i2').tobytes())
            rows = []
            # The service returns token-piece deltas, not cumulative text. Keep
            # all words on both sides of every emitted control token.
            pieces = re.split('(<EOU>|<EOB>)',result.text)
            for piece in pieces:
                if piece in ('<EOU>','<EOB>'):
                    rows.append(self._event(self.partial.strip(),True,raw_model_delta=result.text,
                        control_token=piece,encoder_cache_policy='official_service_reset_on_predicted_EOU_EOB',
                        eou_probability=result.eou_prob,eob_probability=result.eob_prob))
                    self.partial = ''
                else:
                    self.partial += piece
            if self.partial:
                rows.append(self._event(self.partial.strip(),False,raw_model_delta=result.text))
            return rows
        import torch
        from nemo.collections.asr.inference.streaming.framing.request import Frame
        from nemo.collections.asr.inference.streaming.framing.request_options import ASRRequestOptions
        request = Frame(samples=torch.from_numpy(np.asarray(audio,np.float32)),stream_id=self.serial,
            is_first=self.first,is_last=last,length=len(audio) if valid_length is None else valid_length,
            options=ASRRequestOptions(enable_itn=False,enable_nmt=False,language_code='en-US',
                stop_history_eou=800,asr_output_granularity='word') if self.first else None)
        result = self.owner.pipeline.transcribe_step([request])[0]
        self.first = False
        rows = []
        if result.final_transcript:
            words=[dict(text=segment.text,start_sec=segment.start,end_sec=segment.end) for segment in (result.final_segments or [])]
            rows.append(self._event(result.final_transcript,True,words=words,
                word_time_kind='reference_native_word_offsets_unadjusted' if words else 'UNAVAILABLE_IN_THIS_RESULT'))
        self.partial = result.partial_transcript or ''
        if self.partial:
            rows.append(self._event(self.partial,False))
        if last and self.partial:
            rows.append(self._event(self.partial,True,explicit_tail_final=True))
            self.partial = ''
        return rows

    def feed(self,audio):
        if self.finished or self.closed:
            raise RuntimeError('Reference stream finished/closed')
        audio = np.asarray(audio,np.float32)
        if audio.ndim != 1 or not np.all(np.isfinite(audio)):
            raise ValueError('Finite mono waveform required')
        self.input_samples += len(audio)
        self.pending = np.concatenate((self.pending,audio))
        rows = []
        began = time.perf_counter()
        # One chunk is held so NeMo receives the actual final frame with its
        # true length. This reference-only extra buffer is recorded as such.
        while len(self.pending) > self.chunk:
            block,self.pending = self.pending[:self.chunk],self.pending[self.chunk:]
            rows.extend(self._step(block))
        self.decode_ms = (time.perf_counter()-began)*1000
        return rows

    def finish_events(self):
        if self.finished:
            return []
        if self.closed:
            raise RuntimeError('Reference stream is closed')
        began = time.perf_counter()
        rows = []
        valid = len(self.pending)
        if self.input_samples:
            block = np.pad(self.pending,(0,self.chunk-valid))
            self.padding_seconds += (self.chunk-valid)/16000
            rows.extend(self._step(block,last=self.owner.variant!='A1',valid_length=valid))
            if self.owner.variant == 'A1':
                for _ in range(16):
                    rows.extend(self._step(np.zeros(self.chunk,np.float32)))
                if self.partial:
                    rows.append(self._event(self.partial.strip(),True,explicit_tail_final=True))
                    self.partial = ''
        self.pending = np.empty(0,np.float32)
        self.finished = True
        self.decode_ms = (time.perf_counter()-began)*1000
        return rows

    def close(self):
        if self.closed:
            return
        if self.owner.pipeline is not None and not self.first:
            self.owner.pipeline.delete_state(self.serial)
        self.closed = True
