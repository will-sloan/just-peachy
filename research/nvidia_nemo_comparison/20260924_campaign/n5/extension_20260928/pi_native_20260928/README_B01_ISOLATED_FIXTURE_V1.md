# B01 separate-process saved-source integration V1

Purpose: exercise actual Controller.start_live, B01 Sherpa/PnC + delayed Q8 D1 + retained ReDimNet, isolated source transport, CaptureTimeline, early Stop/full restart, compact archive Save/Open and withdrawn Tk together. This is a new integration boundary, not a rerun of the model-free engine shell. Hardware is denied in parent and child. The existing saved fixture supplies original 1x pacing, constructed 48k input and qualified FIR conversion; no PortAudio import, microphone, playback or accuracy scoring. The installed application is untouched.

Inputs: fresh WINDOW_V5 census, exact prior app/model/source manifests, original 715127-sample file and route metadata. The copied application is process-bound to isolated_pipeline_source_v2. An explicit Controller subclass supplies a fresh child configuration per epoch; all startup/model/archive/controller methods remain the actual application methods. Spatial modes remain unavailable. The saved child has no callback queue; transport accepted tails must still drain. This does not qualify real PortAudio aggregate memory or fix the DSP readback failure.

Outputs: private target b01-isolated-fixture-v1, source/owner/unit/admission receipts, child terminal ACKs, compact events, saved-fixture float/PCM audio, model vectors, snapshots and independent review. Run ID and admissions are single-use. Preserve failures. Parent hard AS768MiB, child256MiB/90s, 1MiB stacks, shared CPU2/3/200%, Tasks64, one model thread, GPU off; service300s/Stop10s, facade startup45s, parent harness140s. Sampled aggregate RSS640MiB/available RAM192MiB stops are not hard RSS enforcement. Initial RAM850MiB, disk5GiB; fixed32GB device unchanged. Combined128MiB output reserve splits64MiB target/64MiB host evidence, per-file8MiB; existing compact and PCM quotas remain.

Acceptance requires full source coverage, exact FIR float/PCM, D1 4470x8 against existing filtered reference at unchanged1e-5, model/controller/child/queue/handle closure, source-clock continuity and fresh epoch reset. Archive raw utterances contain nested display rows: compare independently decoded raw utterances separately from the actual reopened 40 GUI rows. No new E0-window parity, live route, visible screen/touch, endurance or field-release claim follows.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/dispatch_b01_isolated_fixture_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V100.json'
& $py -B "$p/review_b01_isolated_fixture_v1.py"
```

CMD and Anaconda Prompt (use the existing interpreter, no installation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"%PY%" -B "%P%\dispatch_b01_isolated_fixture_v1.py" --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V100.json
"%PY%" -B "%P%\review_b01_isolated_fixture_v1.py"
```

Census must be under15minutes old with fresh target-inclusive budget and exact closed owners/leases. Internal --worker/--gate entry points are dispatcher-only. Independent reader verifies immutable hashes, native envelopes and numerical/source/archive boundaries; collected results alone are not acceptance. A later correction requires a fresh version and admission.
