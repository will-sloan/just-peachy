# Whole-study storage forecast

`s6d_storage_forecast_v1.py` reads the latest saved native176 HEALTH census and checkpoint, the preserved52-row physical ledger, exact bank/native/beam/E preparation manifests and a bounded selection of closed output folders. It estimates all remaining physical378, native176 unfinished jobs, serial892, Tk8, HOST2, C12, beam core96, stream diagnostics528 and a stated reporting/gallery/listening allowance. It does not rerun a census, open waveform contents, run inference, access hardware, delete/compress files or alter limits.

Inputs are the existing immutable S6D manifests and mutable saved HEALTH/checkpoint/ledger under the fixed run roots. Only four closed physical samples and at most twelve closed native job folders are recursively inventoried by file metadata; each is capped at1000 files. All62 E/physical-continuous input WAVs are already counted by the all-root census; their future physical captures are within378. The two HOST jobs are distinct and use exact declared1827.426625s sources. This version refuses a physical ledger count other than52: a changed physical state requires an explicitly updated forecast epoch, not silent reuse.

The fresh small report folder contains INPUT_SNAPSHOT.json (saved mutable evidence, immutable metadata hashes and selected inventories), FORECAST.json (arithmetic, assumptions and limits) and FORECAST.md (compact interpretation). Low/central/high are sensitivity estimates, not statistical intervals or hard upper bounds. New beam/Tk/long-context event populations and retries are uncertain. Existing 40GiB additional-payload cap and C50/G75GiB floors remain mandatory. No forecast is execution authority.

PowerShell, select a fresh suffix:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_storage_forecast_v1.py" --output "$sim\reports\S6D\20260913T195357Z\storage_forecast_v1"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_storage_forecast_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\storage_forecast_v1"
```

Only Python standard-library modules are used. Historical physical failures, original/source profiles, parallel-versus-serial interpretation and pending qualification remain unchanged. Review the arithmetic and source bindings before relying on this estimate for planning; it cannot grant a cap increase or reduce required work.
