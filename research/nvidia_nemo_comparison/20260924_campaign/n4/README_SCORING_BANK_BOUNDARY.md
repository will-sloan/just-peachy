# Verify the actual method-bank to evaluator boundary

`probe_scoring_bank_boundary.py` uses the existing app interpreter and frozen
N4 source to produce three model-free method cells: baseline, A3/D1/E1 and a
successful empty A0 session. It uses the exact integrated_bank.predict_cell
function and V2 Controller projection, then calls scoring_bank.prediction.
The resulting evaluator prediction must equal the previously qualified saved
prediction. A changed publication count must fail, and a missing production
bank must not be admitted. No evaluator truth enters prediction or inference.

Inputs are the existing public publication, empty-output, gallery, source and
bank implementation receipts, with their saved component/output bindings.
Outputs are a fresh private ADMISSION.json, three complete publication/projection
artifact sets and method receipts, then RESULT.json or preserved FAILED.json.
This is development qualification, not a complete/partial production bank.
The older nonempty V1 projection lacks V2's explicit empty-caption field; it
cannot be directly substituted for an integrated-bank cell. Existing V1 evidence
remains intact and serves only as the semantic comparison parent.

The helper uses CPU14 below normal, single-thread math, GPU off and forbidden
model loading, with no visible GUI, audio hardware, playback or desktop control.
It inherits the 128-MiB private output bound, drive floors, 12-minute between-cell
budget, packaging cutoff and conservative shared-reservation check. Do not run
it during controlled stack timing or concurrently with another application-method
bank helper. Preserve all previous output/code bindings.

PowerShell from the campaign worktree:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_scoring_bank_boundary.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\scoring-bank-boundary-v1'
```

Command Prompt / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_scoring_bank_boundary.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\scoring-bank-boundary-v1"
```

Purpose, production scorer inputs/outputs, partial-status rules and its commands
are in README_SCORING_BANK.md. This helper imports the app for method replay;
the production evaluator does not. The established metric process is separately
checked in the isolated metric environment by probe_metric_process.py.
