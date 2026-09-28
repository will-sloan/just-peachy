# Selected-backend catalog binding for the panel retry

V1 stopped before dispatch because it required the entire old and current catalogs to be byte-identical. V2 keeps the original gallery payload and requires the complete selected backend row, catalog schema/metadata and derived open-with-names E0 routing contract to be identical. It records changes to unselected rows explicitly. It never relaxes a model, runtime, input, inference/drain or closure check. V1 source and failure receipt remain preserved.

Purpose/inputs/outputs and resource limits otherwise follow README_PANEL_RETRY_V1.md. New code: panel_catalog_v1.py validates the binding; build_panel_retry_v2.py produces a fresh panel_retry_v2.py and runs positive/negative selected-row checks using the actual catalogs. Output is the private CATALOG_REBIND_V2.json and V1 preflight-failure receipt plus the generated runner. The existing panel-journal-v1 derivative is reused unchanged. Nothing is downloaded or connected; no source model is run by the builder.

PowerShell / Anaconda PowerShell from this directory:

```powershell
$p='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $p -B build_panel_retry_v2.py
& $p -B panel_retry_v2.py prepare --name a0-panel-retry-v2 --backend nemotron_hybrid
& $p -B panel_retry_v2.py review --name a0-panel-retry-v2
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B build_panel_retry_v2.py
"%RESEARCH_PY%" -B panel_retry_v2.py prepare --name a0-panel-retry-v2 --backend nemotron_hybrid
"%RESEARCH_PY%" -B panel_retry_v2.py review --name a0-panel-retry-v2
```

Builder runs once; admission and run names must be fresh. Review only after terminal status and exact process closure. A2 uses nemotron_600m and a distinct run name after A0 review. A scoped retry pass is not semantic/timing acceptance or completion of the original panel.
