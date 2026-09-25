"""Capture the frozen D1 application lane. See README_D1_COMPONENTS.md."""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import threading
import time


class CausalJournal:
    """Forward delivery plus exact rereads of already delivered query support."""
    def __init__(self, samples):
        self.samples = samples
        self.committed_samples = len(samples)
        self.duration_sec = len(samples) / 16000
        self.finished = True
        self.delivered_samples = self.reads = self.query_reads = 0

    def read(self, cursor, size, *, wait_sec=None):
        if type(cursor) is not int or type(size) is not int or cursor < 0 or size <= 0:
            raise ValueError('Invalid journal coordinates')
        if wait_sec is not None:
            if wait_sec != 0 or cursor + size > self.delivered_samples:
                raise ValueError('Query support exceeds actual delivered audio')
            self.query_reads += 1
            return self.samples[cursor:cursor + size]
        if cursor != self.delivered_samples or size != 1600:
            raise ValueError('D1 must retain the application 100-ms forward reads')
        block = self.samples[cursor:cursor + size]
        self.delivered_samples += len(block)
        self.reads += bool(len(block))
        return block


class ModeledClock:
    """Serial source/compute clock; never an observed S7 or caption clock."""
    def __init__(self):
        self.ready = 0.

    def advance(self, source, elapsed):
        if not math.isfinite(source) or not math.isfinite(elapsed) or min(source, elapsed) < 0:
            raise ValueError('Invalid modeled clock input')
        self.ready = max(self.ready, source) + elapsed

    def relative(self):
        return self.ready


class _Diarizer:
    def __init__(self, capture, native):
        self.capture = capture
        self.native = native
        self.samples = self.finished = 0

    def manifest(self):
        return self.native.manifest()

    def push(self, block):
        if self.finished:
            raise ValueError('No native input after finish')
        self.samples += len(block)
        if self.samples != self.capture._journal.delivered_samples:
            raise ValueError('Native input differs from journal delivery')
        return self._call('push', self.native.push, block)

    def finish(self):
        self.finished += 1
        if self.finished != 1:
            raise ValueError('Native finish must be called exactly once')
        return self._call('finish', self.native.finish)

    def _call(self, kind, function, *args):
        start = time.perf_counter()
        update = function(*args)
        end = time.perf_counter()
        if abs(update.audio_received_sec - self.samples / 16000) > 1e-7:
            raise ValueError('Native received-source census differs')
        self.capture._s7_observed_clock.advance(self.samples / 16000, end - start)
        self.capture._emit('component_d1_dispatch', self.samples / 16000, dict(
            operation=kind, input_samples=self.samples, frame_start=update.frame_start,
            frame_end=update.frame_end, actual_started_elapsed_sec=start-self.capture.origin,
            actual_finished_elapsed_sec=end-self.capture.origin,
            modeled_available_at_sec=self.capture._s7_observed_clock.relative(),
            observed_live_latency_qualified=False))
        return update


class _Resident:
    def __init__(self, capture, resident):
        self.capture = capture
        self.resident = resident
        self.native = None

    def acquire_diarizer(self, session):
        if self.native is not None:
            raise ValueError('Only one native acquisition/reset per independent scene')
        self.native = _Diarizer(self.capture, self.resident.acquire_diarizer(session))
        return self.native


class MeasuredEmbedding:
    """Real encoder calls with exact query bytes, without changing their output."""
    def __init__(self, capture, models):
        self.capture = capture
        self.models = models
        self.namespace = models.namespace
        self.pending = []

    @property
    def last_embed_ms(self):
        return self.models.last_embed_ms

    def embed(self, waveform):
        start = time.perf_counter()
        vector = self.models.embed(waveform)
        end = time.perf_counter()
        self.capture._s7_observed_clock.advance(self.capture._journal.delivered_samples/16000, end-start)
        self.pending.append(dict(samples=len(waveform),
            waveform_sha256=hashlib.sha256(waveform.astype('<f4').tobytes()).hexdigest(),
            vector=vector.tolist(), actual_started_elapsed_sec=start-self.capture.origin,
            actual_finished_elapsed_sec=end-self.capture.origin))
        return vector


def capture_type(engine_type, timeline_type, name_map_type):
    """Use unchanged N2Engine._speaker_loop and _accept_activity, no Controller."""
    class Capture(engine_type):
        def __init__(self, wave, log, resident, session_id):
            import numpy as np
            if (wave.ndim != 1 or wave.dtype != np.float32 or not np.isfinite(wave).all()
                    or not 0 < len(wave) <= 120*16000):
                raise ValueError('Finite mono float32 independent scene of at most 120 seconds required')
            self.log = log
            self.origin = time.perf_counter()
            self._journal = self._identity_journal = CausalJournal(wave)
            self._session_dir = Path(session_id)
            self._state = 'RUNNING'
            self.error = None
            self.n2_diarization = 'D1'
            self._n2_lock = threading.RLock()
            self._n2_timeline = timeline_type()
            self._n2_names = {}
            self._n2_last_query = {}
            self._n2_embedding_serial = 0
            self._n2_name_history = {}
            self._n2_reported_runs = set()
            self._n2_admitted_runs = set()
            self._n2_short_run_count = 0
            self._n2_short_run_sec = 0.
            self._n2_reported_run_end = -1.
            self._s6d_presentation = None
            self.n2_name_map = name_map_type(None)
            # The actual lane expects this attribute; explicitly substitute a
            # modeled component clock. Raw native monotonic stamps stay intact.
            self._s7_observed_clock = ModeledClock()
            self.resident = _Resident(self, resident)
            self._telemetry = {}
            self.counts = Counter()
            self.vectors = []
            self.watermarks = []
            self.models = None

        def _fail(self, error):
            self.error = error
            self._state = 'FAILED'

        def _scheduler_advance(self, lane, source, available):
            if lane != 'speaker':
                raise ValueError('Unexpected ASR dependency')
            self.watermarks.append(dict(source=None if math.isinf(source) else source,
                closed=math.isinf(source), modeled_available_at_sec=available))

        def _emit(self, kind, source, payload):
            import numpy as np
            if sum(self.counts.values()) >= 100000:
                raise ValueError('Component event bound exceeded')
            if kind == 'research_embedding':
                if self.models is None or not self.models.pending:
                    raise ValueError('Embedding event has no actual model call')
                actual = self.models.pending.pop(0)
                first = round(payload['source_start_sec']*16000)
                last = round(payload['source_end_sec']*16000)
                wave = self._journal.samples[first:last]
                vector = np.asarray(payload['normalized_embedding'])
                if (not 0 <= first < last <= self._journal.delivered_samples
                        or last-first != actual['samples']
                        or hashlib.sha256(wave.astype('<f4').tobytes()).hexdigest() != actual['waveform_sha256']
                        or payload['normalized_embedding'] != actual['vector']
                        or vector.shape != (192,) or not np.isfinite(vector).all()
                        or abs(float(np.linalg.norm(vector))-1) > .001):
                    raise ValueError('Actual embedding vector or query slice differs')
                self.vectors.append(dict(start_sample=first, end_sample=last,
                    waveform_sha256=actual['waveform_sha256'], model_slot=payload['model_slot'],
                    tracker_id=payload['tracker_id'], normalized_embedding=actual['vector']))
                self._emit('component_d1_embedding_call', source,
                    {k:v for k,v in actual.items() if k != 'vector'})
            self.log.write(json.dumps(dict(event_type=kind, source_time_sec=source, payload=payload,
                component_clock='modeled_serial_source_plus_actual_compute_not_observed_S7'),
                ensure_ascii=False, separators=(',', ':'), allow_nan=False)+'\n')
            self.counts[kind] += 1

        def run_capture(self, models):
            self.models = MeasuredEmbedding(self, models)
            engine_type._speaker_loop(self, self.models)
            if self.error is not None:
                raise RuntimeError(self.error)
            native = self.resident.native
            if (native is None or native.finished != 1 or self.models.pending
                    or self._journal.delivered_samples != self._journal.committed_samples
                    or self._telemetry.get('identity_audio_samples') != self._journal.committed_samples
                    or self._n2_embedding_serial != len(self.vectors)
                    or self._journal.query_reads != len(self.vectors)
                    or len(self.watermarks) != self._journal.reads+1
                    or not self.watermarks[-1]['closed']):
                raise ValueError('D1 lane closure, source or embedding census failed')
            return dict(input_samples=self._journal.delivered_samples, source_reads=self._journal.reads,
                event_counts=dict(self.counts), native_frames=self._n2_timeline.next_frame,
                embeddings=len(self.vectors), vectors=self.vectors, telemetry=self._telemetry,
                modeled_completion_sec=self._s7_observed_clock.relative(),
                observed_live_latency_qualified=False, integrated_N4_cells=0)
    return Capture
