"""Unintegrated bounded event and PCM sinks; README_BOUNDED_LIVE_ARTIFACTS_V1.md."""
import copy
import json
import os
import threading
import time
import wave
from collections import OrderedDict
from field_artifact_limits_v1 import resolved


class OutputLimit(RuntimeError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':'), sort_keys=True).encode('utf-8')


def changes(old, new, path=(), ops=None):
    """Bounded recursive replacements/deletions; lists retain original ordering."""
    if ops is None:
        ops = []
    if len(path) > 24 or len(ops) > 4096:
        raise OutputLimit('PATCH_COMPLEXITY')
    if type(old) is not type(new):
        ops.append(['set', list(path), new])
    elif isinstance(new, dict):
        for key in sorted(old.keys() - new.keys()):
            ops.append(['del', list(path) + [key]])
        for key in sorted(new):
            if key not in old:
                ops.append(['set', list(path) + [key], new[key]])
            else:
                changes(old[key], new[key], path + (key,), ops)
    elif isinstance(new, list):
        for i in range(min(len(old), len(new))):
            changes(old[i], new[i], path + (i,), ops)
        if len(new) < len(old):
            ops.append(['truncate', list(path), len(new)])
        elif len(new) > len(old):
            ops.append(['append', list(path), new[len(old):]])
    elif old != new:
        ops.append(['set', list(path), new])
    return ops


class CompactJournal:
    """Owned consumer-thread writer, never for the audio callback. No silent drop."""
    reserve = 512

    def __init__(self, path, byte_limit, record_limit=1024**2, *, artifact_limits=None):
        limits = resolved(artifact_limits)
        ceiling = max(limits["native_journal_bytes"], limits["conversation_journal_bytes"])
        if type(byte_limit) is not int or not 1024 <= byte_limit <= ceiling:
            raise ValueError('Journal byte limit outside tested design envelope')
        if type(record_limit) is not int or not 128 <= record_limit <= 1024**2:
            raise ValueError('Record bound invalid')
        self.limit = byte_limit
        self.record_limit = record_limit
        self.owner = threading.get_ident()
        self.file = open(path, 'xb', buffering=0)
        self.states = OrderedDict()
        self.count = self.bytes = self.full = self.patches = 0
        self.serialization_ns = self.write_ns = 0
        self.closed = False
        self.status = 'OPEN'

    def _check(self):
        if threading.get_ident() != self.owner or self.closed:
            raise RuntimeError('Closed journal or wrong owning thread')

    def _write(self, data):
        begin = time.perf_counter_ns()
        view = memoryview(data)
        while view:
            n = self.file.write(view)
            if not n:
                raise OSError('Incomplete journal write')
            self.bytes += n
            view = view[n:]
        self.write_ns += time.perf_counter_ns() - begin

    def append(self, event):
        self._check()
        if not isinstance(event, dict):
            raise ValueError('Event must be an object')
        begin = time.perf_counter_ns()
        kind = event.get('event_type', event.get('kind'))
        payload = event.get('payload')
        key = None
        if kind == 's6d_display' and isinstance(payload, dict):
            key = (kind, payload.get('session_id'))
            if not isinstance(key[1], str):
                raise ValueError('Display session ID required')
        literal = dict(format='event', seq=self.count, value=event)
        data = encoded(literal) + b'\n'
        literal_size = len(data)
        is_patch = False
        if key in self.states:
            previous_seq, previous = self.states[key]
            try:
                ops = changes(previous, payload)
                compact = dict(format='patch', seq=self.count, base_seq=previous_seq,
                               key=list(key), meta={k:v for k,v in event.items() if k != 'payload'}, ops=ops)
                candidate = encoded(compact) + b'\n'
                if len(candidate) < len(data):
                    data = candidate
                    is_patch = True
            except OutputLimit:
                pass  # Explicit whole-event fallback, still byte bounded.
        self.serialization_ns += time.perf_counter_ns() - begin
        reason = 'RECORD_LIMIT' if max(literal_size, len(data)) > self.record_limit else 'BYTE_LIMIT'
        if max(literal_size, len(data)) > self.record_limit or self.bytes + len(data) + self.reserve > self.limit:
            self.close(reason)
            raise OutputLimit(reason)
        self._write(data)
        if key is not None:
            self.states[key] = (self.count, copy.deepcopy(payload))
            self.states.move_to_end(key)
            while len(self.states) > 2:
                self.states.popitem(last=False)
        self.count += 1
        self.patches += int(is_patch)
        self.full += int(not is_patch)

    def close(self, status='COMPLETE'):
        self._check()
        if status not in ('COMPLETE', 'BYTE_LIMIT', 'RECORD_LIMIT', 'SOURCE_FAILURE'):
            raise ValueError('Unknown terminal reason')
        footer = encoded(dict(format='footer', count=self.count, status=status)) + b'\n'
        assert len(footer) <= self.reserve and self.bytes + len(footer) <= self.limit
        self._write(footer)
        self.file.flush()
        os.fsync(self.file.fileno())
        self.file.close()
        self.closed = True
        self.status = status
        self.states.clear()

    def metrics(self):
        return dict(events=self.count, bytes=self.bytes, full_records=self.full,
                    patch_records=self.patches, serialization_ns=self.serialization_ns,
                    write_ns=self.write_ns, status=self.status, closed=self.closed,
                    retained_states=len(self.states), byte_limit=self.limit)


class PCM16Writer:
    """Little-endian mono16k PCM with exact source offsets and finalized WAV header."""
    def __init__(self, path, max_frames, *, artifact_limits=None):
        limits = resolved(artifact_limits)
        if type(max_frames) is not int or not 0 < max_frames <= limits["pcm_max_frames"]:
            raise ValueError("PCM frame bound exceeds explicit artifact contract")
        self.owner = threading.get_ident()
        self.max_frames = max_frames
        self.frames = self.clipped = 0
        self.closed = False
        self.status = 'OPEN'
        self.file = open(path, 'xb')
        self.wav = wave.open(self.file, 'wb')
        self.wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        self.wav.writeframesraw(b'')  # Header exists even if no frame is accepted.

    def write_pcm(self, data, *, source_start_frame):
        if self.closed or threading.get_ident() != self.owner:
            raise RuntimeError('Closed PCM or wrong owning thread')
        if type(source_start_frame) is not int or source_start_frame != self.frames:
            raise ValueError('Discontinuous PCM source')
        if not isinstance(data, bytes) or len(data) % 2 or len(data) > 65536:
            raise ValueError('Require complete little-endian PCM16 samples')
        n = len(data)//2
        if self.frames+n > self.max_frames:
            self.close('FRAME_LIMIT')
            raise OutputLimit('FRAME_LIMIT')
        self.wav.writeframesraw(data)
        self.frames += n

    def write_float32(self, samples, *, source_start_frame):
        import numpy as np
        x = np.asarray(samples)
        if x.dtype != np.float32 or x.ndim != 1 or len(x)>32768 or not np.isfinite(x).all():
            raise ValueError('Finite mono float32 <=32768samples required')
        clipped = int(np.count_nonzero((x < -1) | (x > 32767/32768)))
        data = np.rint(np.clip(x, -1, 32767/32768)*32768).astype('<i2').tobytes()
        self.write_pcm(data, source_start_frame=source_start_frame)
        self.clipped += clipped

    def close(self, status='COMPLETE'):
        if self.closed or threading.get_ident() != self.owner:
            raise RuntimeError('Closed PCM or wrong owning thread')
        if status not in ('COMPLETE','FRAME_LIMIT','SOURCE_FAILURE'):
            raise ValueError('Unknown terminal reason')
        self.wav.close()
        self.file.flush()
        os.fsync(self.file.fileno())
        self.file.close()
        self.closed = True
        self.status = status

    def metrics(self):
        return dict(frames=self.frames, max_frames=self.max_frames, status=self.status,
                    closed=self.closed, clipped_samples=self.clipped,
                    expected_file_bytes=44+2*self.frames, max_file_bytes=44+2*self.max_frames)
