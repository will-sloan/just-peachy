# Bounded S4 H2 summary recovery

This helper recovers only the diagnosed S4_18/O1 session `edge_wav_20260909T013655Z_c62a4b6f`. The original model process returned zero and retained matching completion-event/stdout journals and a complete PCM16 spool, but left a zero-byte summary. The original H2 daemon watcher announces COMPLETED before writing its summary; the CLI can exit during that final write. This cause has strong implementation evidence without a direct thread trace.

The helper does not run models, open hardware, alter H2 source/policies, or change frozen runner/scoring code. It rejects nonempty corruption, nonzero exits, other errors, failure/stop events, incomplete cursors/spool, divergent event/stdout or transcript journals, and changed baseline/config/code identities. Unit tests use tiny synthetic data only.

Inputs are the preserved S4_18/O1 failed run receipt, zero-byte original summary, events, stdout, labelled transcript, raw PCM16 spool, bound input adapter and unchanged S0/execution contract. The helper reproduces the exact PCM16 conversion to verify the entire spool. Expected asset identities come from the bound original configuration; successful internal validation is inferred from the original constructors before session_started. No asset-validation event is invented and model weights are not rehashed by recovery.

With no arguments it validates and makes no writes. `--execute` takes only the offline runner lease, preserves exact original bytes at `h2/S4_18/O1/recovery_evidence/session_summary.original_empty.json` and `run_receipt.original_failed.json`, and writes a clearly labelled derived `session_summary.json` with primary-evidence bindings. It writes `H2_SUMMARY_RECOVERY.json` and advances the active run receipt to MODEL_COMPLETED with links to the preserved failure and recovery. Original error/end fields move into explicit failure provenance. The unchanged runner can then finish scoring without repeating this model job. Existing recovery artifacts stop repeat execution for review.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\anaconda3\python.exe'
& $py "$sim\scripts\s4_recover_h2_summary.py" --self-test
& $py "$sim\scripts\s4_recover_h2_summary.py"
# Only after the runner has stopped and validation passes:
& $py "$sim\scripts\s4_recover_h2_summary.py" --execute
```

Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s4_recover_h2_summary.py --self-test
"C:\Users\amiri\anaconda3\python.exe" s4_recover_h2_summary.py
"C:\Users\amiri\anaconda3\python.exe" s4_recover_h2_summary.py --execute
```

After reviewing the recovery receipt, the coordinator resumes `s4_h2_run.py` using the same alignment input and frozen execution contract described in `README_S4_H2_ANALYSIS.md`. Recovery itself starts zero model jobs and never substitutes an inferred transcript or speaker decision for recorded model output.

## Remaining-job recovery, version 2

The same original CLI export race subsequently occurred for S4_20/O0. `s4_recover_h2_summary_v2.py` preserves the version-1 helper and recovery receipt unchanged. It applies the same strict primary-evidence checks to an explicitly selected remaining canonical case S4_20 through S4_24 and output O0 or O1. It additionally joins the raw audio to the authoritative accepted capture and verifies the output-specific frozen adapter gain. It still accepts only an empty summary after exit zero, complete matching journals and exact full PCM16 spool; other failures are rejected.

Each version-2 recovery writes `H2_SUMMARY_RECOVERY_<case>_<stream>.json` and preserves that job's originals under its own `recovery_evidence` folder. Its schema and reconstruction marker match version 1, while `recovery_code` binds the version-2 script. The original `H2_SUMMARY_RECOVERY.json` is unchanged. These are distinct recoveries of completed jobs, never extra model invocations.

PowerShell, for the diagnosed second occurrence:

```powershell
& $py "$sim\scripts\s4_recover_h2_summary_v2.py" --self-test
& $py "$sim\scripts\s4_recover_h2_summary_v2.py" --case S4_20 --stream O0
& $py "$sim\scripts\s4_recover_h2_summary_v2.py" --case S4_20 --stream O0 --execute
```

Anaconda Prompt or Command Prompt, from the scripts directory:

```bat
"C:\Users\amiri\anaconda3\python.exe" s4_recover_h2_summary_v2.py --self-test
"C:\Users\amiri\anaconda3\python.exe" s4_recover_h2_summary_v2.py --case S4_20 --stream O0
"C:\Users\amiri\anaconda3\python.exe" s4_recover_h2_summary_v2.py --case S4_20 --stream O0 --execute
```

The six version-2 tests include both fixed gains and rejection of an excluded raw capture. The coordinator may use another explicit remaining case/output only after it exhibits the same failure and passes the same read-only validator. Resume with the original `output_alignment.json`; omitting it changes analysis identity and can remove available turn-scoring evidence.
