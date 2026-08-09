# Worker Assignment and Independent Result Merge (Stage 6)

## Purpose

This package divides one immutable global campaign between independent repository clones, validates the selected work before execution, packages only completed scenario artifacts, and merges copied results without silently overwriting anything. It reuses Stage 2 scenario IDs, Stage 3 completion/checksum validation, the Stage 4 executor, and Stage 5 environment/resource artifacts. It does not change inference, augmentation, scoring, plots, reports, scenario hashes, model code, or component configurations.

There is no shared database coordinator. One authoritative pending campaign is planned and assigned once. Each worker receives a one-time copy on local disk and runs only their assignment. The SQLite file in that copy is local to that worker; it must never be opened from a network drive. Result-transfer packages do not contain SQLite.

## Inputs

- one entirely pending `automated_runs/<campaign_id>` campaign;
- its immutable campaign and benchmark manifest hashes;
- one or more short worker IDs;
- the exact expected Git commit and environment profile;
- optional exact scenario IDs, inclusive range, `family=name` component filters, dataset/panel filters, modulo partition, and scenario cap;
- complete scenario artifact folders for export;
- a Stage 3 `environment-fingerprint.v1` collected during export.

All workers must clone the complete Git repository, checkout the recorded commit, install the recorded environment profile, and have the required local datasets/models. Credentials are never accepted in an assignment or transfer.

## Outputs

```text
automated_runs/<campaign_id>/
  worker_assignments/
    worker_amir.yaml
    worker_friend.yaml
  analysis/
    merge_validation_report.json
    analysis_input_index.json
    merged_results/
      merged_result_index.json
      scenarios/<global_scenario_id>/...
```

An external transfer package contains:

```text
transfer_<worker>/
  transfer_manifest.json
  worker_assignment.yaml
  environment_fingerprint.json
  scenarios/<global_scenario_id>/...
```

Every transferred file is listed by portable relative path, byte count, and SHA-256. The scenario directory also has a deterministic tree hash and must pass ordinary scenario-completion validation. Missing assigned work is explicit. The analysis input index is the small handoff document for later loading, comparison, plotting, and final analysis-manifest generation.

## Assignment behavior

Selectors are combined as intersections. Repeated values within one selector are alternatives. Results are always sorted by global scenario ID before an optional maximum count is applied.

Deterministic partitioning uses `int(global_scenario_hash, 16) % partition_count == partition_index`. This does not depend on catalog row order, machine, worker name, or output path. Scenario IDs and hashes remain those of the global campaign.

Overlap is rejected unless both assignments set `allow_overlap: true`; this bilateral rule is reserved for intentional reproducibility duplicates. Different expected Git commits are rejected across one assignment set.

## Anaconda Prompt or Command Prompt

Plan the complete campaign once, then create and validate assignments:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"

python run_evaluation.py campaign plan --campaign-id campaign_example01
python run_evaluation.py campaign assign --campaign-root automated_runs\campaign_example01 --worker-id amir --environment-profile core-cpu --partition-index 0 --partition-count 2
python run_evaluation.py campaign assign --campaign-root automated_runs\campaign_example01 --worker-id friend --environment-profile core-cpu --partition-index 1 --partition-count 2
python run_evaluation.py campaign validate-assignments --campaign-root automated_runs\campaign_example01
```

Before anyone runs work, create the second person's independent campaign copy. Copy the resulting directory to the second clone's local `automated_runs` directory using an ordinary complete file transfer:

```bat
python run_evaluation.py campaign prepare-worker-copy --campaign-root automated_runs\campaign_example01 --assignment automated_runs\campaign_example01\worker_assignments\worker_friend.yaml --destination C:\transfer\campaign_example01
```

Do not execute `database/campaign.sqlite` in place on a network share. Copy the complete prepared campaign directory onto Machine B's local disk first.

Each worker runs only their assignment:

```bat
python run_evaluation.py campaign run-assignment --campaign-root automated_runs\campaign_example01 --assignment automated_runs\campaign_example01\worker_assignments\worker_amir.yaml --environment-profile core-cpu
```

Export completed results on each machine:

```bat
python run_evaluation.py campaign export-results --campaign-root automated_runs\campaign_example01 --assignment automated_runs\campaign_example01\worker_assignments\worker_amir.yaml --environment-profile core-cpu --destination C:\transfer\transfer_amir
```

Validate and merge on the analysis machine:

```bat
python run_evaluation.py campaign validate-transfer --campaign-root automated_runs\campaign_example01 --transfer-root C:\transfer\transfer_amir
python run_evaluation.py campaign merge-results --campaign-root automated_runs\campaign_example01 --transfer-root C:\transfer\transfer_amir --transfer-root C:\transfer\transfer_friend
python run_evaluation.py campaign validate-merged --campaign-root automated_runs\campaign_example01
```

Assignments may also use exact selection:

```bat
python run_evaluation.py campaign assign --campaign-root automated_runs\campaign_example01 --worker-id amir --environment-profile core-cpu --scenario-id scenario_0123456789ab --scenario-id scenario_abcdef012345
python run_evaluation.py campaign assign --campaign-root automated_runs\campaign_example01 --worker-id friend --environment-profile core-cpu --scenario-range scenario_800000000000:scenario_ffffffffffff --component asr=whisper_base --dataset cmu_arctic --panel controlled_clean --maximum-scenario-count 25
```

## PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python run_evaluation.py campaign validate-assignments --campaign-root automated_runs/campaign_example01
python run_evaluation.py campaign run-assignment --campaign-root automated_runs/campaign_example01 --assignment automated_runs/campaign_example01/worker_assignments/worker_amir.yaml --environment-profile core-cpu
python run_evaluation.py campaign merge-results --campaign-root automated_runs/campaign_example01 --transfer-root C:/transfer/transfer_amir --transfer-root C:/transfer/transfer_friend
```

## Validation and merge rules

- Campaign, benchmark, scenario, seed, component, model, Git, and environment-profile identities must match.
- Package environment and hardware differences are retained in the merge report.
- Missing files, changed bytes, stale checksums, incomplete scenario artifacts, and partial copies are rejected.
- Byte-identical duplicates are recorded once and do not overwrite the canonical copy.
- Conflicting duplicates reject the merge before an index is changed.
- Missing global work remains in `missing_scenario_ids`.
- The merged index contains only portable, campaign-relative paths and global scenario IDs.
- Existing merged results are revalidated before an incremental merge.

## Tests

Stage 6 tests use synthetic subprocesses and need no GPU, model, API key, network access, or download:

```bat
python -m pytest tests\automated_evaluation\test_stage6_campaign_exchange.py -q --basetemp artifacts\pytest_stage6
python -m ruff check --no-cache app\campaign_exchange app\campaign_executor\cli.py tests\automated_evaluation\test_stage6_campaign_exchange.py
```

The suite includes two independent campaign databases, deterministic partitioning, overlap handling, mismatched identities, incomplete transfers, checksum corruption, byte-identical and conflicting duplicates, long paths, full split/run/transfer/merge, and analysis handoff validation.
