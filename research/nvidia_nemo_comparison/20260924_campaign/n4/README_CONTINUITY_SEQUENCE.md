# Existing-session host-continuity input

Purpose: prepare one lossless saved-audio input for the later N4 long-run check.
The N4 specification authorizes concatenated existing sessions with truthful
actor/capacity semantics. This code selects whole accepted sessions and copies
their original mono PCM16 bytes. It never mixes, resamples, changes gain, trims,
crossfades, adds silence, synthesizes speech or creates a new acoustic scene bank.
No model, source playback, capture, microphone, USB, GUI or Pi is started.

Inputs: the accepted PREPARATION_V2_CHECK.json chain, all 480 audio-only jobs,
240 evaluator strata, 480 evaluator reference cells and the paired-capture
provenance. Both original taps must retain identical frame counts and their
original mappings and gains. Reference/actor identity mismatches fail. Waveform
hashes and PCM headers are checked again when materializing selected O0 files.
Previously applied O0 gain stays applied exactly once; runtime gain is unity.

The fixed deterministic selection uses complete-reference metadata only. It grows
an at-most-eight-actor pool by maximizing available speech duration, ties by
smaller pool then actor IDs. Within that pool it greedily covers family,
reference class, room, orientation, level, requested noise and short-turn fields,
ties by case ID. Each session is used once, with at most one empty control.
Selection must include nonoverlap, overlap and an empty control. It stops at the
first whole-session boundary at or after 1200 seconds, within 1300 seconds and
64 sessions. Keeping the full final session preserves every reference word.
The current accepted bank produces 27 sessions, 1206.7768125 seconds (20:06.78),
eight global actors, 23 nonoverlap sessions, three overlap sessions and one empty
control. This is a dependent engineering continuity sequence, not unseen efficacy
data. Incomplete ambient scenes remain in the main bank, outside this sequence.

O0 is predeclared for the long-run input; O1 continuity is not implied. Original
actor IDs remain global across every join. No session/seat renaming or resetting
at joins reduces the actual identity union. Native model capacity still needs
verification during execution; the eight-actor bound alone is not proof of good
speaker tracking. Research galleries retain their original E/C/Q coverage and
model-specific identities. This code does not generate enrollments or set names.

`build(docs, bindings)` returns a private plan and separate evaluator truth. Whole
turn text, actor/source identities and availability stay unchanged. Only turn IDs
gain an occurrence prefix; file-support and estimated activity ranges gain the
exact cumulative integer frame offset. Exact word timing is absent and stays
absent; future inputs with word timing are refused until explicitly supported.
Mixed activity grids fail. Overlap remains overlap, so concatenated ordinary WER
is unavailable; use the existing speaker-aware evaluator where references permit.
Original per-session timebase mappings remain attached to evaluator provenance.

`materialize(plan, fresh_path, checkpoint=...)` copies bounded chunks, hashes each
source PCM stream, verifies each original WAV before/after reading, and verifies
the complete output PCM again after closing. It returns an eight-field audio-only
job and a copy receipt. The application must receive only that one job/file;
`reset_between_scenes=True` means the initial reset for this single sequence,
never an internal session reset. Evaluator references, join positions, roster IDs
and capture metadata must never be passed to the prediction process.

Outputs of `continuity_sequence.py`: ADMISSION.json, PLAN.json, CONTINUITY_O0.wav
(about 37 MiB), INFERENCE_AUDIO_ONLY.json, EVALUATOR_TRUTH.json, COPY_RECEIPT.json
and RESULT.json, or FAILED.json with a preserved attempted prefix. Outputs are
private and must not be committed. The status is PREPARED_LOSSLESS_CONTINUITY_INPUT_ONLY.
Actual continuity, delivery, stop/restart, accuracy, resource and N4/N5 acceptance
remain false. This is not continuous physical XVF state. The existing paced-panel
runner does not admit this extra input yet: a separate qualified continuity
runner must join the accepted shortlist, exact source/configuration and exclusive
supervision before any launch. The baseline and every retained release candidate
must use this same input and policy. A functional stop/restart check remains due.

`probe_continuity_sequence.py` runs ten checks: full saved-bank deterministic
selection and capacity; exact reference preservation; missing/mismatched pairs,
gain and identity refusal; inadequate capacity/duration; no clipped reference or
silently dropped word times; exact tiny synthetic PCM byte concatenation;
hash/gain/offset/tap/header/census failures; and preserving existing/failed files.
The tiny PCM numbers test byte transport only and are never played. The probe
does not assemble the actual saved recordings. It writes immutable source
snapshots, ADMISSION.json, tests.txt, private metadata/truth and RESULT.json or
FAILED.json. Both commands use CPU14, the existing helper lock, disk/deadline
guards and the shared allowance with its six-GiB reservation. Do not run beside
controlled paced resource measurements. Use a fresh output for every attempt.

PowerShell qualification probe:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_continuity_sequence.py" --output "$jpLocal\n4\continuity-sequence-probe-v1"
```

Command Prompt and Anaconda Prompt (the pinned interpreter is used directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_continuity_sequence.py" --output "%JP_LOCAL%\n4\continuity-sequence-probe-v1"
```

After CONTINUITY_SEQUENCE_CHECK_V1.json records the passed implementation probe,
prepare the actual lossless saved-audio input (no application or playback):

```powershell
& $jpPython -B "$jpCode\continuity_sequence.py" --output "$jpLocal\n4\continuity-sequence-v1"
```

```bat
"%JP_PY%" -B "%JP_CODE%\continuity_sequence.py" --output "%JP_LOCAL%\n4\continuity-sequence-v1"
```
