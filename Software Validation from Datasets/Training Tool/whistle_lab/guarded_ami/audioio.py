"""Explicit channel selection; original decoder handles unchanged mono inputs."""
import numpy as np
import soundfile as sf
import data
from common import audio_path

original_load = data.load_audio


def load_audio(row):
    channel = int(row.get("channel_index", 0))
    if channel == 0:
        return original_load(row)
    with sf.SoundFile(audio_path(row["audio_root_id"], row["audio_relative_path"])) as handle:
        if channel < 0 or channel >= handle.channels:
            raise ValueError("Manifest channel does not exist")
        rate = handle.samplerate
        start = round(float(row["start_sec"]) * rate)
        count = round((float(row["end_sec"]) - float(row["start_sec"])) * rate)
        if start < 0 or count < 1 or start + count > handle.frames + rate // 20:
            raise ValueError("Invalid expanded-channel segment bounds")
        handle.seek(start)
        samples = handle.read(count, dtype="float32", always_2d=True)[:, channel]
    if len(samples) < count - rate // 20 or not len(samples) or not np.isfinite(samples).all():
        raise ValueError("Incomplete or nonfinite expanded-channel audio")
    if rate != 16000:
        import soxr
        samples = soxr.resample(samples, rate, 16000, quality="HQ")
    return np.ascontiguousarray(samples, dtype=np.float32)


data.load_audio = load_audio
