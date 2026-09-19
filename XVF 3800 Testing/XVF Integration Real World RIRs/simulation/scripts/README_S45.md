# S4.5 diverse-source and real-noise expansion

This version adds 240 intended scenes to the completed S4 bank, using original CMU ARCTIC, HiFiTTS and older English Common Voice. L2 ARCTIC is excluded by the user's current instruction. It preserves the canonical RIRs and all old S4 artifacts. Only the documented H2 artifact-writer lifecycle repair may change the previous H2 implementation; scientific configuration/models stay fixed.

Small code/manifests/reports live in the existing simulation folder. New large source, rendered, packed and captured payloads live under `G:\Just_Peachy_S4_5\20260909T031300Z`, independently mapped to the Kingston SSD. Inputs include the S4 policies, canonical RIR v1, native corpus metadata/audio, official noise provenance and the unchanged Revision 9 Word workbook. Outputs are frozen source/scene/split manifests, four-channel canonical audio, simultaneous XVF O0/O1 and microphone diagnostics/telemetry, 24 development sentinel pairs, at most 24 dry-source jobs and one compact handoff. Reserve task accuracy is not scored.

## Environment and commands

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
& 'C:\Users\amiri\anaconda3\python.exe' s45_preflight.py
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
"C:\Users\amiri\anaconda3\python.exe" s45_preflight.py
```

`s45_common.py` supplies immutable run paths/limits, atomic JSON writing, 20-second progress, exact file bindings and SSD/deadline checks. It has no hardware side effects on import. `s45_preflight.py` binds the pack, user override/fresh analog-output confirmation, prior S4 receipts, workbook and resource/Git observations. Existing preflight evidence is verified/reused without overwriting its initial snapshot. Speech/noise and H2 helpers have separate READMEs with exact commands.

Limits: 8 hours from the conservative start 2026-09-09 03:13 UTC; stop launching long work by 10:43 UTC. At most 320 physical passes/4.5 hours active playback, two attempts per scene, 60 GiB new storage/16 GiB downloads. Preserve 50 GiB free on C: and 75 GiB on G:. One coordinator owns the XVF; no PC default endpoint is allowed. Restore exact exposed settings and USB width, disable packed input, close all handles and release keep-awake state in cleanup. No S5/S6, training, driver changes or automatic Git operations.

## Physical execution and exact resume

The initial `s45_execute.py` v1 supervisor closed after the preserved 232-capture checkpoint. The already-tested `s45_execute_v2.py` subsequently resumed at 09:13:33 UTC, closed after the 235-capture checkpoint, and resumed again at 09:24:53 UTC following verified restoration recovery. See `README_S45_EXECUTE.md` and current supervisor/acceptance receipts for the full history and present state. Do not launch a standalone coordinator alongside a supervisor or its owned children. The commands below document the standalone capture entrypoint for use only after the existing owner has ended and its cleanup is verified; they do not start a new run or reset its budgets.

With the frozen bank verified and no existing owner, the standalone entrypoint from the same scripts directory is:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s45_campaign.py
```

Anaconda/CMD equivalent:

```bat
"C:\Users\amiri\anaconda3\python.exe" s45_campaign.py
```

This same command resumes identical frozen inputs without repeating accepted captures. It first captures six F01 nominal/louder source representatives (02,03,05,06,08,09), restores hardware, then checks their raw O0/O1 levels before proceeding to the predeclared sentinels and remaining bank. A gross O0 representative stops expansion; gross O1 is retained and quarantined for task use, while residual rails are LIMITED. This predeclared screen never changes the frozen gain or source selection. Acceptance requires final recipe, matching input/manifest/code contract and PASS audio, payload and telemetry. Every actual playback is charged before it starts. A failed attempt remains in its unique batch, with at most one identical retry. Three consecutive systemic failures, a corrupt payload, failed or missing restoration, the 320-pass/4.5-hour limit or deadline prevents new hardware work. A completed batch restores the exact starting exposed settings and closes all handles. A scoped system keep-awake request is released/restored by the coordinator. `STOP_REQUEST.json` requests finite owner cleanup, including aborting an active stream when required; an owner timeout is explicitly unverified and never labelled restored.

Only after all 240 are accepted, the same command attempts the separately prepared 34 optional references if the time reserve also leaves 45 minutes for offline diagnostics/analysis. `REFERENCE_CAPTURES.json` and `reference_campaign_receipt.json` record them separately. They never enter the 240 count, sentinel jobs or task scoring. Global playback/attempt limits apply to both categories. A missing optional reference remains pending with its reason; it is not reported as captured.

`test_s45_campaign.py` exercises frozen-contract rejection and representative saturation decisions using temporary local fixtures, without hardware or models. Run from this directory in PowerShell: `& 'C:\Users\amiri\anaconda3\python.exe' test_s45_campaign.py`; in Anaconda/CMD: `"C:\Users\amiri\anaconda3\python.exe" test_s45_campaign.py`. Inputs are synthetic PCM24 fixtures and receipt dictionaries; output is the unittest pass/fail report, with temporary fixtures removed automatically.

`s45_hardware.py` and `s45_transport.py` are versioned adapters of the proven S4 capture/framing path. The old code is unchanged; every executed owner/helper hash and source snapshot is retained in its batch. New payloads and captures use G:, while receipts/status remain in the repo. The first tagged eight-second historical fixture is a separate diagnostic, not a new corpus scene. From the scripts directory above, offline format tests use `& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s45_transport.py` in PowerShell, or `"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" s45_transport.py` in Anaconda/CMD. This format-test entrypoint makes no hardware call.

`s45_capture_analysis.py` follows restored capture batches; see README_S45_ANALYSIS.md. The predeclared gross-saturation screen quarantines an output when a continuous rail run reaches100 ms or rails reach1% of all captured samples. Shorter residual rails remain LIMITED. This screen affects task use, not raw evidence or transport validity; it does not change any gain based on model results. `README_S45_H2_RUN.md` documents the separately released, small offline diagnostic. Optional enrollment-reference inputs/captures are separate from240 and take lower priority than canonical coverage.
