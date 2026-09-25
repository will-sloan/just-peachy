# Reconstruct saved GUI viewport evidence

Purpose: `review_viewport_evidence.py` reads every raw change in a closed V2
viewport ledger and independently reconstructs its first-visible, first-final,
latest and heading-change span states. It verifies their exact times, references
and counts against SUMMARY.json. This is a saved-evidence integrity check, not
a new GUI run, source-to-widget latency qualification or stage acceptance.

Inputs: the hash/size binding of a closed SUMMARY.json and its adjacent bound
OBSERVATIONS.jsonl. The API is `review(binding, checkpoint=optional_callback)`.
Summary size is limited to 8 MiB; raw log to 64 MiB, records to 8 MiB and total
observations to 100,000. Active rows, spans and memberships retain the original
512/8192/16384 limits. Failed prefixes, missing/changed files, duplicate JSON
keys, noncanonical records, index gaps, bad references and clocks, impossible
pane/glyph visibility, incorrect summaries and inflated acceptance flags fail.
The reviewer preserves unavailable source clocks. It never infers identity or
correctness from caption headings, including assumed closed-roster names.

The V2 collector does not record the order of unchanged rows. If two simultaneous
rows share a span, their visitation order cannot be reconstructed reliably; this
review refuses that ambiguous evidence. It does not change the frozen collector
or guess an ordering. Replacement of a retired row with a new row for the same
span is supported when the resulting current rows have unique span membership.

Output: PASS_RECONSTRUCTED_VIEWPORT_OBSERVATIONS_ONLY with input bindings,
observation/update/retirement/span counts, reconstructed span-summary digest,
sampling interval and recorded source-clock availability. Raw private text stays
in the input log. Glyph-counter consistency is reported separately because
synthetic collector fixtures can omit it. Observed counters cannot prove actual
rendering without the application and source evidence. Point observations do not
prove continuous exposure, physical scanout, verified source delivery or timing
accuracy; these claims remain false, and integrated N4 acceptance remains zero.
Observer overhead is validated for type/range but cannot be independently
remeasured from the log. Nothing starts or enumerates audio devices or models.

The CLI checks the qualified implementation, CPU14 helper lock, original deadline,
free-space floors and shared allowance, then writes a fresh private ADMISSION.json
and REVIEW.json. A periodic checkpoint enforces those resource/time guards while
reading. Use a new output for every attempt; preserve failed evidence. Do not run
beside controlled paced application measurements. Model-free review can run beside
the existing CPU4 component evaluation.

`probe_viewport_review.py` runs ten tests: all 160 previously saved actual Tk
histories; the saved synthetic 8192-span history; source-clock availability and
changes; finality, heading change, resegmentation and retirement; tampered states,
references, counters and types; ambiguous simultaneous span membership; invalid
pane/glyph flags; truncation, foreign paths, failed status, duplicate JSON keys,
hashes, indices, redundant changes and bounds. It creates private synthetic test
ledgers and reuses saved observations. No new GUI, model, source, playback,
microphone, Pi or actual 20-minute continuity test is launched.
Probe outputs include immutable source snapshots, ADMISSION.json, tests.txt,
SAVED_REVIEWS.json and RESULT.json or FAILED.json.

PowerShell probe (choose a fresh output suffix if this attempt already exists):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_viewport_review.py" --output "$jpLocal\n4\viewport-review-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_viewport_review.py" --output "%JP_LOCAL%\n4\viewport-review-probe-v1"
```

After qualification, standalone review of the first original saved actual widget
history (replace summary/output for a subsequently collected application cell):

```powershell
& $jpPython -B "$jpCode\review_viewport_evidence.py" --summary "$jpLocal\n4\viewport-ledger-v2\test_saved_160_actual_viewport_histories_match_exactly-000\SUMMARY.json" --output "$jpLocal\n4\saved-viewport-review-v1"
```

```bat
"%JP_PY%" -B "%JP_CODE%\review_viewport_evidence.py" --summary "%JP_LOCAL%\n4\viewport-ledger-v2\test_saved_160_actual_viewport_histories_match_exactly-000\SUMMARY.json" --output "%JP_LOCAL%\n4\saved-viewport-review-v1"
```
