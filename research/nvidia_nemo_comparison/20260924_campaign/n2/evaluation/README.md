# N2 frozen evaluation and window preparation

Purpose: prepare exact paired saved-audio manifests, model-independent E/C windows, evaluator-only Q windows, and conservative C calibration/scoring helpers. This module never opens audio devices, runs models, changes N1, or creates acoustic scenes. Research identities, transcripts and paths stay in the private output directory.

Inputs: frozen N1 `data/SCREEN_48.json`, `ENROLLMENT_ROSTER_PLAN.json`, `DATA_AUDIT_SUMMARY.json`, private N1 `ECQ_BINDINGS.json` and `CORPUS_BINDINGS_240.json`; the referenced saved audio files. `protocol.json` predeclares the comparison. Outputs: private `WINDOW_MANIFEST.json`, `EVALUATOR_TRUTH.json`, `AUDIO_ONLY.json`, `ROSTERS.json`, `MANIFEST_RECEIPT.json`; redacted preparation receipt. No thresholds or successful model results are manufactured by preparation.

Use the existing environment; no package install is needed for preparation beyond its existing soundfile, numpy and scipy. Python 3.10+ is required. Calibration helpers additionally use scipy for assignment; the existing environment includes it.

PowerShell, from any directory:

```powershell
$EvalDir = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\evaluation'
$PythonExe = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $PythonExe "$EvalDir\prepare.py"
& $PythonExe -m unittest discover -s $EvalDir -p 'test_*.py' -v
```

Command Prompt / Anaconda Prompt (the explicit interpreter avoids modifying the active conda environment):

```bat
set "EVAL_DIR=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\evaluation"
set "PYTHON_EXE=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PYTHON_EXE%" "%EVAL_DIR%\prepare.py"
"%PYTHON_EXE%" -m unittest discover -s "%EVAL_DIR%" -p "test_*.py" -v
```

Optional preparation inputs: `--n1-data PATH`, `--n1-local PATH`, `--out PATH`. Existing generated manifests must match exactly; changed inputs fail rather than overwrite frozen windows. Receipt hashes bind protocol, N1 inputs, every selected waveform and output manifest. Verify every model-specific gallery against those hashes before embedding. The primary clean E tier is the already frozen whole-clip prefix meeting approximately 15 s of estimated speech; do not crop, loop or pad a person's clips to disguise shortages. Diagnostic tiers use only identities available at 5, 15 and 30 s, without dropping missing identities from the coverage report.

`scoring.py` exports `calibrate_c`, `apply_gate`, `activity_metrics`, `cpwer`, `asr_invariance`, and `turn_coverage`. Scores are cosine similarities, never probabilities. Calibration requires explicit model/preprocessing/window/roster/domain provenance. Q is forbidden as calibration input. Processed C remains collection-only; clean-to-processed transfer remains uncalibrated for naming. No-gallery and explicit closed-roster assumptions cannot certify an identity.

`run_embeddings.py` runs one resident CPU encoder, with one compute thread pinned to one CPU at below-normal priority. Coordinate the campaign's two-worker ceiling before running it. E0 calls the original `SpeakerModels.embed` with N1-bound weights; E1 requires the actual hash-verified TitaNet export bundle. Both consume the exact 1,194 manifest windows (872 E/C and 322 evaluator-only Q). A short span below 8,000 samples is retained as unavailable. No waveform repetition/padding is performed. Inputs can be changed only through explicit CLI paths, `--encoder E0|E1`, and `--cpu NUMBER`. Each extraction caches by model/frontend/source/manifest/window hash; incompatible resume attempts fail. Source snapshots, wall time, CPU work and RSS receipts are written, with concurrent desktop work explicitly outside isolated performance claims.

PowerShell extraction after preparation:

```powershell
& $PythonExe "$EvalDir\run_embeddings.py" --encoder E0 --cpu 4
& $PythonExe "$EvalDir\run_embeddings.py" --encoder E1 --cpu 4
```

Command Prompt / Anaconda Prompt:

```bat
"%PYTHON_EXE%" "%EVAL_DIR%\run_embeddings.py" --encoder E0 --cpu 4
"%PYTHON_EXE%" "%EVAL_DIR%\run_embeddings.py" --encoder E1 --cpu 4
```

Outputs are under private `local/n2/evaluation/component/E0` and `E1`: individual hashed window vectors, `ADMISSION.json`, `PROGRESS.json`, `RESULT.json`, `GALLERY_INDEX.json`, runtime-loadable `galleries/*.json`, and evaluator-only `scores/*.json`. Gallery profiles use stable research UUIDs and generic names; vectors never leave the private directory. Galleries use the canonical namespace requested by the shared runtime. Clean templates average each whole-clip unit vector weighted by that clip's previously estimated active duration, then L2-normalize. Processed templates use the single whole captured file embedding. The weights and aggregation apply equally to E0/E1. Whole-window diagnostic C/Q comparisons are component analyses, distinct from the application's predicted 0.5–2 s evidence windows.

C calibration is re-fitted for each model/domain/duration/roster/position/stream. Pairwise EER is a descriptive verification diagnostic; correlated pairs are not independent false-known trials. Runtime Q is processed-domain and processed C is not admitted, so runtime gallery gates conservatively reject all open-world names. C-only clean gates and Q component curves remain available for analysis. Explicit closed-roster forced labels remain unverified assumptions, and are reported separately by the application. An interrupted runner may leave `RUNNING.json`; verify its PID and creation time no longer refer to a living owned process before removing only that stale lock and repeating the same command.

Finalize private runtime galleries and create redacted component results after extraction:

```powershell
& $PythonExe "$EvalDir\publish_galleries.py" --component 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E0'
& $PythonExe "$EvalDir\publish_galleries.py" --component 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E1'
& $PythonExe "$EvalDir\summarize_components.py"
```

```bat
"%PYTHON_EXE%" "%EVAL_DIR%\publish_galleries.py" --component "G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E0"
"%PYTHON_EXE%" "%EVAL_DIR%\publish_galleries.py" --component "G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E1"
"%PYTHON_EXE%" "%EVAL_DIR%\summarize_components.py"
```

Only `RUNTIME_GALLERY_INDEX_SAFE.json` is admitted to the runtime observer. It exposes E gallery metadata, without Q score/truth fields. It references finalized `runtime_galleries/*.json`. E0's preprocessing name is explicitly aliased to the established baseline `mono-float32-16k-redimnet2-native-l2-v1`; the exact graph, preprocessing and every vector remain unchanged and the original receipt is preserved. Gate hashes bind the final runtime profile payload and exact candidate UUID population. `COMPONENT_SUMMARY.json` / `COMPONENT_RESULTS.md` contain redacted component results; full scores and vectors remain private.

`runtime_observer.py` is imported by the common N2 saved-file runner; it is not a standalone model launcher. With `prototype` and `prototype/vendor` on Python's import path, construct `RuntimeGalleryObserver(embedding, gallery_index_path, output_dir, session_id)` using one encoder's safe index and the actual session ID. Call `.event(event_type, source_sec, payload)` after each actual emitter call; call `.finish(final_rows)` after all model/policy lanes drain. The root runner owns the actual transcript/audio input. The observer evaluates the 15 nonempty primary 15-second galleries with actual emitted embedding windows and actual tracker decisions. It enqueues events without waiting for naming, uses a bounded 8,192-event queue, and fails on overflow. It never loads evaluator truth or performs audio/model calls.

Observer outputs include `OBSERVER_ADMISSION.json`, actual embedding-window and per-gallery decision JSONL journals, native activity frames, the common caption event journal, each shadow condition's final S7 timestamped-span rows and first-visible/first-final/latest `_STAGES.json`, `ACTUAL_FINAL_ROWS.json`, and `OBSERVER_RESULT.json`. Gallery scores and immutable name snapshots are captured online. Expensive S7 caption replay runs only after model lanes drain, using those snapshots in original publication order; it never applies final names retrospectively. Identical uncalibrated open presentation states are shared to reduce work. The same S7 implementation receives identical source intervals, versions and span IDs. Every condition's raw and formatted words are compared with a baseline observer clone, itself compared with actual controller rows after reconstructing flattened segments by utterance/token order. Callback/worker clocks are actual; shadow presentation timing is modelled from source publications, not actual GUI/display latency. These are simultaneous online naming policy observations and causal caption replays on one model run, not independent resource trials or proof that each condition ran in a GUI.

`score_runtime.py` reads finished observer artifacts and private truth **only after inference**. Inputs are one `--observer-dir`, its audio-only `--job-id`, optional `--runtime-events` from the common runner (needed for older observer versions), and optional `--truth` override. Output `EVALUATOR_SCORE_V2.json` stays beside private observer evidence. It includes zero-collar primary and 250 ms sensitivity approximate activity metrics, source-turn/short/return/evidence denominators, actual-window naming including explicit closed assumptions, and separate caption stages. Missing ambient/word-time/activity support stays unavailable. A first-visible partial hypothesis against full reference is labelled a diagnostic, not final lexical accuracy. Old `EVALUATOR_SCORE.json` is preserved.

```powershell
& $PythonExe "$EvalDir\score_runtime.py" --observer-dir 'G:\path\to\attempt\galleries' --job-id N2_S45_01_04_O0 --runtime-events 'G:\path\to\attempt\RUNTIME_EVENTS.jsonl'
```

```bat
"%PYTHON_EXE%" "%EVAL_DIR%\score_runtime.py" --observer-dir "G:\path\to\attempt\galleries" --job-id N2_S45_01_04_O0 --runtime-events "G:\path\to\attempt\RUNTIME_EVENTS.jsonl"
```

The actual component extraction used the hash-bound v1 sources preserved in private `local/n2/evaluation/executed_source_v1`. Subsequent source review added cached-vector shape/finite/L2 validation and corrected matched-diagnostic metadata to distinguish deliberately excluded roster identities from missing eligible references; numerical scores/vectors remain unchanged. Existing extraction receipts stay immutable. A fresh extraction with the reviewed runner must use `--out G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component_v2` (or another new campaign-private directory); the runner refuses to silently reuse a cache made by different code. The published summary corrects matched denominators without rewriting original results.

For a no-gallery attempt use `score_runtime.py --attempt-dir G:\path\to\attempt --job-id N2_S45_01_04_O0`. It reads `FINAL_SNAPSHOT.json` and `RUNTIME_EVENTS.jsonl` and writes `EVALUATOR_ACTIVITY_SCORE_V2.json`, retaining explicit unavailable naming/full-D0-activity metrics. The module functions are available for a batch runner: `score(observer_dir, job_id, truth_path, runtime_events=None)` and `score_activity_attempt(attempt_dir, job_id, truth_path)`.

`summarize_screen.py` scores completed cells from the four common Controller `RESULT_INDEX.json` files and produces a redacted comparison. It runs no audio or models. Inputs are repeated `--index PATH` arguments, private `--truth` (default prepared `EVALUATOR_TRUTH.json`), the adjacent frozen roster/manifest receipt, and the results' bound runtime events, snapshots and optional gallery observer files. It checks contract, source-audio/gain, checkpoint and evidence hashes. Outputs are private `SCREEN_EVIDENCE.json` under `--out`, and public `SCREEN_SUMMARY.json` / `SCREEN_SUMMARY.md` under `--public-out`. Cell evaluator V2 scores are also written beside private runtime evidence. Public outputs contain aggregate counts and hashes, with no source audio, vectors, speaker names/identities, transcripts or waveform paths.

Use the variables defined above, and replace the four example index paths with the actual run directories. PowerShell:

```powershell
& $PythonExe "$EvalDir\summarize_screen.py" --index 'G:\path\to\D0_E0\RESULT_INDEX.json' --index 'G:\path\to\D1_E0\RESULT_INDEX.json' --index 'G:\path\to\D0_E1\RESULT_INDEX.json' --index 'G:\path\to\D1_E1\RESULT_INDEX.json' --out 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\screen_summary' --public-out $EvalDir --require-complete
```

Command Prompt / Anaconda Prompt:

```bat
"%PYTHON_EXE%" "%EVAL_DIR%\summarize_screen.py" --index "G:\path\to\D0_E0\RESULT_INDEX.json" --index "G:\path\to\D1_E0\RESULT_INDEX.json" --index "G:\path\to\D0_E1\RESULT_INDEX.json" --index "G:\path\to\D1_E1\RESULT_INDEX.json" --out "G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\screen_summary" --public-out "%EVAL_DIR%" --require-complete
```

For preflight, pass whichever indexes exist and omit `--require-complete`; choose separate output directories to retain that preflight. `PARTIAL` never means the fixed 96 × 4 screen is complete. Runtime/scoring failures and missing cells remain in the original denominator. The complete flag also requires exact ASR and caption invariance; lexical/source-bound mismatches receive explicit failed statuses. Four-way matched cells are reported separately from all completed cells, with O0/O1 and CPU/CUDA library/model/source hashes separated. The ASR comparator hashes exact `s6d_text_ready` observations, final text, and source dispatch/reset semantics against D0/E0, excluding compute/publication clocks, session IDs and labels. Formatted words are compared separately. No missing event sequence can establish invariance.

The summary retains zero-collar activity DER/JER plus the 250 ms sensitivity's retained/excluded wall and speaker-time denominators. D0 full activity remains unavailable; its turn/return/merge/split counts use actual embedding-decision window support and are labelled a proxy. Short turns retain both unresolved-track and no-evidence counts. Evidence coverage includes summed active-speaker duration with any window intersection, which does not certify usable identity evidence. Known-reference and incomplete-ambient conditions are separated. cpWER uses complete lexical references and includes Unknown; empty controls preserve inserted words. The shadow conditions retain first-visible, first-final and latest snapshots; actual main GUI first-stage full snapshots remain unavailable in these receipts. Actual final Controller text is authoritative. Process CPU/RSS/queue and recorded operation counts remain qualified; native calls that emit no recorded frame event cannot be counted from that journal.

Run a separately admitted regression population with the same command plus `--scope regression --expected-manifest G:\path\to\REGRESSION_AUDIO_ONLY.json`, four regression indexes, and distinct private/public output directories. Regression jobs must already exist in the frozen evaluator truth; they cannot be silently combined with Screen48. `test_summarize_screen.py` verifies exact text/source/reset invariance, actual receipt tampering rejection, full/partial population status, empty-control errors, and public redaction without audio/model calls. Run it with `& $PythonExe -m unittest discover -s $EvalDir -p 'test_summarize_screen.py' -v` in PowerShell, or `"%PYTHON_EXE%" -m unittest discover -s "%EVAL_DIR%" -p "test_summarize_screen.py" -v` in Command Prompt/Anaconda Prompt.

`summarize_native_profiles.py` evaluates the separate pure Nemotron screen. Its input is one native `run_fixed_screen.py` `RESULT_INDEX.json`, the adjacent hash-bound `ADMISSION.json`, completed checkpoint/result/probability/availability files, and the same private frozen evaluator truth. The full population is exactly 96 audio cells × three profiles = 288, even when the input is partial or admits fewer profiles. It runs no models. It accepts the historical scheduler alias `N1_BASELINE_S45_xx_yy_Ot` → `N2_S45_xx_yy_Ot` only when every other audio-job field is exactly equal. The original frozen `SCREEN_48.json` hash must agree. Original IDs and the alias mapping remain in the private receipt; changing an identifier never changes audio or requires another inference run.

Native outputs are private `NATIVE_PROFILE_EVIDENCE.json`, and redacted `NATIVE_PROFILE_SUMMARY.json` / `NATIVE_PROFILE_SUMMARY.md` under the specified public directory. Both summary programs capture the exact input index bytes privately before scoring, so a running coordinator can advance its index without changing the scored population's provenance. `--require-complete` exits unsuccessfully unless the entire admitted fixed population succeeds. Use separate output directories to preserve earlier partial summaries. Each native cell is checked against its original checkpoint, model/library/profile/device/source hashes, probability array, monotone availability journal and delivered sample count. Raw extra endpoint frames remain intact; scoring intersects only the actually delivered waveform per publication.

PowerShell native scoring (the numerical runner must already have produced its receipts):

```powershell
& $PythonExe "$EvalDir\summarize_native_profiles.py" --index 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\fixed-cuda-all-v1\RESULT_INDEX.json' --out 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\native_profile_summary' --public-out $EvalDir --require-complete
```

Command Prompt / Anaconda Prompt:

```bat
"%PYTHON_EXE%" "%EVAL_DIR%\summarize_native_profiles.py" --index "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\fixed-cuda-all-v1\RESULT_INDEX.json" --out "G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\native_profile_summary" --public-out "%EVAL_DIR%" --require-complete
```

Native metrics use the same zero-collar primary / 250 ms sensitivity amendment, with actual frame support, complete-reference restrictions, all source turns, short replies, unresolved returns, merges/splits and eight-slot saturation counts. A turn tied across slots stays unresolved. Saturation at the fixed 0.5 activity threshold is descriptive and does not prove an extra speaker. This runner has no embedding, gallery, naming or ASR evidence; those metrics are explicitly not run. Its actual call durations and accelerated wall/audio ratios exclude model loading and are not application caption latency. Model/library/device strata remain separate; process CPU/RSS does not establish isolated GPU memory, CM5/Pi suitability or a total 2 GB budget. Matched profile ratios use the identical cells and tap against `low_latency`.

Historical native coordinator error receipts are bound separately from numerical-cell failures. After a valid unchanged-cache resume, a complete 288-cell numerical result can retain an earlier coordinator I/O incident. Resource totals sum individual completed-cell receipts, not the most recent coordinator launch's elapsed time. Activity breakdowns by reference class preserve empty-control false alarms even when that control has no individual speech denominator.

`test_native_summary.py` checks raw extra endpoint preservation, supported activity scoring, saturation with unresolved ties, incomplete references, malformed probability/availability rejection, and strict scheduler alias identity. Run with `& $PythonExe -m unittest discover -s $EvalDir -p 'test_native_summary.py' -v` in PowerShell, or `"%PYTHON_EXE%" -m unittest discover -s "%EVAL_DIR%" -p "test_native_summary.py" -v` in Command Prompt/Anaconda Prompt. These checks perform no audio/model calls.

Final read-only verification, with no model or hardware calls:

```powershell
& $PythonExe "$EvalDir\audit_evaluation.py"
```

```bat
"%PYTHON_EXE%" "%EVAL_DIR%\audit_evaluation.py"
```

This checks all frozen preparation inputs/outputs, runtime gallery hashes, all 2,388 stored component vectors for shape/finite/L2 validity, the preserved executed-runner hash, and the regression suite. It writes `EVALUATION_AUDIT.json` with current source hashes and test output. It does not re-run the models or replace prior runtime failures.

`prepare_regression.py` prepares the exact existing eight-job regression manifest for N2. It reads private `local/data/REGRESSION_AUDIO_ONLY.json`, the frozen N2 evaluator truth and its manifest receipt, and the eight accepted saved waveforms. It verifies waveform hashes and mono PCM16/16 kHz headers, paired frame counts, gain 1 and reset flags. Its sole data change is the scheduler prefix `N1_REGRESSION_` to `N2_`; every other job and root manifest field is preserved. It writes private `local/n2/evaluation/REGRESSION_AUDIO_ONLY.json` and the redacted `REGRESSION_PREPARATION_RECEIPT_V1.json` here. Existing outputs must match exactly. No audio is created, played or inferred. Optional inputs are `--source PATH`, `--truth PATH` and `--out PATH`; changing frozen inputs requires a separately versioned preparation receipt.

PowerShell preparation and verification:

```powershell
& $PythonExe -B "$EvalDir\prepare_regression.py"
& $PythonExe -B "$EvalDir\audit_evaluation.py"
```

Command Prompt / Anaconda Prompt:

```bat
"%PYTHON_EXE%" -B "%EVAL_DIR%\prepare_regression.py"
"%PYTHON_EXE%" -B "%EVAL_DIR%\audit_evaluation.py"
```

For the four regression result indexes, add `--scope regression --expected-manifest G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\REGRESSION_AUDIO_ONLY.json` to the four-index summary command above. The regression denominator is eight jobs per combination, 32 total; it is separate from the 384-cell main screen. The source noise control remains in Screen48. The audit also verifies the regression generator/input/output/alias bindings and that the nominal decision and its original protocol, collar amendment and native summary remain unchanged.

`NOMINAL_PROFILE_DECISION_V1.json` and its Markdown companion are immutable decision artifacts, not executable code. Their purpose is to bind the pre-factorial selection of `low_latency` to the original preference and complete 288-cell native sensitivity results, including both collar denominators and noise failures. They contain no transcript, waveform or vectors. Do not overwrite this version; a later decision needs a new version and an explicit supersedes binding. Check its JSON SHA-256 with `Get-FileHash "$EvalDir\NOMINAL_PROFILE_DECISION_V1.json" -Algorithm SHA256` in PowerShell, or `certutil -hashfile "%EVAL_DIR%\NOMINAL_PROFILE_DECISION_V1.json" SHA256` in Command Prompt/Anaconda Prompt. Expected hash: `09b86b287ae76f64f13bddd26ae30a7aa26d3f6ab12f94c2093e176ebdf30eac`.

`SCREEN_SMOKE_READINESS_REVIEW_V1.md` documents the reviewed parser, admission and event/archive gates and gives exact read-only scoring commands. `FOUR_WAY_SMOKE_RECEIPT_V1.json` is the redacted four-cell readiness receipt. Its `NOT_FULL_SCREEN` classification is deliberate: each combination has only one of 96 jobs, and the main experiment remains incomplete. It preserves D0 tracking failures, the older D0/E1 archive counter limitation, and the v3/v4/v5 source distinctions. Full source words and per-condition rows stay in private evidence. These artifacts do not launch the main experiment or establish GUI/deployment acceptance.

Activity references already include the historical 800-sample RIR convention; only the saved per-tap output offset is added. Source whole-clip diagnostic support adds that existing convention once. Out-of-file support is flagged unavailable, never silently clamped. DER/JER are approximate activity metrics on a 20 ms grid with included overlap, restricted to complete-reference scenes. Amendment 01 makes zero collar primary and retains the 250 ms collar as mandatory sensitivity. They are not publishable phonetic DER. cpWER has a lexical stream/permutation scope and no word-timing claim. tcpWER is unavailable. All 240 scenes remain in evaluator truth; the screen retains exactly 48 × 2 runtime cells. The known N1 noise control S45_12_20 inserted one word per tap and stays a failure baseline.
