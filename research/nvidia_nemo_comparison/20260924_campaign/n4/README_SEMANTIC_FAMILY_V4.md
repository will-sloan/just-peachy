# V4 caption, timing, naming and full-panel review

## Purpose and files

This family joins the V4 scored planner and stopped application runner to the
existing caption, fixed-roster, recorded timing and conditional naming readers.
`review_application_semantics_v4.py` exposes `review_content`, `review_timing`,
`review_labels`, `load_reference_context` and `score_cell`. It uses the actual
V4 cell reader; it does not reinterpret old V2/V3 receipts as V4 results.
The semantic calculations, reference restrictions and missing-data treatment
are preserved, with new versioned result statuses.

`review_application_content_panel_v4.py` reviews the complete planned content
population, retaining every missing/unobserved span and fixed roster.
`review_semantic_panel_v4.py` reviews complete conditional naming diagnostics,
separating taps, repeats, configurations and reference classes. Rates use summed
counts. Neither can treat an available subset as the complete 40–240-cell plan.
Raw source delivery remains in its exact bound envelope. Compact summaries keep
its hash and never subtract scheduling/append cost or promote latency acceptance.

`semantic_family_v4.py` preserves all parent source/proof bindings and qualifies
only its exact stopped development probe. Its shared bounded writer counts
UTF-8 and Windows newline expansion before writing, preserves existing receipts,
and reserves 64 KiB for failure evidence within the 8-MiB review allowance.

`test_application_semantics_v4.py`, `test_semantic_panel_v4.py`,
`test_application_content_panel_v4.py` and `test_semantic_family_v4.py` test actual
readers over synthetic process/source/delivery/native-caption/viewport facts,
complete population, denominator preservation, reference separation, source
equivalence and output boundaries. `probe_semantic_family_v4.py` runs these as
one bounded development probe. No application, model, saved-audio inference,
capture, playback, enrollment or Pi connection is performed by the probe.

## Inputs and outputs

Development inputs: frozen application/context and exact parent qualifications,
historical closed metadata, the qualified V4 synthetic cell, private accepted
evaluator reference inputs and fresh main-bank ownership/resource snapshots.
New synthetic files, source snapshots, logs, `ADMISSION.json`, `RESULT.json` or
preserved `FAILED.json` stay in a fresh private output folder. The public
`SEMANTIC_FAMILY_CHECK_V4.json` is sealed only after tests pass and the exact
helper exits. Its status is development qualification only.

Production inputs: a stopped, completely collected V4 application run whose
exact scored selection/plan, preparer/coordinator identities, fixed command,
child code, frozen source, audio and population all reconstruct successfully.
Outputs: per-cell compact evidence, immutable input-binding registry and complete
content/name report. Evaluator references stay separate from runtime inputs.
Conditional estimated-support naming is not exact-word naming accuracy. Recorded
row timing is not physical scanout or accepted source-to-widget latency.
Resource, continuity, restart, deployment tier and N4/N5 acceptance stay separate.

## PowerShell

Use the existing admitted interpreter; no environment installation is needed:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
$env:OMP_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'
$env:CUDA_VISIBLE_DEVICES='-1'; $env:PYTHONDONTWRITEBYTECODE='1'
& $jpPython -B "$jpN4\probe_semantic_family_v4.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\semantic-family-v4-probe-v1'
```

The probe pins itself to CPU14/BelowNormal, uses the existing metric writer lock,
allows 20 minutes and 8 MiB, preserves the active numerical allocation and pending
reservations, and checks C50/G75 free-space floors and the packaging cutoff.
Retain failed attempts; use a new directory suffix only after investigating them.

After an actual V4 selected application run has completed and all exact owners
have stopped, use separate new private output folders:

```powershell
& $jpPython -B "$jpN4\review_application_content_panel_v4.py" --run 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-application-run-v4' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-content-review-v4'
& $jpPython -B "$jpN4\review_semantic_panel_v4.py" --run 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-application-run-v4' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-name-review-v4'
```

Each full review allows one hour and 8 MiB. These commands only review existing
evidence. Actual application execution belongs to the existing authorized
supervisor after exclusive-slot/resource admission; this family starts none.

## CMD and Anaconda Prompt

Both can call the same admitted environment explicitly without modifying Conda:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set CUDA_VISIBLE_DEVICES=-1
set PYTHONDONTWRITEBYTECODE=1
"%JP_PYTHON%" -B "%JP_N4%\probe_semantic_family_v4.py" --output G:\Just_Peachy_N1\20260924_campaign\local\n4\semantic-family-v4-probe-v1
"%JP_PYTHON%" -B "%JP_N4%\review_application_content_panel_v4.py" --run G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-application-run-v4 --output G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-content-review-v4
"%JP_PYTHON%" -B "%JP_N4%\review_semantic_panel_v4.py" --run G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-application-run-v4 --output G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-name-review-v4
```

The last two commands require the completed admitted run described above; the
probe does not create it. Keep private captions, reference identities, audio,
profiles, evidence and model weights outside Git. Preserve the original checkout.
The Pi stays offline; live CM5 checks wait for reconnection. Packaging starts
2026-09-28 02:48:19 UTC and the deadline remains 14:48:19 UTC that day.
