# Campaign Core01 Run Guide

## Purpose and current status

`campaign_core01` is a conservative first real campaign for qualifying the ordinary Evaluation Tool campaign workflow before larger screening runs. It uses:

- the immutable `small` benchmark manifest;
- the `controlled_clean` panel;
- seed `3800`;
- Whisper Base on CPU;
- full-record input with VAD, segmentation, speaker processing, and diarization disabled;
- clean, white-noise, pink-noise, and DiningRoom RIR conditions;
- one model-heavy scenario at a time.

The campaign contains 12 globally identified scenarios and 660 total prediction rows. The work is split into two non-overlapping assignments of six scenarios and 330 rows each.

As of 2026-08-10:

- `scenario_8cff9abad3fc` completed successfully through inference, standardized predictions, scoring, plotting, reporting, telemetry, and artifact validation;
- 11 scenarios remain pending;
- campaign validation passes;
- no API key or external service credential is needed for this campaign;
- the Whisper Base asset is already present and its SHA-256 matches the recorded model identity.

The earlier `campaign_quickstart` failure is retained as diagnostic evidence. Its inference and scoring finished, but final artifact publication encountered a generator-length defect. That defect and the current artifact-registry assignment compatibility defect were corrected and covered by regression tests before `campaign_core01` was created.

## Important code-version gate before using a second computer

The two fixes are presently in the local working tree, while both assignment files record Git commit:

```text
4e1c1e7cea17bfdea87f4af6c4ae1d23d5052f44
```

Cloning that commit alone does **not** include the uncommitted fixes. Before the friend runs anything, Amir must either:

1. commit and push the tested fixes, then recreate the campaign and assignments so they record the new commit; or
2. transfer and apply the exact reviewed patch to the friend's clone and verify that both working trees are identical.

The first option is recommended. Do not edit `expected_git_commit` in an assignment by hand. Regenerate assignments after committing so the recorded identity remains truthful.

This guide does not commit or push changes automatically.

## Files already generated

Run all commands from:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool
```

The generated files are:

```text
automated_runs\campaign_core01\campaign_manifest.json
automated_runs\campaign_core01\campaign_manifest.sha256
automated_runs\campaign_core01\benchmark_manifests\small_source_manifest.parquet
automated_runs\campaign_core01\worker_assignments\worker_amir.yaml
automated_runs\campaign_core01\worker_assignments\worker_friend.yaml
automated_runs\campaign_core01\scenarios\<scenario_id>\...
```

Important identities:

| Item | Identity |
|---|---|
| Campaign | `campaign_core01` |
| Campaign manifest SHA-256 | `7EA60C034344FAAE0DC7EF0B6489916FF30E415985323FB9442718E47797E6F6` |
| Benchmark manifest | `manifest_0bd28359f11a` |
| Benchmark manifest SHA-256 | `0BD28359F11AB283C349386BB5DFC78E52C3C1E8B4EDE271551F5029C9FC44F6` |
| Amir assignment | `assignment_7206ee2bb55c` |
| Friend assignment | `assignment_6412dae52b84` |

## Campaign scope

| Scenario | Dataset | Rows | Condition | Worker | Current state |
|---|---:|---:|---|---|---|
| `scenario_01aa02f9a7d4` | LibriSpeech | 60 | DiningRoom RIR | Amir | pending |
| `scenario_10a46594e616` | CMU Arctic | 90 | pink noise, 10 dB | Amir | pending |
| `scenario_3032e61b2ed5` | HiFiTTS | 15 | DiningRoom RIR | Amir | pending |
| `scenario_8cff9abad3fc` | CMU Arctic | 90 | clean | Amir | succeeded |
| `scenario_985b27ddeab0` | LibriSpeech | 60 | white noise, 10 dB | Amir | pending |
| `scenario_eb7dbc0fccff` | HiFiTTS | 15 | white noise, 10 dB | Amir | pending |
| `scenario_416585f6ad95` | CMU Arctic | 90 | DiningRoom RIR | Friend | pending |
| `scenario_5509d22d611d` | HiFiTTS | 15 | clean | Friend | pending |
| `scenario_6b22a27ab5d0` | CMU Arctic | 90 | white noise, 10 dB | Friend | pending |
| `scenario_cfbbf67cac76` | LibriSpeech | 60 | pink noise, 10 dB | Friend | pending |
| `scenario_d40313a3c3f1` | HiFiTTS | 15 | pink noise, 10 dB | Friend | pending |
| `scenario_e179e764d5c6` | LibriSpeech | 60 | clean | Friend | pending |

Bedroom is unresolved in the current RIR registry, and the frozen scenario catalog does not currently contain a Restaurant scenario for this pipeline and tier. No substitutions or hand-edited scenario identities were made. This first campaign therefore contains DiningRoom only. Add Bedroom and Restaurant later through a new, versioned scenario contract once their approved records are available.

## 1. Open Anaconda Prompt and activate the environment

In Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
call "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\activate.bat"
python --version
python -m pip check
```

If activation is inconvenient, replace `python` in every command with:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe
```

Do not install or update packages between workers after assignments are frozen. Each worker should retain the environment fingerprint produced by the framework.

## 2. Verify local prerequisites

On each computer, from its complete repository clone:

```bat
python ..\..\scripts\verify_install.py --profile dev --device cpu --cache-root ..\..\models\cache --whisper tiny,base,small --require-models
python run_evaluation.py campaign validate --campaign-root automated_runs\campaign_core01
python run_evaluation.py campaign status --campaign-root automated_runs\campaign_core01
```

On Amir's machine the readiness script currently finds all three approved Whisper assets and the required Python packages, but returns a nonzero status because `ffmpeg` is not on `PATH`. The real WAV-based Whisper Base scenario still completed successfully because this path did not need FFmpeg. Treat FFmpeg as an outstanding machine prerequisite for broader audio-format coverage; it is not an API credential and must not be downloaded implicitly by a campaign run. Both workers should record whether it is available so their environments can be compared honestly.

The worker must also have the source datasets and RIR collection at the paths expected by its normalized metadata and scenario configuration. Source audio is not copied into the campaign package.

Stop if validation reports a mismatched campaign hash, benchmark hash, Git commit, environment profile, model asset, seed, or scenario identity. Fix the underlying mismatch; do not edit generated identities.

Validate the complete split on Amir's coordinator copy:

```bat
python run_evaluation.py campaign validate-assignments --campaign-root automated_runs\campaign_core01 --assignment automated_runs\campaign_core01\worker_assignments\worker_amir.yaml --assignment automated_runs\campaign_core01\worker_assignments\worker_friend.yaml
```

Expected result: 12 assigned scenarios, no overlaps, no missing scenario IDs, and `valid: true`.

## 3. Inspect and dry-run each assignment

Amir:

```bat
python run_evaluation.py campaign run-assignment --campaign-root automated_runs\campaign_core01 --assignment automated_runs\campaign_core01\worker_assignments\worker_amir.yaml --environment-profile core-cpu --dry-run
```

Friend, after preparing a worker copy as described below:

```bat
python run_evaluation.py campaign run-assignment --campaign-root C:\worker_campaigns\friend_core01 --assignment C:\worker_campaigns\friend_core01\worker_assignments\worker_friend.yaml --environment-profile core-cpu --dry-run
```

The dry run must show only the six scenario IDs in that worker's assignment. The successful Amir scenario should be recognized as complete and skipped when the real assignment resumes.

## 4. Prepare the friend's independent campaign copy

After the code-version gate is satisfied, Amir prepares a checksummed worker copy:

```bat
python run_evaluation.py campaign prepare-worker-copy --campaign-root automated_runs\campaign_core01 --assignment automated_runs\campaign_core01\worker_assignments\worker_friend.yaml --destination C:\worker_campaigns\friend_core01
```

Transfer `C:\worker_campaigns\friend_core01` to the friend without altering its contents. The friend places it at the same location or adjusts both command paths consistently. The friend's repository clone supplies code, dependencies, datasets, and model assets; the worker copy supplies the immutable campaign, scenarios, and assignment.

Do not run both assignments against one SQLite database on a network share. Each person runs an independent local campaign copy and returns a checksummed result package.

## 5. Run Amir's remaining assignment

From Amir's Evaluation Tool directory:

```bat
python run_evaluation.py campaign run-assignment --campaign-root automated_runs\campaign_core01 --assignment automated_runs\campaign_core01\worker_assignments\worker_amir.yaml --environment-profile core-cpu
```

This command validates the assignment, skips the already completed scenario, and runs the remaining assigned scenarios in deterministic order. Keep the terminal open. The executor persists status, attempts, heartbeats, partial artifacts, and events as it works.

## 6. Run the friend's assignment

From the friend's Evaluation Tool clone:

```bat
python run_evaluation.py campaign run-assignment --campaign-root C:\worker_campaigns\friend_core01 --assignment C:\worker_campaigns\friend_core01\worker_assignments\worker_friend.yaml --environment-profile core-cpu
```

Use one model-heavy scenario at a time. Do not add parallel GPU execution to this first CPU contract campaign.

## 7. Monitor, stop, and resume safely

View progress:

```bat
python run_evaluation.py campaign status --campaign-root automated_runs\campaign_core01
python run_evaluation.py campaign list --campaign-root automated_runs\campaign_core01
```

On the friend's copy, replace the campaign root with `C:\worker_campaigns\friend_core01`.

Press `Ctrl+C` once for a safe interruption. To continue the same assignment, rerun the same `run-assignment` command. Valid completed scenarios are revalidated and skipped.

To request an explicit campaign stop:

```bat
python run_evaluation.py campaign stop --campaign-root automated_runs\campaign_core01 --reason "operator requested stop"
```

Inspect command help before clearing or changing a stop request:

```bat
python run_evaluation.py campaign --help
```

Do not delete scenario directories to force a retry. Use the campaign status and retry commands so attempts remain auditable.

## 8. Validate completed artifacts

Each worker validates its campaign root after execution:

```bat
python run_evaluation.py campaign validate --campaign-root automated_runs\campaign_core01
python run_evaluation.py campaign validate-artifacts --campaign-root automated_runs\campaign_core01
```

Friend:

```bat
python run_evaluation.py campaign validate --campaign-root C:\worker_campaigns\friend_core01
python run_evaluation.py campaign validate-artifacts --campaign-root C:\worker_campaigns\friend_core01
```

A successful scenario is not complete unless its state, schemas, expected counts, and checksums all validate.

## 9. Export each worker's result package

Amir:

```bat
python run_evaluation.py campaign export-results --campaign-root automated_runs\campaign_core01 --assignment automated_runs\campaign_core01\worker_assignments\worker_amir.yaml --environment-profile core-cpu --destination C:\transfer\transfer_amir_core01
```

Friend:

```bat
python run_evaluation.py campaign export-results --campaign-root C:\worker_campaigns\friend_core01 --assignment C:\worker_campaigns\friend_core01\worker_assignments\worker_friend.yaml --environment-profile core-cpu --destination C:\transfer\transfer_friend_core01
```

The friend transfers the complete `transfer_friend_core01` directory to Amir. Do not copy only prediction files; merge validation also needs manifests, status, diagnostics, checksums, environment identity, metrics, reports, and logs.

## 10. Validate and merge on Amir's computer

Place both transfer directories under `C:\transfer`, then run:

```bat
python run_evaluation.py campaign validate-transfer --campaign-root automated_runs\campaign_core01 --transfer-root C:\transfer\transfer_amir_core01
python run_evaluation.py campaign validate-transfer --campaign-root automated_runs\campaign_core01 --transfer-root C:\transfer\transfer_friend_core01
python run_evaluation.py campaign merge-results --campaign-root automated_runs\campaign_core01 --transfer-root C:\transfer\transfer_amir_core01 --transfer-root C:\transfer\transfer_friend_core01
python run_evaluation.py campaign validate-merged --campaign-root automated_runs\campaign_core01
```

The merge must report:

- all 12 global scenario IDs present;
- no assignment overlap;
- no conflicting duplicate;
- no incomplete transfer;
- valid checksums and schemas;
- any machine or environment differences explicitly recorded.

Byte-identical duplicates may be recognized, but conflicting duplicates must never be overwritten.

## 11. Build the analysis outputs

Only after merged validation passes:

```bat
python run_evaluation.py analysis index --campaign-root automated_runs\campaign_core01
python run_evaluation.py analysis validate --campaign-root automated_runs\campaign_core01
python run_evaluation.py analysis coverage --campaign-root automated_runs\campaign_core01
python run_evaluation.py analysis run --campaign-root automated_runs\campaign_core01
python run_evaluation.py analysis release-status --campaign-root automated_runs\campaign_core01
```

This is a first contract and workflow qualification campaign, not a release benchmark or final model-selection study. Interpret its WER, CER, timing, resource, and reliability outputs as evidence that the machinery works and as an initial Whisper Base baseline.

## Inputs and outputs

Primary inputs:

- frozen Parquet benchmark manifest;
- normalized metadata pointing to local source audio;
- immutable scenario definitions;
- Whisper Base model asset;
- white/pink noise settings or exact DiningRoom RIR identity;
- assignment YAML identifying globally stable scenarios.

Each scenario stores outputs under:

```text
automated_runs\campaign_core01\scenarios\<scenario_id>\
  resolved_scenario.json
  run_config.yaml
  status.json
  predictions\
  metrics\
  resource_logs\
  logs\
  report\
  checksums.json
```

The later analyst should begin with the campaign's merged result index and analysis manifest, not arbitrary individual files. The campaign manifest, benchmark hash, assignment files, scenario IDs, environment fingerprints, and checksums provide the handoff contract.

## Common problems

| Symptom | Required action |
|---|---|
| Assignment says Git commit mismatch | Put both workers on the exact same committed code and regenerate assignments; do not edit YAML hashes |
| Model unavailable or hash mismatch | Restore the approved offline model asset; do not permit an implicit download |
| Dataset/RIR file missing | Restore the expected local source file/path; do not substitute another recording or RIR |
| Scenario failed but others continue | Inspect its `logs\errors.jsonl`, `logs\runner.log`, status, and diagnostics; retain the failed output |
| Valid success is skipped on resume | This is expected and protects completed work |
| Corrupt success is not skipped | This is expected; restore/retransfer valid artifacts before retry or merge |
| Transfer validation fails | Recopy the entire exported package; do not recalculate checksums to legitimize edited files |
| Bedroom or Restaurant is absent | Expected for this frozen campaign; create a new versioned campaign later rather than changing these scenarios |
