# Desktop shortcuts and optional audio export
User authority: October 1, 2026 follow-up after V135. Required additions to ongoing delivery; **not implemented or qualified in the active native release yet**. Hard deadline 17:42:44 UTC unchanged. This report work did not start an app/capture.

## Desktop launchers
Provide named desktop shortcuts for available backend profiles through one versioned local launcher and one frontend. Preserve the baseline shortcut as a recoverable choice. Each selects its immutable backend/mode manifest and opens idle/capture off; visible Start/consent still controls recording. Show backend/mode/unavailable reasons. A second shortcut must not create a competing microphone/model owner.

First candidates remain B01 (Sherpa ONNX/PnC + Nemotron-3 diarization + compatible ReDimNet) and B05 (explicit anonymous identity). Latest user decision: retain Sherpa ONNX ASR because measured Nemotron ASR was about 1.75 RTF. Other ASR experiments are deferred; do not make them delivery prerequisites or silently replace Sherpa. Saved Streaming/Chunk52 and live Delayed availability remain distinct. Never point icons at expired research dispatchers or qualification drivers.

Acceptance: verified desktop/launcher/config backups, actual profile selection and double-launch exclusion, Start/Stop/Return, restart/recovery, offline local-asset invocation and rollback. Programmatic activation and physical touch are separate evidence. Preserve display 270 and the user's idle app.

## Optional recording
Expose a pre-session choice: Off / Processed audio / Raw + processed. Show recording indicator, elapsed time, admitted duration/storage remaining, Stop and explicit failure. Future manual field sessions are separate from current bounded quiet qualifications.

Processed means the exact waveform supplied to ASR/D1/identity, with taps/gains/resampling labelled. Float model-input and PCM WAV copies are two encodings of processed audio, not raw microphones.

Raw means untouched physical MIC0–MIC3 before XVF beamforming/AEC/noise suppression, if this firmware exposes them. Existing UA routing documents 48 kHz stereo O0 automatic ASR/O1 processed output; a transport variable named raw does not prove raw microphone capture. Validate exact firmware channel/routing capability. If simultaneous raw+processed taps are unavailable, show that explicitly and preserve the working route. No playback/injection or periodic reset.

Save synchronized native/model sample clocks, rates/channel map, route/firmware configuration, gain/filter delay, model/release hashes, consent, gaps/overflows, start/end and integrity receipt. Stream bounded files outside callbacks. Preserve original samples and partial failed recordings; ensure Stop closes all writers. Keep recordings private.

Storage examples for PCM16, decimal units, excluding headers/events/backups:
- Processed mono 16 kHz: 115.2 MB/hour.
- Four raw 48 kHz channels + processed mono 16 kHz: 1.4976 GB/hour.
- Six raw/packed 48 kHz channels + processed mono 16 kHz: 2.1888 GB/hour.

Float32 doubles each affected stream. Reserve worst-case recording plus independent Pi/PC copies and preserve 5 GiB Pi free space/finite duration. Existing caps do not authorize these new streams. RAM does not add recording storage.

## Offload to PC
Provide Recording Export after Stop/physical closure, with selected raw/processed lossless audio and a manifest. Transfer over authenticated local SSH/SFTP using existing strict host/key binding, or selected removable storage; no internet service needed. Verify complete membership/sizes/SHA256 and PC readback, save receipt and show destination. Copy by default; never delete the Pi original because transfer started. Preserve interrupted partial output and original.

V120/V123 processed-archive export/import is narrower evidence, not proof of raw-channel export or production PC offload. Required new evidence: bounded native paired capture if supported, synchronized lengths/no drops, Stop/route restoration, complete PC copy/readback and explicit failure behavior. Functional quiet recording is not noisy-human accuracy validation.
