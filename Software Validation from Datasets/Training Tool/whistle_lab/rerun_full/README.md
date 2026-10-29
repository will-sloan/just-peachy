# Whistle full-parameter rerun

The user requested a complete rerun on 26 October 2026 to seek an incremental
transcription improvement. This is one **fresh pretrained-base, full-parameter**
trajectory, separate from the completed initial, follow-up and short continuation
experiments. The preserved initial final model remains the default. Full tuning
is a hypothesis to test, not a promise of improvement.

## Fixed training design

- Start from the original pinned Whistle pretrained weights, revision
  741118687e1f008f06d1351a402a731274789790; no initial adapter is merged.
- Train every parameter using the locally tested full-training QAT path,
  bf16 activations, rematerialization and the existing native exporter.
- Use all 2,052,751 qualified **training** microphone views from the published
  audit. Three complete passes give 6,158,253 view visits. These are not distinct
  utterances. Preparation records distinct sources and exact update counts.
  The frozen pool contains 220,174 distinct source utterances. Each pass has
  294,740 updates; the three-pass horizon is 884,220 updates. The first native
  validation is at update 147,370. All 55,151,433 parameters are trainable.
- Preserve original relative objective weights: Common Voice 40.0807412535%,
  AMI 31.3596765027%, CHiME-6 18.5595822438%, VOiCES 10%.
  Within each dataset, source utterances have equal total mass; microphone views
  share it according to the completed audit's confidence. Quiet views retain
  their relative .25 confidence; quarantined views remain excluded.
- AdamW, peak learning rate 1e-5 (one tenth the original LoRA rate), 1,000-update
  warmup, cosine decay across the entire three-pass horizon to 5e-7, weight
  decay .01, gradient norm cap 1. Batch caps: 8 clips, 60 padded audio seconds,
  1,024 tokens. These full-method settings fitted this RTX 3080 in the earlier
  short pilot; this run still verifies all GPU shapes.
- Every row is visited once per pass, including partial batches. Loss scaling
  preserves row influence across variable batch sizes. Dataset weights control
  the loss objective, not the fraction of raw microphone-view visits.
- Six native-model validations: halfway through and at the end of each pass.
  No 10,000-update/one-hour pilot cap and no early stopping for initial poor
  scores. Numerical failure, a user pause or exhausted recovery stops safely.
  There is no automatic memory-method fallback, recipe change, sweep or refit.

The earlier full-method pilot saw only 69,791 views in 10,000 updates, so its
inconclusive result did not test three-pass full training on this pool. This run
changes method and qualified-view coverage together; it cannot isolate which
change causes any measured difference.

## Inputs and outputs

Output: C:\Users\amiri\Documents\GitHub\just-peachy\training\whistle_full_rerun_v1

Inputs are the unchanged base assets and initial final reference in
training/whistle_age_robust_v1, the completed qualified training manifest in
training/whistle_followups_v1/quality, and the already frozen exploratory panels
and initial baseline in training/whistle_transcription_guarded_v1.
Preparation reads metadata and hashes; it does not rescan audio or launch a new
quality audit. It checks source and meeting/session/speaker separation,
including shared LibriVox reader identities, against the full training pool.

No development or evaluation examples join training. No new downloads, dataset
policy changes or environment upgrades are needed. The completed quality
generation is ce763f776b2cf4a81168. Original age filtering, the 45 quarantined
AMI TS3007c annotations, near-silent quarantine and CHiME opening annotation
reservations remain in force. Amplitude confidence does not prove intelligibility.

The main outputs are:
- config.json, split_snapshot.json, execution_snapshot.json: frozen recipe,
  complete exposure, code/input hashes and explicit authorization.
- initialization_verification.json, resume_verification.json, preflight.json:
  exact pretrained initialization, full optimizer round-trip and all GPU shapes.
- checkpoint.msgpack and checkpoint.previous.msgpack: full weights, AdamW state,
  scheduler count and exact epoch/batch position; checkpoint.json is small.
- weights.step_XXXXXXX.msgpack and whistle.step_XXXXXXX.cact: six distinct
  full-parameter/native candidate exports with hashed exports/ receipts.
- whistle.base_zero.cact: distinct fresh pretrained zero-update native export.
  **Scoring ID zero always means the preserved initial tuned comparator.**
- scores/dev_XXXXXXX.json, paired uncertainty summaries and confirmation scores.
- validation_summary.json, development_decision.json, confirmation_summary.json,
  decision.json, model_manifest.json and final summary.json.
- whistle.selected.cact: byte-identical initial default; separately named
  weights.experimental.msgpack / whistle.experimental.cact only when selected.
- status.json, control.json, monitor_state.json, worker.log, launcher.json,
  worker.json and finite recovery summaries.

Full weights are not LoRA adapters. Do not load a weights.msgpack into the
adapter loader. Use the exported native cact model for transcription. The
existing runtime and source hashes are pinned; do not upgrade or edit training
code after execution_snapshot.json is frozen.

## Evaluation and limitations

Compare source-balanced native WER across all nine cohorts: AMI, CHiME-6, VOiCES,
older-speaker Common Voice, CMU clean, HiFiTTS clean/native and LibriSpeech
clean/native. Average microphone variants within each utterance before cohort
WER. The primary objective is equal-weight nine-cohort macro WER.

Screen for at least a 0.2 percentage-point macro WER decrease versus initial,
with every clean cohort worsening at most 0.25 points, other cohorts at most
0.5 points, quiet speech at most 1 point with at least 100 reference words,
and no extra false positives or inserted words on the 20 silence/noise probes.
Missing evidence fails. Choose the best passing checkpoint after all three
passes; ties favor the earlier checkpoint. If none pass, retain the initial.
These screening thresholds are fixed design choices, not established optima.

Each completed checkpoint gets paired 95% cluster-bootstrap intervals
(10,000 draws) by meeting/session/speaker. Development intervals are descriptive
and not corrected for selecting among six checkpoints. Freeze one candidate,
then score it and the initial on the separate exploratory confirmation panel;
never use confirmation to try a runner-up. A positive numerical confirmation
requires the same guards, at least 0.2 points macro gain and an upper macro
delta interval below zero. Regardless, the initial model stays default.

These panels reuse previously evaluated populations. All local CHiME sessions
have prior exposure. They are **not fresh independent confirmation**. VOiCES
has sparse source coverage, and HiFiTTS clean confirmation has only one reader:
its interval, and therefore the full nine-cohort confirmation interval, are
undefined. Do not substitute zero uncertainty or claim a proven general gain.
Product-microphone validation, base pretraining independence and an independent
final age test are not established. Preserve all cohort regressions in reporting.

Base/runtime: Apache-2.0. Common Voice: CC0; AMI and VOiCES: CC-BY-4.0;
CHiME-6: CC-BY-SA-4.0 (resolved by the user 23 October). Preserve attribution,
share-alike obligations and the original release_review.json provenance.
The public [Whistle fine-tuning documentation](https://www.cactuscompute.com/blog/needle-python-docs)
describes LoRA; full training here uses the existing repository implementation.

## Anaconda Prompt or Command Prompt

No conda activation is required; use the existing pinned environments.

~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\rerun_full"
wsl.exe -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -m unittest discover -s "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/rerun_full" -p "test_*.py"
wsl.exe -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -u "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/rerun_full/prepare.py"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\install_monitor.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\launch.ps1" -Action start
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\launch.ps1" -Action status
~~~

## PowerShell

~~~powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\rerun_full'
wsl.exe -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -m unittest discover -s '/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/rerun_full' -p 'test_*.py'
wsl.exe -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -u '/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/rerun_full/prepare.py'
.\install_monitor.ps1
.\launch.ps1 -Action start
.\launch.ps1 -Action status
.\launch.ps1 -Action pause
.\launch.ps1 -Action resume
~~~

Anaconda/cmd pause or exact continuation:

~~~bat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\launch.ps1" -Action pause
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\launch.ps1" -Action resume
~~~

Start is idempotent for an owned active launcher; a completed run does not
restart. Pause saves at a safe boundary. Resume clears only this run's pause;
a pause in any of the three earlier runs remains effective. Do not launch
worker.py or score.py alongside the owned pipeline.

## Ownership, recovery and monitoring

A hidden Windows launcher and distinct mutex start one WSL supervisor.
An inherited Linux supervisor lock and the shared old training/GPU locks
prevent duplicate/competing workers. The Windows scheduled task
**JustPeachy Whistle Full Rerun Monitor** checks every 15 minutes and at sign-in.
Each stage has three attempts; at most two unexpected supervisor recoveries
are automatic. Failed stages require inspection; never delete state, start
from scratch or change method to bypass a failure. Exact continuation restores
full weights, optimizer, warmup/cosine position and deterministic epoch batch
position. Latest and previous checkpoints are retained.

The existing Codex heartbeat whistle-training-check-in monitors this new root,
remaining at 15 minutes during preflight, export, scoring and stage transitions.
During healthy advancing training, use two hours above three hours remaining,
30 minutes with one to three hours remaining, otherwise 15 minutes. A user pause
or already reported block awaiting action uses three hours.
ETA measures training progress only; future scoring, compilation/export, disk
writes and pauses add time. It is not a promised whole-campaign completion time.

Read small states and at most the final 40 log lines at heartbeat visits.
No dataset/prediction scans, new evaluations alongside training, repeated waits,
extra trials or automatic promotion. Record state, cadence and milestones in
the new monitor_state.json while preserving recovery history.

## Findings report

Keep the existing Word findings document and its CPU scheduled report task.
The collector does not automatically collect this root. On completed milestones,
append stable, evidence-hashed entries to the existing reporting/analyst_notes.json
and invoke ../reporting/update_report.ps1 once. Follow ../reporting/README.md.
Do not block training for Word locks or visual-review limitations. The previously
blocked renderer installation must not be retried.

After a complete summary and final interpretation are published, deliver actual
nine-cohort/quiet/noise results, uncertainty, model paths and license provenance.
Then disable the Full Rerun Monitor, Findings Report task and the same heartbeat.
Do not disable them because any older experiment is complete.

## Launch record: 26 October 2026

Preparation verified all three complete metadata schedules, original objective
weights and train/evaluation group separation. Six automated tests passed,
covering full-pass membership, weighting, fixed recovery boundaries, guard/identity
checks, absence of pilot early stopping, and sparse-group uncertainty. The owned
WSL worker has launched. Fresh-base initialization matched exactly; full optimizer
and all-shape GPU preflight are recorded as they complete. Optimizer progress and
the measured training ETA must be read from this run's current status.json.
