# Bounded local Whistle follow-up campaign

## Authorized amendment — 24 October 2026

`extension_plan.json` is a separately frozen amendment to the original eight-run
`plan.json`; the original policy and `production_all_audio` configuration and
checkpoint identity stay unchanged. The combined maximum is **12 training runs**.
The current production fit finishes first and is preserved. Its frozen-test
scoring is deferred until the following development-only decision is fixed:

1. `ext_mix_reference`: fresh-base LoRA on the original four-dataset mixture.
2. `ext_without_voices`: same recipe with VOiCES omitted.
3. `ext_without_chime6`: same recipe with CHiME-6 omitted.
4. Only if an omission passes all guards, `production_selected_omission`: one
   fresh-base three-pass fit on the retained qualified train plus dev views.
   Otherwise keep `production_all_audio`; do not refit an unchanged recipe.

Each new pilot stops at **30,000 updates, two active training hours, or three
passes**, whichever comes first. Maximum additional pilot training is six active
hours; compilation, export and scoring are extra. Batch limits are 8 / 60 padded
audio seconds / 1,024 tokens, with the same base, LoRA settings and seed. Original
relative dataset weights are renormalized over the retained datasets. Every
pilot uses qualified training only and the same four-dataset development panel.
Record actual duration, updates, audio and per-dataset view visits. Promotion
also requires at least 20,000 updates and 500 visited views per retained dataset
for both reference and candidate. These are exposure floors, not proof of
representativeness. An insufficient run is inconclusive, not extended or retried
with a new budget. No extra seeds, method/rank/weight sweep or recursive trials.

The original WER/bootstrap/dataset/quiet/noise guards still apply. The pilots
answer a marginal-contribution question that standalone adaptation cannot answer;
they do not establish a globally optimal mixture or account for all multiple
comparisons. Current production already includes development data, so its
development accuracy cannot select the new recipe. Neither production test
result can trigger another experiment. Both production identities, if present,
are reported in the final matched comparison after the decision is fixed.

Implementation: `extension.py` validates the amendment, pins the existing policy,
production identity/config and completed audio-audit summary, freezes
`extension_snapshot.json`, restricts stage-specific jobs and gates one optional
refit. `extension_decision.json` records development comparisons and exposure;
`extension_production_decision.json` records the retain/refit decision. Per-run
matched summaries preserve both model identities. `summary.json` names the
selected model. It is written only after all authorized work and comparisons.
The small-file ETA shows the current fit separately and an explicit conditional
upper scenario including one extra fit. Exporting the first model does not mark
the amended campaign complete. No data scan occurs in dashboard polling.

Use the existing commands below; no second supervisor, GPU worker or environment
is required. Never rerun preparation or reset checkpoints merely to install this
amendment. A running supervisor may need an ownership-verified process refresh;
its existing WSL launcher is reattached without terminating GPU work. Pause
controls and three-attempt recovery apply to every additional stage.

CPU verification from **Anaconda Prompt or Command Prompt**:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
.venv\Scripts\python.exe -m pytest "Software Validation from Datasets/Training Tool/whistle_lab/followup/test_campaign.py" "Software Validation from Datasets/Training Tool/whistle_lab/followup/test_extension.py" -q -p no:cacheprovider
```

In PowerShell use the same directory with `Set-Location`, and prefix the Python
command with `& '.\.venv\Scripts\python.exe'`. These tests write temporary
fixtures only; they do not train or read audio. They cover budget/identity
immutability, deferred frozen scoring, insufficient-exposure fallback,
conditional refitting, preserved model comparisons and whole-campaign ETA.

This supervisor waits for the original AGE + ROBUST training **and its queued
matched comparison** to finish. It then audits additional microphone views, runs
a bounded development comparison, trains one final candidate, and evaluates the
frozen test. All data and compute stay on this computer. It never rewrites the
original run or starts a second GPU worker beside it.

## Original scope and limits (preserved beneath the amendment)

The plan in `plan.json` permits at most **eight training runs**:

1. One expanded-data LoRA reference.
2. Four LoRA pilots, one each for age-filtered Common Voice, AMI, CHiME-6 and VOiCES.
3. At most one mixture-weight proposal: multiply the best standalone dataset's
   weight by 1.5 and renormalize. Skip it if no standalone pilot beats the base.
4. One full fine-tuning pilot, compared with the selected LoRA mixture.
5. One final three-pass production candidate, using the selected method and
   weights on all eligible training plus development recordings.

Each pilot stops at 10,000 optimizer updates, three passes, or **one hour of
active training**, whichever comes first. Shape compilation, audio auditing,
export, and native-runtime scoring are additional time. All pilots use at most
8 clips, 60 padded audio seconds and 1,024 target tokens per batch. The final
fit has three passes and no pilot time cap: every retained view is visited in
each pass. If LoRA wins, that final fit uses the original run's faster validated
batch limits (16 clips / 120 padded seconds / 2,048 tokens), with a fresh shape
preflight on the expanded pool. Full tuning retains the smaller batch limits.
Pilot comparisons use identical batch limits; final refitting changes data and
may change LoRA batch sizes, so pilot gains are not promised final gains.
The original protocol had no omission sweep, LoRA-rank sweep, partial-tuning pilot, second-seed
sweep, or repeated weight search is queued. A retry resumes the same experiment
and budget. Three failures require attention; a full-tuning CUDA out-of-memory
failure marks that method unavailable and retains LoRA. No batch-size search is
started automatically. `policy_snapshot.json` prevents changing the policy once
the campaign begins.

These short pilots are screening experiments, not a definitive causal ranking
of datasets or proof of the best possible full-tuning result. Single-dataset
runs can hit the epoch/time caps at different exposures. A fixed development
panel is scored with the native W4A8 deployment runtime. Mixture/method promotion
requires at least 2% relative macro-WER improvement, a paired cluster-bootstrap
95% interval below zero, and no dataset worsening by more than 2 WER percentage
points. Resampling uses AMI meetings, CHiME sessions, and the other datasets'
speakers; the small number of CHiME development sessions limits certainty.
These intervals do not correct for the whole model-selection process.

The public base is also exported to W4A8 for a like-quantization development
reference. The original public mixed-bit base, initial tuned models and cached
GigaSpeech results remain in the original frozen-test comparison. No frozen
test result selects weights or method. The final frozen test is evaluated once,
after the final fit, and does not start another optimization cycle. Final scores
and development scores have different cohorts and must not be compared as one
ranking. Recorded-dataset results cannot establish performance on the future
product microphone. There is no untouched age test after development is folded
into the final fit; fresh product recordings are needed for that claim.

## Microphone and level policy

Development scoring reuses a completed decode and negative probes when best and
final exports are byte-identical within the same scoring invocation. Model hash,
panel and runtime therefore match; the result explicitly identifies reused
timings. Different weights still receive independent decodes. This avoids
redundant CPU inference without changing selection or training budgets.

Only the already selected source datasets are expanded. Original annotation
timing, text cleaning, age filters and known AMI annotation quarantine persist.

- **AMI:** all locally present Array1 channels 01–08 and the transcript speaker's
  own headset. Another participant's headset is not assumed to have the same
  foreground transcript. No Array2/lapel files are locally present in the audit.
- **CHiME-6:** both channels of the corresponding speaker's worn microphone and
  all locally present synchronized `Sxx_Uyy.CHn.wav` array channels for eligible
  sessions. Times remain relative to the original synchronized recordings.
  Two S01 development utterances (44 expanded views) overlap the user-reported
  opening beep. The quality audit reserves those complete labelled segments;
  it does not cut off a second while keeping a now-incomplete transcript. No
  original training annotation overlaps that opening second. Never remove a
  second from every extracted utterance. Additional views beyond actual file
  bounds are documented and excluded.
- **VOiCES:** existing close/far re-recordings plus locally present clean source
  speech for the same eligible utterances. Distractor-only recordings have no
  foreground speech transcript and are not assigned one.
- **Common Voice:** the existing age-filtered training/development selection.

Frozen-test AMI meetings, CHiME sessions and VOiCES speakers are reserved from
the expanded campaign, including all their microphone views. The source audit
found shared VOiCES speakers between the old training plan and the frozen
benchmark; their recordings are reserved from this new campaign. This does not
retroactively make the original Whistle/GigaSpeech comparisons speaker-disjoint.
`pool.json` records exact identities/counts and original manifest hashes.

After the original run finishes, `quality.py` makes one CPU pass over eligible
AMI, CHiME and VOiCES files, with two threads. It decodes each file once, measures
20 ms RMS/peak frames and clipping, and caches per-segment results in SQLite.
Completed files survive a pause/crash. Common Voice is retained without this
multi-microphone level audit. No PCM copy is created and no dataset ASR inference
is required for the audit.

Levels are dBFS (relative to digital full scale), **not SNR or intelligibility**.
Speech-labelled views with RMS below -65 dBFS **and** peak below -50 dBFS are
quarantined. Other views with RMS below -45 dBFS **or** peak below -35 dBFS receive
0.25 relative view confidence. Dataset totals and source-utterance weighting
remain normalized: more microphones cannot multiply a dataset's influence.
The confidence reduces a quiet view relative to clearer views of that same
utterance; if every surviving view has the same confidence, it cancels in that
normalization. Genuine blank targets remain blank-target examples. No positive
transcript is silently changed to silence. No automatic gain or denoising is
applied. Low gain can be recoverable; loud noise with inaudible foreground speech
can evade an energy check. The report explicitly records this limitation.

The development panel includes quiet views of sampled source utterances when
available. Every model is also tested on 20 fixed synthetic silence/white-noise
probes (3–20 seconds, several levels). A candidate cannot be promoted if its
probe false-positive rate or total inserted words increase. Quiet-speech WER
may not regress by over 3 percentage points when at least 100 reference words
are available. These probes are evaluation only and cannot guarantee absence of
hallucinations in real rooms or prove intelligibility of every training segment.

## Inputs and outputs

Inputs are the original `training/whistle_age_robust_v1` manifests/assets,
phase-5a framework metadata, existing local audio, frozen benchmark manifest,
and `plan.json`. No additional account, API key, download or data upload is used.
The original `release_review.json` and pinned model/runtime license provenance
are carried into each run. CHiME-6 licensing was confirmed resolved by the user
on 23 October 2026 and is not an outstanding gate.

Outputs are under `C:\Users\amiri\Documents\GitHub\just-peachy\training\whistle_followups_v1`:

- `pool.json` and train/dev manifests: aligned microphone expansion and protected identities.
- `quality/`, `audio_quality.json`, `quality_status.json`: cached level measurements,
  quarantine, qualified manifests, counts and progress. Training requires a
  complete audit with matching manifest hashes.
- `queue.json`, `status.json`, `worker.json`, `control.json`: persistent sequence,
  progress, owned Windows launcher PID and pause state.
- `runs/<name>/`: immutable config, exact resume checkpoint and previous copy,
  history, logs, GPU preflight, checkpoint-equivalence verification, adapters
  or full weights, `whistle.best.cact`, `whistle.final.cact`, model hashes,
  predictions, quiet/noise metrics and scores.
- `dataset_contributions.json`, `weight_decision.json`, `method_decision.json`,
  `production_decision.json`, `matched_comparison.json`, `summary.json`: evidence,
  decisions and final results. The matched comparison keeps the original eight
  cohorts and normalizer for base, initial tuned, final tuned and cached GigaSpeech.

LoRA trains attention adapters; full tuning trains all model parameters with
W4 quantization-aware training. Full tuning uses a smaller learning rate
(1e-5 versus LoRA's 1e-4). bf16 activations, rematerialization, duration/token
buckets, prefetching and the native export are inherited from the initial run.
Each new method must pass every actual batch shape and an optimizer-resume
equivalence check before sustained training. CUDA checks are intentionally
deferred until the original job is finished; CPU contract tests do not prove
that full tuning will fit in 10 GB of VRAM.

## Run from Anaconda Prompt or Command Prompt

No Conda activation is required; the launcher uses the repository's Windows
venv for the supervisor and the existing Ubuntu WSL environment for training.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\followup"
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action watch
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action open
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action status
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action pause
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action resume
```

`watch` ensures the singleton background supervisor is available. It does not
bypass the initial-run gate. `open` also opens <http://127.0.0.1:8767/>. In PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab\followup'
.\launch.ps1 -Action watch
.\launch.ps1 -Action open
.\launch.ps1 -Action pause
.\launch.ps1 -Action resume
.\launch.ps1 -Action status
```

Pause/resume on this dashboard affects only follow-ups. Pausing the original
run also blocks the follow-ups; resume that original run separately if needed.
Training pauses after the current update and saves optimizer, schedule and batch
position. Scoring resumes from completed clips. A crash can replay up to the
five-minute checkpoint interval. Locks prevent duplicate supervisors/workers.
The initial worker and its configuration are not stopped or changed.

The scheduled task **JustPeachy Whistle Experiment Monitor** starts this
supervisor at sign-in and every five minutes. It uses the current interactive
account, without a saved password; sign in after reboot to resume. Closing the
browser or Codex does not stop the worker. The active supervisor prevents idle
sleep during the recording-level audit and training/scoring; manual sleep or
shutdown still interrupts work.
The existing Codex heartbeat `whistle-training-check-in` continues through this
campaign with the adaptive cadence requested on 23 October 2026. It checks every
15 minutes during scoring, short pilots, compilation/export and stage
transitions. During healthy production training with advancing checkpoints and
more than three hours remaining, it backs off to every two hours; with one to
three hours remaining it checks every 30 minutes, and in the last hour (or with
an unknown ETA) every 15 minutes. A healthy long CPU audit uses 30 minutes.
A user pause or an already reported blocker requiring user action uses three
hours and never triggers an automatic unpause.

Each visit reads a brief state/log snapshot and updates this same heartbeat's
schedule through the Codex automation tool only when the cadence needs to
change. It records the interval and reason in `monitor_state.json`, preserves
recovery history, and stays quiet during normal progress. No extra datasets are
scanned or evaluations started by a check-in. These visits use occasional
tokens; the local supervisor, dashboard, and five-minute Windows recovery task
do not. The heartbeat needs the Codex app running; the worker continues
independently when the app closes.

The Word findings report is maintained separately by
`JustPeachy Whistle Findings Report`, a CPU-only task every 15 minutes. It appends
completed measurements, explanatory analysis and automatic selection decisions
without blocking this supervisor or creating more experiments. See
[`../reporting/README.md`](../reporting/README.md) for exact commands, inputs,
outputs, document-lock recovery and the analyst-note format. The report is
`training/whistle_followups_v1/reporting/Whistle_Fine_Tuning_Findings.docx` under
the repository root. The adaptive Codex heartbeat adds milestone interpretation
and checks publication and visual-review status.

To install/reinstall that recovery task from Anaconda Prompt/cmd in this folder:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File install_monitor.ps1
```

In PowerShell use `.\install_monitor.ps1`. Its input is this local launcher path;
its outputs are the named Windows task and a detached singleton supervisor.
It does not overwrite the original training monitor task.

Keep at least 12 GiB free. The supervisor waits below that floor; it never
automatically deletes datasets or checkpoints. Do not edit prepared manifests,
configs or the frozen plan. To remove only this recovery task later:

```powershell
Unregister-ScheduledTask -TaskName 'JustPeachy Whistle Experiment Monitor' -Confirm:$false
```

## Verification and metadata preparation

The following tests use synthetic tiny audio and fake scores, with no GPU use:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest test_campaign.py -q -p no:cacheprovider
```

To prepare/cache just expansion metadata and header evidence (no training or
PCM level audit):

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action prepare
```

The automatic supervisor performs the level audit after the original comparison.
Do not manually invoke GPU workers or the audit alongside their supervisor.
Progress and ETA become measured per run after compilation. Whole-campaign time
is an estimate because microphone expansion, level exclusions, full-tuning memory
and native scoring have not yet been measured end-to-end.

## Whole-campaign ETA

The dashboard labels the active work as **Current task**, with readable pilot
names and **Final production fit · LoRA/full** when the production run starts.
The original monitor on port 8766 also follows this live status above its saved
initial-run results. Reload either browser page to receive HTML-only updates;
the Python supervisor and GPU worker keep running. Its existing `/api/status`
response supplies the task, counters, phase and ETA; no new training input is used.

Both port 8766 and port 8767 now show time remaining through the exported
production model, plus a separate estimate through the final matched test.
`eta.py` reads only small status/benchmark/queue files and `eta_profile.json`.
The profile stores duration/token bucket counts, made once from existing
manifests and refreshed after the audio-level audit. It does not decode audio.
The estimate combines measured initial-run speed, remaining bounded pilots,
compilation/export/scoring allowances, and a LoRA/full-tuning range until method
selection. It switches to measured final-fit speed after that run has enough
updates. The displayed range is a planning range, not a statistical confidence
interval; pauses, sleep and failures are excluded. Calendar dates are suspended
while paused or blocked. No optimizer, sampler, run budget or dataset is changed
by the ETA feature. The read-only `/api/eta` endpoint allows access from the
original local dashboard; training control remains restricted to its own origin.
