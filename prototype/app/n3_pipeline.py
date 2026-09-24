"""Continuous N3 ASR events through the frozen display/identity contract."""
import math
import time
import string
import numpy as np

from .pipeline import PrototypeEngine
from .n2_pipeline import N2Engine


class StreamingASRLane:
    """Consume all journal samples; native EOU never resets speaker state."""

    def _asr_loop(self, asr):
        cursor = 0
        last_partial = {}
        last_display = -math.inf
        read_size = round(self.config.sample_rate * self.config.journal_read_ms / 1000)
        assert self._journal is not None

        def publish(rows):
            nonlocal last_display
            for row in rows:
                # Native timing is preserved in its own event. UI support uses
                # actual delivered audio, never an adjusted model frame clock.
                source_sec = row['input_end_sec']
                text = row['raw_text']
                utterance = row['utterance']
                self._emit('n3_asr_result', source_sec, dict(row,
                    normalized_lexical_score_text=' '.join(text.lower().translate(str.maketrans('','',string.punctuation)).split()),
                    formatted_text=text,manual_corrections=[],
                    sample_rate_hz=self.config.sample_rate, input_gain=self.config.input_gain,
                    source_timing='received_journal_samples', display_support='coarse_revision_window',
                    decoder_binding=self.resident.asr_document))
                if row['final']:
                    if text:
                        self._publish_final(asr, text, source_sec, utterance, asr.decode_ms)
                    self._research_utterance_start_sec = source_sec
                    last_partial.pop(utterance, None)
                    last_display = -math.inf
                elif text and text != last_partial.get(utterance) and source_sec - last_display >= self.config.partial_display_min_interval_sec:
                    self._transcript_event(text, source_sec, final=False, utterance=utterance, decode_ms=asr.decode_ms)
                    last_partial[utterance] = text
                    last_display = source_sec

        try:
            if self.config.sample_rate != 16000:
                raise ValueError('N3 is admitted for 16 kHz audio only')
            if self._research_profile.xvf.mode not in ('off', 'none', 'disabled'):
                # Saved file comparisons have no live endpoint telemetry. Do not
                # silently substitute a spatial endpoint recipe.
                raise ValueError('N3 ASR comparison requires native endpointing without XVF endpoint advice')
            while True:
                if self._state == 'FAILED':
                    raise RuntimeError('N3 ASR stops after session failure')
                audio = self._journal.read(cursor, read_size)
                if audio.size:
                    start = cursor
                    cursor += int(audio.size)
                    if self.config.input_gain != 1.0:
                        audio = audio * np.float32(self.config.input_gain)
                    began = time.perf_counter()
                    rows = asr.feed(audio)
                    source_sec = cursor / 16000
                    self._research_asr_available_sec = max(self._research_asr_available_sec, source_sec) + asr.decode_ms / 1000
                    self._emit('research_asr_dispatch', source_sec, dict(source_start_sec=start/16000,
                        source_end_sec=source_sec, samples=cursor-start, compute_ms=asr.decode_ms,
                        modeled_available_at_sec=self._research_asr_available_sec,
                        compute_started_elapsed_sec=began-self._started_monotonic,
                        compute_finished_elapsed_sec=time.perf_counter()-self._started_monotonic,
                        native_endpoint=any(row['final'] for row in rows),
                        reset_requested=False, state_policy='native stream retained across utterance events'))
                    publish(rows)
                    self._telemetry.update(asr_cursor_sec=source_sec,
                        asr_lag_sec=max(0., self._journal.duration_sec-source_sec), n3_input_samples=cursor)
                    if self._research_v2:
                        self._scheduler_advance('asr', source_sec, self._research_asr_available_sec)
                elif self._journal.finished and cursor >= self._journal.committed_samples:
                    break
            began = time.perf_counter()
            rows = asr.finish_events()
            elapsed = (time.perf_counter()-began)*1000
            self._research_asr_available_sec = max(self._research_asr_available_sec,cursor/16000)+elapsed/1000
            self._emit('research_asr_drain',cursor/16000,dict(source_end_sec=cursor/16000,
                synthetic_right_padding_sec=asr.padding_seconds,padding_is_observed_audio=False,
                compute_ms=elapsed,modeled_available_at_sec=self._research_asr_available_sec,
                exact_input_samples=asr.input_samples,compute_finished_elapsed_sec=time.perf_counter()-self._started_monotonic))
            publish(rows)
            if asr.input_samples != cursor:
                raise RuntimeError('ASR adapter did not account for every delivered sample')
            self._telemetry.update(asr_cursor_sec=cursor/16000,asr_lag_sec=0.,n3_input_samples=cursor)
        except Exception as exc:
            self._fail(f'N3 ASR lane failed: {exc}')
        finally:
            asr.close()
            if self._research_v2 and self._scheduler is not None:
                self._scheduler_advance('asr',float('inf'),self._research_asr_available_sec)


class N3Engine(StreamingASRLane, PrototypeEngine):
    pass


class N3IdentityEngine(StreamingASRLane, N2Engine):
    pass
