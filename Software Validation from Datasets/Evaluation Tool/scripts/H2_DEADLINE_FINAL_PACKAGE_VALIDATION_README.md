# H2 deadline final-package validation

## Purpose

`validate_h2_deadline_final_package.py` independently validates the compact
time-boxed H2 export after final inference, metric consolidation, and ZIP
creation. It does not run neural inference or alter scientific results.

The validator checks the exact frozen 24-case order in both retained modes,
result-tree checksums and schemas, critical and all-metric tables,
punctuation-insensitive WER, the 2,000-repetition seed-3800 speaker bootstrap,
the upload pointer, ZIP CRCs, every inventoried disk/ZIP hash, and the copied
deadline/retry/ARM64 receipts. It rejects stale inventory self-hashes as well as
model weights, audio, NumPy embeddings, and transient cache payloads in the ZIP.

The known-only result is an intentionally stopped prefix of the original
180-case job, so the generic result-tree validator correctly reports it as
non-reusable for the full job. Final-package validation accepts that one tree
only when it is schema/checksum valid, contains the exact ordered 24-case
prefix, lives under the receipt-bound known-only attempt root, and the copied
direct-retry receipt proves `TARGET_REACHED`, unchanged science, no metric
inspection, the frozen plan hash, and a stopped lease-free queue. Every other
non-reusable result remains rejected.

## Inputs and outputs

Inputs are the v17 campaign workspace and final summary directory. The optional
`--receipt` output is a small JSON validation receipt; place it in the workspace
so the validated ZIP is not modified after validation.

The summary must contain byte-identical copies of the immutable held-out
execution manifest and `deadline_panel_cases.jsonl`; the validator compares
both against their authoritative workspace sources before accepting the ZIP.
It also requires the checksum-bound receipt for the non-scientific low-I/O
finalizer restart, so the operational change cannot disappear from reporting.
The deadline host-interference observation is likewise required; it preserves
the observed backup-process provenance while explicitly refusing unsupported
causal or clean-resource claims.
The user-facing operational-recovery document is mandatory so both Windows
publication failures and all evidence-eligibility limits remain visible.

Successful output has status `PASS`, the two result identities, verified case
and metric counts, and the final ZIP path and SHA-256. Any failed invariant
causes a non-zero exit and no passing receipt.

## PowerShell

```powershell
$Tool = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
$Python = 'C:\Users\amiri\anaconda3\python.exe'
$Workspace = Join-Path $Tool 'automated_runs\h2_complete_product_pipeline_v17'
$Summary = Join-Path $Tool 'JustPeachyResearchSummaries\h2_complete_product_pipeline_v17'

& $Python -B (Join-Path $Tool 'scripts\validate_h2_deadline_final_package.py') `
  --workspace $Workspace `
  --summary-root $Summary `
  --expected-case-count 24 `
  --receipt (Join-Path $Workspace 'timeboxed_completion\deadline_final_package_validation.json')
```

## Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
C:\Users\amiri\anaconda3\python.exe -B scripts\validate_h2_deadline_final_package.py --workspace "automated_runs\h2_complete_product_pipeline_v17" --summary-root "JustPeachyResearchSummaries\h2_complete_product_pipeline_v17" --expected-case-count 24 --receipt "automated_runs\h2_complete_product_pipeline_v17\timeboxed_completion\deadline_final_package_validation.json"
```

Run this only after `FINAL_STATUS.json` reports
`COMPLETE_H2_DEADLINE_BOUNDED_RESULTS` and the finalizer process has exited.
