# Supported backend combinations

> Current October3 update: **v28, desktop-first startup**. Use the ten desktop
> shortcuts; choose **Exit to desktop** in the main manager to close normally.
> Four recording slots remain. See [DESKTOP_GUIDE.md](DESKTOP_GUIDE.md) and
> DESKTOP_RELEASE_INDEX.json. Earlier v27 measurements below remain historical.

The authoritative executable profile table and commands are in [MODE_GUIDE.md](MODE_GUIDE.md). All ten profiles use Sherpa ONNX ASR/PnC and the same versioned frontend.

Six microphone choices: Pyannote with ReDimNet, TitaNet or anonymous ReDimNet continuity; Nemotron-3 Delayed with ReDimNet, TitaNet or native anonymous slots. Four saved-input choices: Nemotron-3 Streaming or Chunk52, each with ReDimNet or TitaNet. Saved inputs are mono16kHz PCM16 WAV. Streaming is limited to30s; microphone/Chunk52 to120s.

NeMo TitaNet was restored at the user's request using its existing ONNX model/frontend and separate gallery. Seven real saved-speech embedding calls succeeded in candidate14. ReDimNet remains selectable; no claim is made that either encoder will outperform the other in the user's environment.

Live Streaming/Chunk52, applied ASR skipping, parallel diarizer pools, whole-waveform ONNX and the unqualified A76 Nemotron ASR alternative remain unavailable. Nemotron ASR is deferred; the user selected Sherpa. The34-method research catalogue and uncompleted full240-cell N4 comparison remain provenance, not extra enabled profiles.

The current ten named shortcuts share duplicate-owner exclusion and capture-off startup. Raw+processed uses qualified four-microphone16kHz PCM32 plus model-input audio where the microphone route offers it. Processed saved-WAV input is not relabelled as raw microphone evidence.

Mounted motion is shared across all ten profile pins in v27. Existing live spatial
consumers receive trusted rotation-aware cues; voice-only/native anonymous rules
are unchanged, and current pose is excluded from plain saved WAVs. MOTION_GUIDE
describes geometry, efficient sampling and limits. Three recording slots remain.
