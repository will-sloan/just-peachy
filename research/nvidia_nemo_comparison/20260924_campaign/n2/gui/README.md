# Actual N2 saved-audio GUI panel

`panel.py` runs the real selectable backend through `Controller.select_backend`,
the balanced recipe, the real saved-file source pacer and the unchanged common
480×800 Tk frontend. It uses the existing
`prototype.tests.run_private_desktop` launcher. It never switches to that
desktop, injects input, brings the window onto the user's desktop, opens audio
hardware, plays audio, or reads the screen of another application.

Each cell now runs in its own private process with one Tk root. The parent
starts these processes sequentially and aggregates only complete, hash-bound
cell results with successful process exit and isolation receipts. It rejects
missing/duplicate cells, skipped tests, mismatched inputs and native crashes.
No application or common-UI source change is involved in this isolation.

This is **Tk text applied**, including actual first-applied, first-final and
latest labels by stable span. It does not measure physical scanout, acoustic
arrival, touch interaction, Pi behavior, or a total-system 2 GB memory budget.
The screenshots are `PrintWindow` captures of the known private application.
They are taken just after the first observed application/finality milestone and
at completion; screenshot capture time is reported and contributes to measured
GUI timing. A screenshot is not the timestamp authority.

The runner is ready for resource-controlled execution. Its 25 model-free tests
pass; that alone is **not** evidence that the actual six GUI cells passed.
Read the aggregate `GUI_PANEL_REPORT.json` and each private cell's launcher
`isolation.json` after execution. The parent task owns
the CPU/GPU resource schedule. This runner selects one CPU affinity and
BelowNormal priority, sets numerical threads to one, and hides CUDA devices.
It rejects a runtime whose `native_device.kind` is not `cpu` or whose
`gpu_index` is not `-1`; an absent legacy device field means CPU.

Every successful cell must also pass archive integrity after Controller close:
the actual archive worker and Controller worker are joined, the session store
has no active archive owner, queues are empty, accepted and completed archive
items match, and both the Controller receipt and persisted epoch have no
`archive_error` or `loss`. The full admitted source sample count must match.
The current conversation may not report archive issues. Audio recording remains
disabled in this transcript panel; zero recorded audio samples is expected.
The final epoch checkpoint is written within the archive worker before it
returns, so its stored `worker_alive` flag is not a post-join measurement. The
actual owner and post-join `last_archive` receipt provide that measurement.
Aggregation independently rechecks the hash-bound archive evidence.

GUI progress/report writes use the shared `n2/io_utils.py` atomic writer with
its two-second transient Windows replacement retry. The exact helper hash and
IO version are bound in every parent/child admission and rechecked. Persistent
write errors still fail; the helper does not change permissions or delete the
prior report. The three shared IO tests exercise transient and persistent
denial behavior; see `../README_IO.md` for their exact commands.

## Inputs and declared panel

Use a newly frozen N2 `prototype` directory, the immutable N1 common release
directory, the existing public model cache, an explicit CPU `n2_runtime.json`,
the two admitted audio-only manifests, and two explicitly published private
`runtime_galleries` JSON files. The galleries must be research-only, retain
component/extraction provenance, use generic research UUID names, and have
`UNCALIBRATED_REJECT_ALL` status. They remain read-only. No research profile is
imported into the user's personal store.

The real engine receives an `N2Gallery` through a narrow store facade. Closed
mode must produce a permitted UUID with `Name · assumed` in actual Tk receipts
and cannot produce a verified profile. Open mode must remain `Unknown` because
processed-query C calibration is unavailable. The chosen roster is explicit;
the runner never selects a roster using Q speaker truth or transcript labels.
An E roster with missing source coverage remains incomplete; the supplied
gallery retains its intended/available counts and provenance.

Default six cells, using the exact O0 prepared mono16k PCM16 files with unity
read gain (O1 can be selected for the whole panel with `--tap O1`):

| Cell | Saved example | Actual mode |
|---|---|---|
| D1_E1_boundary | S45_08_07, C105 boundary regression | selected_closed |
| D1_E1_short | S45_03_03 | enrolled_names |
| D1_E1_returning | S45_06_07 | selected_closed |
| D1_E1_noise | S45_12_20 | enrolled_names |
| D1_E1_silence | S45_12_15 | enrolled_names |
| D1_E0_boundary | identical S45_08_07 audio | selected_closed |

This is a bounded regression panel with differing declared open/closed modes,
not a complete accuracy factorial. Each cell has a fresh Controller, data root,
model stack, process, Tk root and source session. Loading happens before source time zero and is
included in cell wall time. Nothing accelerates or truncates the source.

The earlier multi-root attempt at private `local/n2/gui-panel-v2` is preserved:
its real boundary cell completed, then the process crashed during the short
cell. Application event 1000 at 2026-09-24 17:17:33.3705434 UTC identified
`tcl86t.dll` 8.6.2.15, exception `0x80000003`, fault offset `0xFDDA4`, in the
original application Python process (PID 32680). The exact lifecycle/thread
cause was not established. The attempt's single completed cell is useful
evidence but cannot be called a completed six-cell panel. The new parent
launches a fresh private process for every cell and retains separate native
and Python fault logs. It does not reuse the incomplete attempt or copy its
boundary result into a fresh full panel.

The isolated short-cell repro at `local/n2/gui-short-isolated-v1` completed its
private process and GUI checks in 101.74 seconds for 44.695 seconds of source.
It still displayed `Window source indices unavailable` and its archive lost one
accepted item. Those receipts remain unchanged and are not an archive-clean
pass under the stronger acceptance check. Use a fresh frozen release containing
the application archive fix for the final six cells. Budget roughly 8–12 minutes
on one CPU based on that measured cell; the six source durations alone total
268.17 seconds. The total timeout is 2,400 seconds. CPU inference may drain
after source delivery; source pacing is never accelerated to hide that delay.

The audio firewall admits only job ID, path/hash, frame count, sample rate,
unity gain, reset flag and tap. The full prepared file is hash- and PCM-bound.
The six original common-UI files and portrait layout are compared to N1 before
and after running; all N2 application/vendor/config sources are also bound.

## PowerShell

Run model-free tests from the worktree. They do not instantiate Tk or models:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$env:OMP_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m unittest research.nvidia_nemo_comparison.20260924_campaign.n2.gui.test_panel -v
```

After the parent task freezes N2 at the path below and authorizes the CPU slot,
run this command. It uses the existing CPU runtime binding and the published
15-second fixed research roster (three available profiles out of four intended).
Both E0 and E1 use the same declared roster and waveform source. Change
`--source` to the actual completed frozen N2 release if its directory differs.
Every `--output` must be new and outside the source tree.

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n2\gui\panel.py' `
  --source 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v6\prototype' `
  --common-source 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype' `
  --models-root 'C:\Users\amiri\JustPeachy\shared\models' `
  --runtime-config 'G:\Just_Peachy_N1\20260924_campaign\local\n2\runtime\cpu\n2_runtime.json' `
  --regression-manifest 'G:\Just_Peachy_N1\20260924_campaign\local\data\REGRESSION_AUDIO_ONLY.json' `
  --screen-manifest 'G:\Just_Peachy_N1\20260924_campaign\local\data\BASELINE_SCREEN_AUDIO_ONLY.json' `
  --e0-gallery 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E0\runtime_galleries\gallery_69c1a03b24b0c86e7998.json' `
  --e1-gallery 'G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E1\runtime_galleries\gallery_69c1a03b24b0c86e7998.json' `
  --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\gui-panel-isolated-v1' --cpu 4 --timeout-seconds 2400
```

Append `--prepare-only` to check and bind inputs without opening Tk or loading
models. It writes `ADMISSION.json` and prints `PREPARED_NOT_EXECUTED`; use a
different fresh output for the eventual run. Append
`--cell D1_E1_boundary` for a one-cell real smoke, or repeat `--cell` to select
a subset. Admission explicitly records that the subset is not the full panel.

## CMD / Anaconda Prompt

The original application environment is used by explicit executable path;
no Conda activation or package installation is needed. The optional command
line continuations below use CMD's caret character.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m unittest research.nvidia_nemo_comparison.20260924_campaign.n2.gui.test_panel -v
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "research\nvidia_nemo_comparison\20260924_campaign\n2\gui\panel.py" ^
 --source "G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v6\prototype" ^
 --common-source "G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype" ^
 --models-root "C:\Users\amiri\JustPeachy\shared\models" ^
 --runtime-config "G:\Just_Peachy_N1\20260924_campaign\local\n2\runtime\cpu\n2_runtime.json" ^
 --regression-manifest "G:\Just_Peachy_N1\20260924_campaign\local\data\REGRESSION_AUDIO_ONLY.json" ^
 --screen-manifest "G:\Just_Peachy_N1\20260924_campaign\local\data\BASELINE_SCREEN_AUDIO_ONLY.json" ^
 --e0-gallery "G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E0\runtime_galleries\gallery_69c1a03b24b0c86e7998.json" ^
 --e1-gallery "G:\Just_Peachy_N1\20260924_campaign\local\n2\evaluation\component\E1\runtime_galleries\gallery_69c1a03b24b0c86e7998.json" ^
 --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\gui-panel-isolated-v1" --cpu 4 --timeout-seconds 2400
```

## Outputs and interpretation

`ADMISSION.json` binds input hashes, source, fixed common frontend, jobs and
scope. The parent's `GUI_PANEL_REPORT.json` aggregates exact successful cells;
`PROGRESS.json` reports the active cell. A failure stops the panel and retains
the failed private process output. `full_panel` and `requested_cells` distinguish
a one-cell smoke from the full six cells.

Each `private_cells/<cell_id>` contains a single-job `ADMISSION.json` bound to
the parent, `isolation.json`, `tests.json`, `unittest.txt`, `LAUNCH_OUTPUT.log`,
`NATIVE_OUTPUT.log`, and its one-cell `GUI_PANEL_REPORT.json`. Native stdout/
stderr and Python fault handling are directed to that known process's log.

Inside each private process directory, `cells/<cell_id>` holds the real application data/session logs,
`FINAL_SNAPSHOT.json`, `PRESENTATION_RECEIPTS.jsonl`,
`FINAL_STATE_APPLIED.jsonl`, `SPAN_PRESENTATION_SUMMARY.json`,
`SOURCE_CLOCK.json`, `PROCESS_SAMPLES.json`, `RESULT.json`, and up to three
application-only PNGs. Files may contain research voice vectors, source paths
and transcripts; keep them outside Git and normal personal enrollment roots.

`ARCHIVE_INTEGRITY.json` binds the persisted archive epoch and records its item
counters, Controller `sessions`/`last_archive`, actual owner state and teardown.
A failed gate sets `archive_integrity_passed=false` and fails the cell even when
all caption/Tk checks passed. Previous repro artifacts are never rewritten.

`PRESENTATION_RECEIPTS` calls the unmodified real Controller recorder first,
then enriches a detached audit value with the exact row being applied. The
common UI skips duplicate callbacks when only the final flag changes. A hook
after its real render verifies the Tk text and records that case separately in
`FINAL_STATE_APPLIED`; it never fabricates a common presentation callback.
Span summaries retain first-applied, first-final and latest actual states plus
label revisions. Source-end-to-Tk timing uses the real `source_started`
`perf_counter` origin; coarse source supports remain explicitly marked and
must not be reported as word-level latency. A scene with no captions has zero
span receipts, not a missing-noise denominator. Noise/silence caption counts
are reported without imposing a model output expectation.

Tests cover the exact six-cell roster, audio-only firewall, hash/PCM binding,
research-only store isolation, namespace rejection, ordered source-clock
receipts, unchanged-text final application, and stable span revisions. The
actual private desktop case also checks final caption coverage, full source
delivery, drained writers, backend identity, no verified uncalibrated names,
real closed assumed-name application, and Controller teardown.

Aggregation tests additionally reject dropped or duplicate cells, changed
evidence/contracts, skipped GUI cases and nonzero native process exits. The
child test refuses more than one admitted job, so a full panel cannot silently
reintroduce sequential Tk roots in one process.

Archive tests exercise a real temporary metadata archive with no models or
hardware, plus rejection of archive warnings, missing items, active workers,
source-count loss, changed persisted checkpoints and session issues. Aggregation
also rejects a cell that claims completion while its archive evidence fails.
