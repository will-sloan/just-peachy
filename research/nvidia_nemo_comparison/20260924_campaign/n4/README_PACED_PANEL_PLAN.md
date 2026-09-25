# Admission and planning of actual application panels

Purpose: `paced_panel_plan.py` prepares paired source-paced application runs
only after both complete modeled scoring banks have passed review. It does not
choose a winner, start a model, claim a memory tier or accept N4. A later launcher
must obtain the exact supervised exclusive resource slot and execute/review the
real source branch. The existing `ApplicationCell` prestart qualification is
bound to the plan; its real source branch remains unqualified at this checkpoint.

Inputs: passed main (7,680) and additional-mode (1,536) scoring-review receipts;
their same-source plans, components, original score/report hashes and stopped
review/scoring workers; the frozen 480-job bank, 24-job panel and eight timing
regressions; original models, runtimes, fixed research galleries and common UI;
and a small explicit candidate-selection JSON. No source files are modified.
The original scoring review verifies reference/count/report consistency; the
planner rechecks that provenance and all sealed score hashes without loading
reference text or rerunning metrics. Missing/partial reviews block preparation.

Selection JSON must have exactly these top-level fields:

- `schema`: `n4-paced-selection-v1`.
- `status`: `PROPOSED_PACED_EVALUATION_ONLY`.
- `reviews`: `main` and `modes-panel` bindings, each with path/SHA-256/byte count.
- `selected`: baseline first, then at most five different alternatives. Each
  row has `composition` (for example A0_D0_E0), `objective`, `rationale` and
  `limitations`. Objectives are baseline, smallest_useful, diarization_identity,
  text_tradeoff, higher_memory or independent_architecture. Rationale and
  limitations are nonempty text up to 4,000 characters each.
- `excluded`: every other one of the 16 compositions, each with `composition`
  and a nonempty `reason` up to 4,000 characters.
- `limitations`: nonempty overall explanation, up to 8,000 characters.

Selection is an engineering decision supported by the complete reviewed
reports. An objective is a reason to test a candidate, not proof of superiority.
Unqualified D0/E1 association and reject-all naming gates must remain explicit
limitations. Fewer alternatives may be proposed when evidence supports that
decision; do not silently omit them or invent a gain. The schema intentionally
contains no query transcripts, names, reference activity or fitted thresholds.

Each candidate receives the same 24 fixed panel jobs (12 scenes, both taps)
in open conversation plus names, followed by two additional passes over the
eight frozen timing regressions. Thus each timing regression occurs three times
including its original panel occurrence, and each candidate has 40 cells.
The paired order is file/repetition first, candidate second. Each cell requires
a fresh process/application, one model owner, CPU4, one math thread, GPU off,
actual source speed, fixed Balanced mode and disabled reference adaptation/text
assistance. A fresh process is not a cold OS disk cache; cache flushing is not
performed. No input desktop switching or injection is permitted.

Outputs: private ADMISSION.json, PLAN.json and RESULT.json with
PREPARED_PANELS_AND_REPEATS_ONLY. `execution_payload(plan, index)` returns an
explicit allowlist of audio, contract, frozen source/runtime/gallery and asset
metadata for the future child. It excludes selection rationales, scoring
reports and evaluator references, and retains source_execution_authorized=false
until a future launcher performs its own supervised admission. It is not a
standalone launch command or a way to bypass resource ownership.

These plans do not include the required separate 20-minute existing-audio
continuity sequence for each release candidate. Other-mode actual release
checks, naming/visibility scoring, full source parity, exclusive resource/latency
measurements, continuity and final acceptance remain separate outstanding work.

The preparer/probe are model-free CPU14 helpers and share the existing Windows
scoring lock. They preserve all existing evidence, check C50/G75-GiB floors,
the shared 50-GiB allowance with 6 GiB pending reservations, an 8-MiB output
budget and twelve-minute between-operation budget, and the original packaging
reserve. They must not overlap controlled whole-application measurements.

`test_paced_panel_plan.py` runs nine dictionary/lifecycle rejection tests.
`probe_paced_panel_plan.py` additionally rechecks the real frozen source,
24 waveforms, panel/anchor/catalog bindings and all 16 composition routes.
Its pure-planner rehearsal uses explicitly unavailable review fixtures,
NO_MODEL_PAYLOAD and no actual selection or production plan. It never calls the
production admission with synthetic passed evidence. A passed rehearsal only
qualifies planning code; the production full-review gate remains unexecuted
until the real full-bank prerequisites exist. Detailed outputs stay private.

PowerShell (production paths below refer to future completed score reviews):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B "$jpCode\test_paced_panel_plan.py" -v
& $jpPython -B "$jpCode\probe_paced_panel_plan.py" --output "$jpLocal\paced-panel-plan-probe-v1"
& $jpPython -B "$jpCode\paced_panel_plan.py" --main-review "$jpLocal\integrated-main-score-review-v1\RESULT.json" --modes-review "$jpLocal\integrated-modes-score-review-v1\RESULT.json" --selection "$jpLocal\PACED_SELECTION_V1.json" --output "$jpLocal\paced-panel-plan-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B "%JP_CODE%\test_paced_panel_plan.py" -v
"%JP_PY%" -B "%JP_CODE%\probe_paced_panel_plan.py" --output "%JP_LOCAL%\paced-panel-plan-probe-v1"
"%JP_PY%" -B "%JP_CODE%\paced_panel_plan.py" --main-review "%JP_LOCAL%\integrated-main-score-review-v1\RESULT.json" --modes-review "%JP_LOCAL%\integrated-modes-score-review-v1\RESULT.json" --selection "%JP_LOCAL%\PACED_SELECTION_V1.json" --output "%JP_LOCAL%\paced-panel-plan-v1"
```

Every run needs a fresh private output. Preserve failed attempts and frozen
code; qualify a derivative for repairs. Do not launch the internal application
cell by replacing a missing passed review with a fixture or an unchecked flag.
