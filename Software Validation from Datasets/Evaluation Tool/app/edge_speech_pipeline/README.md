# Clean Edge Speech Pipeline

## Purpose

This is a new, isolated Windows-first demonstration pipeline using:

- Sherpa ONNX LibriSpeech + GigaSpeech Zipformer for stateful streaming English ASR;
- Sherpa's Edge-Punct-Casing CNN-BiLSTM INT8 ONNX model for final-utterance casing, periods, and question marks;
- Pyannote Segmentation 3.0 exported to ONNX for speech/overlap segmentation;
- ReDimNet2-B2 exported to ONNX for anonymous clustering and enrolled identity matching;
- the frozen H2 open-set score, margin, evidence, and clustering policy from the completed development analysis.

It does not modify or reinterpret frozen evaluation results. The GUI contains no model logic; it consumes events from the same backend used by the CLI.

## Why audio does not use `drop_oldest`

The microphone callback only copies frames into a two-minute raw reserve. A fast normalization thread writes every accepted 16 kHz sample to one append-only PCM16 session journal. ASR and speaker inference have independent file cursors, so one lane can lag without blocking capture or the other lane. No old frame is discarded to make room.

If PortAudio reports a real device overflow, or the raw reserve is exhausted, the session records an explicit fatal event and stops. The research view shows `Audio dropped`, capture faults, ASR lag, and speaker lag. User-requested pause audio is explicitly marked as intentionally excluded.

The spool uses about 115 MB per hour and is also the reproducible session audio. It is never uploaded.

## Inputs and outputs

Inputs:

- one Windows microphone selected in the GUI or by device number;
- one WAV/FLAC file for real-time or accelerated simulation;
- one or more speaker-labelled WAV files, or an unlimited start/stop microphone enrollment.

Every session is written below:

`Software Validation from Datasets/Evaluation Tool/edge_speech_sessions/`

Each session contains:

- `audio_spool.pcm16`: mono 16 kHz source-clock audio;
- `events.jsonl`: complete transcript, segmentation, identity, timing, error, and XVF-placeholder events;
- `labelled_transcript.jsonl`: final labelled utterances;
- `transcript.md`: readable final transcript;
- `session_summary.json`: asset hashes, policy, no-drop telemetry, and status.

Local profiles are stored below `edge_speech_profiles/` as a JSON metadata file and a safe NumPy vector file. They include the exact ReDimNet graph hash and are never uploaded.

## One-time Windows setup

### Anaconda Prompt

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
powershell -ExecutionPolicy Bypass -File ".\scripts\setup_edge_speech_pipeline.ps1"
```

The setup creates `.edge-speech-env` at the repository root and installs only the Windows runtime dependencies. It does not download model weights.

### Ordinary PowerShell

Run the same command from PowerShell:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
.\scripts\setup_edge_speech_pipeline.ps1
```

## Launch the GUI

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
.\scripts\run_edge_speech_pipeline.ps1 gui
```

In **Live microphone**, choose the device, press **Start live**, speak, then press **Stop**. In **WAV simulation**, choose audio and select 1.0× or accelerated mode. In **Speaker enrollment**, enter a name, press **Start recording**, speak for as long as needed, and press **Stop and create profile**. There is no fixed enrollment-duration limit. You can also import WAV samples. Poor duration, level, clipping, and within-enrollment consistency are reported.

Both transcription and enrollment have their own activity panel. An animated loading bar appears while the microphone/models initialize or while a profile is being built. The timer begins only after the corresponding audio source is actually active. Enrollment is streamed directly to a PCM16 WAV rather than retained in RAM, so long recordings remain memory-bounded. At the preferred 16 kHz rate, enrollment audio uses approximately 115 MB per hour.

The raw Sherpa hypothesis remains preserved. Partial text receives display-only casing but no guessed punctuation. At each confirmed ASR endpoint, the 7.1 MB INT8 ONNX punctuation model adds learned casing and punctuation. When the online model leaves a short final utterance without terminal punctuation, a bounded English question-starter check chooses `?`; all other such utterances receive `.`. This replaces the old unconditional-period formatter while keeping short endpoint output readable. During detected simultaneous speech, the GUI explicitly warns that attribution is uncertain and the event log records `overlap_detected=true`; it does not fabricate a two-person word split.

Final JSONL records contain both raw `text` and learned `display_text`, plus the punctuation model ID, SHA-256, compute time, status, and any fallback error. Punctuation runs once per final utterance on one CPU thread; it never runs in the microphone callback or delays audio capture.

The first launch spends a few seconds validating hashes and loading models. This happens before capture starts, so startup cannot lose microphone audio.

## Direct command-line use

List devices:

```powershell
.\scripts\run_edge_speech_pipeline.ps1 devices
```

Live microphone (replace `31` with the displayed device number):

```powershell
.\scripts\run_edge_speech_pipeline.ps1 live --device 31
```

WAV in real time:

```powershell
.\scripts\run_edge_speech_pipeline.ps1 file "C:\audio\sample.wav"
```

Accelerated WAV engineering run:

```powershell
.\scripts\run_edge_speech_pipeline.ps1 file "C:\audio\sample.wav" --accelerated
```

WAV enrollment:

```powershell
.\scripts\run_edge_speech_pipeline.ps1 enroll-wav "Amir" "C:\audio\amir_1.wav" "C:\audio\amir_2.wav"
```

Bounded microphone enrollment from the CLI (the GUI provides unlimited manual start/stop recording):

```powershell
.\scripts\run_edge_speech_pipeline.ps1 enroll-mic "Amir" --device 31 --seconds 6
```

Validate every model checksum:

```powershell
.\scripts\run_edge_speech_pipeline.ps1 validate
```

## Raspberry Pi export

The ASR assets are already ONNX. The segmentation and embedding assets reuse checksum-validated FP32 ONNX exports that passed the prior bounded Windows native-versus-ONNX parity checks. Exporting therefore stages exact assets rather than re-converting or downloading them:

```powershell
.\scripts\run_edge_speech_pipeline.ps1 export-pi ".\JustPeachyResearchSummaries\edge_speech_pi_bundle_v1"
```

The export contains all eight runtime model/token files, including the punctuation ONNX graph and vocabulary, this runtime source, the Apache-2.0 license/provenance records, an ARM64 requirements file, and `bundle_manifest.json`. Hard links are used on C: when supported, avoiding duplicate storage. Copying the bundle elsewhere materializes normal files.

This export is **not yet Raspberry Pi qualified**. It is classified `PORT_REQUIRES_WORK` until actual ARM64 Raspberry Pi OS testing verifies wheel installation, model loading, audio capture, numerical parity, real-time operation, memory, temperature, restart, and sustained streaming. The punctuation model is declared Apache-2.0 and commercial-use compatible subject to its conditions; see `PUNCTUATION_LICENSE_AUDIT.md` and `EDGE_PUNCT_CASING_LICENSE.md`. Review the other upstream model licenses before product redistribution; Pyannote access/provenance remains gated.

See `ARCHITECTURE.md` for thread ownership and extension contracts, `BUILD_VALIDATION_REPORT.md` for measured Windows evidence and the exact remaining Pi gates, and `IMPROVEMENT_ROADMAP.md` for the enrolled-name audit, active-roster/manual-correction design, vocabulary options, overlap limitations, and recommended XVF/fine-tuning sequence.

## XVF3800 extension point

Every speaker event already carries a source-clock `SpatialEvidence` object with fields for energy, angle, angle confidence, direction change, and provider. All fields are inactive in this version and cannot affect results. A future XVF adapter should only produce this contract; fusion/weight policies belong in a versioned policy module, not in audio capture, models, or GUI code. This permits controlled audio-only, energy, AoA, and combined ablations without rewriting the pipeline.

## Tests

```powershell
& "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m pytest ".\tests\edge_speech_pipeline" -q
```

If the setup used standard `venv` rather than Conda, its interpreter is under `.edge-speech-env\Scripts\python.exe`; the launch and setup scripts detect either layout automatically.

The tests verify exact multi-cursor journal replay, no loss with a deliberately slow consumer, profile decisions, source-clock contracts, raw-text preservation, and learned-punctuation output handling. A bounded end-to-end WAV smoke should also finish with `audio_frames_dropped = 0`, both inference cursors at the complete source duration, and a final punctuated transcript.

## Known boundaries

- The desktop package demonstrates real behavior; it is not a replacement for held-out scientific evaluation.
- The segmentation graph has a fixed 10-second receptive window. Early live decisions use left zero-padding and are marked by their source time.
- Profiles are backend/checkpoint-specific and are ignored if their backend identity does not match.
- XVF data is contract-only and has no result effect yet.
- Raspberry Pi/CM5 real-time and memory claims require measurement on the actual ARM64 target.
