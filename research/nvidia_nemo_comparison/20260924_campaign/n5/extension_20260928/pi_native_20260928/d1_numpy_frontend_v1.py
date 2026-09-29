"""Pinned D1 FP32 frontend candidate. See README_D1_NUMPY_FRONTEND_V1.md."""
import numpy as np


class Frontend:
    """One 16 kHz mono stream; centered 512 FFT, 160 hop, exact bound buffers."""
    def __init__(self, coefficients):
        with np.load(coefficients, allow_pickle=False) as c:
            window = c['window'].copy()
            self.filters = c['filterbank'][0].copy()
        assert window.shape == (400,) and self.filters.shape == (128, 257)
        assert window.dtype == self.filters.dtype == np.float32
        self.window = np.pad(window, (56, 56))
        self.reset()

    def reset(self):
        self.buffer = np.empty(0, np.float32)
        self.base = self.total = self.next_frame = 0
        self.previous = np.float32(0)
        self.closed = False
        self.maximum_buffer_samples = 0

    def _features(self, frames):
        # NeMo explicitly sqrt(power) then raises magnitude to power 2.
        spectrum = np.fft.rfft(frames*self.window, n=512, axis=-1).astype(np.complex64)
        magnitude = np.sqrt(spectrum.real**2 + spectrum.imag**2)
        power = magnitude**2
        mel = self.filters @ power.T
        return np.log(mel + np.float32(2**-24)).T.astype(np.float32)

    def _emit(self, finish=False):
        valid = self.total//160
        end = valid if finish else min(valid, max(0, (self.total-256)//160+1))
        if end <= self.next_frame:
            return np.empty((0, 128), np.float32)
        centers = np.arange(self.next_frame, end, dtype=np.int64)*160
        positions = centers[:, None] + np.arange(-256, 256, dtype=np.int64)
        frames = np.zeros(positions.shape, np.float32)
        mask = (positions >= 0) & (positions < self.total)
        assert not np.any(mask & (positions < self.base)), 'Retired input needed by FFT'
        frames[mask] = self.buffer[(positions[mask]-self.base)]
        result = self._features(frames)
        self.next_frame = end
        keep = max(0, min(self.total, self.next_frame*160-256))
        self.buffer = self.buffer[keep-self.base:].copy()
        self.base = keep
        assert self.buffer.size <= 512, 'Persistent frontend buffer exceeded'
        return result

    def push(self, audio):
        if self.closed:
            raise RuntimeError('Frontend already finished')
        x = np.asarray(audio)
        if x.ndim != 1 or x.dtype != np.float32 or x.size > 32768 or not np.isfinite(x).all():
            raise ValueError('Need finite float32 mono, at most32768 samples per push')
        if not x.size:
            return np.empty((0, 128), np.float32)
        emphasized = np.empty_like(x)
        emphasized[0] = x[0] if self.total == 0 else x[0]-np.float32(.97)*self.previous
        emphasized[1:] = x[1:]-np.float32(.97)*x[:-1]
        self.previous = x[-1]
        self.buffer = np.concatenate((self.buffer, emphasized))
        self.total += x.size
        self.maximum_buffer_samples = max(self.maximum_buffer_samples, self.buffer.size)
        assert self.buffer.size <= 32768+512
        return self._emit()

    def finish(self):
        if self.closed:
            raise RuntimeError('Frontend already finished')
        result = self._emit(finish=True)
        self.closed = True
        self.buffer = np.empty(0, np.float32)
        self.base = self.total
        return result

    def process(self, audio, sizes=(3200,)):
        """Fresh stream, valid frames only; NeMo's masked padding is separate."""
        self.reset()
        rows = []
        offset = 0
        index = 0
        while offset < len(audio):
            size = sizes[index % len(sizes)]
            if not 0 < size <= 32768:
                raise ValueError('Invalid push size')
            rows.append(self.push(audio[offset:offset+size]))
            offset += size
            index += 1
        rows.append(self.finish())
        return np.concatenate(rows, axis=0)

    @staticmethod
    def padded(valid, sample_count):
        """Match batch NeMo [1,128,T], including masked extra STFT/pad-to16."""
        width = ((sample_count//160+1+15)//16)*16
        result = np.zeros((1, 128, width), np.float32)
        assert len(valid) == sample_count//160
        result[0, :, :len(valid)] = valid.T
        return result
