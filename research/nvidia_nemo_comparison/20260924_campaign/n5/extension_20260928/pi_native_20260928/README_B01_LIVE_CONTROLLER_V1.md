# B01 live-controller branch with a saved-source fixture

Purpose: exercise actual native `Controller.start_live`, `LivePipelineSource`, `CaptureTimeline`, B01 models, withdrawn Tk, early Stop and same-process full restart before preparing a user-ready live-model test. This is a new branch check, not a repetition of the file-input check. Application files and qualified previews are unchanged.

No microphone/device/control API is used. `saved_live_fixture_v1.py` substitutes only the XVF source and its integrity summary. PortAudio, host controls, hardware leases and inventory calls are blocked in this process. A saved 16kHz source is expanded threefold, passed through the qualified FIR and delivered in 10ms blocks at original1x pacing, with actual host timestamps. The real pipeline checks contiguous samples, epochs and stream-start feasibility. The fixture has no independent hardware callback producer/ring pressure; its restoration is simulated. Neither callback performance nor real combined live capture is qualified by this check. Actual source-only quiet evidence remains separate.

Inputs: existing original44.6954375s WAV, unchanged `shared-app-b01-fir-v1/prototype`, qualified D1 delayed runtime and installed Sherpa/ReDimNet/punctuation assets, copied private runtime configuration and route metadata. No profiles/enrollment or downloads. The copied route metadata is labelled a fixture and supplies schema fields, not a new device measurement. Captions and vectors come only from saved audio; no accuracy scoring.

Outputs: private unique `b01-live-controller-v1` admission, owners, logs, session journals/archives, source conversion digests, real timeline counts, model resources, withdrawn widget rows and independent review. Preserve every failure. The reader requires original715127samples/4470x8 full D1 against the existing filtered-source reference at unchanged1e-5, exact converted input hashes, coverage, distinct session origins, natural queue/handle/controller/Tk/OS closure and no inference errors. E0 windows must be finite normalized192D vectors with valid support, but new window numerical references remain explicitly unqualified by this reader. No stage/release/live-quality/endurance acceptance follows.

Envelope: target CPUs2/3 total200%, one native model thread, hard768MiB virtual space,1MiB startup/Python stacks, existing allocator bounds, Tasks64,180s service; >=850MiB available RAM and5GiB disk. Shared research dispatch lease and exact boot/PID/start identities are checked. Combined output reservation32MiB includes target and collected evidence under the existing1GiB cap. Original app/data remain unchanged. Source/harness/README hashes bind admission. The fixed run ID is immutable; do not repeat a completed run.

PowerShell after a fresh comprehensive host census, while no other owned job is active:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b01_live_controller_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V30.json
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_live_controller_v1.py
```

CMD / Anaconda Prompt: use `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`, then the same interpreter/script arguments without `&` and with double quotes around the interpreter path. No environment installation/activation is required. Inputs and output locations are fixed above; a stale census, changed hashes, active owner or insufficient resources rejects dispatch.

This code has no real-capture mode. A later spoken-model test requires a separately bounded implementation/admission and current user readiness. Do not turn the fixture into hardware capture by removing its protections.
