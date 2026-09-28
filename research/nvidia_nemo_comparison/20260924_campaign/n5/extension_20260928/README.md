# Extended Nemotron research campaign

The user's September 28 instruction explicitly extends research beyond the six-hour preconnection window. WINDOW.json establishes a three-day review point: October 1, 2026 at 17:47:34 UTC (13:47:34 Toronto). The previous 22:20:48 UTC stop instruction is superseded for new dispatch. Original campaign closure, old WINDOW.json, admissions, source hashes, failures and accepted releases remain unchanged. Pi connection is a separate milestone; do not probe it before the user confirms it is connected.

Read RESEARCH_PLAN.md, NEXT.md and CANDIDATE_QUEUE.json. The queue records execution order and dependencies, not completed experiments. The main combinations are Sherpa ASR / Nemotron English ASR, each with Nemotron 3 diarization and retained ReDimNet. TitaNet stays retired. Baselines and anonymous encoder bypass are controls, not permission to remove persistent identification silently. New methods are hypotheses until implemented, measured and independently reviewed.

The hourly follow-up continues this task. Report meaningful changes, failures requiring attention, completion and required decisions; remain quiet on unchanged status. At the three-day checkpoint stop new dispatch, close owned work safely, pause the follow-up and report remaining work. Stop earlier if the authorized campaign is verified complete. Do not continually repeat passed one-file tests or use waiting time as acceptance.

## Fresh offline admission guard

Purpose: allow future bounded offline admissions to use the user's new time authorization while retaining the existing CPU, ownership, storage and privacy checks. `window_guard.py` is a fresh derivative of the old guard; `GUARD_DERIVATION.json` records the parent/child hashes. The old guard and bound runs are not modified. This is not a worker launcher or a shared-ledger mutation.

Inputs: WINDOW.json; existing supervisor identity/spec and N4 admission census; preserved six-link WSL inventory; original campaign storage policy; physical private output. Outputs: read-only authorization/census JSON printed to stdout when requested. It counts all earlier preconnection output, the listening examples and new extension output against the same combined 1-GiB cap. Original 50-GiB payload ceiling, 2.5-GiB reservations and C50/G75-GiB free-space floors remain. GPU is off, two host logical CPUs total, one native thread per model. No new downloads are admitted.

Future launchers must bind this guard, this WINDOW.json, their own source and full input hashes in a new admission, constrain each job to a bounded lifetime and use the existing supervisor. Existing prepi launchers still use their old window and must not be relabeled or patched in place to run after expiry. A fresh launcher can import this guard from this directory while explicitly retaining the original source locations. A longer campaign does not extend any running admission.

PowerShell / Anaconda PowerShell, from this directory:

```powershell
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B -m unittest test_window_guard -v
& $researchPython -B check_admission.py --requested-mib 128 --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\initial-census.json'
```

Command Prompt / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B -m unittest test_window_guard -v
"%RESEARCH_PY%" -B check_admission.py --requested-mib 128 --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\initial-census.json"
```

Use a fresh output filename for subsequent censuses. The checker creates no worker, contacts no device, enumerates no microphones and installs nothing. It pins its lightweight process to CPU14. Its result means admission prerequisites were observed, not exclusive reservation or stage acceptance; recheck immediately before any dispatch.

Native Pi tests require a separate target inventory and admission after reconnection. Windows CPU IDs must not be copied to ARM64. Start with saved-audio checks; later acoustic comparisons need the user physically ready in the test setting. No training or new human enrollment is authorized by this research extension.

## Additional verified checks and audit

`EMPTY_STORE_CHECK_SUMMARY_V1.json` binds both independently reviewed A0/A2 empty-store checks. `README_EMPTY_STORE_V1.md` documents the actual Tk mode/transfer protocol, Unknown-only naming proof, fresh launcher/reviewer and all shell commands. No personal profiles were created and no populated-gallery or spatial inference is claimed. The original application source and timing gates remain unchanged.

`TIMING_COVERAGE_FINDINGS_V1.md` documents why rotated older journals cannot provide complete per-component compute totals. `README_RETAINED_COSTS_V1.md` gives inputs, outputs and PowerShell/CMD/Anaconda commands for the read-only audit. Partial retained times are not full-run RTF or Pi measurements. NEXT.md prioritizes cumulative accounting and integrated/panel work; neither is credited as implemented by this audit.

`ASR_FAILURE_CHECK_SUMMARY_V2.json` records the independently reviewed A2 missing-model/runtime-hash startup failures and recovery. Run instructions, inputs, outputs, preserved V1 failure and the corrected memory-journal evidence contract are in `README_ASR_FAILURE_V1.md` and `README_ASR_FAILURE_V2.md`. Application source and inference gates are unchanged. The pass covers these two faults and a short recovery prefix, not complete N4/N5 acceptance.

`ARM_OPTIMIZATION_FINDINGS_V1.md` reports the existing model precision and generic ARM build baseline. `README_ARM_CANDIDATES_V1.md` gives PowerShell/CMD/Anaconda instructions for the read-only, pinned-source/GGUF-header audit. Its private JSON output binds the exact files and findings. It measures neither runtime RAM nor speed and launches no target or model. NEXT.md carries remaining untested work; prior passed checks are not scheduled for repetition without a new concern.
