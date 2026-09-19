# S4 complete Common Voice development bank

See README_S4_PIPELINE.md for the final capture, repeat, analysis and H2 commands; README_S4_RESTORE.md covers exact restoration recovery.

These scripts implement the bounded S4 source/scene, physical replay, unchanged H2 and compact reporting workflow. They preserve S0–S3 and canonical RIR v1. New work belongs to run `20260909T002140Z`; S5/S6 are not started. The current complete authorization is the V2 S4 pack.

## Environment and inputs

Run from this scripts directory. Anaconda Python is used for offline scientific work; the bundled recorder Python owns the explicitly identified XVF endpoints, and the existing `.edge-speech-env` runs H2. Do not install or mix their dependencies. Source corpora, transcript/identity metadata, canonical RIRs, S3 evidence and local XMOS 3.2.1 tools are read locally. The S4 report folder contains hashes and exact source paths.

PowerShell setup and preflight:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& 'C:\Users\amiri\anaconda3\python.exe' s4_preflight.py
```

Anaconda Prompt / Command Prompt equivalent:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
"C:\Users\amiri\anaconda3\python.exe" s4_preflight.py
```

Preflight writes `simulation\reports\S4\20260909T002140Z\preflight.json`, the referenced user speaker-safety receipt, atomic status and heartbeat. It hashes only the supplied pack and canonical manifest. It never accesses hardware. Source, telemetry and H2 helper READMEs document their disjoint offline steps. Do not rerun preflight over an active run; it is the initial snapshot.

## Render, validate and resume

After the source adapter has written its manifest, use Anaconda Python. Four worker processes each use one numerical thread. `s4_bank.py` renders and regenerates all 24 cases, verifies identical FLOAT32 samples, source/cast/split/RIR compatibility and the paired noise component, and freezes the policies/manifests. A normal subsequent invocation checks bindings and preserves the frozen manifests. It never repeats hardware.

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s4_bank.py
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s4_transport.py
```

Command Prompt / Anaconda Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" s4_bank.py
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" s4_transport.py
```

`--refresh-before-capture` is restricted to a documented review correction before ANY physical pass. It archives draft JSON and preserves superseded WAV bytes. It is not a way to change a running campaign. Current scene 20 includes deliberate near/distant speech overlap; 13/14 vary distance and path as well as bearing. Scene 07 uses the shortest eligible complete utterances, not invented subsecond yes/no clips.

## Physical batches

The root owner writes/reads the referenced speaker safety receipt and frozen calibration/initialization policies. `s4_hardware.py` takes a unique `--batch`, one or more `--cases`, and a declared `--recipe`. It locks the existing recorder lease, rejects competing server ownership, identifies XVF endpoints after each reset, retains all raw capture/telemetry, compares the four microphone payloads exactly, and restores the initial exposed state and USB width in `finally`. It charges every started pass before playback. The owner uses bit-transparent PCM24 stereo 48 kHz; there is no default-PC-output fallback.

PowerShell examples for the authorized first regression and six calibration cases:

```powershell
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s4_hardware.py --batch transport_regression --cases transport_regression --recipe baseline
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s4_hardware.py --batch calibration_base --cases S4_01 S4_02 S4_03 S4_04 S4_05 S4_06 --recipe baseline
```

Command Prompt / Anaconda Prompt uses the same arguments without the PowerShell `&`:

```bat
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" s4_hardware.py --batch transport_regression --cases transport_regression --recipe baseline
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" s4_hardware.py --batch calibration_base --cases S4_01 S4_02 S4_03 S4_04 S4_05 S4_06 --recipe baseline
```

Only the recorded calibration decision can choose `limiter_quarter_power` or `limiter_and_agc_headroom`. Final captures require `--final` and a matching frozen OUTPUT_LEVEL_POLICY.json. Repeating the exact compatible batch command resumes by skipping completed case receipts; it does not replay them. Incomplete/failed attempts are retained and require a diagnosed distinct attempt name. A corrupt transport or failed restoration blocks further playback. Raw artifacts are in `reports\S4\20260909T002140Z\hardware\<batch>\<case>`. `physical_ledger.json` includes every charged attempt, and each batch has a restoration receipt.

The hardware output must remain physically unable to produce sound during packed replay. Other PC speakers/headphones/microphones may stay connected; only the unique verified XVF endpoints may be opened. One hardware owner, no competing recorder/control processes. Restore the initial exposed configuration and USB width in every exit path.

Generated work is limited to 5 GiB with 50 GiB SSD reserve. Physical attempts are capped at 40 and active playback at 45 minutes. Each independent scene resets device/H2 state; there is no reset between conversation turns. Ground truth and estimated activity masks belong only to scoring. Source-label ±5° is operator uncertainty, not a device-accuracy tolerance.
