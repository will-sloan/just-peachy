# Finish a completed N2 campaign

`finish_campaign.py` is an offline evidence validator and report generator. It
does not start models, run the GUI, wait for jobs, package a release, change Git,
or declare the wider project stage complete. Invoke it only after the numerical
coordinator has exited and the isolated test suite has completed. The current
run has an active `execute_campaign.py --wait-for-existing` waiter, which owns
this finalization step. Do not also invoke the commands below while that waiter
is active; they document its finalizer inputs and a later controlled resume.

The finisher takes the coordinator's OS lifetime lock without waiting and holds
it through final publication. It rejects a live or unverified coordinator/child
process, incomplete jobs, changed contracts and changed result hashes. It uses
`run_campaign.completion()` for every job. The exact required population is:

| Jobs | Required cells |
| --- | ---: |
| `screen-D0_E0`, `screen-D0_E1`, `screen-D1_E0`, `screen-D1_E1` | 96 each, 384 total |
| `regression-D0_E0`, `regression-D0_E1`, `regression-D1_E0`, `regression-D1_E1` | 8 each, 32 total |
| `gui-panel` | 6 |
| Total | 9 jobs, 422 cells |

The supplied frozen source receipt is verified against every prototype file,
the runtime/common-UI digests, release archive and optional `auxiliary_files`.
Auxiliary paths must remain inside the frozen release directory. Controller
admissions and the GUI must bind the same frozen source. The isolated suite's
own read-only validator checks its exact module/test census, source, commands,
exit/isolation receipts and explicit skip reasons. Public checks retain counts,
including skips; private skip reasons and paths stay in the suite evidence.

The full GUI aggregate is revalidated down to individual private-process
receipts and archive integrity. A successful caption run with an archive error,
lost items or unfinished worker cannot pass.

## Inputs

- `--spec`: the reviewed coordinator JSON. The final planned file is
  `local/n2/numerical-spec-v3.json`.
- `--coordinator-result`: its completed `RESULT.json`, with adjacent
  `ADMISSION.json` and `owner.lock`; final planned output is
  `local/n2/numerical-v1`.
- `--source-receipt`: the actual frozen release receipt; final source is
  `local/releases/n2-common-v6/SOURCE_RECEIPT.json`.
- `--test-report`: completed isolated suite report; final planned output is
  `local/n2/checks/full-suite-isolated-v2/RESULT.json`.
- `--gui-report`: the completed six-cell report at
  `local/n2/gui-panel-isolated-v1/GUI_PANEL_REPORT.json`.
- `--output`: a new private directory outside the frozen source and public tree.
- `--public-out`: a public report directory, normally this campaign's
  `n2/evaluation`. Existing final/summary target files are never overwritten.
- `--cpu`: one logical CPU, default 4. The CLI uses BelowNormal priority on
  Windows and one numerical thread. It performs no neural inference.

The Controller admissions must bind the existing private normalized
`evaluation/AUDIO_ONLY.json` and `evaluation/REGRESSION_AUDIO_ONLY.json`, in one
directory with `EVALUATOR_TRUTH.json`, `ROSTERS.json` and `MANIFEST_RECEIPT.json`.
The finisher never creates, normalizes or changes these populations. Regression
and main-screen summaries remain separate. No evaluator truth reaches a model.

## PowerShell

Run the focused tests; these create temporary JSON/text fixtures, take real OS
locks and call no model or GUI. The test process is pinned to CPU4:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil,unittest; p=psutil.Process(); p.cpu_affinity([4]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('research.nvidia_nemo_comparison.20260924_campaign.n2.test_finish_campaign')); raise SystemExit(not r.wasSuccessful())"
```

After the coordinator exits and the suite finishes, use the actual paths below.
The source/spec versions are explicit; do not substitute another release under
an existing receipt. This command is not a promise that those runs passed:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n2\finish_campaign.py' `
  --spec 'G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-spec-v3.json' `
  --coordinator-result 'G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-v1\RESULT.json' `
  --source-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v6\SOURCE_RECEIPT.json' `
  --test-report 'G:\Just_Peachy_N1\20260924_campaign\local\n2\checks\full-suite-isolated-v2\RESULT.json' `
  --gui-report 'G:\Just_Peachy_N1\20260924_campaign\local\n2\gui-panel-isolated-v1\GUI_PANEL_REPORT.json' `
  --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\final-analysis-v1' `
  --public-out 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\evaluation' --cpu 4
if ($LASTEXITCODE -ne 0) { throw 'N2 final evidence or quality checks failed; preserve and inspect the reports.' }
```

## CMD / Anaconda Prompt

Use the existing application Python by absolute path; no activation or package
installation is required. The caret continues a CMD command:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil,unittest; p=psutil.Process(); p.cpu_affinity([4]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('research.nvidia_nemo_comparison.20260924_campaign.n2.test_finish_campaign')); raise SystemExit(not r.wasSuccessful())"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "research\nvidia_nemo_comparison\20260924_campaign\n2\finish_campaign.py" ^
 --spec "G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-spec-v3.json" ^
 --coordinator-result "G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-v1\RESULT.json" ^
 --source-receipt "G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v6\SOURCE_RECEIPT.json" ^
 --test-report "G:\Just_Peachy_N1\20260924_campaign\local\n2\checks\full-suite-isolated-v2\RESULT.json" ^
 --gui-report "G:\Just_Peachy_N1\20260924_campaign\local\n2\gui-panel-isolated-v1\GUI_PANEL_REPORT.json" ^
 --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\final-analysis-v1" ^
 --public-out "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\evaluation" --cpu 4
if errorlevel 1 echo N2 final checks failed. Preserve and inspect the reports.
```

## Outputs, failure handling and claims

The public directory receives `SCREEN_SUMMARY.json`/`.md`,
`REGRESSION_SUMMARY.json`/`.md`, and `FINAL_CHECKS.json`/`.md`. Summaries are made
with the existing `summarize_screen.summarize()` implementation, once per
population. The final checks bind the exact input reports, nine result hashes,
source/runtime digests and summary hashes. They contain no private paths,
transcripts, voice vectors, profile IDs or skip reasons.

The private output retains each scorer's `SCREEN_EVIDENCE.json`, immutable index
copies, redacted summary copies, `PRIVATE_ERRORS.json` and a copy of the final
checks. Do not commit private output.

Exit 0 means these evidence and quality checks passed. Exit 2 means a checked
input, completeness, ASR invariance or caption invariance gate failed. Early
invocation errors such as an owned lifetime lock or a nonfresh output also exit
nonzero. The program never waits for running jobs. Fixing a problem requires a
new private output and fresh public target files; preserve the failed reports.

Both populations are summarized even if the first produces a real quality
failure. Such summaries remain available and the final status remains FAILED.
An exception in one summary does not prevent attempting the other. Incomplete
or mutable campaign evidence is rejected before either summary runs. Accuracy
metrics retain the evaluator's qualifications; no new arbitrary accuracy
threshold is invented. No Pi, total-system 2 GB memory, physical scanout or
calibrated open-name claim follows from a passing report.

The 11 focused tests pass without model or GUI execution. They cover exact populations, changed result/source/auxiliary
files, live/unverified processes, a real nonblocking OS lock, incomplete runs,
quality-failure preservation, independent summary failures, source-path escape,
redaction and refusal to overwrite existing reports.
