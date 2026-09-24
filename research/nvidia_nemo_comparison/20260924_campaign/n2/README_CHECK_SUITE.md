# Frozen prototype suite in separate private processes

`check_suite.py` discovers every `tests/test*.py` module in the supplied frozen
prototype and runs each sequentially through that source's original
`tests/run_private_desktop.py`. Each module receives a separate private Windows
desktop process. The launcher never switches the input desktop or injects
keyboard/mouse input. A failure or native crash in one module is retained and
does not remove later modules from the denominator. Frozen source is not edited.
The frozen tests directory remains on the module search path for existing
sibling fixture imports. Missing target imports count as launcher loader errors
and can never produce suite success. Source-receipt auxiliary files and exact
tool snapshots are bound alongside the prototype tree.

`suite_child.py` is the unittest loading/accounting helper. Before target test
imports it disables real sounddevice enumeration/capture/playback/settings,
Windows endpoint enumeration in both app import namespaces, and actual
non-Python subprocesses (including external USB/host tools). Mock hardware
adapters remain permitted. It asserts one requested CPU, BelowNormal priority,
empty CUDA visibility and `N2_TEST_E1=1`. The latter enables the existing saved
waveform TitaNet/store test; no new acoustic scenes, personal enrollment or model
installation are performed. Existing synthetic test files may create temporary
synthetic data, as their original contracts specify.

Inputs: the immutable prototype directory and adjacent `SOURCE_RECEIPT.json`,
the original application Python environment, one allocated CPU and a **fresh**
private output directory. The existing real E1 test also needs the already
staged TitaNet bundle and E window manifest; its usual `N2_E1_BUNDLE`/`N2_WINDOWS`
overrides remain supported. No active numerical owner's CPU may be reused.

Outputs: immutable source/tool/interpreter/module admission; per-module exact
test census and IDs, skip reasons, test/native/launcher logs, commands, guard,
private-desktop isolation and accounting receipts; `PROGRESS.json`; and final
`RESULT.json`. `COMPLETE` requires all discovered modules, exact started/completed
test census, successful unittest results, clean child exits and preserved
desktop isolation. Expected failures and skips remain explicitly counted.
Failed or missing receipts produce `FAILED` and process exit 2. No old failed
suite is overwritten. A module has a 240-second default bound (configurable
1–1800); the parent allows an additional 30 seconds for launcher cleanup before
stopping only the launcher identity and its descendants.

From PowerShell (CPU4 must be allocated and free):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B research\nvidia_nemo_comparison\20260924_campaign\n2\check_suite.py --source 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v7\prototype' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\checks\full-suite-isolated-v3' --cpu 4
```

Command Prompt / Anaconda Prompt (no environment activation/install needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B research\nvidia_nemo_comparison\20260924_campaign\n2\check_suite.py --source "G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v7\prototype" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\checks\full-suite-isolated-v3" --cpu 4
```

`validate_completed_report(report_path, source_receipt_path)` in `check_suite.py`
is a read-only finalization API. It rereads every census, result, command and
bound evidence file, verifies current source/tool hashes and exact aggregate
counts, and returns counts, skip reasons and report bindings. It launches no
processes or models. A native crash remains a failure even if unittest wrote a
successful receipt before shutdown.

`test_check_suite.py` checks accounting using small temporary JSON fixtures:
crash rejection, missing/unfinished tests, skip retention, count/guard mismatch,
complete module denominator, and continued accounting after a failed module.
It uses no UI, audio or models and prints five unittest results. Run on the
allocated CPU using the following (PowerShell, then CMD/Anaconda equivalent):

```powershell
& $py -B -c "import psutil,runpy; p=psutil.Process(); p.cpu_affinity([4]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); runpy.run_path('research/nvidia_nemo_comparison/20260924_campaign/n2/test_check_suite.py',run_name='__main__')"
```

```bat
"%PY%" -B -c "import psutil,runpy; p=psutil.Process(); p.cpu_affinity([4]); p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); runpy.run_path('research/nvidia_nemo_comparison/20260924_campaign/n2/test_check_suite.py',run_name='__main__')"
```

## Recorded verification

The five accounting regressions passed. The complete v6 prototype run at
`local/n2/checks/full-suite-isolated-v2/RESULT.json` completed 46/46 modules and
432/432 discovered tests: 430 passed, two skipped with the explicit reason
`Linux recovery policy`, zero failures/errors/expected failures/unexpected
successes. The real saved-waveform E1 test and all 44 N2 integration tests passed.
Every module had its own private process; no native/Tk crash occurred. The
read-only validator passed and `VALIDATION.json` records that all 46 launcher
owners had ended before CPU4 was released. RESULT SHA256 is
`5815daa4bd8ff16cdf59280576395b0dbce87d9533b4ba4e32372f66083e4742`.

The earlier `full-suite-v4` native crash and `full-suite-isolated-v1` failed
attempt remain intact. The latter exposed sibling fixture import paths and a
missing frozen auxiliary scoring file; the helper path and v6 package fixed
those issues without editing the frozen application or skipping tests.
`full-suite-isolated-v2` is completed evidence: choose an unused output name to
run the command again. These results establish the software tests performed,
not Linux/CM5 execution or physical hardware validation.

After the separately reviewed archive-record bound fix, the full v7 run at
`local/n2/checks/full-suite-isolated-v3/RESULT.json` passed all 46 modules and
accounted for all 436 tests: 434 passed and the same two Linux-only tests skipped.
All 20 session tests (including four new record/queue regressions) and all 44 N2
integration tests passed. Source, auxiliary-file, tool and evidence validation
passed; all 46 launcher owners had ended before CPU4 was released. RESULT SHA256
is `b606bf350bf671a21dad142c1732608048fbeedd981e838fd781c94a32174273`.
The commands above record that v7 run; use a fresh output name for a new run.
No model, association, N2 revision-dedup or common-UI change was made by this
suite runner. Earlier passed and failed receipts remain intact.
