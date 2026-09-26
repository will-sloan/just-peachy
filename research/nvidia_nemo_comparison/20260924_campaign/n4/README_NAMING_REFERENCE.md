# Evaluator reference joins for observed GUI names

Purpose: `naming_reference.py` connects the independently recorded heading reader
to the accepted N2 evaluation references and actual available E galleries. This
is an evaluator-only helper. Reference identities and transcripts must never be
passed to the application, inference worker, enrollment process or GitHub.

Inputs: ten exact private/public file bindings anchored in accepted N2,
`INTEGRATED_SCORING_CHECK_V1.json`, N4's 480-job preparation and the qualified
application context. The helper verifies every hash and the reference population:
240 paired O0/O1 scenes, 480 cells, including nonoverlap, overlap, incomplete
ambient references and empty controls. Gallery membership is recovered only
from each actual profile's E-window, template, source and manifest provenance.
Q/C windows, mixed identities, foreign UUIDs and changed roster ordering fail.
Neither display-name spelling nor calibration fitting supplies reference identity.
Gallery documents include vectors, but this helper never uses them numerically.

`build_context` returns a private `VERIFIED_REFERENCE_CONTEXT_ONLY` object with
the existing reference cells, audio-only job metadata, E0/E1 available profile
mapping, counts and bindings. It reads no waveform and starts no model. Actual
available membership is distinct from intended enrollment: each primary open
gallery has 24 available profiles, 34 intended members and 10 unavailable.
Outside the available gallery includes both outsiders and intended members
without usable E; this helper does not silently classify all of them as outsiders.

`join_observed` requires the independent observed-heading review and its exact
bound `INPUT.json`, including job, source context, gallery and roster fingerprint.
An alternative valid job from the same bank still fails that input join. Baseline
gallery ordering and N2 ordering retain their existing application conventions.
Its private result describes each native lexical span's positive intersections
with estimated reference activity, retaining all intersecting identities and
union durations without double counting same-person overlap. Multiple identities,
no activity, incomplete target-only references, empty captions, zero-width
windows and native windows extending past the file remain explicit categories.
Invalid reference ranges fail; overhanging native windows are not clamped.

These source windows are ASR revision windows, and reference activity is estimated.
Even one intersecting person does **not** establish exact word identity, purity,
correct naming or an exact word timestamp. A tiny intersection retains its
measured duration without receiving whole-word credit. No dominant speaker is
invented; incomplete references never receive a complete single-person label.
No naming accuracy, name-acquisition latency, continuous wrong-name exposure,
complete panel result or accepted N4 cell is produced. Full metrics still require
their own qualified missing-reference/ambiguity policy, fixed-identity controls
and actual complete application observations. Earlier immutable panel wrappers
do not automatically invoke this new helper.

The guarded `probe_naming_reference.py` reads existing reference data and a
previously qualified **synthetic** GUI observation. Sixteen tests check the real
population and E rosters, the saved synthetic join, changed input/roster rejection,
E/Q/C separation, UUID and reference-range integrity, hand-computed interval
unions, ambiguity, incomplete and empty cases. A successful synthetic join is
not a new GUI run or an observed accuracy result.

Resource controls: CPU14, BelowNormal priority, one math thread, GPU off,
model-free helper lock, 12-minute and 8-MiB output bounds, campaign disk floors
and private allowance. D1 PID creation identities, active bindings and heartbeat
are verified before/after. Every fresh attempt preserves its owner and four
source snapshots before dependent checks, including failed attempts. The probe
may run alongside the admitted CPU4 D1 worker, outside exclusive measurements.

PowerShell (use a fresh output suffix; never overwrite a prior attempt):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_naming_reference.py" --output "$jpLocal\n4\naming-reference-probe-v1"
```

Command Prompt and Anaconda Prompt (invoke this pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_naming_reference.py" --output "%JP_LOCAL%\n4\naming-reference-probe-v1"
```

Internal evaluator API, after the public qualification exists and the observation
has independently passed the qualified cell reader:

```python
from naming_reference import load_qualified_context, join_observed
references = load_qualified_context(checkpoint=bounded_evaluator_guard)
private_join = join_observed(references, verified_observed_heading_review,
                            exact_admitted_payload, checkpoint=bounded_evaluator_guard)
```

Probe outputs stay private: `PROBE_OWNER.json`, `source/`, `ADMISSION.json`,
`CONTEXT.json`, `tests.txt`, `SYNTHETIC_REFERENCE_JOIN.json` and `RESULT.json`
or `FAILED.json`. The public qualification contains hashes, paths, counts and
scope only; do not publish reference/context contents, profile mappings, names,
transcripts, vectors or audio. No device, visible application or Pi is contacted.
