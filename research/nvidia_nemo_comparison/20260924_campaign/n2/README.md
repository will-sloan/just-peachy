# Final N2 status

N2 offline integration/evidence review is COMPLETE: 422/422 evaluations and
final checks pass. See N2_HANDOFF.md and FINAL_REVIEW.md for acceptance, measured
quality limitations and the N4 disposition. This README retains historical
implementation/run instructions below; any pending-state statements there are
superseded by those final receipts. Do not rerun completed unchanged jobs.

# N2: actual streaming diarization and model-specific speaker embeddings

This folder contains the second campaign stage. `diarization/` builds and
verifies official native Nemotron 3 Q8 and reference NeMo parity; `embeddings/`
exports/verifies official TitaNet; `evaluation/` freezes disjoint E/C/Q evidence,
calibrates only on C, and scores the fixed paired screen. Root integration lives
in `prototype/app/n2_*.py`. Read `prototype/app/README_N2.md` for the actual
personal gallery, caption and rollback behavior.

All large/private inputs and outputs are under
`G:\Just_Peachy_N1\20260924_campaign\local\n2`. Model paths are explicit and
hash-bound. The usual application environment and personal data are preserved.
No microphone, USB, playback, new acoustic scene generation or Pi access is used.

PowerShell setup:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B research\nvidia_nemo_comparison\20260924_campaign\n2\configure.py --data 'G:\Just_Peachy_N1\20260924_campaign\local\n2\interactive-data'
```

Command Prompt / Anaconda Prompt setup:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B research\nvidia_nemo_comparison\20260924_campaign\n2\configure.py --data "G:\Just_Peachy_N1\20260924_campaign\local\n2\interactive-data"
```

Input: staged pinned native model/DLL and TitaNet export. Output: the new data
root's `n2_runtime.json`, containing paths, hashes and compatible embedding
namespace. No weights are copied into Git. Subdirectory READMEs include explicit
commands, input schemas and output receipts for every numerical step.

CPU is the default. A separate Windows CUDA runtime can be requested with
`configure.py --device cuda --data A_NEW_DATA_DIRECTORY`, only after the pinned
CUDA build and parity receipts exist. The runtime records the explicit device
and every native DLL hash. `run_screen.py --device cuda` selects that route;
it must never silently substitute CPU. CUDA results are Windows desktop
measurements, not CM5 performance. ASR and embedding inference remain CPU.

For the complete frozen prototype software suite, use
[README_CHECK_SUITE.md](README_CHECK_SUITE.md). Its runner gives each discovered
test module a separate guarded private Windows process, retains native crash
evidence, and accounts for every test and skip before declaring completion.

Campaign deadline and the existing code-only 10/15/30-minute probes retain their
N1 ledger. N2 does not create a second campaign or promise automatic LLM resumption.
Metrics distinguish accelerated causal inference, actual source-paced Windows
execution, event fixtures, and unavailable target-hardware measurements.

## Fixed paired screen and resume

`run_screen.py` runs the actual Windows Controller on every admitted audio-only
job, at source speed, with fresh session state and resident immutable weights.
Choose one of `D0_E0`, `D1_E0`, `D0_E1`, `D1_E1`. The main frontend condition is
anonymous/no gallery. An optional sanitized gallery index enables simultaneous
model-specific naming-policy observations. Their caption reconstructions are
explicit counterfactual event replays, not independent visible GUI trials.

PowerShell example (one-cell smoke; remove `--limit 1` for all 96 cells):

```powershell
& $py -B research\nvidia_nemo_comparison\20260924_campaign\n2\run_screen.py --source prototype --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\screen-example-D1E1' --manifest 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\AUDIO_ONLY.json' --combination D1_E1 --galleries 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E1\RUNTIME_GALLERY_INDEX_SAFE.json' --cpu 6 --limit 1 --stop-on-failure
```

CMD / Anaconda Prompt:

```bat
"%PY%" -B research\nvidia_nemo_comparison\20260924_campaign\n2\run_screen.py --source prototype --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\screen-example-D1E1" --manifest "G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\AUDIO_ONLY.json" --combination D1_E1 --galleries "G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E1\RUNTIME_GALLERY_INDEX_SAFE.json" --cpu 6 --limit 1 --stop-on-failure
```

Use an immutable copied `prototype` directory for a full run. Resume with exactly
the same command, removing the smoke limit. Completed cells are hash-verified;
changed source/configuration uses a new output directory. `--retry-failed`
creates new attempts and preserves failures. The supervisor, not a polling LLM,
owns long numerical runs. At most two CPU workers are admitted campaign-wide.
Omit `--galleries` for a separate resource measurement without comparison-policy
overhead. Do not run another inference worker during that isolated measurement.

Outputs: `ADMISSION.json`, per-cell private `RUNTIME_EVENTS.jsonl`, final controller
snapshots, process samples, source/model hashes, `CHECKPOINT.json`, and compact
`PROGRESS.json` / `RESULT_INDEX.json`. Full words and voice vectors remain local.
Read `evaluation/README.md` for scoring; evaluator truth is never passed to the
controller or the runtime observer.

Controller completion also requires a complete metadata archive: all source
samples, no archive error/loss, equal accepted/completed items, empty queues
and a closed writer. An optional archive warning therefore fails this screen
even when the visible transcript finishes. Audio recording remains disabled.

## Durable numerical coordinator

`make_plan.py` writes the actual reviewed 422-cell plan: four 96-cell main
screens, four eight-cell C105/short/return/silence regressions, and six actual
GUI cells. It does not start processes. Inputs are the frozen source, admitted
private manifests/galleries and CPU runtime. Output is a new explicit JSON
specification. CPU4 runs the six separate GUI processes then D0/E0 and D0/E1;
CPU14 alone owns CUDA for D1/E0 and D1/E1. The whole file is always source paced.
All combinations use the frozen low-latency decision; 288 native-only cells
already provide the three-profile sensitivity.

`--run-version` defaults to `v1`, preserving the original generated paths.
Use `--run-version v2` for the planned v7 common-source rerun: its outputs are
`local/n2/factorial-v2/<combination>`, `regressions-v2/<combination>` and
`gui-panel-isolated-v2`. Accepted suffixes are `v` followed by a positive
integer without leading zeros, such as `v1`, `v2` or `v12`; separators and
traversal strings are rejected. The generator changes only result/progress and
job output locations. It reuses the same evaluation manifests, galleries and
runtime assets without copying them, creating model results or launching jobs.
The plan JSON destination must be new.

The v6 run under `numerical-spec-v3.json` / `numerical-v1` was interrupted after
a real D1/E0 archive-integrity failure. Its complete and failed cells, six GUI
cases and `local/n2/recovery/archive-item-limit-v1/INTERRUPTION.json` remain
historical evidence. The v7 plan requires all 422 cells again, including all six
GUI cases, under the new common application source. Do not import v6 results
as v7 cache. The planned suite is `checks/full-suite-isolated-v3/RESULT.json`;
offline analysis targets `final-analysis-v2` after the new coordinator and
suite complete. These destinations do not imply that the rerun has passed.

PowerShell:

```powershell
& $py -B research\nvidia_nemo_comparison\20260924_campaign\n2\make_plan.py --source 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v7\prototype' --local 'G:\Just_Peachy_N1\20260924_campaign\local\n2' --run-version v2 --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-spec-v4.json'
```

CMD / Anaconda Prompt:

```bat
"%PY%" -B research\nvidia_nemo_comparison\20260924_campaign\n2\make_plan.py --source "G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v7\prototype" --local "G:\Just_Peachy_N1\20260924_campaign\local\n2" --run-version v2 --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-spec-v4.json"
```

The main paired screen contains 4,290.762 seconds per combination. Its strict
two-worker source-delivery floor is about 2.38 hours; model loading, drainage,
the GUI and supplemental checks add time. Use the coordinator's measured
progress instead of treating this lower bound as a completion estimate.

`run_campaign.py` executes a reviewed JSON specification with one or two CPU
lanes and at most one CUDA lane. Jobs within a lane run sequentially. An OS lock,
child PID plus creation time, immutable admission, and result hashes prevent
overlapping or incompatible resumes. A failed job stops its lane; the independent
lane may finish. A zero process exit is insufficient: the exact expected completed
cell count and successful result status must also match. Results, logs and
checkpoint references stay in the private output. The existing supervisor owns
the coordinator and refreshes its heartbeat without invoking an LLM.

Input specification fields are `schema: n2-numerical-coordinator-v1` and `lanes`.
Each lane supplies `cpu` and `jobs`; each job supplies a unique `id`, explicit
`argv` list, `cwd`, expected `cells`, `device`, `result_kind` (`controller`,
`native`, or `gui`), bounded `timeout_seconds`, and absolute `result` and `progress` paths. Controller
completion reads `RESULT_INDEX.json`; native completion reads `PROGRESS.json`;
GUI completion reads `GUI_PANEL_REPORT.json`. It never contains evaluator truth.

PowerShell (use the actual reviewed private specification path):

```powershell
& $py -B research\nvidia_nemo_comparison\20260924_campaign\n2\run_campaign.py --spec 'G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-spec-v4.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-v2' --state 'G:\Just_Peachy_N1\20260924_campaign\local\supervision'
```

CMD / Anaconda Prompt:

```bat
"%PY%" -B research\nvidia_nemo_comparison\20260924_campaign\n2\run_campaign.py --spec "G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-spec-v4.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-v2" --state "G:\Just_Peachy_N1\20260924_campaign\local\supervision"
```

For unattended runs, put this exact argument list in the existing supervisor's
worker spec and use its documented `start` command. Repeating the identical
coordinator command verifies and skips completed jobs. A GUI attempt requires
a fresh output if it failed; declare that in a new reviewed specification/output.
Disk reserves and the shared 12-hour final packaging reserve stop new work;
only verified owned processes are stopped. Never delete a live ownership lock.

`test_campaign.py` checks the coordinator using harmless temporary children that
only write small JSON files, wait for a sibling, and sleep. Two actual children
prove overlapping lanes and CPU affinity; tests also cover failure isolation,
resume without respawn, changed evidence/specification/result rejection, native
failure counts, packaging cutoff, disk-reserve cleanup and job timeout. No
models, UI or hardware are opened. Temporary files are removed; results print
to the terminal. The tests briefly change and then restore their own process
affinity and priority. Run from the worktree, with two CPUs available:

```powershell
& $py -B -m unittest research.nvidia_nemo_comparison.20260924_campaign.n2.test_campaign -v
```

CMD / Anaconda Prompt:

```bat
"%PY%" -B -m unittest research.nvidia_nemo_comparison.20260924_campaign.n2.test_campaign -v
```

The 11 coordinator tests passed with real harmless children. This verifies
orchestration behavior, not numerical model completion or timing.

`test_make_plan.py` verifies default/explicit-v1 byte compatibility, fresh v2
output paths, unchanged shared asset locations, the fixed 422-cell denominator,
traversal rejection and refusal to overwrite a plan. It uses only temporary
JSON fixtures and creates no result directories, models or processes. Run from
the worktree; results print to the terminal and temporary fixtures are removed.

```powershell
& $py -B -m unittest discover -s research\nvidia_nemo_comparison\20260924_campaign\n2 -p test_make_plan.py -v
```

Command Prompt / Anaconda Prompt:

```bat
"%PY%" -B -m unittest discover -s research\nvidia_nemo_comparison\20260924_campaign\n2 -p test_make_plan.py -v
```
