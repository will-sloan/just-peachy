from pathlib import Path
from app.inference_pipeline.audio_io import load_audio
from app.inference_pipeline.vad.silero_vad import SileroVAD

audio_path = Path("newyork_yapping.wav")
    
record = {
    "recording_id": "manual-test",
    "utt_id": "manual-test-utt",
    "inference_audio_path": str(audio_path),
}

audio = load_audio(record)
vad = SileroVAD({
    "threshold": 0.5,
    "min_speech_ms": 250,
    "min_silence_ms": 100,
    "pad_ms": 30,
    "sample_rate": 16000,
})

regions = vad.detect(audio)

print(f"Audio duration: {audio.duration_sec:.2f}s")
print(f"Detected regions: {len(regions)}")
for region in regions:
    print({
        "start_sec": round(region.start_sec, 3),
        "end_sec": round(region.end_sec, 3),
        "confidence": region.confidence,
        "label": region.label,
    })
