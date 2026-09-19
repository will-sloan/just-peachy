# S6D operational width scorer adapter

`s6d_angle_width_score.py` prepares and, only after root admission, scores the
exact C079/C120 × 2/5/10/20-degree × O0/O1 × 240-case matrix. It calls the
unchanged `s6c_analysis_v3.analyze` and `tables` lower APIs. It never invokes the
S6C runner, changes its REPORT globals, edits a registry, launches a model, opens
audio, talks to hardware, or changes the manual +/-5-degree reference metadata.

Inputs are the root's `ANALYSIS_PREDECLARATION_V1.json`, its bound width plan,
original full-bank/input/support bindings, and the exact inherited scorer graph.
Preparation verifies 1920 frozen parent/cue-off prediction and score bindings,
including each score's analysis identity, code, bank, support, tap and population.
It does not calculate a new score. It writes `ADAPTER_PLAN.json` and a source
snapshot with 3840 expected output paths and 1920 reusable exact control scores.
This metadata plan creates no execution authorization.

The later execute action requires a root-created authorization binding that
adapter plan and an ordered list of literal complete replay-index bindings.
All 16 jobs and 3840 unique outputs must be present. The adapter validates each
prediction's width-only profile, parent, native evidence, telemetry, plan/cell
identity and actual raw ASR words. It scores new predictions under the original
support and preserves every profile/population, regardless of the result.

Per-case rich scores go to the supplied new G payload root. Compact CSV/JSON
tables and `SCORING_RECEIPT.json` go to a fresh S6D C report directory. No S6C
artifact is written. Interrupted output directories remain preserved; execution
requires a newly reviewed output epoch, with no overwrite or silent salvage.

Outputs contain first-final, latest-revised and first-display-label cpWER,
fixed-word checks, source-supported Unknown and false-merge counts, return
consistency, whole-clip short-reply bins, lifecycle/cue activation and overlapping
source/room/corpus/quality/noise strata. Missing metrics remain null. The 156
primary, 47 complete-overlap, 26 incomplete-reference and 11 strict-empty cases
remain separate. Empty controls never acquire an invented WER denominator.

The inherited paired-comparison bootstrap reports raw lexical WER. An explicit
adapter applies the same inherited count-ratio uncertainty API to actual cpWER
view counts, with the same 2000 replicates, fixed seed 20260909, primary matched
blocks, observed rooms and whole-block missing-data exclusions. The API's
internal O0/O1 and word_counts names mean left/right count lanes in these
additional records; metric labels identify the actual cpWER view. These
conditional intervals retain the original shared-source/dependency limitations.
Per-case adverse count deltas are retained for both exact parent and cue-off
comparisons. Existing shuffle/nominal diagnostics provide width25 context only.

## Model-free PowerShell commands

Use fresh output suffixes if the example paths already exist. The inherited
analysis environment supplies pinned MeetEval0.4.3, NumPy1.26.4 and SciPy1.13.1.
The Edge/Anaconda base environments do not supply this pinned scorer. No model is loaded.

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r = "$sim\reports\S6D\20260913T195357Z"
$py = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $py -B "$sim\scripts\s6d_angle_width_score.py" check --output "$r\angles\width_scorer_checks_v1.json"
& $py -B "$sim\scripts\s6d_angle_width_score.py" prepare --predeclaration "$r\angles\operational_width_v1\ANALYSIS_PREDECLARATION_V1.json" --output "$r\angles\width_scorer_plan_v1" --score-payload 'G:\Just_Peachy_S6D\20260913T195357Z\width_scores_v1' --analysis-report "$r\angles\width_analysis_v1"
```

Anaconda Prompt or CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
set "PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%PY%" -B "%SIM%\scripts\s6d_angle_width_score.py" check --output "%R%\angles\width_scorer_checks_v1.json"
"%PY%" -B "%SIM%\scripts\s6d_angle_width_score.py" prepare --predeclaration "%R%\angles\operational_width_v1\ANALYSIS_PREDECLARATION_V1.json" --output "%R%\angles\width_scorer_plan_v1" --score-payload "G:\Just_Peachy_S6D\20260913T195357Z\width_scores_v1" --analysis-report "%R%\angles\width_analysis_v1"
```

## Later reviewed scoring command shape

Only root may issue the real authorization and supervise execution. This
documents arguments, not an instruction or authorization to launch:

```text
<PinnedAnalysisPython> -B <SIM>/scripts/s6d_angle_width_score.py execute
--adapter-plan <exact ADAPTER_PLAN.json>
--authorization <root-issued scorer authorization.json>
--prediction-indices <one or more literal complete indices covering all16jobs>
```

Authorization JSON must contain `root_review_passed: true`,
`adapter_plan_sha256`, and `prediction_indices` in CLI order with exact
path/bytes/SHA256 bindings. The adapter checks its own and all inherited source
bytes before and after scoring. This first adapter exposes finite stdout
progress every60 new scores; root must provide reviewed supervisor lifecycle
integration before an unattended scoring job. It does not pretend to emit the
runner's heartbeat/stop/completion protocol itself.

Fixture checks use synthetic rows to reject changed denominators, absent
controls and changed scorer bindings while preserving missing/Unknown data.
No new neural, policy replay, native, paced, GUI or physical execution is part
of the check or preparation action. A scoring receipt is not a default
promotion, native confirmation, CM5 timing result or S6D completion.
