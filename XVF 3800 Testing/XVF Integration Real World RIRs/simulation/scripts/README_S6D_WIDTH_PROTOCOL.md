# S6D operational-width protocol bridge

Purpose: run the exact already-declared 16-job / 3,840-cell operational tracker-width matrix inside the reviewed code-only supervisor. It imports the bound policy helper in the same Python process; it starts no neural worker and no device. It does not modify or replace the frozen S6C policy graph.

Inputs: exact `angles/operational_width_v1/PLAN.json` (SHA256 c89cf5169fd4e53335714b34a2bc8111623e95800a74df38e05e9cb9fa7409c1), a root admission listing all 16 literal jobs, original native evidence and immutable parent controls. Supervisor-provided S6D run/job/child identity and protocol paths are required. Output directories must be fresh. Outputs: original policy predictions and immutable cell receipts, PREDICTION_INDEX.json, identity-bound heartbeat and semantic completion (or WRAPPER_FAILURE.json).

The observer writes every five seconds and counts parseable, exact-plan cell receipts with declared output files as progress. It ignores partial writes and unrelated filenames; validated receipt identities are cached for inexpensive progress observation. A matching supervisor STOP_REQUEST interrupts this one offline Python process; interrupted predictions remain unadmitted and are preserved. The supervisor may terminate only this identified offline owner after its grace period. Never rerun into partial output directories or infer completion from liveness/receipt count alone. Completion verifies exact equality with all 3,840 planned cell identities/output paths, every prediction hash, semantic index fields and the unchanged admission binding. Scores, native confirmation and S6D completion are separate stages.

This bridge is launched only by the approved supervisor queue; do not manually fabricate its identity environment. The concrete queue, approval hashes and full launch command are saved in `reports/S6D/20260913T195357Z/runner/README_WIDTH_RUN.md` after review/admission.

PowerShell: inspect the approved run instructions before using their complete literal command:
```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
Get-Content -LiteralPath "$s6dSim\reports\S6D\20260913T195357Z\runner\README_WIDTH_RUN.md"
```

Anaconda Prompt / Windows CMD (no activation required):
```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
type "%S6D_SIM%\reports\S6D\20260913T195357Z\runner\README_WIDTH_RUN.md"
```

The existing `.edge-speech-env\python.exe` is required. No install, model download, device connection or package mutation is performed. All 2/5/10/20-degree widths remain experimental, and the original manual 5-degree measurement uncertainty is unchanged.

Independent model-free regression fixtures and PowerShell/Anaconda commands are documented in `README_S6D_WIDTH_PROTOCOL_CHECKS.md`; `s6d_width_protocol_checks.py` uses temporary synthetic data only. Preserved adverse wrapper source and reviewer receipts remain under `reports/S6D/20260913T195357Z/runner/width_protocol_review_v1`. Background receipt scans check the close signal between files and ignore malformed/schema-invalid or oversized receipts. After the observer joins, the main process performs the full final receipt scan and requires all3,840 committed receipts; the five-second join is not enlarged to hide a slow background walk.

The final scan clears the progress cache and rereads every receipt, so a deleted or changed receipt cannot survive through cached progress. It checks the matching owner STOP before/between/after final-scan entries and again immediately before completion commit. A STOP or changed admission observed there produces failure without a COMPLETE receipt. Progress counts remain observations; the separate exact index validation checks every prediction hash.

Atomic replacement retries only Windows sharing/access PermissionError: at most seven attempts with1.575 seconds total backoff. Other I/O failures propagate immediately. Persistent refusal preserves the prior destination and prepared temporary file and prevents successful completion; retries do not skip checks or change result contents.
