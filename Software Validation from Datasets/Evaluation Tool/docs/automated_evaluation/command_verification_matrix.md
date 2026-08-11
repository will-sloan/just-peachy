# Command verification matrix

> Historical Stage 13 command audit. For the supported production interface and
> current acceptance evidence, use the root `START_HERE.md`,
> `launch_control_sheet.md`, and `operational_launch_readiness.md`. Placeholder
> and optional-backend commands below are not production launch steps.

Audit date: 2026-08-10. Working directory is the repository root for install/
activation commands and `Software Validation from Datasets/Evaluation Tool`
for `run_evaluation.py` and launch scripts. The root `.venv` is used unless an
isolated Stage 8 profile is named.

The three audited documents contain 130 command-start lines: 52 in
`system_guide.md`, 49 in `quick_reference.md`, and 29 in
`two_machine_launch_runbook.md`. Continuation lines belong to the command that
starts on the listed line. Repeated commands are grouped below; each cited line
instance inherits the row's classification.

| Source / command instances | Executed | Exit | Expected and observed result / artifacts | Status |
|---|---:|---:|---|---|
| System 83–86; Quick 10–13: enter/activate root environment, verifier, `pip check`, enter tool | Yes, clean clone | 0 with process-policy bypass | New clone-local environment activated; verifier ran; `pip check` clean. Plain PowerShell activation was policy-blocked, while `powershell -ExecutionPolicy Bypass` and cmd activation passed. FFmpeg remained a documented prerequisite. | `EXECUTED_SUCCESSFULLY` / policy path `EXECUTED_EXPECTED_FAILURE` |
| System 98; Quick 21: component catalog one-liner | Yes, prior acceptance and parser recheck | 0 | Runtime catalog loads and prints component identities/statuses. | `EXECUTED_SUCCESSFULLY` |
| System 106, 362–364; Quick 44–47: dry-run/plan/validate/list small/core campaign | Yes | 0 | Deterministic scenarios and validated campaign state produced. | `EXECUTED_SUCCESSFULLY` |
| System 116–118: `campaign_quickstart` exact plan/validate/list | Yes, earlier operator trace | 0 | Exact scenario planned/listed after running commands separately; shell punctuation in the original pasted attempt was an operator invocation issue, not a CLI defect. | `EXECUTED_SUCCESSFULLY` |
| System 126–128; Quick 55–60, 66–67, 143–146: run/status/stop/resume/retry/artifacts and selectors | Yes on bounded real/synthetic campaigns | 0 for valid paths | Real install smoke and local shakedown exercised execution and validation; controlled stop/resume preserved work. Selector variants are regression-tested; massive variants were not run. | `EXECUTED_SUCCESSFULLY`; full-scale use `NOT_SAFE_TO_EXECUTE_FULL_SCALE` |
| System 136–140, 700–705; Quick 105–109: analysis index/validate/coverage/run/release-status | Yes | 0 | Install smoke and two-worker rehearsal produced index, tables, plots, reports, coverage, and explicit gate status. Missing prerequisite correctly blocks release status. | `EXECUTED_SUCCESSFULLY` |
| System 154–155: root dev install/download/verify | Yes in clean clone | 0 install; verifier partial | Fresh `.venv` created; repository bootstrap prepared Whisper Tiny/Base/Small and ECAPA; 25/26 verifier checks, with only FFmpeg absent. | `EXECUTED_SUCCESSFULLY` with manual prerequisite |
| System 176: extended-local qualification | Prior Stage 8/9 evidence; not rerun | 0 in retained evidence | Isolated qualification artifacts exist. | `EXECUTED_SUCCESSFULLY` |
| System 290; Quick 27: one-item configured Base | Yes, genuine clean clone | 0 | One prediction, zero failed/missing, diagnostics, scoring, 11 plots, report; smoke WER 0.25. | `EXECUTED_SUCCESSFULLY` |
| System 305: configured `run` with explicit thread override | Parser/regression verified | — | Override path is validated by Stage 1 tests; no need to duplicate real inference for launch. | `PARSER_VERIFIED_ONLY` |
| System 372: scenario inspection one-liner | Yes during campaign audit | 0 | Frozen scenario content/identity inspected. | `EXECUTED_SUCCESSFULLY` |
| System 391–398: core01 plan/run/stop/resume/retry/validate | Yes across prior real trace and Stage 14 stop/resume rehearsal | 0 | Persistent states and artifacts validated. | `EXECUTED_SUCCESSFULLY` |
| System 421–453; Quick 73–99: assign/copy/run/export/validate-transfer/merge/validate-merged | Yes in complete local two-worker real rehearsal | 0 | Two non-overlapping real assignments, checksummed transfers, accepted merge, 2/2 scenarios, no missing/conflicts. | `EXECUTED_SUCCESSFULLY` |
| System 711; Quick 115: placeholder paired comparison | Parser and deterministic metric tests only | — | Syntax accepted; placeholders are not runnable scientific IDs. | `PARSER_VERIFIED_ONLY` |
| Quick 33: core screening qualification | Prior Stage 7 real evidence | 0 where prerequisites available | Core qualification registry/report retained; no full canary rerun in Stage 14. | `EXECUTED_SUCCESSFULLY` with current canary still incomplete |
| Quick 34: extended screening smoke | Prior Stage 9 evidence | 0 for available profiles | Available backends retain real smoke evidence; blocked backends remain excluded. | `EXECUTED_SUCCESSFULLY` |
| Quick 35: speaker protocol smoke | Prior Stage 10 evidence | 0 | Bounded real speaker artifacts exist; not a full benchmark. | `EXECUTED_SUCCESSFULLY` |
| Quick 36: diarization smoke | Prior Stage 11 Sherpa evidence | 0 where qualified | Sherpa RTTM/UEM smoke exists; pyannote/Falcon credentials and NeMo platform remain blocked. | `EXECUTED_SUCCESSFULLY`; optional backends `BLOCKED_CREDENTIAL` / `BLOCKED_PLATFORM` |
| Quick 81–82: explicit IDs/range/component assignment variants | Regression-tested, examples not executed against massive | 0 tests | Deterministic selectors and overlap validation pass. | `PARSER_VERIFIED_ONLY` for literal example IDs |
| Quick 131: core CUDA install | Prior Stage 8 real qualification | 0 retained evidence | CUDA environment/GPU model smokes exist, but Stage 5 CUDA-event timing remains incomplete. | `EXECUTED_SUCCESSFULLY` with limitation |
| Quick 132: extended-local install/download | Prior Stage 8 | 0 retained evidence | Profile/assets qualified where available. | `EXECUTED_SUCCESSFULLY` |
| Quick 133: ONNX install/download | Prior Stage 8 | 0 retained evidence | Sherpa profile qualified; this contradicts the old planning-only ONNX exclusion because later stages explicitly added it. | `EXECUTED_SUCCESSFULLY` |
| Quick 134: WeNet install/download | Yes in prior qualification | non-ready expected | Available archive has `final.pt`; adapter requires `final.zip`; no silent rename. | `EXECUTED_EXPECTED_FAILURE` |
| Quick 135: WeSpeaker install/download | Prior Stage 8/10 | 0 with warnings | Real extraction smoke retained; warning status explicit. | `EXECUTED_SUCCESSFULLY` |
| Runbook 12–21: identity/materialize/validate/credentials | Materialize/validate/help/credential checks executed on A | 0 except credentials 2 | Candidate hash reproduced; assignments cover 41 with no overlap; credentials safely report missing. | `EXECUTED_SUCCESSFULLY` / credential check `EXECUTED_EXPECTED_FAILURE` |
| Runbook 31–40: clone/install/Base/verify/materialize | Clone/install/Base/real run executed for remote `4e1`; Stage 14 materializer unavailable there | 0 for committed path | Proves remote core run, not uncommitted launch package. Final `<final-launch-commit>` does not yet exist. | `EXECUTED_SUCCESSFULLY` for core; final launch `NOT_SAFE_TO_EXECUTE_FULL_SCALE` |
| Runbook 56–57: Machine A launch/status | Yes | wrapper 1; underlying preflight 2; status 0 | Wrapper validated campaign/assignments and all 20 A scenarios, then stopped on dirty-tree/FFmpeg blockers before inference. Status confirms 41/41 remain pending. | `EXECUTED_EXPECTED_FAILURE` / `NOT_SAFE_TO_EXECUTE_FULL_SCALE` |
| Runbook 66–67: Machine B launch/status | No | — | Actual B unavailable; no profile or full preflight. | `BLOCKED_MACHINE_B` |
| Runbook 77–87: massive status/stop/worker resume | Bounded shakedown plus tests only | 0 | Assignment-scoped resume proven not to requeue other worker's stopped scenario. Massive commands withheld. | `EXECUTED_SUCCESSFULLY` bounded; massive `NOT_SAFE_TO_EXECUTE_FULL_SCALE` |
| Runbook 101–105: massive A/B export wrappers | Parser passed; shakedown equivalent executed | — | Full export intentionally unavailable until 20/20 and 21/21 succeed. | A `NOT_SAFE_TO_EXECUTE_FULL_SCALE`; B `BLOCKED_MACHINE_B` |
| Runbook 120–127: massive transfer validation/merge | Parser passed; exact workflow executed on two-scenario real rehearsal | 0 rehearsal | Transfer validation and merge accepted with no missing/conflicts. Massive transfers do not yet exist. | `NOT_SAFE_TO_EXECUTE_FULL_SCALE` |
| Runbook 141: massive analysis wrapper | Parser passed; bounded analysis executed | — | Massive merge and passed standard evidence do not exist; wrapper would keep release blocked without evidence. | `NOT_SAFE_TO_EXECUTE_FULL_SCALE` |

No audited command is classified `INVALID`. Commands with placeholders remain
parser-only by design. Machine B and full-scale campaign commands remain
explicitly blocked rather than being promoted from bounded evidence.
