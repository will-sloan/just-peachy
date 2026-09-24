# N1 saved-audio campaign

Purpose: one 480x800 Tk frontend with independent backend composition, logical
mode, engine recipe and O0/O1 tap. Existing model hashes and preprocessing are
retained. Caption spans have stable IDs, source revision windows and separate
speaker revision history. These windows are not phonetic word alignment.

Default launch is idle and saved-audio-only. It blocks microphone enumeration,
live capture, live enrollment and IMU startup even if a previous data root has
saved permission/configuration. Use isolated research data. Personal profiles
remain outside source and releases. Future manual live operation is retained
behind `--allow-live`; it still opens idle and is NOT tested during N1.

Inputs: prepared mono16k PCM16 WAV, explicit matching O0/O1 tap, content-addressed
baseline model cache, isolated data root, optional immutable backend ID. Prepared
O0 already contains its declared +3dB, so runtime gain is 1.0 for both taps. No
new waveform, mixing, denoising, RIR processing or hardware capture is performed.
Outputs: caption/event/session journals and optional result JSON in the isolated
data root. Default mode is caption_only, recipe fast, O0; paired research uses
anonymous_conversation/balanced to exercise the speaker models without a gallery.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\prototype\main.py validate
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\prototype\main.py gui --data-root 'G:\Just_Peachy_N1\20260924_campaign\local\manual-gui' --models 'C:\Users\amiri\JustPeachy\shared\models'
```

The GUI command is for the user's later manual use; campaign checks run on an
isolated Windows desktop without switching or controlling the user's desktop.

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prototype\main.py validate
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prototype\main.py gui --data-root "G:\Just_Peachy_N1\20260924_campaign\local\manual-gui" --models "C:\Users\amiri\JustPeachy\shared\models"
```

For a saved file replace `gui` with `file --wav "EXACT_ACCEPTED_WAV" --mode
anonymous_conversation --recipe balanced --tap O0 --result "RESULT_JSON"` and
retain the explicit data/model roots. Choose the correct actual tap; the app
rejects a filename/tap mismatch. No Conda activation or global upgrade is needed.

`--backend sha256:...` selects a content-identified manifest. Available baseline
and unavailable future candidates share the same mode list and event contract.
Unavailable candidates or spatial modes without matching recorded telemetry
cannot silently substitute algorithms. Baseline recipes are policy choices,
not different model compositions. See `app/README_BACKENDS.md` and
`vendor/edge_speech_pipeline/README_N1_SPANS.md`.

Rollback is selection of the preserved original checkout or verified baseline
archive in `G:\Just_Peachy_N1\20260924_campaign\local\baseline`, using a separate
data root. No installed Pi release or original Windows source was activated or
replaced by N1. Do not reset unrelated original changes.

GUI application receipts preserve the first applied labels and subsequent revisions
separately from ASR/source events. During a session, they append to
`gui_presentation.jsonl` in that session's local evidence directory; recent in-memory
metrics retain at most 256 receipts. These measure Tk text application, not viewport
visibility or physical display scanout. Idle fixture receipts stay in bounded metrics.
