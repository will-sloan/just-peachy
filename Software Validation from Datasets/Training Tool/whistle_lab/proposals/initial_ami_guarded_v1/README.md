# Proposed Whistle run: guarded AMI adaptation of the initial model

Status: **superseded for execution by the authorized exploratory mixed run**
(25 October 2026). The original `plan.json` remains the unchanged design snapshot.
The metadata prerequisite is implemented in `../../guarded_ami/audit_sources.py`,
with tested commands in `../../guarded_ami/README.md`. It found no entirely fresh
local CHiME-6 session: 10 sessions were used in parent training, 2 in earlier
development and 8 in the inspected historical comparison. The evidence is saved
in `training/whistle_initial_ami_guarded_v1/provenance_audit.json` under the repository.

The user accepted exploratory adaptation, retaining the initial model as default,
then explicitly allowed any dataset combination to improve transcription. The
execution amendment adds clean LibriSpeech replay to the four qualified domains
and freezes a bounded source-balanced visit schedule. It permits exploratory
held-out evaluation with the disclosed independence limitation; it never permits
automatic replacement of the initial model. Commands and maintained execution
instructions are in `../../guarded_ami/README.md`; the new output directory is
`training/whistle_transcription_guarded_v1` under the repository.
The completed campaign, its original policies and its models remain separate.

## Purpose and interpretation

Test whether a short, low-learning-rate AMI-only adaptation improves noisy speech
while preserving the initial tuned model's other capabilities. The initialization
is the original **final** adapter, not the production adapter.

This is AMI-only **additional** training. The initial model already learned from
Common Voice, AMI, CHiME-6 and VOiCES. A positive result would not prove that a
model trained exclusively on AMI is best, or isolate the causal value of AMI.
The objective is a better useful model with a single bounded trajectory.

The initial final model is the comparison reference and the default outcome.
It remains a valid candidate at step zero. Training is allowed to produce no
promoted replacement.

## What the completed evidence supports

The initial model is a better accuracy tradeoff than production on most of the
reported historical cohorts. Production improved AMI from 31.79% to 30.79% WER,
but worsened CHiME-6 from 63.23% to 66.43% and worsened the other six cohorts.
Base Whistle still has lower WER on the clean HiFiTTS and LibriSpeech cohorts
than either tuned model. "Best" therefore depends on the intended domains.

On the **four-dataset development panel**, the initial final model scored about
28.06% macro WER; the short mixed pilot 31.70%; and AMI-only 31.85%.
AMI was the strongest short single-dataset pilot, but it did not beat the initial
model or clearly improve on the matched short mixed pilot. Other single-dataset
pilots were worse overall. Removing VOiCES or CHiME-6 from the longer mixture
also worsened development WER and failed the saved gates.

The initial and production fits used different microphone pools and training
exposure. Their results do not identify a single cause of regression.
Domain over-specialization or forgetting is plausible; it has not been isolated
here. The next test therefore measures retention throughout training and keeps
the selected checkpoint, instead of assuming that a full final fit will improve it.

## Fixed proposed training recipe

| Item | Proposed value |
| --- | --- |
| Initialization | Preserved initial final adapter on the pinned pretrained base |
| Additional training | Qualified AMI training views only |
| Method | Existing attention LoRA, rank 16, alpha 32; base frozen |
| Learning rate | Peak 1e-5, 200-update warmup, cosine to 5e-7 over 10,000 updates |
| Optimizer | New AdamW state; weight decay 0.01; gradient norm cap 1 |
| Batch limits | 8 clips, 60 padded audio seconds, 1,024 tokens |
| Budget | First of 10,000 updates, one training pass, or one active optimizer hour |
| Native validation | Step zero, then every 2,000 updates; at most five candidate passes |
| Selection | Best checkpoint passing noisy, clean, age, VOiCES and quiet/noise guards |
| Final fit | None; preserve the selected export exactly |
| Total new training runs | One |

These are proposed conservative settings, not measured optimal settings.
Compilation, panel preparation and native scoring are outside the one-hour
optimizer cap. Based on the old short AMI pilot, training itself could be tens of
minutes; total elapsed time cannot be promised before the new panel and runner
are prepared.

Keep the existing audio quarantine, source-utterance weighting, quiet-view
confidence and annotation alignment. Use all eligible AMI microphone views under
that weighting; additional microphones do not count as independent utterances.
Do not assume energy alone establishes intelligibility. Do not add clean speech
to the training loss: it belongs to the retention evaluation in this experiment.

## Inputs and protected identities

- Base revision: `741118687e1f008f06d1351a402a731274789790`.
- Initial adapter: `training/whistle_age_robust_v1/adapter.final.safetensors`.
  SHA256: `2b65dbd47bc82f629e65f32e356299a15774073dec8d61f9181f9b477f8bc558`.
- Reference native model: `training/whistle_age_robust_v1/whistle.final.cact`.
  SHA256: `cd6b10970450112a70f08cbf6416cac04462932be4604bda8f93b758f5b1c337`.
- Existing published quality generation: `ce763f776b2cf4a81168`.
- Qualified AMI train metadata, pinned runtime/tokenizer/normalizer and retained
  license/attribution records.
- Frozen development and fresh confirmation manifests prepared as described below.

The proposed output root is
`C:\Users\amiri\Documents\GitHub\just-peachy\training\whistle_initial_ami_guarded_v1`.
Neither completed training directory may be reused as the new run directory.

A continuation must restore the trained adapter tensors on their original base.
It must not try to train directly from a merged quantized `.cact`, silently start
with random adapters, or resume the initial run's exhausted three-pass schedule.
After initialization, start a fresh optimizer/schedule in a separate run identity.
Verify zero-update native output equivalence to the initial model before training.

## Evaluation design

Freeze the panel and thresholds before the first optimizer update. Evaluate
AMI, CHiME-6, VOiCES and older-speaker Common Voice, plus CMU Arctic,
HiFiTTS clean/native and LibriSpeech clean/native. Target at least 128 distinct
utterances per cohort where available, with microphone slices retained and
source-group counts reported. This is a target sample size, not a power guarantee.

Group AMI by meeting, CHiME by session, VOiCES/Common Voice by speaker and other
speech by speaker/book/source recording. Keep microphone and re-recorded variants
of the same source together. Check exclusions against the **entire initial model's
training history**, not only the new AMI training split. Avoid creating apparently
fresh examples by changing segment boundaries.

The already-inspected 512-clip benchmark is historical evidence for this new
design. It cannot serve as a fresh independent confirmation test. Freeze an
additional unscored, source-disjoint confirmation set and leave its outcomes
unread until one development checkpoint is selected. Previously trained or
previously selected-on examples do not become independent when relabelled.
If such panels cannot be established locally, preparation stops and reports the
missing coverage; do not claim independent improvement.

A fresh age test requires genuinely unused, speaker-disjoint age data. The
previous production model's inclusion of development data is not a reason to
reuse those data as an independent test of that model. Only claim independence
for a model whose training history passes the audit.

Serialize native evaluation between saved training blocks. There should be one
owned training worker, with exact pause/resume, finite recovery and no competing
inference job. Keep all development checkpoints scored at the prescribed points.

## Selection, stopping and promotion

Primary score: equal-weight mean of AMI and CHiME-6 WER. The business goal is
better noisy-speech recognition while retaining other domains.

At each development check:
- Require at least 4,000 updates and 1,000 distinct AMI source utterances before
  a nonzero-step checkpoint can be selected for confirmation.
- Stop after three checks without at least 0.2 percentage-point improvement in
  the best primary score, or after two consecutive retention-guard violations.
- Keep the best eligible checkpoint and step zero. A checkpoint's latest loss
  alone does not select the exported model.

Select at most one checkpoint on development, then compare it with the initial
model once on confirmation. Promotion requires **all** of the following:
- At least 2% relative improvement in the AMI/CHiME primary WER.
- Upper bound below zero for the paired 95% interval of candidate minus initial
  primary WER. Use 10,000 bootstrap draws at the meeting/session/speaker group
  level, preserving within-source variants; report the number of groups.
- No AMI, CHiME-6, VOiCES, age, HiFiTTS-native or LibriSpeech-native WER increase
  greater than 0.5 percentage points.
- No clean CMU, HiFiTTS or LibriSpeech WER increase greater than 0.25 points.
- No quiet-speech WER increase greater than 1 point, with at least 100 reference
  words available.
- No increase in false-positive rate or inserted words on the 20 fixed
  silence/noise probes.

Apply the point guards on development and confirmation and report uncertainty
for retention slices. Small panels may be inconclusive. Failure or insufficient
evidence retains the initial model; there is no second candidate tested after
seeing confirmation, extra trial, seed search or train-plus-development refit.

Synthetic silence/noise probes do not establish real room or product-microphone
robustness. Any deployment claim still needs that evidence.

## How to inspect this design

No Conda activation is required. These commands only display and validate the
proposal; they do not train.

Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\proposals\initial_ami_guarded_v1"
type README.md
type plan.json
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m json.tool plan.json
```

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\proposals\initial_ami_guarded_v1'
Get-Content -LiteralPath .\README.md
Get-Content -LiteralPath .\plan.json -Raw | ConvertFrom-Json
```

## Implementation and execution status

There is no training launch command for this proposal yet. The existing
`followup/launch.ps1` controls the completed campaign and does not implement this
warm-start/retention design. Do not pass this proposal JSON to that worker.

Before execution, implement an isolated runner with explicit adapter loading,
step-zero selection, native checkpoint scoring, all stop/selection guards and
immutable panel hashes. Verify initialization, every batch shape and exact
optimizer/scheduler resume. Then add tested Anaconda/cmd and PowerShell
start/status/pause/resume commands here. No training was started and no disabled
report task or heartbeat was reactivated while writing this design or performing
the metadata prerequisite check.

## Expected outputs

The new run should produce immutable proposal/split snapshots, provenance and
initialization checks, control/status/checkpoint files, per-checkpoint validation
summaries, one confirmation summary, a saved accept/reject decision, model
identity/license provenance, the selected adapter/native export and a final
summary. Preserve initial and production models whether the candidate passes
or fails. Distinguish recorded measurements from proposed settings throughout.

## Evidence and references

Local evidence is recorded by hash in `plan.json`, especially
`dataset_contributions.json`, `extension_decision.json` and the completed
`summary.json`.

Cactus's [Whistle fine-tuning guide](https://www.cactuscompute.com/blog/finetuning-whistle)
documents adapter export, validation selection and checking native exported
models. This proposal retains the locally pinned implementation rather than
silently upgrading it.

[ASR domain-adaptation research](https://arxiv.org/abs/2207.00216) demonstrates that
adaptation can trade target-domain gains against retained capabilities. It
motivates explicit retention checks here; it does not prove the cause of this
Whistle regression or validate the proposed numerical settings.

