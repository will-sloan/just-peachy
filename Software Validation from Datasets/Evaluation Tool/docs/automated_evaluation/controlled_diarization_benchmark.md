# Controlled scientific diarization benchmark

## Scientific question and boundary

`controlled_diarization_v1` is a permanent model-independent reference for the
question “who spoke when?” It compares lightweight embedding clustering,
learned segmentation with the same embedding/clustering, and complete
diarization systems on identical audio. Primary scoring is permutation-
invariant and anonymous. `SPK00`, `SPK01`, and predicted `speaker_00` labels are
local clusters, never names.

Known-speaker recognition is a separate future overlay. The same waveform has
deterministic `ALL_UNKNOWN`, `MIXED_KNOWN_UNKNOWN`, and `ALL_KNOWN` metadata,
but those states never alter DER/JER. Enrollment uses reserved source clips,
not speech copied from a mixture.

## Source and holdout design

The default explicit source pool is the frozen Common Voice 60+ breadth
protocol `commonvoice_60plus_v1_27e72793b4c0`. Its pseudonymous speaker
inventory defines the cohort. Its canonical `validated.tsv` supplies additional
natural complete utterances needed for realistic rapid scheduling; the
generator freezes every selected clip path, transcript hash, source-audio
SHA-256, crop, and gain.

The source is prompted/read speech. The voices are real; turn-taking is
synthetic. Raw contributor IDs and transcript text are not published. The
implemented pools are:

| Tier | Speakers | Recordings | Use |
| --- | ---: | ---: | --- |
| Smoke | 12 | 8 | non-scientific contract/runtime check |
| Development | 60 | 60 | clustering and segmentation parameter decisions |
| Evaluation | 120 | 120 | frozen scientific comparison |

All three speaker pools are disjoint. Evaluation speakers, evaluation source
clips, and rendered evaluation mixtures are listed in
`protected_evaluation_assets.json` and prohibited from future training.

## Factorial panel

The development and evaluation multi-speaker panels cross:

- speaker count: 2, 3, 5;
- synthetic cadence: relaxed, standard, rapid;
- overlap: none, backchannel/short-overlap, moderate.

Development has two replicates per cell (54 mixtures) plus six single-speaker
controls. Evaluation has four replicates per cell (108 mixtures) plus twelve
single-speaker controls. Every multi-speaker source appears in at least three
non-adjacent turns. Greedy deterministic assignment minimizes speaker
appearance imbalance, pair co-occurrence, and source reuse.

Relaxed and standard cases target 60 seconds. Rapid cases target 48 seconds,
inside the preregistered 45–75 second range, because naturally short complete
utterances are scarce. This avoids random word cuts, looping, or exact clip
reuse. Actual turn, gap, overlap, participation, and re-entry values are stored
per case.

## Waveform and reference construction

Each MP3 is decoded, downmixed, resampled to mono 16 kHz, and conservatively
trimmed only at its leading/trailing boundaries using
`deterministic_boundary_rms_v1` at -60 dBFS with 20 ms frames/padding. Internal
pauses remain. Source RMS is adjusted toward -24 dBFS with gain limited to
±12 dB. A final deterministic peak-protection gain keeps the PCM16 mixture
below -3 dBFS. Every gain is recorded.

Timing is written from exact global sample placements during rendering:

```text
source file/hash + prepared crop + gain + global start/end sample
    -> waveform placement
    -> JSON recipe + RTTM + UEM
```

Overlapping source placements create simultaneous RTTM rows; they are never
collapsed into a new speaker. This is exact synthetic placement timing, not
human annotation. Small leading/trailing or internal source pauses can remain,
which is an explicit limitation.

Every WAV has a file SHA-256 and canonical PCM SHA-256. Recipes preserve the
seed, source path/hash, crop, gain, channel, sample rate, order, and placement.
The reconstruction test renders the same recipe twice and requires identical
output hashes.

## Scoring and diagnostics

Primary scoring reuses the existing Stage 11 RTTM/UEM scorer with strict
zero-collar, overlap-included DER/JER. It also writes:

- 0.25-second practical boundary-tolerant DER;
- non-overlap DER;
- missed speech, false alarm, and speaker confusion;
- reference/predicted speaker count, signed/absolute error, and exact accuracy;
- split/fragmentation and merge counts;
- cluster purity and reference-speaker coverage;
- explicitly defined re-entry consistency: the fraction of later turns mapped
  to the reference speaker’s dominant predicted cluster;
- overlap-only scoring where overlap exists;
- boundary precision/recall/F1 at ±250 ms and ±500 ms;
- wall time and real-time factor grouped by machine/environment.

`oracle_turn_campplus_diagnostic` embeds and clusters exact reference turns on
non-overlap development cases. It is diagnostic only and never appears in the
primary ranking. Oracle speaker count is likewise a separate diagnostic mode.

## Development and evaluation gate

Every result-affecting modular threshold belongs to one exact pipeline. Tune it
on development only. Run analysis, make an operator decision, then use
`freeze-pipelines` to bind the benchmark ID and exact pipeline configuration
hashes. Evaluation refuses to run when that file is absent, unresolved, bound
to a different benchmark, or missing the no-evaluation-tuning declaration.

Complete/off-the-shelf Community-1 should first use its documented local
default. Do not tune it aggressively while leaving another complete pipeline
at defaults unless the comparison is explicitly labelled tuned.

## Restart and environment isolation

The management process plans units but never imports incompatible model stacks.
Each unit is launched with the interpreter declared for its pipeline profile.
Valid checksum-bound results are reused. Invalid/partial and failed attempts are
preserved separately. A stop request is checked between cases. Runs are always
sequential unless a future qualification explicitly authorizes concurrency.

## Analysis

Analysis produces the required overall, recording, factor, speaker-count,
overlap, cadence, fragmentation, merge, single-speaker-control, re-entry,
resource, reliability, oracle, and paired-comparison tables. Development and
evaluation remain separate. Paired
recording-level bootstrap intervals use seed 3800. Interaction plots are
separate rather than combined into one unreadable figure. No composite
“diarization score” is calculated; advancement is a Pareto judgment across
accuracy, confusion, overlap, count, fragmentation, re-entry, reliability,
runtime, RAM availability, integration, and terms.

## Limitations

1. The source is prompted/read speech, not spontaneous conversation.
2. Turn scheduling is synthetic.
3. Placement timing is exact for the recipe but is not human frame-level speech annotation.
4. Source microphones and rooms differ by speaker.
5. Gain normalization reduces some source-level variability.
6. Clean mixtures do not replace room, microphone, or XVF3800 testing.
7. Primary Stage 11 evaluates anonymous diarization, not known-speaker recognition.
8. Full product evidence still requires hybrid identity and target-device studies.

## Commands

From Anaconda Prompt/Command Prompt, activate `.venv`, enter the Evaluation Tool,
and use `python run_evaluation.py diarization-benchmark ...`. From PowerShell,
use `scripts/run_controlled_diarization.ps1`. The package README contains exact
Audit, Prepare, Validate, Plan, Smoke, development, freeze, evaluation, Analyze,
and Collect examples plus every input/output root.
