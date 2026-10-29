# Local Whistle AGE + ROBUST fine-tuning

The authorized, bounded follow-up campaign is documented in
[followup/README.md](followup/README.md). Its separate dashboard is
<http://127.0.0.1:8767/>. It waits for this original run and its matched comparison,
then audits expanded microphone levels, runs at most seven short pilots and one
final production fit. Its controls and data do not change this initial run.

This experiment installs Whistle, fine-tunes its attention LoRA adapters on the
RTX 3080 through Ubuntu WSL2, and exports a local `.cact` model. Nothing uploads
your audio. Runtime and package telemetry are disabled. Public packages and model
weights are downloaded once during setup. The Raspberry Pi is not required.

## Inputs

`config.json` selects the latest existing AGE_ROBUST freeze: all 91,123 older
Common Voice training clips (including the previously reassigned heldout set),
682,896 AMI microphone-view segments, 51,761 CHiME-6 segments, and 16,704 VOiCES
views. Existing
development and frozen evaluation data keep their roles; no new holdout is taken.
CMU is the separate exploratory branch and is not part of this first run.
The source plan contains 842,484 rows. The usable training pool is 842,439 rows
(682,851 AMI views), 1,004.9 physical audio hours per pass, and
approximately 257.6 hours of distinct source speech. Three full passes are planned.

The only exclusions are 45 invalid AMI annotations: five utterances with nine
microphone views each in TS3007c extend beyond the official recording's 2420-second
end. They represent 114.012 seconds across views (0.00534% of planned rows).
The local files and official HTTP audio headers agree; downloading again cannot
restore the missing tail. `annotation_quarantine.json` lists every ID, exact bounds,
source-manifest checksum, and evidence. No other source selection is reduced and
no new evaluation holdout is created. The official Lhotse AMI recipe likewise
[rejects annotations beyond recording duration](https://lhotse.readthedocs.io/en/latest/_modules/lhotse/recipes/ami.html).
Preparation refuses to apply this quarantine if the source or annotation changes.
The initial diagnostic checkpoint/history are preserved under
`preflight_before_audio_audit`; the corrected pool starts a fresh, reproducible run.

Every training row is visited once in every epoch; final partial batches are
padded with zero weight. Repeated microphone views are weighted by source identity
and the existing dataset mixture to prevent AMI's view count dominating the loss.
The optimizer also corrects for variable batch sizes, preserving the intended
per-clip objective when long clips need smaller batches. Model activations use
bfloat16; float32 quantization/adapter matrix products use highest precision to
avoid reduced-precision changes in quantization codebook selection.
Blank references remain language + EOS targets. Long segments use larger training
buckets without trimming audio or assigning full transcripts to partial audio.
Training beyond the vendor's usual 30-second examples is an experimental extension;
the exported runtime still uses its standard windowing. Punctuation/case are kept
where supplied, annotation tags are removed, and the known Common Voice TSV-tail
correction is preserved. No labels are invented.

Whole-file MP3 examples use their complete decoded PCM length because the header
can overestimate duration. On 23 October a valid Common Voice clip reported
355,137 frames but decoded to 352,512 frames at 44.1 kHz in both SoundFile and
FFmpeg, without decoder errors. The loader now accepts that complete audio instead
of rejecting it as a short segment. Segmented recordings retain strict bounds and
length checks; empty/nonfinite audio still fails. This repair changes no selected
rows, labels, batch shapes, training settings, or checkpoint identity. The regression
test references the existing local clip and skips if that dataset is absent; no
dataset audio is copied into the source repository. Seven focused tests passed
after this repair, including rejection of an out-of-bounds WAV segment.

## Run from Anaconda Prompt or Command Prompt

No Conda activation is required. Open Anaconda Prompt or cmd.exe and enter:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab"
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/bootstrap_assets.py"
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/prepare.py"
```

PowerShell uses `Set-Location` instead of `cd /d`:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Training Tool\whistle_lab'
```

The environment was created with:

```bat
wsl -d Ubuntu -- python3 -m venv /home/amiri/.venvs/whistle
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -m pip install "cactus-needle[train,gpu]==3.2.1" soundfile pyarrow pandas psutil jiwer pytest
```

The PyPI wheel with version 3.2.1 predates the current Whistle trainer even though
the repository still reports the same version. This run therefore installs the
official source at commit `b4fc11b04f1852888d375c8c6dfbaca44572d014` after the CUDA
dependencies. To reproduce from the existing pinned source checkout:

```bat
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -m pip install --no-deps "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/training/toolchains/needle-whistle"
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -m pip install soxr whisper-normalizer
```

`requirements.lock.txt` in the run directory records installed versions. Setup
verified JAX 0.12.0.1 with `CudaDevice(id=0)` on the RTX 3080. The public Whistle
revision is pinned in config; assets.json records SHA-256 hashes and the tokenizer
revision. No signup or API token was needed.
The Linux x86-64 native runtime and tokenizer are pinned to Needle3 revision
`d6c7d6a2e9655505e0f8e23339356dd1705900eb`; the runtime comes from its 3.3.3 wheel.
The model, engine, and Python package license texts are retained in `assets`.

## Dashboard, start, pause and resume

Open <http://127.0.0.1:8766>. From Anaconda Prompt or cmd.exe, in this directory:

The top **Current task** panel follows the active campaign, including the final
production fit, instead of presenting the completed initial run as current work.
It reads the follow-up supervisor's `/api/status` every ten seconds and shows its
task name, phase, progress, steps, views, active time and current-run ETA. The
older panels are explicitly labelled initial-run results. Initial-run buttons
are disabled after completion; the current-task link opens the follow-up
pause/resume controls on port 8767. A disconnected follow-up service is shown as
unavailable, rather than leaving old progress looking live. These HTML changes
take effect on browser refresh and do not require restarting either worker.

The same status response contains the whole-campaign ETA (also available at
`http://127.0.0.1:8767/api/eta`), showing all remaining stages through final
production export and final testing separately. This includes the microphone
audit, at most seven pilots, scoring and one final three-pass fit; it is a
planning range until future-stage throughput is measured. Current-run ETA
remains separate. See `followup/README.md` for its inputs, controls and recovery.
If the follow-up service is unavailable, the dashboard displays that limitation
instead of treating the current run's remaining time as the entire campaign.

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action open
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action start
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action pause
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action resume
powershell -NoProfile -ExecutionPolicy Bypass -File launch.ps1 -Action status
```

In PowerShell, the equivalent is `./launch.ps1 -Action pause`, and so on. Pause
finishes the current optimizer update, saves weights and Adam/schedule state,
then exits the GPU worker. Resume restores the exact deterministic batch position.
A crash can replay at most the work since the last five-minute checkpoint. One
previous checkpoint is retained. Do not edit config or manifests during a run:
resume verifies their identities and refuses incompatible state.

State-file updates use private temporary files, flush their contents, and retry
atomic replacement for up to five seconds when Windows briefly denies replacement
because a reader or scanner holds the file. Adapter replacement and checkpoint
rotation use the same retry. A persistent progress-display lock defers that update
without stopping GPU work; persistent checkpoint errors still stop the worker and
preserve the earlier checkpoint. This fixes the Windows/WSL status-file outage
observed after the first full pass, without changing training settings or data.

`start` runs any missing asset download, data preparation, all-file audio-header
audit, full GPU shape benchmark,
checkpoint continuation test, training, export, and then comparison. The supervisor
is a detached local Python process, independent of Codex and the browser. It retries
a failed worker at most three times; pressing Resume resets that failure budget.
The browser can be closed without stopping training. During setup, the run is not
allowed to enter full training until all GPU batch shapes and checkpoint
continuation have passed.

The Windows scheduled task **JustPeachy Whistle Training Monitor** launches the
supervisor at your sign-in and checks it every five minutes. It uses your current
interactive account, not stored credentials. After a reboot, sign in to Windows
to resume. The supervisor prevents automatic idle sleep while a job is active;
manual sleep/shutdown still stops computation. Pause state persists across reboot.
Codex's **Whistle training check-in** heartbeat checks the small status files every
three hours and only reports meaningful changes or problems. The dashboard and
Windows recovery do not use model tokens; the occasional Codex check-ins do.

To remove automatic recovery later, run in PowerShell:

```powershell
Unregister-ScheduledTask -TaskName 'JustPeachy Whistle Training Monitor' -Confirm:$false
```

## Verify or benchmark manually

`audit_audio.py` checks actual audio-file headers against every selected train and
development segment. From this folder in Anaconda Prompt or cmd.exe, run it with
the repository's Windows Python for fast access to NTFS:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" audit_audio.py
```

It writes `audio_header_audit.json`, `audio_header_audit.parquet` and
`audio_bounds_issues.parquet`. It never edits recordings or removes training rows.
It returns a nonzero exit code on invalid bounds. The supervisor requires a clean
audit tied to the current manifest hashes before benchmarking or training.

```bat
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -m pytest -q "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/test_data.py"
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -m pytest -q "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/test_state.py"
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -u "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/train.py" --benchmark
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -u "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/evaluate.py" --smoke
```

The benchmark does not keep its weight updates. It exercises every real batch shape
and restores optimizer state in memory to check identical next-step parameters.
`benchmark.json` reports measured steady-state timing, initial compilation, and
an approximate runtime with uncertainty. Normal training produces history.jsonl,
status.json, checkpoint.json, and adapter.latest/best/final.safetensors. The exported
whistle.best.cact and whistle.final.cact use the vendor's W4A8 export, which is larger
than the 16.9 MB public mixed-bit base. The best adapter is chosen by a small fixed
sample of the existing development sets. It is not a final independent test score.

The focused loader benchmark (`loader_benchmark.py`) reads randomized source
batches with 6, 12 and 16 threads and writes `loader_benchmark.json`. Run it using
the same WSL Python command above, substituting `loader_benchmark.py` and omitting
`--benchmark`. It measured median batch-loading times of 0.279, 0.199 and 0.227
seconds respectively in the initial test; this run uses 12 threads. These are I/O
measurements during setup, not training throughput claims.

After at least one training checkpoint exists, the optional export check is:

```bat
wsl -d Ubuntu -- /home/amiri/.venvs/whistle/bin/python -u "/mnt/c/Users/amiri/Documents/GitHub/just-peachy/Software Validation from Datasets/Training Tool/whistle_lab/verify_export.py"
```

`verify_export.py` reads the latest saved adapter, exports a separate
`whistle.export_smoke.cact` on CPU, and checks transcription and finite acoustic
embeddings on one existing AMI evaluation clip. It writes
`export_verification.json`; this is a compatibility check, not a quality score.
It does not modify the training checkpoint or final/best model names.

## Post-training evaluation

The small comparison samples up to 64 matched segments from each unaugmented
clean/native cohort of the frozen Large benchmark, reuses historical GigaSpeech
transcripts, and scores all hypotheses with the same English Whisper normalizer.
It reports WER, CER, CPU real-time factor and first-token latency. Historical GPU/
CPU timings are not compared across hardware. No training data is withheld to
create this comparison. Base, best and final Whistle predictions are resumable.
The dashboard shows the completed WER comparison by cohort. Pause during this
stage stops after the current clip and retains completed predictions.
Streaming and acoustic-embedding API checks are separate smoke probes; they do
not establish speaker-recognition quality or Raspberry Pi power consumption.

## Outputs

Machine-local outputs live under `just-peachy/training/whistle_age_robust_v1`:
public assets and their hashes, converted full-pool manifests, data audit, training
status, loss history, resumable optimizer checkpoints, adapters and exported models.
`model_manifest.json` records final model hashes, the training/base identities,
completed coverage and the project licensing status.
The original training freezes and product pipeline are not modified.

The dashboard distinguishes setup, benchmarking, training, paused, export and
comparison phases. Its percentage counts completed training-row visits across all
three passes. Setup/compilation time is separate from that percentage. The ETA
starts with measured GPU/loader timings, then uses recent actual training speed.

## Licensing

Whistle weights and the Needle package are Apache-2.0. Retain the license,
applicable attribution/NOTICE files, and modification notices when distributing.
The local route does not require a Cactus paid plan or API key. Common Voice is
CC0 under its acquisition terms; AMI and VOiCES require attribution. CHiME-6 is
CC-BY-SA-4.0. The user confirmed on 23 October 2026 that its licensing is resolved
and good to go for this project. This run's release-review flag is cleared, with
that confirmation recorded in `release_review.json`. Retain the dataset license
and attribution records when applying the project's resolved distribution terms.

Whistle's `embed(audio)` gives acoustic encoder frames, not a demonstrated speaker
identity embedding. Keep the working Nemotron/speaker pipeline until a separate
speaker-discrimination evaluation establishes a benefit. Common Voice acquisition
terms prohibit speaker identification, so do not use its clips for that experiment.


## Verified on 23 October 2026

### Monitor and campaign amendment on 24 October 2026

The existing monitor at `http://127.0.0.1:8766/` shows the live current task from
the follow-up supervisor on port 8767, with completed initial results labelled
historical. Both pages include the separately authorized extension: three longer
development comparisons (two active hours / 30,000 updates / three passes each)
and at most one conditional production refit. The current fit continues without
configuration or checkpoint changes. Whole-campaign ETA includes the conditional
branch; it is distinct from current-run remaining time. See `followup/README.md`
for the finite 12-run cap, protected identities, selection guards, inputs,
outputs, tests and existing start/status/pause/resume commands. These UI changes
need a browser refresh; they do not require restarting GPU training.

- Five data/coverage contract tests passed.
- The later file-sharing repair passed all 11 data/state tests in WSL and all
  four state tests on Windows. `test_state.py` uses temporary files to exercise
  transient and persistent locks, concurrent writers, and deferred progress
  updates; it does not change the training run.
- Every selected audio header passed: 121,910 files and 950,922 usable train/dev
  segments, after the 45 explicitly documented invalid AMI annotations were excluded.
- All 22 actual GPU batch shapes passed, including the longest clips and transcripts.
- The final trainer calls Cactus's complete quantization function; its numerical
  comparison and next-step optimizer restoration both had zero parameter difference.
- A diagnostic pause saved step 30, including optimizer/scheduler state and the next
  batch position. The checkpoint checksum passed, and a new worker restored it
  and advanced beyond step 30. See the preserved `pause_resume_verification.json`
  in `preflight_before_audio_audit`.
- The corrected pool also passed a real pause/resume: step 149 was saved with a
  verified checksum, then a fresh worker restored the exact optimizer/scheduler
  state and advanced beyond that step. The current run's
  `pause_resume_verification.json` records this check. Training was left enabled.
- The saved adapter exported to a 29,346,671-byte local model and passed native
  transcription and finite-embedding checks. See the preserved
  `export_verification.json` in `preflight_before_audio_audit`.
- The corrected pool's isolated benchmark estimated 9.3 hours for three passes.
  The earlier diagnostic run's end-to-end
  throughput estimated roughly 15-17 hours remaining as the pipeline warmed up.
  Allow approximately 12-24 hours initially, plus pauses and final scoring; the
  dashboard continuously revises its estimate from actual progress.
- CHiME-6 licensing was resolved by explicit user confirmation; the review flag
  is cleared. Training was left enabled with three-hour Codex check-ins.

These are setup/recovery checks, not a claim that fine-tuning has completed or
improved WER. Current progress is in the live dashboard and `status.json`.
