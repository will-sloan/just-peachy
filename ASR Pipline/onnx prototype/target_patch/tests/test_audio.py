import numpy as np
import soundfile as sf

from app.onnx_pipeline.audio import load_audio_mono


def test_load_audio_mono_crops_and_resamples(tmp_path):
    path = tmp_path / "tone.wav"
    sr = 8000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    audio = 0.1 * np.sin(2 * np.pi * 440.0 * t).astype(np.float32)
    stereo = np.stack([audio, audio], axis=1)
    sf.write(path, stereo, sr)

    out, out_sr = load_audio_mono(path, target_sample_rate=16000, start_sec=0.25, end_sec=0.75)
    assert out_sr == 16000
    assert out.dtype == np.float32
    assert 7000 <= len(out) <= 9000
