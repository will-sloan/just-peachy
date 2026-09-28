# Extension-local N4 collector paths

V2's actual full-file run reached stopped state with zero ASR/speaker lag and closed its Controller. It nevertheless remains FAILED_PRESERVED: closure's archive reader could not import the repository research namespace, and the delivery reader restricted output to local/n4. Neither failure is waived or credited as acceptance.

Purpose: preserve the original collection checks while making their import and output locations explicit for this extension. Inputs: immutable V2 runner, original paced_application_cell_v2.py and application_delivery.py, current unchanged panel-journal-v1 source. build_panel_retry_v3.py creates panel_retry_v3.py, panel_cell_v1.py and panel_delivery_v1.py. The runner adds the worktree to its import path and binds the N3 archive-reader source files. The cell imports the derivative delivery reader, whose permitted evidence root is narrowed to local/n5/research-extension-20260928. It still rejects escaping/reparse paths and retains every existing delivery/source/closure assertion. No application, inference or drain code changes.

Outputs: private HARNESS_PATHS_V3.json source lineage and path/import checks, followed by fresh run/review evidence. The builder checks that the actual namespace resolves and that an outside-root path is rejected. The V1/V2 harnesses, preflight and numerical failure are preserved. Resource, source/gallery and interpretation limits remain those in README_PANEL_RETRY_V1.md and README_PANEL_RETRY_V2.md. Each new run needs a fresh census and supervised admission. No broader N4 population or release acceptance is implied.

PowerShell / Anaconda PowerShell:

```powershell
$p='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $p -B build_panel_retry_v3.py
& $p -B panel_retry_v3.py prepare --name a0-panel-retry-v3 --backend nemotron_hybrid
& $p -B panel_retry_v3.py review --name a0-panel-retry-v3
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_panel_retry_v3.py
"%RESEARCH_PY%" -B panel_retry_v3.py prepare --name a0-panel-retry-v3 --backend nemotron_hybrid
"%RESEARCH_PY%" -B panel_retry_v3.py review --name a0-panel-retry-v3
```

Use fresh a2-panel-retry-v3 / nemotron_600m after the A0 review. Never rerun a passing cell absent a new concern. Review after supervisor termination and exact process closure only. The builder changes report/harness modules, not source bound to a numerical run.
