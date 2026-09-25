"""Unchanged reviewed ReferenceStream, used only by A1; README_N3_A1.md."""
import re
import time
import numpy as np


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
