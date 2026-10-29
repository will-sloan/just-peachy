"""Full-coverage buckets and on-demand audio; never truncate or silently skip rows."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import math
import re
import numpy as np
from common import CONFIG, audio_path

SECONDS = (5, 10, 20, 30, 60, 90, 150)


def clean_text(raw, dataset, legacy_text):
    if not str(legacy_text or "").strip():
        return ""
    text = str(raw or "")
    if dataset == "common_voice":
        text = text.splitlines()[0].split("\t", 1)[0]
    text = re.sub(r"\[[^\]]*\]|<[^>]*>", " ", text)
    text = text.replace("_", " ").replace("’", "'")
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    return " ".join(text.split())


def capacities(seconds, tokens):
    # Allow for rounding during sample-rate conversion by choosing the next
    # bucket at an exact edge, never by admitting an oversized clip.
    duration = next((s for s in SECONDS if seconds + 2 / 16000 <= s), None)
    if duration is None:
        raise ValueError(f"Audio is longer than supported audited buckets: {seconds}")
    target = max(32, 2 ** math.ceil(math.log2(max(1, tokens - 1))))
    if target > 1024:
        raise ValueError(f"Transcript needs {tokens} tokens; refusing to truncate")
    return duration, target


def plan_batches(frame, epoch, config=CONFIG):
    rng = np.random.default_rng(config["seed"] + epoch)
    batches = []
    groups = frame.groupby(["audio_capacity", "token_capacity"], sort=True).indices
    for (seconds, tokens), indices in groups.items():
        size = max(1, min(config["max_batch_size"], config["batch_audio_seconds"] // int(seconds), config["batch_tokens"] // int(tokens)))
        shuffled = rng.permutation(indices)
        for start in range(0, len(shuffled), size):
            # The final batch is padded with zero loss weight, never dropped.
            batches.append((shuffled[start:start + size], int(seconds), int(tokens), size))
    rng.shuffle(batches)
    return batches


def load_audio(row):
    import soundfile as sf
    import soxr
    path = audio_path(row["audio_root_id"], row["audio_relative_path"])
    with sf.SoundFile(path) as handle:
        rate = handle.samplerate
        start = round(float(row["start_sec"]) * rate)
        count = round((float(row["end_sec"]) - float(row["start_sec"])) * rate)
        if start < 0 or count < 1 or start + count > handle.frames + rate // 20:
            raise ValueError(f"Invalid segment bounds for {row['source_registry_row_id']}: {path}")
        # A whole-file MP3's frame count can be a duration estimate. Decode its
        # complete payload and use the returned length; applying a segment-length
        # check to that estimate rejected valid Common Voice recordings.
        whole_mp3 = handle.format == "MP3" and start == 0 and abs(count - handle.frames) <= 1
        handle.seek(start)
        # First physical channel matches the previous framework manifest loader.
        samples = handle.read(-1 if whole_mp3 else count, dtype="float32", always_2d=True)[:, 0]
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError(f"Empty/nonfinite audio: {path}")
    if not whole_mp3 and len(samples) < count - rate // 20:
        raise ValueError(f"Incomplete segment audio: {path}; decoded {len(samples)} of {count} frames")
    if rate != 16000:
        samples = soxr.resample(samples, rate, 16000, quality="HQ")
    return np.ascontiguousarray(samples, dtype=np.float32)


class BatchLoader:
    def __init__(self, frame, workers=6):
        self.frame = frame
        self.pool = ThreadPoolExecutor(max_workers=workers)

    def batch(self, item):
        indices, seconds, token_capacity, size = item
        rows = self.frame.iloc[indices].to_dict("records")
        samples = list(self.pool.map(load_audio, rows))
        wav = np.zeros((size, seconds * 16000), np.float32)
        lengths = np.ones(size, np.int32) * 1600
        tokens = np.zeros((size, token_capacity + 1), np.int32)
        weights = np.zeros(size, np.float32)
        for i, (row, sample) in enumerate(zip(rows, samples)):
            if len(sample) > wav.shape[1] or len(row["tokens"]) > tokens.shape[1]:
                raise ValueError(f"Bucket would truncate {row['source_registry_row_id']}: audio {len(sample)}/{wav.shape[1]} samples; tokens {len(row['tokens'])}/{tokens.shape[1]}")
            wav[i, :len(sample)] = sample
            lengths[i] = max(len(sample), 1)
            tokens[i, :len(row["tokens"])] = row["tokens"]
            weights[i] = float(row.get("sample_weight", 1.0))
        return wav, lengths, tokens, weights

    def close(self):
        self.pool.shutdown(wait=True)
