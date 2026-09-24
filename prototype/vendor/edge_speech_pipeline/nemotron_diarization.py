"""Stateful standalone Nemotron 3 Q8 C-ABI adapter. See README_N2_NEMOTRON.md."""
from __future__ import annotations

import ctypes as C
from dataclasses import dataclass, asdict
import hashlib
import math
import os
from pathlib import Path
import threading
import time
import uuid

import numpy as np

MODEL_SHA256 = '08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1'
MODEL_REVISION = 'f667ed73aee57d40cc39428eb768b4fd87a0a29e'
RUNTIME_REVISION = '97a15afa5caa9bce5baaa86c1184103877af4101'
_RUNTIME_DIRECTORY_LOCK = threading.Lock()
_PROCESS_RUNTIME_DIRECTORY: Path | None = None


@dataclass(frozen=True)
class StreamingProfile:
    name: str
    chunk_frames: int
    right_context_frames: int
    left_context_frames: int = 0
    fifo_frames: int = 264
    spkcache_frames: int = 264
    update_period_frames: int = 222

    @property
    def input_buffer_sec(self) -> float:
        return (self.chunk_frames + self.right_context_frames) * 0.08

    @property
    def right_context_sec(self) -> float:
        return self.right_context_frames * 0.08


PROFILES = {p.name: p for p in (
    StreamingProfile('low_latency', 9, 4),
    StreamingProfile('very_low_latency', 6, 2),
    StreamingProfile('ultra_low_latency', 3, 1),
)}


@dataclass(frozen=True)
class DiarizationUpdate:
    session_id: str
    frame_start: int
    probabilities: np.ndarray
    seconds_per_frame: float
    audio_received_sec: float
    received_at_monotonic: float
    available_at_monotonic: float
    compute_sec: float
    is_final: bool
    track_ids: tuple[str, ...]
    capacity_status: str = 'EIGHT_SLOTS_OVERFLOW_UNDETECTABLE'

    @property
    def frame_end(self) -> int:
        return self.frame_start + len(self.probabilities)

    @property
    def emitted_audio_end_sec(self) -> float:
        return self.frame_end * self.seconds_per_frame

    def activity_spans(self, threshold: float = 0.5) -> list[dict]:
        """Contiguous raw activity spans, including simultaneous channels.

        This diagnostic threshold is not identity confidence or a calibrated
        speech operating point. No padded/morphological native segments are used.
        Spans retain the model frame clock; a centered-STFT endpoint frame may
        extend beyond the last real sample. Consumers must use actual support.
        """
        if not 0.0 < threshold < 1.0:
            raise ValueError('activity threshold must lie strictly between 0 and 1')
        active = self.probabilities >= threshold
        spans = []
        for slot in range(8):
            edges = np.diff(np.r_[False, active[:, slot], False].astype(np.int8))
            for first, last in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
                spans.append({'start_sec': (self.frame_start + int(first)) * self.seconds_per_frame,
                              'end_sec': (self.frame_start + int(last)) * self.seconds_per_frame,
                              'model_slot': slot, 'track_id': self.track_ids[slot],
                              'mean_activity_probability': float(self.probabilities[first:last, slot].mean()),
                              'available_at_monotonic': self.available_at_monotonic,
                              'audio_received_sec': self.audio_received_sec,
                              'contains_overlap': bool(np.any(active[first:last].sum(axis=1) > 1))})
        return sorted(spans, key=lambda s: (s['start_sec'], s['model_slot']))


class _ModelConfig(C.Structure):
    _fields_ = [('size', C.c_size_t), ('model_path', C.c_char_p), ('gpu', C.c_int32),
                ('preset', C.c_char_p), ('chunk_frames', C.c_int32),
                ('right_context_frames', C.c_int32), ('left_context_frames', C.c_int32),
                ('fifo_frames', C.c_int32), ('spkcache_frames', C.c_int32),
                ('update_period_frames', C.c_int32)]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class NemotronDiarizer:
    """One model and one persistent 16 kHz mono native stream; no ASR/TTS.

    Pushes are serialized. Never reset at VAD/ASR endpoints: reset explicitly
    only for an independent scene/session. Slots map to the same session track
    even after prolonged absence. More than eight physical speakers cannot be
    represented reliably or detected merely by counting output channels.
    """
    sample_rate = 16000
    num_speakers = 8

    def __init__(self, model_path: str | Path, library_path: str | Path, *,
                 profile: str = 'low_latency', session_id: str | None = None,
                 expected_library_sha256: str | None = None, gpu: int = -1):
        if profile not in PROFILES:
            raise ValueError(f'unsupported profile: {profile}')
        self.profile = PROFILES[profile]
        if isinstance(gpu, bool) or not isinstance(gpu, int) or gpu < -1:
            raise ValueError('gpu must be -1 for CPU or a nonnegative explicit device index')
        self.gpu = gpu
        self.model_path, self.library_path = Path(model_path).resolve(), Path(library_path).resolve()
        self.model_sha256 = _sha256(self.model_path)
        if self.model_sha256 != MODEL_SHA256:
            raise ValueError('D1 requires the exact pinned official Nemotron 3 Q8 artifact')
        self.library_sha256 = _sha256(self.library_path)
        if expected_library_sha256 and self.library_sha256 != expected_library_sha256:
            raise ValueError('native library hash mismatch')
        global _PROCESS_RUNTIME_DIRECTORY
        self._dll_directory = None
        with _RUNTIME_DIRECTORY_LOCK:
            if _PROCESS_RUNTIME_DIRECTORY is not None and self.library_path.parent != _PROCESS_RUNTIME_DIRECTORY:
                raise RuntimeError('This process already selected native runtime directory '
                                   f'{_PROCESS_RUNTIME_DIRECTORY}; use a fresh process for {self.library_path.parent}')
            # Retain the selection even after close or a loader failure: native
            # dependencies may remain loaded and share CPU/CUDA DLL basenames.
            _PROCESS_RUNTIME_DIRECTORY = self.library_path.parent
            try:
                self._dll_directory = os.add_dll_directory(str(self.library_path.parent)) if os.name == 'nt' else None
                self._api = C.CDLL(str(self.library_path))
                self._bind()
            except BaseException:
                if self._dll_directory is not None:
                    self._dll_directory.close()
                    self._dll_directory = None
                raise
        self._lock = threading.RLock()
        self._model = C.c_void_p()
        self._stream = C.c_void_p()
        self._finished = self._closed = self._failed = False
        config = _ModelConfig(C.sizeof(_ModelConfig), os.fsencode(self.model_path), self.gpu, b'v3-streaming',
                              self.profile.chunk_frames, self.profile.right_context_frames,
                              self.profile.left_context_frames, self.profile.fifo_frames,
                              self.profile.spkcache_frames, self.profile.update_period_frames)
        try:
            self._check(self._api.nemo_speech_diar_create(C.byref(config), C.byref(self._model)))
            speakers = self._api.nemo_speech_diar_num_speakers(self._model)
            self.seconds_per_frame = self._api.nemo_speech_diar_seconds_per_frame(self._model)
            if speakers != 8 or not math.isclose(self.seconds_per_frame, 0.01, abs_tol=1e-6):
                raise RuntimeError(f'expected Nemotron V3 8 channels/10 ms, received {speakers}/{self.seconds_per_frame}')
            self.reset(session_id=session_id)
        except BaseException:
            self.close()
            raise

    def _bind(self):
        p, pp = C.c_void_p, C.POINTER(C.c_void_p)
        signatures = {
            'nemo_speech_diar_create': ([C.POINTER(_ModelConfig), pp], C.c_int),
            'nemo_speech_diar_destroy': ([p], None),
            'nemo_speech_diar_num_speakers': ([p], C.c_int32),
            'nemo_speech_diar_seconds_per_frame': ([p], C.c_double),
            'nemo_speech_diar_stream_open': ([p, pp], C.c_int),
            'nemo_speech_diar_stream_push_f32': ([p, C.POINTER(C.c_float), C.c_size_t, C.c_int32], C.c_int),
            'nemo_speech_diar_stream_finish': ([p], C.c_int),
            'nemo_speech_diar_stream_close': ([p], None),
            'nemo_speech_diar_frame_count': ([p], C.c_int64),
            'nemo_speech_diar_frame_probs_start': ([p], C.c_int64),
            'nemo_speech_diar_frame_probs': ([p, C.POINTER(C.c_float), C.c_size_t], C.c_int),
            'nemo_speech_asr_last_error': ([], C.c_char_p),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self._api, name)
            function.argtypes, function.restype = arguments, result

    def _check(self, status):
        if status:
            self._failed = True
            error = self._api.nemo_speech_asr_last_error()
            raise RuntimeError(f'native diarization error {status}: {error.decode("utf-8", "replace")}')

    def _ensure_open(self):
        if self._closed:
            raise RuntimeError('diarizer has been closed')
        if self._failed:
            raise RuntimeError('native stream failed; reset required')

    def reset(self, *, session_id: str | None = None):
        """Discard this stream and create a new independent session on the resident model."""
        with self._lock:
            if self._closed:
                raise RuntimeError('diarizer has been closed')
            if self._stream:
                self._api.nemo_speech_diar_stream_close(self._stream)
            self._stream = C.c_void_p()
            self._failed = False
            self._check(self._api.nemo_speech_diar_stream_open(self._model, C.byref(self._stream)))
            self.session_id = str(session_id or uuid.uuid4())
            self.track_ids = tuple(f'{self.session_id}:nemotron-slot-{slot}' for slot in range(8))
            self._samples_received = self._frames_delivered = 0
            self._finished = False

    def _update(self, received_at: float, started: float, final: bool) -> DiarizationUpdate:
        count = self._api.nemo_speech_diar_frame_count(self._stream)
        base = self._api.nemo_speech_diar_frame_probs_start(self._stream)
        if count < self._frames_delivered or base > self._frames_delivered:
            self._failed = True
            raise RuntimeError('native frame timeline regressed or compacted undelivered frames')
        first = self._frames_delivered
        if count > first:
            retained = np.empty((count - base, 8), dtype=np.float32)
            self._check(self._api.nemo_speech_diar_frame_probs(
                self._stream, retained.ctypes.data_as(C.POINTER(C.c_float)), retained.size))
            values = retained[first - base:].copy()
            if not np.all(np.isfinite(values)) or np.any(values < 0) or np.any(values > 1):
                self._failed = True
                raise RuntimeError('native probabilities are non-finite or outside [0,1]')
        else:
            values = np.empty((0, 8), dtype=np.float32)
        self._frames_delivered = count
        values.setflags(write=False)
        completed = time.perf_counter()
        return DiarizationUpdate(self.session_id, first, values, self.seconds_per_frame,
                                 self._samples_received / self.sample_rate, received_at,
                                 completed, completed-started, final, self.track_ids)

    def push(self, samples: np.ndarray, *, received_at_monotonic: float | None = None) -> DiarizationUpdate:
        audio = np.asarray(samples, dtype=np.float32)
        if audio.ndim != 1 or not np.all(np.isfinite(audio)):
            raise ValueError('audio must be finite one-dimensional mono float32 at 16000 Hz')
        audio = np.ascontiguousarray(audio)
        with self._lock:
            self._ensure_open()
            if self._finished:
                raise RuntimeError('cannot push after finish; reset only for a new scene/session')
            started = time.perf_counter()
            received = started if received_at_monotonic is None else float(received_at_monotonic)
            if not math.isfinite(received) or received > started + 0.001:
                raise ValueError('received time must be finite and no later than current monotonic clock')
            if len(audio):
                self._check(self._api.nemo_speech_diar_stream_push_f32(
                    self._stream, audio.ctypes.data_as(C.POINTER(C.c_float)), audio.size, self.sample_rate))
                self._samples_received += audio.size
            return self._update(received, started, False)

    def finish(self) -> DiarizationUpdate:
        with self._lock:
            self._ensure_open()
            started = time.perf_counter()
            if not self._finished:
                self._check(self._api.nemo_speech_diar_stream_finish(self._stream))
                self._finished = True
            return self._update(started, started, True)

    def manifest(self) -> dict:
        return {'model_id': 'nvidia/Nemotron-3-Diarization', 'model_revision': MODEL_REVISION,
                'model_sha256': self.model_sha256, 'precision': 'official-Q8_0',
                'library_path': str(self.library_path), 'library_sha256': self.library_sha256,
                'runtime_revision': RUNTIME_REVISION, 'profile': asdict(self.profile),
                'input_buffer_sec': self.profile.input_buffer_sec,
                'right_context_sec': self.profile.right_context_sec,
                'feature_fft_right_extent_sec': 256 / 16000,
                'first_complete_chunk_min_audio_sec': (8 * (self.profile.chunk_frames + self.profile.right_context_frames) - 1) * 0.01 + 256 / 16000,
                'sample_rate_hz': self.sample_rate, 'num_speakers': 8, 'mel_features': 128,
                'encoder_subsampling': 8, 'native_output_sec_per_frame': self.seconds_per_frame,
                'session_reset': 'independent_scene_or_session_only', 'slot_recycling': False,
                'overflow_behavior': 'more than eight physical speakers unresolved; overflow is not detectable from eight probabilities alone',
                'identity_confidence': False, 'gain': 1.0, 'standalone': True,
                'gpu': self.gpu >= 0, 'gpu_device_index': self.gpu if self.gpu >= 0 else None}

    def close(self):
        with self._lock:
            if self._closed:
                return
            if self._stream:
                self._api.nemo_speech_diar_stream_close(self._stream)
                self._stream = C.c_void_p()
            if self._model:
                self._api.nemo_speech_diar_destroy(self._model)
                self._model = C.c_void_p()
            self._closed = True
            if self._dll_directory:
                self._dll_directory.close()
                self._dll_directory = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
