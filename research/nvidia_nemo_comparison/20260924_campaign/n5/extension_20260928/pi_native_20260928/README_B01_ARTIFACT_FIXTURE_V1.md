# B01 compact archive and PCM combined saved-input fixture V1

Purpose: validate the new compact event writers/readers and bounded PCM copy while actual Sherpa/PnC, delayed Q8 D1 and retained ReDimNet execute. Uses the real live controller, CaptureTimeline and withdrawn Tk with a saved-source substitute. No microphone opens, capture, playback, enrollment or new accuracy scoring. This does not repair or qualify the physical callback.

Inputs: fresh WINDOW_V5 census; independently reviewed `app-artifact-integration-v1/prototype`; current original 44.6954375s saved file, models and qualified NumPy FIR. A fresh copied app adds only the existing fault-detail wrapper around XVFLiveSource and its helper, preserving abort decisions. The fixture then substitutes saved input for this class and verifies that the diagnostic binding was present beforehand. Exact raw flags on real capture remain a later gate. It uses original1x pacing and a constructed48k input (repeat each16k sample3times), not a real48k recording. Existing app and previews are untouched.

Protocol: process-local hardware-only ALSA config before real sounddevice import; then hardware access explicitly denied. Actual controller starts an audio-retaining private conversation, early Stop at >=8s, same-process full restart, source/model/archive drain, withdrawn widget rendering, Save and Open through controller commands. Actual compact readers reopen the two epochs. Float masters remain exact, WAV copies are explicitly rounded/clipped PCM16. `native_artifact_envelope_v1.py` saves live systemd properties before transient-unit collection.

Outputs: separate `b01-artifact-fixture-v1` target run, derivative hashes, exact owner/admission/unit receipts, compact logs, private float/WAV recordings of the saved fixture, captions/vector diagnostics, snapshots and review. No private content goes into Git. Fresh128MiB combined reserve is64MiB target plus64MiB host backup;8MiB per-file hard limit. Each compact journal retains8MiB cap/1MiB full-record cap; PCM60second bound per epoch. Actual768MiB virtual,1MiB startup stacks,CPU2/3,200%,64tasks,one native thread/model,300second service/290second alarm/140second harness,10second service stop. Initial850MiB available and5GiB free disk; sampled stop at640MiB RSS or192MiB available. These are short test guards, not long-run field qualification. User's fixed32GB storage remains unchanged.

Gates: preserve full715127input/ASR/D1 samples and4470x8D1 frames, compare full filtered D1 output against the existing independent reference at unchanged1e-5, unchanged input hashes, finite normalized E0 vectors, single model loads, source reset, learned punctuation, all queues/handles/controller/Tk and exact owner closure. New E0-window standalone correspondence is explicitly pending, not inherited from other window sets. Reopened caption rows must match independently decoded archive events, float master must match the qualified FIR prefix, PCM bytes must match its declared quantization. Saved/withdrawn success is not live microphone, physical touch, sustained real time or quality acceptance.

## PowerShell

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/dispatch_b01_artifact_fixture_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V66.json'
& $py -B "$p/review_b01_artifact_fixture_v1.py"
```

## CMD / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"%PY%" -B "%P%\dispatch_b01_artifact_fixture_v1.py" --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V66.json
"%PY%" -B "%P%\review_b01_artifact_fixture_v1.py"
```

Use the explicit existing interpreter from either prompt; do not install anything. Census must be fresh (<15minutes), target/host owners closed, leases available and original identities verified. Run ID is immutable/single-use. `--worker`/`--gate` are target-only internal entry points, never manually invoked. Preserve failures and use a fresh justified derivative for corrections. Read review status and its scope before promotion; natural exit alone is insufficient. The next live test requires a fresh autonomous-quiet admission bound to current authority, hardware lease, route restoration and exact limits.
