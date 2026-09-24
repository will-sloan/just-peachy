# Frozen baseline GUI replay

`replay_baseline_gui.py` renders every completed baseline `FINAL_SNAPSHOT.json`
through the frozen N1 frontend after inference. It verifies the source hashes
in `ADMISSION.json`, the result/checkpoint bindings and snapshot hashes before
opening a test app. Every row's display text and stable span IDs must survive
in the UI; the fixed active pane and 480×800 client are checked. It collects
exact GUI-applied labels/revisions and renders up to six representative app
client PNGs. Source and evidence hashes are rechecked at completion.

This is **final-snapshot rendering**, not original online first-label timing,
live latency, acoustic accuracy or physical display scanout. The first GUI
labels in this replay describe the saved final-state application only. The
original controller/model events remain the online evidence. Inference is not
rerun and no audio is opened. Each saved view settles for 1.3 real seconds so
the existing 1.2-second pending-identity bound and one GUI poll can expire;
this added replay wait is not acoustic or original online latency.

The script starts an isolated Windows desktop through the already tested
`prototype/tests/run_private_desktop.py`. It never switches the input desktop,
sends mouse/keyboard input, captures the user's screen, loads models, reads
personal galleries or opens microphone/USB/playback. The app is mapped only
on the private desktop. The actual UI module is loaded from the specified
frozen release and its resolved path is asserted. The frozen PrintWindow
helper is separately hash recorded.

Inputs:

- `--source`: immutable release `prototype` directory.
- `--index`: completed `RESULT_INDEX.json`, with adjacent `ADMISSION.json` and
  unchanged result/checkpoint/snapshot files.
- `--output`: a fresh private evidence directory outside source/Git.
- Optional `--allow-partial`: explicit smoke evidence, reported PARTIAL; never
  represented as all 96 cells. The default requires full successful coverage.
- Optional `--timeout-seconds`: bounded isolated child timeout, default 600.

Outputs: `GUI_REPLAY_REPORT.json`; per-cell `GUI_RENDER_CHECK.json` and
`PRESENTATION_RECEIPTS.jsonl`; up to six `FINAL_SNAPSHOT_RENDER.png` files;
`tests.json`, `unittest.txt` and `isolation.json`. Detailed caption/label
receipts and images stay in private evidence and must not be blanket-added to
Git. Handoffs can use redacted count/hash summaries with explicit scope.

PowerShell, from the campaign worktree:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' 'research\nvidia_nemo_comparison\20260924_campaign\frontend\replay_baseline_gui.py' --source 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype' --index 'G:\Just_Peachy_N1\20260924_campaign\local\baseline_screen_v1\RESULT_INDEX.json' --output 'G:\Just_Peachy_N1\20260924_campaign\evidence\frontend\baseline_full_gui_v1'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "research\nvidia_nemo_comparison\20260924_campaign\frontend\replay_baseline_gui.py" --source "G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype" --index "G:\Just_Peachy_N1\20260924_campaign\local\baseline_screen_v1\RESULT_INDEX.json" --output "G:\Just_Peachy_N1\20260924_campaign\evidence\frontend\baseline_full_gui_v1"
```

For the explicit two-cell smoke, add `--allow-partial` and change the output
directory to a fresh `baseline_smoke_gui_v1`. Existing output directories are
refused to preserve earlier evidence. All ordinary source-only EVENT test and
capture commands are in `prototype/tests/README_N1_FRONTEND.md`.

## Actual installed entrypoint idle/closure check

`test_installed_entrypoint.py` executes the installed package's real `main.py`
through `runpy`, with its real Controller and UI. Only UI construction is
wrapped to schedule observation and normal `UI.close`; no source is changed.
An isolated data root deliberately contains saved microphone permission and
auto-start preferences. After 900ms the app must still be IDLE, use a 480×800
client, have zero model loads/streams and make zero guarded endpoint, playback,
USB-control or start calls. Normal closure must release the runtime lock, stop
the controller worker and permit a new lock owner. Installed source hashes
are rechecked. Outputs include `INSTALLED_MAIN_RECEIPT.json`, an app-client
`INSTALLED_IDLE.png`, isolated settings/closure data and standard test/isolation
receipts. This is actual entrypoint behavior with nonhardware guards, not a
physical microphone test. The installed source path is explicitly pinned at
the top of the test module.

PowerShell (same worktree directory):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m prototype.tests.run_private_desktop --receipt-dir 'G:\Just_Peachy_N1\20260924_campaign\evidence\frontend\installed_idle_v1' research.nvidia_nemo_comparison.20260924_campaign.frontend.test_installed_entrypoint
```

CMD / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m prototype.tests.run_private_desktop --receipt-dir "G:\Just_Peachy_N1\20260924_campaign\evidence\frontend\installed_idle_v1" research.nvidia_nemo_comparison.20260924_campaign.frontend.test_installed_entrypoint
```

Choose a fresh receipt directory on repeated runs. The test only maps its app
on the private desktop and never switches or controls the user's desktop.

## Recorded N1 verification

The completed `baseline_full_gui_v1` run rendered all 96 actual final snapshots
successfully: 1,469 rows and 2,493 summed scene span IDs retained, with 2,938 GUI
application receipts. Six app-client PNGs were generated and three representative
images were visually inspected. The source bindings passed before and after
replay; the user's input desktop stayed unchanged and the private desktop
handle was closed. This remains final-state rendering, not original online
first-label timing, acoustic accuracy or physical scanout evidence.

The actual installed-entrypoint check passed in `installed_idle_v2`: saved
auto-start preferences did not start capture, all model-load/stream counters
were zero, and normal UI closure stopped the worker and released/reacquired
the runtime lock. The installed runtime source remained unchanged.

`FRONTEND_STATUS.json` is the redacted handoff summary. It binds the external
test, isolation, full replay and visual-review evidence by SHA-256. Detailed
caption receipts and rendered actual transcript images remain in private
campaign evidence outside Git.
