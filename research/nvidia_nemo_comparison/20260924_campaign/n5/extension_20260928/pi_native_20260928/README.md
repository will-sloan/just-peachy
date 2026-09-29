# Native Pi priority from confirmed September 28 reconnection

The user confirmed power and Ethernet and authorized native testing, ready-to-run modes and native/ONNX speed investigations over the next few days. This supersedes the extension's earlier no-Pi-contact condition for this confirmed device. Keep the existing October 1 17:47:34 UTC review checkpoint. Do not modify old offline admissions or WINDOW.json. Native qualification and usable modes now take priority over additional Windows analysis.

The user further specified: saved audio is for functionality and CPU/real-time/resource tests, **not new ASR or WER accuracy claims**. Microphone use is permitted; nobody is currently speaking. A quiet-room live route check is not speech-quality evidence. Record real speech accuracy only in a later ready, labelled/consented real-life session. Do not deliberately capture unrelated conversations. No training or human enrollment is authorized. No new capture has been initiated by these scripts.

## Observed target and initial scope

Authenticated SSH verified the retained host key and actual Compute Module 5 Rev 1.0, aarch64 Bookworm, Python 3.11.2, four Cortex-A76 cores, about 2 GB RAM and 19 GiB free disk. The existing rc5 application auto-started and occupies about 428 MiB RSS. Preserve it and its data/autostart. Concurrent observations are not uncontended performance measurements. The initial native task uses CPUs 2/3 (verified target numbering), one model thread, no GPU, 768 MiB cgroup memory limit, no swap for its cgroup, at most 600 seconds and 64 tasks. Keep 5 GiB free on the Pi and at least 850 MiB available before model dispatch. This is a new bounded target admission, not reuse of Windows CPU IDs. Later integrated jobs need their own measured memory admission.

Pi staging is private and separate: `~/JustPeachy/research/nemotron-20260928/d1-generic-v1`. Initial transferred assets plus unpacked runtime are capped at 160 MiB; run output is capped at 16 MiB. Existing host limits and combined 1-GiB private-output allowance remain. Reuse cached model/runtime files; no network model/package acquisition is performed. Do not alter the current release pointer, personal data, OS or firmware.

## Code, inputs and outputs

- `inventory_v1.py`: read-only metadata, installed package versions, current release and relevant exact PID/start-tick identities. It reads no transcript/profile payloads and opens no microphone/model/UI. Run through SSH stdin using the existing app interpreter; save its JSON privately on Windows. PID identity includes Linux boot ID plus start ticks.
- `stage_v1.py`: verifies the fresh stage's INPUTS.json filenames/sizes/SHA256, target identity and free-space floor, checks the known runtime tar's paths/types/size, then extracts it only into a new `nemo-arm64` directory. Outputs STAGED.json. It never updates the active install or creates a virtual environment.
- `d1_smoke_v1.py`: under a fresh bound ADMISSION.json and systemd user resource limits, uses the unchanged, hash-bound current D1 adapter, cached generic ARM64 runtime and pinned mixed-Q8 model. It runs the exact first 12 seconds of the saved 44.695-second source, resident repeat, contiguous frame/finite probability checks, repeat-finish, post-finish rejection and empty-stream handling. Output is OWNER.json, two small private probability arrays and RESULT.json. This is a native component check; it does not produce ASR text, establish integrated modes, DER/WER, independent real-life accuracy or sustained performance.

The stage manifest binds runtime.tar.gz, D1.gguf, source.wav, the unchanged adapter, these scripts and this README. The admission binds the inventory's boot ID, manifest hash, cpus, memory cap, expiration and existing process observations. A successful terminal result still requires independent input/output/lifetime review. Preserve failures and use fresh names for later experiments.

## PowerShell / Anaconda PowerShell on Windows

Use the known retained host key; never disable host-key checking. Work from this directory. Do not paste a private key into any command or file.

```powershell
$jpKey='C:\Users\amiri\.ssh\just_peachy_cm5_ed25519'
$jpTarget='peachyprototype@raspberrypi.local'
Get-Content -Raw .\inventory_v1.py | ssh.exe -i $jpKey -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 $jpTarget '/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B -'
```

Save stdout to a **fresh private** H01 JSON path and require exit zero before reuse. Stage only hash-checked existing inputs under the fresh research directory with `scp.exe -i $jpKey -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 SOURCE "$($jpTarget):/home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-generic-v1/TARGET_NAME"`. INPUTS.json is an explicit list of those source hashes, never a model download request. Run the staging script only after all expected inputs are present:

```powershell
ssh.exe -i $jpKey -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 $jpTarget 'python3 -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-generic-v1/stage_v1.py'
```

## CMD / Anaconda Prompt on Windows

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
set "JP_KEY=C:\Users\amiri\.ssh\just_peachy_cm5_ed25519"
type inventory_v1.py | ssh.exe -i "%JP_KEY%" -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local "/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B -"
```

Use the same explicit `scp.exe` source/target list as PowerShell; `%JP_KEY%` replaces `$jpKey`. No environment activation or package installation on Windows is required.

## Actual target execution through SSH, after fresh admission

The native command is executed on the Pi as its ordinary user, without a visible terminal or GUI:

```bash
systemd-run --user --unit=jp-d1-generic-smoke-v1 --wait --pipe \
  -p MemoryMax=768M -p MemorySwapMax=0 -p TasksMax=64 \
  -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p Nice=10 \
  taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B \
  /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-generic-v1/d1_smoke_v1.py
```

Use a unique unit/run/stage for a new attempt. Do not bypass a missing memory-controller capability. Inspect the unit's Result, ExecMainCode/Status, ControlGroup, MemoryPeak if exposed, and remaining cgroup processes after exit. Copy only this run's small evidence privately, independently review it and verify exact owner closure. No benchmark speed claim is allowed while the unrelated existing app is active. Native low-level timings remain diagnostic observations until matched isolated trials qualify them.

## Ready-to-run modes and subsequent investigations

1. Preserve existing fast Sherpa mode as rollback/control and verify saved-file passage/transcription and quiet live input on-device.
2. Deliver Sherpa + D1 + ReDimNet with immediate captions and pending/delayed speaker labels.
3. Evaluate Nemotron ASR + D1 + ReDimNet against actual RAM and sustained compute; do not silently swap/thrash or substitute another model.
4. Expose delayed-speaker and on-demand-identity variants only after native state/EOF/returning-speaker checks; anonymous bypass is explicitly anonymous.
5. Investigate a two-pass mode: fast live captions, optional Nemotron refinement after the session, with visible revisions and no simultaneous duplicate ASR load by default.

First reuse the generic native binary, then build a fresh Cortex-A76/dot-product-capable native variant with matched Q8 weights/recipe. Compare actual compiler flags/emitted instructions, controlled threads and supported whole cache/chunk profiles. ONNX Runtime CPU/INT8 is a separate runtime comparison: inspect graph/frontend/cache coverage, unsupported-op fallback and thread contention; a .onnx file or smaller graph alone does not prove faster execution. XNNPACK/other kernels are candidates only where the important operators are supported. Existing ONNX Runtime installation does not mean a D1 ONNX model is installed. Download limits remain until a concrete necessary acquisition is admitted.

Measure actual native load/wall/CPU time, peak/steady RAM, clocks/temperature/throttling, caption/label delay, pending backlog trend/max/drain, total context/gate/IPC costs and errors. Run original-pacing controls, dense speech, natural pauses, quiet/short replies, overlap and returning speakers; then 30/60-minute endurance. Synthetic silence savings are not real-world throughput. Final real speech/noisy-location validation freezes modes/settings and compares XVF reference/ASR/postprocessed audio separately for babble, steady noise and impacts. Keep implementation, native functionality, resource measurements and independent real-life validation as separate states.
