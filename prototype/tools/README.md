# Development tools

Task12 small native transcript review and protected-change touch workflow:
[README_TRANSCRIPT_REVIEW.md](README_TRANSCRIPT_REVIEW.md).

Task11's small native reference/contamination check and actual touch workflow:
[README_ADAPTATION.md](README_ADAPTATION.md).

For the small native roster proof and actual mode/recipe configuration export,
see [README_ROSTER.md](README_ROSTER.md).

For linked session/native archive checks and on-demand model-window export, see
[README_SESSIONS.md](README_SESSIONS.md). No new capture or inference is required
to export an already recorded window.

For the task 01 timing/Stop lifecycle check, see
[README_LIVE_TIMING.md](README_LIVE_TIMING.md). It reuses the current environment
and models, requires explicit consent for live capture, and writes only to a
new private evidence directory. It is a small functional check, not a sweep.

## Bounded real Windows microphone check

`check_live_desktop.py` exercises the actual XVF live source, native models,
source clock, beam diagnostic reads, and clean stop. It requires `--consent`,
an existing site configuration, and a **fresh private directory outside the app**.
The duration is 5–120 seconds. It never opens playback, saves a WAV, or creates
an enrolled person. Local session text can contain nearby speech; the result
JSON contains counters and device/clock integrity, not caption text. A pass
establishes live transport/inference lifecycle, not speech or identity accuracy.
Close the GUI first so its device lease is free. Pick a new data directory for
each invocation. Shared model files must already be provisioned.

PowerShell from the repository:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\check_live_desktop.py --consent --seconds 20 --config "$env:USERPROFILE\JustPeachy\data\live_config.json" --data-root "$env:USERPROFILE\JustPeachy\checks\live-check-01"
```

CMD / Anaconda Prompt from the repository:

```bat
.edge-speech-env\python.exe -B prototype\tools\check_live_desktop.py --consent --seconds 20 --config "%USERPROFILE%\JustPeachy\data\live_config.json" --data-root "%USERPROFILE%\JustPeachy\checks\live-check-01"
```

Default recipe/mode is Balanced identity/Anonymous. Add `--recipe fast --mode
caption_only` for the ASR-only path. Output is `LIVE_CHECK.json` and local session
and restoration receipts in the chosen directory. Exit status is nonzero on
capture, inference, duration, integrity, or cleanup failure.

Use `--mode spatial_assisted` or `--mode strongly_spatial_assisted` to check the
new field modes with the same existing site configuration. The result includes
bounded spatial counters, explicitly estimated associations, and telemetry
state; a quiet room can produce no qualified voice/spatial decisions. See
`README_SPATIAL_INTEGRATION.md` for the separate small prerecorded-speech test
with clearly synthetic direction fixtures.

`bootstrap_from_s7.py` performs a one-time copy of the exact hash-bound S7 source
and eight existing model assets. It does not read/copy research identities or
change historical files. Runtime never imports S7 report directories.

Inputs: the PROTO1 pack's `evidence/S7_SOURCE_AND_ASSET_SEED.json` and an external
shared models directory. Outputs: `vendor`, asset/profile configuration and
`evidence/SOURCE_MIGRATION.json`. Existing vendor files are preserved; do not use
bootstrap as an upgrade tool.

From the repository in PowerShell:

```powershell
& .\.edge-speech-env\python.exe .\prototype\tools\bootstrap_from_s7.py --seed "<pack>\evidence\S7_SOURCE_AND_ASSET_SEED.json" --models "$env:USERPROFILE\JustPeachy\shared\models"
```

From CMD or Anaconda Prompt:

```bat
.edge-speech-env\python.exe prototype\tools\bootstrap_from_s7.py --seed "<pack>\evidence\S7_SOURCE_AND_ASSET_SEED.json" --models "%USERPROFILE%\JustPeachy\shared\models"
```

Replace `<pack>` with the extracted PROTO1 pack path. No new environment or
package installation is needed on the development desktop.

## Bounded native acceptance

`acceptance_run.py panel` runs six existing scenes through four actual recipes
and five modes, including C105 and one15.53-second delayed disk writer. It keeps
failed evidence and reports exact source-frame delivery, native failures and
writer closure. It does not recapture audio or change hardware.

`sustained` opens the actual portrait GUI for the existing30.7-minute S7 source,
switches modes/recipes20times at controlled boundaries, and logs compact progress
once per minute. This is an automated file test, never microphone/live proof.
Each command requires a fresh external output directory. Outputs include a
machine-readable result, progress JSON and pinned private test-session evidence.

PowerShell from the repository (CMD/Anaconda: omit `&`):

```powershell
& .\.edge-speech-env\python.exe .\prototype\tools\acceptance_run.py panel --inputs "G:\Just_Peachy_S6B\20260909T230840Z\inputs" --output "G:\Just_Peachy_PROTO1\acceptance\panel_v1"
& .\.edge-speech-env\python.exe .\prototype\tools\acceptance_run.py sustained --wav "G:\Just_Peachy_S7\20260917T141700Z\inputs\long_source_v1\O0_continuous.wav" --output "G:\Just_Peachy_PROTO1\acceptance\soak_v1"
```

Do not rerun a completed panel or long test unless a relevant code change or
failure warrants it. Resource observations describe this desktop, not CM5.

## Read-only closeout and handoff

`closeout.py audit` reads the completed sustained-run receipts for all 21 epochs.
It checks sample totals, worker/handle closure, queue drains and capture-loss
counters, then writes `prototype/evidence/CLOSEOUT_AUDIT.json`. It starts no
inference, microphone or playback. Run it only after `SOAK_RESULT.json` exists.

`closeout.py package` copies an explicit allowlist of source, guides and compact
evidence into a **new** output folder and ZIP. Inputs are the completed acceptance
directory, final reports/releases/test receipts, and a prepared START_HERE file.
Outputs are an analysis handoff, per-file hashes and a ZIP checksum printed on
the console. It excludes audio, vectors, models, credentials and Word workbooks;
it refuses more than 60 files or a ZIP over 20 MiB. It does not delete or replace
existing output folders. Full source/releases stay at their recorded local paths.

`closeout.py final-bindings` additionally compares every final release payload
with the current source, every seeded historical S7 source file with its original
hash, the unchanged V22 workbook, Git HEAD, the untouched default personal store
and available disk space. Inputs are `--release`, `--workbook` and `--acceptance`.
Output is `evidence/FINAL_SOURCE_REVIEW.json`; a mismatch fails the command.

PowerShell from the repository:

```powershell
& .\.edge-speech-env\python.exe .\prototype\tools\closeout.py audit --acceptance 'G:\Just_Peachy_PROTO1\acceptance'
& .\.edge-speech-env\python.exe .\prototype\tools\closeout.py final-bindings --acceptance 'G:\Just_Peachy_PROTO1\acceptance' --release 'G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.1.2.zip' --workbook "$env:USERPROFILE\Downloads\XVF_Measurement_V22.docx"
& .\.edge-speech-env\python.exe .\prototype\tools\closeout.py package --acceptance 'G:\Just_Peachy_PROTO1\acceptance' --output '<simulation>\handoffs\PROTO1_CHATGPT_HANDOFF_<run_id>' --start-here '.\prototype\evidence\START_HERE.md'
```

CMD / Anaconda Prompt from the repository:

```bat
.edge-speech-env\python.exe prototype\tools\closeout.py audit --acceptance "G:\Just_Peachy_PROTO1\acceptance"
.edge-speech-env\python.exe prototype\tools\closeout.py final-bindings --acceptance "G:\Just_Peachy_PROTO1\acceptance" --release "G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.1.2.zip" --workbook "%USERPROFILE%\Downloads\XVF_Measurement_V22.docx"
.edge-speech-env\python.exe prototype\tools\closeout.py package --acceptance "G:\Just_Peachy_PROTO1\acceptance" --output "<simulation>\handoffs\PROTO1_CHATGPT_HANDOFF_<run_id>" --start-here "prototype\evidence\START_HERE.md"
```

Replace `<simulation>` with the existing measurement simulation directory and
`<run_id>` with a fresh identifier. These commands package evidence; they never
turn an untested live/CM5 requirement into a passing result.

## Final focused software check

`run_unit_checks.py` discovers `tests/test_*.py`, runs the focused contract tests,
and writes `tests/evidence/FINAL_UNIT_CHECKS.json` plus a detailed text log. Inputs
are the current source and synthetic/mock test fixtures. It performs no physical
microphone capture, playback or native speech inference; Tk tests create and
close their own windows. It records source/test hashes and rejects source changes
during the test run. Run once after the final runtime edits; do not rerun native
panels solely to generate this summary.

Pass `--output-dir "<fresh directory>"` to keep historical receipts unchanged.
This runner also installs the repository/application/vendor import paths needed
by the release tests, so prefer it over bare discovery from a nested directory.

PowerShell from the repository:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\run_unit_checks.py
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype\tools\run_unit_checks.py
```

# Task 02 caption checks

See [README_CAPTION_PRESENTATION.md](README_CAPTION_PRESENTATION.md) for the
short GUI timer fixture, explicit mock screenshots and optional actual native
saved-file layout check. Inputs, outputs and PowerShell/CMD/Anaconda commands
are included. No microphone or extra model download is involved.

## Task 05 bounded assigned-seat native check

See [README_SEATS.md](README_SEATS.md) for `check_seat_modes.py`: three short native saved-audio cases with explicitly synthetic telemetry, actual caption-widget checks, source hashes and resource observations. `--case direction_change_motion` selects only the UI/motion case when that is the relevant regression. Run commands, inputs and private outputs are documented there. No microphone, playback or training.
# Task 06 native enrollment verification

See [README_ENROLLMENT.md](README_ENROLLMENT.md) for the small prerecorded-audio
before/after embedding parity check, ordinary ASR, profile restart/export/import,
quality negatives and resource receipts. No microphone or playback is used.
`run_unit_checks.py` additionally performs main-thread garbage collection between
cases to release completed Tk test interpreters before worker tests begin; its
own source hash is recorded in the final receipt.
## Task 07 native text assistance check

See [README_TEXT_ASSISTANCE.md](README_TEXT_ASSISTANCE.md) for one small actual
native caption/archive run, explicit text-only edge cases, source/API bindings
and resource measurements. It does not enable hotword inference or run a sweep.
# Task09 actual-audio evidence check

See [README_SCRIPT_EVIDENCE.md](README_SCRIPT_EVIDENCE.md) for the small native
script/reference/fresh-query test, inputs, private outputs and exact commands.

Task10 optional noise checks and run commands: [README_NOISE.md](README_NOISE.md).
