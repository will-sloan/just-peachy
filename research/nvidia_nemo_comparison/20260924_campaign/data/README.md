# N1 saved corpus and reference binding

`bind_corpus.py` verifies the authoritative 240 accepted physical capture pairs, all 480 prepared mono tap inputs, full original/normalized transcripts, E/C/Q references, and existing processed enrollment audio. It freezes a deterministic 48-scene screen using input metadata only. It does not load a model, enumerate audio devices, open a microphone, play audio, contact the Pi, change personal galleries, or produce new acoustic scenes.

The existing `.edge-speech-env` supplies Python, NumPy and SoundFile. C: and G: must be mounted at their recorded locations. No installation or activation is required. It reads existing evidence in the original repository and the saved S4.5/S6B/S6C/S6D disk trees. Full transcripts and detailed private references are written only under the `--local` directory outside the worktree.

From PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\data\bind_corpus.py'
```

From Command Prompt or Anaconda Prompt, enter the same command without PowerShell's leading `&`:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\data\bind_corpus.py"
```

Optional inputs are `--repo` (original evidence repository), `--worktree` (Git privacy boundary), `--out` (redacted report directory), and `--local` (private report directory). Run `--help` for their defaults. The script is serial, reads each unique bound file once per run, and makes no raw-audio copies. It refuses hash mismatches, mixed physical passes, duplicate gain, reference overlap, population changes, and changes to a previously frozen panel. Rerunning reproduces the screen and re-verifies evidence; the verification timestamp changes.

Outputs suitable for review/Git:

- `CORPUS_CATALOGUE_240.csv`: one row per scene, both tap hashes and metadata/reference limitations; no transcript text.
- `SCREEN_48.json` and `SCREEN_48.csv`: immutable panel identities, both taps, four scenes per family.
- `ENROLLMENT_CAPABILITY_MATRIX.csv`: person/duration/domain/stream availability, without vectors.
- `ECQ_AUDIT.json` and `DATA_AUDIT_SUMMARY.json`: aggregate counts, verification receipts and local evidence hashes.
- `ECQ_PLAN.md`, `METRIC_LIMITATIONS.md`, `REGRESSION_LIST.json`, and `BASELINE_RUNNER_PROPOSAL.md`: declared use and interpretation.

Private outputs in `G:\Just_Peachy_N1\20260924_campaign\local\data`:

- `CORPUS_BINDINGS_240.json`: exact filenames, capture IDs, mappings, roles, activity and full scene references.
- `FULL_TRANSCRIPT_AUDIT.json`: all 777 utterance occurrences and original/normalized source text.
- `ECQ_BINDINGS.json`: full E/C/Q source rows and processed reference mappings.
- `FILE_HASH_AUDIT.json`: every audited file's exact path, size and SHA-256.
- `BASELINE_SCREEN_AUDIO_ONLY.json`: 96 inference jobs, containing only audio path/hash, sample count, sample rate, tap and unity runtime gain. No reference text, activity, identities or seats are passed to inference.

Prepared O0 already contains the historical +3 dB scalar exactly once; O1 is unity. Both must be consumed at runtime gain 1.0. The 800-sample/50 ms RIR convention is already included in saved activity. It is not a physical-latency measurement. The catalogue retains all 240 scenes, including incomplete references and empty controls. Historical 180/60 assignments are metadata and create no N1 holdout.

This script is an integrity/reference audit, not a model benchmark or a physical hardware test. Baseline inference has its own execution receipts and must use the repaired frozen common core.

`bind_supplemental.py` takes the already-generated local corpus/ECQ bindings, verifies 12 existing processed C captures (72 mono conditions), freezes 84 concrete domain/duration/roster conditions without model/query-dependent selection, and binds four explicitly separate saved regression scenes including C105 and digital silence. Run it after `bind_corpus.py` using the same PowerShell or CMD/Anaconda commands above with the script filename replaced by `bind_supplemental.py`. It accepts `--repo`, `--out`, and `--local` with the same defaults. Outputs are redacted `PROCESSED_C_CAPABILITY.csv`, `PROCESSED_C_AUDIT.json`, `ENROLLMENT_ROSTER_PLAN.json`, `REGRESSION_LIST.json`, and private `PROCESSED_C_BINDINGS.json`, `HISTORICAL_BOUNDARY_BINDINGS.json`, `REGRESSION_AUDIO_ONLY.json`. These are data integrity checks, not model inference. Processed C is accepted for collection only; it has no admitted exact source-to-output gold projection, so the existing clean C condition remains the usable declared calibration reference until a separate review.

## Run the baseline screen

`run_baseline_screen.py` uses an explicit frozen prototype directory, the private audio-only manifest and the installed content-addressed model cache. Substitute the actual frozen prototype path for `G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype` if the release receipt names a different directory. Never point a running job at source being edited.

PowerShell preparation (hash/header checks, no model loading):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\data\run_baseline_screen.py' --source 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype' --manifest 'G:\Just_Peachy_N1\20260924_campaign\local\data\BASELINE_SCREEN_AUDIO_ONLY.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\baseline_screen_v1' --workers 2 --prepare-only
```

For the first two actual source-paced cells, replace `--prepare-only` with `--limit 2`. To execute/resume the full panel after a successful smoke, remove `--limit 2` and leave the remaining arguments unchanged. Completed matching cells are skipped after hash verification. Add `--retry-failed` only to create new attempts for prior failed cells. `--workers 1` runs a single resident stack. `--progress <absolute-path.json>` selects the parent-owned status location. The default model root is `C:\Users\amiri\JustPeachy\shared\models`; use `--models` only when the release receipt identifies another cache.

Command Prompt or Anaconda Prompt preparation:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\data\run_baseline_screen.py" --source "G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype" --manifest "G:\Just_Peachy_N1\20260924_campaign\local\data\BASELINE_SCREEN_AUDIO_ONLY.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\baseline_screen_v1" --workers 2 --prepare-only
```

The same flag substitutions apply. Numerical work runs without desktop interaction. The source-speed floor is 71.51 minutes for one worker or 35.76 minutes for two, plus startup/finalization overhead. Actual receipt timestamps determine completion.

Runner outputs are `ADMISSION.json` (complete reproducibility contract), `PROGRESS.json` (aggregate state), `RESULT_INDEX.json` (cell result paths), and `cells/<job_id>/CHECKPOINT.json`. Each attempt retains native session journals, a final shared-controller snapshot, bounded process samples, heartbeat, checks and evidence hashes. These contain text/private evaluation evidence and must remain outside Git. Ctrl+C stops this runner's owned worker processes; rerun the exact command to resume intact completed cells. An interrupted attempt stays preserved and does not count as complete.

## Analyze completed baseline evidence

`summarize_baseline.py` verifies completed output/cache/evidence bindings, all selected model files, source hashes and runtime versions. It reads full native event, clock, transcript and conversation journals locally, then emits only transcript-free counts, integrity results, source span ownership and optional aggregate lexical metrics. It neither runs models nor rewrites outputs. GUI rendering needs the separate GUI receipt.

PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\data\summarize_baseline.py' --run 'G:\Just_Peachy_N1\20260924_campaign\local\baseline_screen_v1' --source 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype' --include-lexical
```

For Command Prompt/Anaconda Prompt use the same command without `&`, changing single quote marks to double quote marks. Inputs: `--run`, frozen `--source`, optional private `--corpus`, output `--out` and filename `--prefix`. The default outputs are `BASELINE_ANALYSIS_CELLS.csv` and `BASELINE_ANALYSIS_SUMMARY.json` beside the scripts. For the separate regression run use its directory and `--prefix REGRESSION_ANALYSIS`. An explicit interim audit can use `--allow-partial --prefix BASELINE_INTERIM`; it is labelled `PARTIAL_NOT_ACCEPTANCE` and cannot stand in for final 96-cell acceptance.

`--include-lexical` computes conventional edit-distance WER only on complete nonoverlap scenes. It deletes ASCII punctuation, lowercases and splits model text, matching the frozen S4.5 reference normalization; the original reference-normalized text is retained. Empty, overlap and incomplete-reference scenes remain in all integrity/event summaries, with their specific omitted-WER reasons. This is descriptive baseline evidence, not a model comparison, exact word-timing test or Pi benchmark.

The exact historical C105 boundary script was separately rerun without neural or hardware calls:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_application_boundary.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\data\c105_boundary_exact_replay'
```

That historical script requires a new output directory for each invocation; preserve the existing receipt and choose a new suffix to repeat. It consumes the exact previously bound C105 cached/native events, saved research vectors/gallery and telemetry, then tests observed/tie/±1 ms scheduling overlays. Its ten source-only variants preserved every raw word. This does not establish a new neural attribution fix or physical timing improvement. Local result: `local/data/c105_boundary_exact_replay/RESULT.json`.

## Check runner admission and resume guards

`check_runner_protocol.py` creates isolated metadata fixtures outside Git and invokes only the runner's `--prepare-only` path. It verifies a live one-writer lock rejection, changed-contract rejection, hash-verified reuse of one actually completed N1 cell, and rejection of a changed result hash. It never alters the original baseline result, lock or progress files; it never starts or kills an inference worker. At least one completed real cell must already exist. Supervision's worker-failure tests have a separate receipt.

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\data\check_runner_protocol.py' --source 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype' --run 'G:\Just_Peachy_N1\20260924_campaign\local\baseline_screen_v1'
```

From Command Prompt or Anaconda Prompt remove `&` and replace the single quotes with double quotes. Optional `--local` chooses the private fixture parent; each run creates a uniquely named subdirectory. Optional `--out` chooses the redacted `RUNNER_PROTOCOL_RECEIPT.json` location. Exact commands/stdout/stderr and copied metadata stay in the local fixture directory.
