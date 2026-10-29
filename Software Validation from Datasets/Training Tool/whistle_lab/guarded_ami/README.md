# Exploratory Whistle transcription adaptation

The user authorized execution on 25 October 2026, accepted exploratory evaluation,
and then allowed any combination of datasets to improve transcription. This
implementation continues the preserved **initial final adapter** on its original
base. The initial model remains the default regardless of this experiment's scores.
The original completed campaign and its frozen policies are unchanged.

The directory name is retained from the initial AMI proposal; the executed run is
**whistle_transcription_guarded_v1**, using mixed-domain clean replay.

Execution completed on 25 October 2026 at 4,000 updates after two consecutive
retention-guard violations. The 2,000-update checkpoint exceeded the clean
HiFiTTS limit; the 4,000-update checkpoint exceeded the AMI and quiet-speech
limits. No nonzero checkpoint qualified, so confirmation was not run and the
unchanged initial model remains the default. The saved `summary.json`,
`validation_summary.json` and `decision.json` contain the completed evidence.
Start/resume commands do not restart a completed run or authorize a new trial.

## Purpose and fixed scope

Test one conservative continuation that gives the model practice on both noisy
and clean speech. These settings are a bounded hypothesis, not known optimal
settings. There is one trajectory, at most five candidate validations, one
preselected exploratory confirmation, and no refit or automatic deployment.

- Original qualified domains: approximately 32.064% older-speaker Common Voice,
  25.088% AMI, 14.848% CHiME-6 and 8% VOiCES.
- Clean replay: 20% LibriSpeech, from 8,000 deterministic utterances in the official
  train-clean-100 split. Its speakers are excluded from all evaluation cohorts.
- A frozen 100,000-visit schedule cycles source utterances within each dataset.
  It samples microphone views using the published relative quiet-view confidence.
  Views and repeat visits are not independent utterances. All retained examples
  receive unit loss weight after sampling.
- LoRA rank 16, alpha 32, original base frozen, bf16 and pinned upstream QAT.
- Fresh AdamW state, peak learning rate 1e-5, 200-update warmup, cosine schedule
  over a fixed 10,000-update horizon to 5e-7, weight decay .01, gradient norm cap 1.
- Batch caps: 8 clips, 60 padded audio seconds and 1,024 tokens.
- Stop at the first of 10,000 updates, 3,600 active optimizer seconds or one
  pass through the frozen visit schedule. Loading, compilation, export and
  evaluation are outside the optimizer-time cap.
- Native exported-model validation at step zero and steps 2,000/4,000/6,000/8,000/
  10,000. An earlier terminal checkpoint replaces the next slot. A partial
  recovery checkpoint does not create another evaluation slot.

The exact data and execution amendment are frozen and hashed before model updates.
No model or dataset is uploaded. No new audio-level audit is launched.

## Inputs and provenance

- Unchanged initial adapter:
  training/whistle_age_robust_v1/adapter.final.safetensors
- Initial native reference:
  training/whistle_age_robust_v1/whistle.final.cact
- Base revision: 741118687e1f008f06d1351a402a731274789790.
- Published qualified training/development manifests, quality generation
  ce763f776b2cf4a81168; existing quarantine and aligned transcripts are reused.
- Normalized LibriSpeech, HiFiTTS and CMU metadata, original eligible speaker/
  meeting/session metadata, and the existing historical CHiME manifest.
- Existing repository Windows virtual environment and pinned WSL Ubuntu Whistle
  environment. No environment upgrade is required.
- execution_amendment.json records the user's exploratory choice and subsequent
  direction permitting a dataset combination.

LibriSpeech clean replay is CC-BY-4.0. The parent already incorporates Common
Voice, AMI, CHiME-6 and VOiCES. Preserve all parent attribution/license provenance;
CHiME-6 licensing was resolved by the user. Base weights/runtime are Apache-2.0.

## Evaluation and default-model safeguards

Both panels cover AMI, CHiME-6, VOiCES, older-speaker Common Voice, CMU clean,
HiFiTTS clean/native and LibriSpeech clean/native. They are disjoint by the
declared grouping identities and excluded from parent/new training. Shared
LibriVox reader identities are excluded across VOiCES/LibriSpeech/HiFiTTS.
The target is 128 distinct sources per cohort per panel where available; actual
counts and group shortfalls are recorded. This target is not a power guarantee.

The 20 local CHiME sessions were already used in earlier training/development/
historical evaluation. The new panels use previously evaluated populations.
They **are exploratory**, not fresh independent confirmation. Pretrained-base
corpus independence, real product-microphone performance, and an independent
final age test are also not established.

The primary score remains equal-weight AMI/CHiME WER, with nine-cohort macro WER
also reported. A nonzero candidate needs at least 4,000 updates and 1,000 distinct
AMI sources. Each noisy/age/VOiCES/native retention cohort may increase at most
0.5 percentage points; clean cohorts at most 0.25 points; quiet speech at most
1 point with at least 100 reference words. The 20 fixed silence/Gaussian-noise
probes must not gain false positives or inserted words. Missing evidence fails
a guard. Select the best eligible passing checkpoint, earlier on an exact tie,
with step zero always available.

Stop after two consecutive guard failures or three validations without a
0.2-point primary improvement. Freeze one development candidate before its
exploratory confirmation; never try a runner-up after viewing confirmation.
Report paired 95% cluster-bootstrap intervals with 10,000 draws. Numerical gains
still do not authorize replacement: selected/default artifacts remain the
unchanged initial model. A passing experimental artifact has a separate name.

## Output directory and files

C:\Users\amiri\Documents\GitHub\just-peachy\training\whistle_transcription_guarded_v1

- proposal_snapshot.json and execution_amendment.json: original design and
  explicitly authorized exploratory/mixed-replay amendment.
- train.parquet, dev.parquet, confirmation.parquet, split_snapshot.json,
  data_audit.json and audio_header_audit.json: immutable schedules and provenance.
- initialization_verification.json: actual zero-update export byte equivalence.
- preflight.json and resume_verification.json: every shape and exact
  optimizer/scheduler next-update tests; diagnostic updates are discarded.
- control.json, status.json, checkpoint.json: small monitoring/control records.
- checkpoint.msgpack and checkpoint.previous.msgpack: exact optimizer state.
- worker.log, launcher.json, worker.json, recovery.json and launcher_recovery.json:
  owned process evidence and finite recovery history.
- adapter.step_XXXXX.safetensors, whistle.step_XXXXX.cact, exports/ and scores/:
  distinct checkpoint exports and resumable per-panel results.
- validation_summary.json, development_decision.json, confirmation_summary.json,
  decision.json, model_manifest.json and summary.json: completed evidence.
- adapter.selected.safetensors / whistle.selected.cact: preserved initial default.
- adapter.experimental.safetensors / whistle.experimental.cact: only the one
  nonzero development-selected candidate, if any.

## Commands: Anaconda Prompt or Command Prompt

Use the existing environments; no conda activation or package installation is
required. Preparation reads metadata, tokenizes clean replay and checks selected
audio headers. It can take several minutes; it performs no optimizer updates.

~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\guarded_ami"
wsl.exe -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -u "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/guarded_ami/prepare.py"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m unittest test_audit_sources.py test_policy.py
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\install_monitor.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\launch.ps1" -Action start
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\launch.ps1" -Action status
~~~

Safe pause and exact continuation:

~~~bat
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\launch.ps1" -Action pause
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\launch.ps1" -Action resume
~~~

## Commands: PowerShell

~~~powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\guarded_ami'
wsl.exe -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -u '/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/guarded_ami/prepare.py'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe' -m unittest test_audit_sources.py test_policy.py
wsl.exe -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -m unittest discover -s '/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/guarded_ami' -p 'test_*.py'
& .\install_monitor.ps1
& .\launch.ps1 -Action start
& .\launch.ps1 -Action status
& .\launch.ps1 -Action pause
& .\launch.ps1 -Action resume
~~~

Start is idempotent for a live owned launcher. Status is read-only. Resume clears
only this run's local pause; either older run's user pause is still respected.
Do not launch worker.py or score.py manually while the supervisor owns the run.

## Startup, ownership and recovery

The hidden Windows launcher starts one WSL supervisor. The supervisor serializes
initialization, native baseline scoring, training blocks and native validation.
The initial export must match the preserved native model byte-for-byte before
any optimizer update. Every batch shape and a full optimizer/scheduler
serialization round trip must pass. This can leave the launched run in
preflight or scoring before its first update.
The complete WSL test suite also exercises partial-checkpoint recovery, paired
reference identity and sparse-speaker panel coverage. Verified GPU shapes are
warmed again after process restarts, with those discarded updates excluded from
the optimizer-time budget.

Windows process identity and a mutex prevent duplicate launchers. The WSL
supervisor lock is inherited by its active child, so an orphan child retains
ownership. Training/scoring also hold the shared original trainer and follow-up
GPU locks, preventing competing jobs.

Each stage has at most three attempts. Recovery uses saved optimizer and
prediction state; unreadable checkpoints fail closed, without restarting from
scratch. The scheduled task **JustPeachy Whistle Exploratory Monitor** checks
every 15 minutes and at sign-in. It allows at most two unexpected supervisor
recoveries and does not automatically bypass a recorded failed stage or user
pause. It disables itself after a complete summary is published.

Inspect status.json and at most the last 40 worker.log lines after a failure.
Do not edit frozen data/configuration, remove checkpoints, launch another trial,
or use a different recipe as a recovery mechanism.

## Findings and heartbeat

During execution, the existing Codex heartbeat `whistle-training-check-in` runs
every 15 minutes. It records small-state observations and completed milestone
analysis in this run's `monitor_state.json`, preserving recovery history.
Normal progress does not require a notification. The older campaign's completion
does not end monitoring of this separately authorized run.

The existing `JustPeachy Whistle Findings Report` task stays active until final
publication, after which both this report task and the heartbeat are disabled.
Its original
collector does not automatically ingest this new run directory. Completed
milestones are added as evidence-hashed entries to
`training/whistle_followups_v1/reporting/analyst_notes.json`, then published by
`whistle_lab/reporting/update_report.ps1`. Earlier findings remain in the same
Word report. See `../reporting/README.md` for commands, document locks and the
retained visual-review limitation. Reporting does not control training.

The separate historical audit_sources.py command still documents why the
original fresh-session gate failed. Its --write output is the earlier
whistle_initial_ami_guarded_v1 preparation directory, not this executing mixed
run. Its exit code 2 is an expected provenance failure, not a training failure.
