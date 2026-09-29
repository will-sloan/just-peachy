"""Single ordered D1 state candidate; README_D1_NUMPY_STATE_V1.md.

Algorithm follows NVIDIA NeMo SortformerModules (Apache-2.0); pinned source
and limitations are recorded in the README. No installed source is modified.
"""
import math
import numpy as np


class AmbiguousSelection(RuntimeError):
    pass


def selected(scores, count):
    """No silent replacement of PyTorch's unspecified finite top-k tie order."""
    if count == 0:
        return np.empty(0, np.int64)
    assert 0 < count <= scores.size
    indices = np.argpartition(scores, scores.size-count)[-count:]
    threshold = scores[indices].min()
    if np.isfinite(threshold):
        equal = np.count_nonzero(scores == threshold)
        available = count - np.count_nonzero(scores > threshold)
        if equal > available:
            raise AmbiguousSelection('Finite score tie crosses top-k boundary')
    return indices


class State:
    def __init__(self, silence_embedding, fifo_capacity=0, refresh=188):
        x = np.asarray(silence_embedding)
        if x.dtype != np.float32 or x.shape != (512,) or not np.isfinite(x).all():
            raise ValueError('Need bound finite float32 silence embedding[512]')
        if fifo_capacity not in (0, 80) or refresh not in (40, 188):
            raise ValueError('Unprepared state geometry')
        self.silence = x.copy()
        self.capacity = fifo_capacity
        self.refresh = refresh
        self.reset()

    def reset(self):
        self.cache = np.empty((0, 512), np.float32)
        self.cache_probs = np.empty((0, 8), np.float32)
        self.fifo = np.empty((0, 512), np.float32)
        self.fifo_probs = np.empty((0, 8), np.float32)
        self.compressed = False
        self.offset = 0
        self.closed = False

    def _compress(self, embeddings, probabilities):
        p = probabilities
        logp = np.log(np.maximum(p, np.float32(.25)))
        log1p = np.log(np.maximum(np.float32(1)-p, np.float32(.25)))
        scores = logp-log1p+log1p.sum(axis=1, keepdims=True)-np.float32(math.log(.5))
        scores[p <= .5] = -np.inf
        positive = scores > 0
        scores[(~positive) & (p > .5) & (positive.sum(axis=0)[None, :] >= 16)] = -np.inf
        scores[264:] += np.float32(.05)
        for count, scale in ((24, 2), (48, 1)):
            for speaker in range(8):
                chosen = selected(scores[:, speaker], count)
                scores[chosen, speaker] -= np.float32(scale*math.log(.5))
        # One learned-silence slot per speaker in the pinned model config.
        scores = np.concatenate((scores, np.full((1, 8), np.inf, np.float32)))
        flattened = scores.T.reshape(-1)
        indices = selected(flattened, 264)
        indices = np.where(flattened[indices] != -np.inf, indices, 99999)
        indices.sort()
        disabled = indices == 99999
        indices %= len(scores)
        disabled |= indices >= len(embeddings)
        indices[disabled] = 0
        cache = embeddings[indices].copy()
        preds = p[indices].copy()
        cache[disabled] = self.silence
        preds[disabled] = 0
        return cache, preds

    def update(self, chunk, probabilities, *, offset, left=0, right=0):
        if self.closed:
            raise RuntimeError('State already finished')
        if type(offset) is not int or offset != self.offset:
            raise ValueError('Noncontiguous coarse source interval')
        if type(left) is not int or type(right) is not int or not 0 <= left <= 1 or not 0 <= right <= 1:
            raise ValueError('Unsupported context offsets')
        x = np.asarray(chunk);p = np.asarray(probabilities)
        count = len(x)-left-right
        if x.dtype != np.float32 or x.ndim != 2 or x.shape[1:] != (512,) or not 0 <= count <= 264:
            raise ValueError('Invalid chunk')
        expected = (len(self.cache)+len(self.fifo)+len(x), 8)
        if p.dtype != np.float32 or p.shape != expected or not np.isfinite(x).all() or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
            raise ValueError('Invalid combined state probabilities')
        cache_len = len(self.cache);fifo_len = len(self.fifo)
        current = p[cache_len+fifo_len+left:cache_len+fifo_len+left+count].copy()
        fifo = np.concatenate((self.fifo, x[left:left+count]))
        fifo_p = np.concatenate((p[cache_len:cache_len+fifo_len], current))
        cache = self.cache;cache_p = self.cache_probs;compressed = self.compressed
        if len(fifo) > self.capacity:
            pop = min(len(fifo), max(self.refresh, len(fifo)-self.capacity))
            cache = np.concatenate((cache, fifo[:pop]))
            prior = cache_p if compressed else p[:cache_len]
            cache_p = np.concatenate((prior, fifo_p[:pop]))
            fifo = fifo[pop:].copy();fifo_p = fifo_p[pop:].copy()
            if len(cache) > 264:
                cache, cache_p = self._compress(cache, cache_p)
                compressed = True
        assert len(cache) <= 264 and len(fifo) <= self.capacity
        # Commit atomically after validation/compression; a tie/error leaves state unchanged.
        self.cache, self.cache_probs = cache, cache_p
        self.fifo, self.fifo_probs = fifo, fifo_p
        self.compressed = compressed
        self.offset += count
        return current

    def finish(self):
        if self.closed:
            raise RuntimeError('State already finished')
        self.closed = True
        # There are no unprocessed embeddings here: the waveform/model driver owns EOF flush.
        return self.offset
