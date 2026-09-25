# Review raw application resource observations

Purpose: `review_resource_evidence.py` verifies a stopped resource collector's
RESULT.json and reconstructs its phase summaries, memory peaks, process census
and CPU deltas from every bound raw sample. It independently recomputes sums from
the per-process records before replaying the original qualified ResourceLedger.
It does not trust stored aggregate counters as their own evidence.

Inputs: a bound application-resources RESULT.json with its adjacent SAMPLES.jsonl,
and optionally the caller's expected exact application PID/creation identity and
a requirement for all seven lifecycle marks. The root must have exited. Result,
raw-log hash/size, phase order/clock/census, complete/incomplete flags, process
uniqueness, memory/thread/CPU counter types and all reconstructed summary fields
are checked. Missing or changed observations, false acceptance flags and malformed
data fail explicitly. The raw stream is limited to 64 MiB, 1 MiB per line and
40,000 records; result size is limited to 8 MiB.

Phase/sample writes share the original collector lock. A sample can span a phase
transition: the end phase must match the last published mark, while its start
phase may be an earlier published phase. The review preserves that transition
classification rather than moving samples into a favorable phase. Marks describe
caller intent; they do not establish actual model load or successful GUI/source
execution. Partial lifecycle observations can be reviewed as diagnostics, but
`require_all_phases=True` rejects them for a caller requiring complete lifecycle.

Outputs: PASS_RECONSTRUCTED_RESOURCE_OBSERVATIONS_ONLY, the rebuilt summaries,
sampled global peaks, marked phase intervals and first-to-last complete running
sample deltas. Growth requires at least two complete running samples and remains
unavailable otherwise. It is not a memory-leak diagnosis. RSS sum, USS, Windows
private commit and Linux PSS stay separate; unavailable values remain null.
Samples can miss peaks and short-lived children; CPU deltas are lower bounds.
The review performs no new process measurement, model run or device access.

The output always retains UNKNOWN deployment tier, no controlled-whole-stack
qualification, no target qualification and zero integrated N4 acceptance. Future
panel review must join the source/GUI success, process lifetime, exclusive parent
slot and identical configuration evidence before interpreting the measurements.
No 2-GB fit, Pi real-time performance, GPU allocator/device measurement or WSL/
cgroup accounting can be inferred from this Windows sample review alone.

The internal API is `review(binding, expected_owner=..., require_all_phases=True)`.
The CLI writes a fresh private ADMISSION.json and REVIEW.json after checking the
implementation qualification, helper lock, shared allowance, disk and deadline.
Preserve failed inputs and prior reviews; use a new output for every attempt.

The guarded development probe runs nine tests and replays the original saved
model-free resource-tree observation (including its actual now-exited hidden
child). It starts no new child or resource collector. Tests cover aggregate and
summary tampering, invalid CPU/clocks, duplicate process/phase order, incomplete
and missing-phase semantics, unavailable PSS, growth, truncation and foreign-root/
false-acceptance refusal. Synthetic fixtures are not application benchmarks.
Probe output includes immutable code snapshots, ADMISSION.json, tests.txt,
SAVED_RESOURCE_REVIEW.json and RESULT.json or FAILED.json. It pins CPU14 and uses
the existing helper lock beside CPU4 ASR. Do not run alongside controlled paced
application measurements. No audio, model, source, GUI, microphone or Pi is used.

PowerShell probe:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_resource_review.py" --output "$jpLocal\n4\resource-review-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_resource_review.py" --output "%JP_LOCAL%\n4\resource-review-probe-v1"
```

After qualification, standalone review of the existing saved model-free resource
fixture (change the result/output paths for actual subsequently collected cells):

```powershell
& $jpPython -B "$jpCode\review_resource_evidence.py" --result "$jpLocal\n4\application-resources-v1\actual-tree\RESULT.json" --output "$jpLocal\n4\resource-fixture-review-v1"
```

```bat
"%JP_PY%" -B "%JP_CODE%\review_resource_evidence.py" --result "%JP_LOCAL%\n4\application-resources-v1\actual-tree\RESULT.json" --output "%JP_LOCAL%\n4\resource-fixture-review-v1"
```
