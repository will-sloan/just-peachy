# H2 Phase-2 quiet resource replay

## Purpose

`replay_h2_phase2_serial_resources.py` closes the resource-evidence gap created
when the original matched R1/R2 serial interval overlapped Windows ESENT I/O
stalls. The original result trees remain checksum-valid and are never changed.

The tool creates a separate replay attempt on C:, reruns the exact original
R1 and R2 jobs one at a time, captures host-I/O evidence over the new interval,
and publishes a matched comparison only when the receipt says
`SERIAL_RESOURCE_HOST_IO_CLEAR`.

It refuses to run unless:

- the complete H2 v17 program has finished;
- its protocol, job manifest, runtime implementation, exact R1/R2 job
  identities, source results, and contamination receipt still match;
- no H2 controller, supervisor, or storage guardian is active;
- the H2 campaign lock is absent;
- no relevant ESENT event occurred during the quiet-window check;
- every workspace/result/summary/config path remains on C:;
- at least 35 GiB remains free.

The tool does not stop backup software or any process. If the host is not
quiet, preflight reports the blockers and performs no replay.

## Inputs

Defaults use:

- source workspace:
  `automated_runs/h2_complete_product_pipeline_v17`;
- source results:
  `JustPeachyResults/full_pipeline/h2_complete_product_pipeline_v17`;
- source config:
  `configs/automated_evaluation/h2_product_program.v17.yaml`;
- exact source jobs:
  `h2p2_r1_two_independent_models_matched_serial_resource_a5d81446a0`
  and
  `h2p2_r2_one_shared_model_matched_serial_resource_6599c41691`;
- attempt ID: `quiet01`;
- quiet window: 15 minutes;
- inter-job cooldown: 60 seconds.

Use another attempt ID such as `quiet02` if the post-run host-I/O receipt says
the first replay was contaminated. Do not reuse or overwrite an attempt.

## Outputs

For attempt `quiet01`:

- workspace:
  `automated_runs/h2_complete_product_pipeline_v17_resource_replay_quiet01`;
- results:
  `JustPeachyResults/full_pipeline/h2_complete_product_pipeline_v17_resource_replay_quiet01`;
- summary:
  `JustPeachyResearchSummaries/h2_complete_product_pipeline_v17_resource_replay_quiet01`;
- immutable replay manifest: `resource_replay_manifest.json`;
- durable queue and progress database;
- exact R1/R2 result trees;
- `diagnostics/host_io_interference/serial_resource_replay.json`;
- `resource_comparison.json` and `resource_comparison.csv`.

No raw source dataset, model weight, biometric template, or original result is
copied into a final summary package. The replay result trees contain the same
kind of locally retained evaluation artifacts as the original resource jobs.

## PowerShell commands

First validate the source bindings. This is read-only and is safe while the
main campaign is running; it reports that replay is not yet eligible.

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"

& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B `
  ".\scripts\replay_h2_phase2_serial_resources.py" self-test
```

After the complete H2 campaign finishes, run the fail-closed quiet-host
preflight:

```powershell
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B `
  ".\scripts\replay_h2_phase2_serial_resources.py" preflight `
  --attempt-id quiet01
```

Only if it reports `ELIGIBLE`, start the serial replay:

```powershell
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B `
  ".\scripts\replay_h2_phase2_serial_resources.py" run `
  --attempt-id quiet01
```

Monitor from another PowerShell window:

```powershell
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B `
  ".\scripts\replay_h2_phase2_serial_resources.py" status `
  --attempt-id quiet01
```

## Anaconda Prompt / Command Prompt commands

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B ".\scripts\replay_h2_phase2_serial_resources.py" self-test
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B ".\scripts\replay_h2_phase2_serial_resources.py" preflight --attempt-id quiet01
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -B ".\scripts\replay_h2_phase2_serial_resources.py" run --attempt-id quiet01
```

The replay has no automatic time cutoff. A stop or failure preserves completed
case shards in the isolated attempt; rerun the same `run` command to resume
that exact attempt. Final resource ranking may use the replay only when
`eligible_for_final_resource_ranking` is `true`.

After an eligible attempt completes, rerun
`scripts/augment_h2_final_package.py`. It deterministically selects the first
lexicographically named eligible replay, not the best-looking metric result.
The augmented ZIP independently validates and embeds the sanitized replay
manifest/state, frozen job manifest, clean receipt, comparison JSON/CSV,
launcher, and this runbook. It also retains the original contaminated receipt
under `reproducibility/host_io/phase2_quiet_replay/`; no source result is
overwritten or discarded.
