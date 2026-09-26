# Complete V3 panel content and conditional naming diagnostics

Purpose: `review_semantic_panel_v3.py` connects the explicit V3 semantic reader
to the qualified V3 production plan/run and exact population reviewer. It keeps
the existing conditional name count arithmetic and axes unchanged. Every planned
cell must pass the source-delivery, native, observation, caption, timing, heading
and evaluator-reference checks. A missing or failed cell cannot be dropped.

Inputs: an immutable completed V3 application run with ADMISSION, RUN_OWNER,
RESULT, cells and ordered progress; the qualified V3 plan/runner/cell/semantic
sources; fixed accepted evaluator references; and a fresh separate private output
directory. The run reviewer verifies the stopped coordinator/preparer identities,
command, interpreter, source and code bindings and reconstructs the full production
plan. Earlier full-bank main/mode comparison, scoring and selection gates remain
required. Exactly 40 cells per candidate (24 panel cells and 16 repetitions), up
to six candidates/240 cells, must match the terminal and progress population.
No planning, application, source or model execution occurs in this reviewer.

Outputs: REVIEW_OWNER, ADMISSION, compact per-cell JSON, INPUT_BINDINGS and REVIEW
with `PASS_COMPLETE_V3_PANEL_NAME_DIAGNOSTICS_ONLY`, or preserved FAILED evidence.
Compact cells retain raw source-delivery summary hashes and their verified
envelope bindings without subtracting observer or scheduling cost. The complete
raw summaries remain at `review.summary` inside those immutable envelopes; each
envelope must appear in the panel registry. Compact cells also retain content
counts, fixed roster, name count vectors, visibility
and revision denominators, and fingerprints of the fully reconstructable private
semantic results. The shared registry retains exact native/viewport/gallery and
reference bindings. Private text, labels and per-span details are recomputable;
they are not duplicated in every compact cell. The semantic chain's content and
timing fingerprints must match. Older V2 semantic receipts are rejected.

Rates use summed counts within composition, tap, panel/repetition kind and
reference-class groups. They never average per-cell percentages. Observed,
all-Unknown and constant-name diagnostic scenarios retain first-visible,
first-final-visible and latest stages with active/history panes separate. Fixed
roster and control identity cannot change within one composition. Counts cover
native lexical span observations, including retired hypotheses, not exact
reference words or speech duration. Forced choices do not become recognized
names; estimated activity support and outside-available-roster limitations remain.

This stage establishes complete diagnostic coverage only. Naming accuracy,
deadline/latency acceptance, continuous exposure, acquisition, returning-person
consistency, fragmentation, controlled resource tiers, continuity, stop/restart
and N4 acceptance remain unqualified. Recorded timing details remain in the
reconstructable semantic review; no new latency threshold is imposed here.
All integrated acceptance counts remain zero. Private evidence and galleries
remain local, and the Pi stays offline.

`test_semantic_panel_v3.py` and `probe_semantic_panel_v3.py` exercise saved synthetic
V3 semantic results, 40/240-cell population fixtures, corruption/refusal cases,
lossless count-vector round trips, summed-count rates, empty/missing observations,
fixed-roster/control consistency, raw delivery retention, and a maximum-panel
serialization budget with 2 MiB reserved for registry/admission. This synthetic
size check does not establish actual production registry size. Twenty-two tests
include the previously qualified V3 population tests. There is no actual panel
run or positive production-plan admission in the development probe.

Attempt v1 passed 21 of 22 checks. The maximum-panel report plus the 2-MiB
registry/admission reserve reached 8,595,136 bytes, exceeding 8 MiB because it
duplicated raw delivery summaries already present in the bound envelopes. V2
retains their exact hashes and envelope bindings instead, with a round-trip
evidence check. The source summaries and traces are unchanged, the hard budget
is unchanged, and the failed attempt and its source snapshots remain preserved.

Both review and probe use CPU14/BelowNormal, one math thread, GPU disabled, the
writer lock, existing disk/private reserve guards and an 8-MiB output ceiling.
The review has a one-hour bound; the probe has a 12-minute bound and checks live
D1 ownership/protected source before and after. Probe attempts snapshot their four
source files before prerequisites. Use fresh private output paths and preserve
failed attempts. Do not run a helper alongside exclusive resource measurements.

PowerShell development probe:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_semantic_panel_v3.py" --output "$jpLocal\n4\semantic-panel-v3-probe-v2"
```

Command Prompt or Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_semantic_panel_v3.py" --output "%JP_LOCAL%\n4\semantic-panel-v3-probe-v2"
```

After an actual production V3 panel has completed and its owners have exited,
replace the descriptive run/output names below with that verified run and a
fresh private review directory. This command is not an instruction to start a run.

```powershell
& $jpPython -B "$jpCode\review_semantic_panel_v3.py" --run "$jpLocal\n4\ACTUAL_COMPLETED_V3_RUN" --output "$jpLocal\n4\FRESH_V3_SEMANTIC_REVIEW"
```

```bat
"%JP_PY%" -B "%JP_CODE%\review_semantic_panel_v3.py" --run "%JP_LOCAL%\n4\ACTUAL_COMPLETED_V3_RUN" --output "%JP_LOCAL%\n4\FRESH_V3_SEMANTIC_REVIEW"
```

Run the review only with its matching SEMANTIC_PANEL_CHECK_V3 qualification and
unchanged bound source. Do not treat a passing development probe as N4 acceptance.
