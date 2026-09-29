# Prepared 30-second live B01 diagnostic

Purpose: after current user readiness, connect the checked real XVF I2S route to Sherpa captions, one ordered delayed Nemotron D1 stream, retained ReDimNet and punctuation. This is an experimental diagnostic, not an accepted live release. The separate saved-source live-controller test passed; actual concurrent hardware/model behavior remains unexecuted until a user-ready trial. Caption widgets stay withdrawn; this does not evaluate the physical screen. No playback, enrollment, personal profiles, alternate backends or reset command.

**User mode captures real microphone input and retains private diagnostic audio journals, transcripts, model vectors and resource/route evidence.** Explain this before asking readiness. Use only the ready user/consenting speakers. An empty research gallery means personal identity remains Unknown; session speaker numbers are not enrolled names. Files stay in the private research run, never Git. This differs from the earlier no-audio-save quiet check.

The accepted-source target is480000samples/30s at16kHz, from1440000accepted48kHz frames. `bounded_live_source_v1.py` ends the source and restores the route before model drainage. Unexpected discontinuities or a callback block crossing the exact target fail rather than being silently clipped. This is a sample bound, not an independent acoustic clock or unconditional30s wall-clock safety guarantee: startup/priming, callback stalls and error cleanup can extend the microphone-open interval. Service180s plus90s stop bounds an abnormal process; forced termination cannot prove restoration. Do not automatically retry capture/reset after failure.

Inputs: unchanged qualified `shared-app-b01-fir-v1/prototype`, actual original config copied into a fresh private data directory, installed/qualified assets, no downloads. Runtime config, source and existing saved-controller qualification hashes are bound. The source wrapper changes the stop condition only; model geometry/history remain unchanged. Models load with one native thread; input is continuous, no ASR gating/skips. Controller/API Start is used once and no restart is offered. Private input is diagnostic evidence, not ASR/WER/DER scoring.

Limits: CPUs2/3 total200%, Tasks64, hard768MiB virtual space,1MiB startup/Python stacks, existing allocator settings, GPUoff,>=850MiB RAM and5GiB disk. Original app/OS/install/autostart/data remain untouched. Timings are conditional while that app runs. Shared research lease spans systemd completion; real source owns the original hardware lease. Fresh census/admission and exact boot/PID/start/source checks are required. Combined new-output reservation32MiB remains inside the existing1GiB cap. Admissionexpires8minutes; unique user IDs prevent overwriting prior evidence.

Boundary mode executes only three model-free native cases: exact accepted limit and source closure, sample discontinuity rejection, overrun rejection. It does not load models, open Tk, import/open audio devices, or assert actual restoration. The user launcher requires a reviewed boundary result with identical source/helper/gate/README/launcher hashes. Even a passed boundary test is not live combined qualification.

PowerShell, boundary preparation (safe for an authorized scheduled follow-up, fixed ID once):

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b01_live_trial_v1.py --mode boundary --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V30.json
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_live_trial_v1.py --run-id b01-live-trial-boundary-v1
```

PowerShell, **only when the user is currently physically ready and agrees to private diagnostic recording** (never from a heartbeat):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b01_live_trial_v1.py --mode user --ready-now --allow-private-diagnostics --census <fresh-census.json>
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_live_trial_v1.py --run-id <returned-user-run-id>
```

CMD / Anaconda Prompt: first `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`; use the same interpreter/script arguments without `&`, with double quotes around the interpreter path. Existing Python is used directly; no install/activation. A census older than15minutes is rejected.

Outputs: `local/n5/research-extension-20260928/pi-native-20260928/<run>-evidence` and matching private Pi run. Each user run needs independent source/coverage/timestamp/worker/queue/archive/route/owner review; no outcome is inferred from the launcher or boundary pass. First text/labels include initial silence and are not phonetic latency. Report actual inference costs, delayed label availability, resources and drainage. Quiet/no-text input is not an accuracy failure. Noisy listening comparisons and30/60minute stability remain separate later sessions.
