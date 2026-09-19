# Publish a completed candidate slice

Purpose: analyze every registered case/route for an early candidate while a larger native batch continues. The helper never selects individual favorable cases and never starts models. It checks the original frozen manifest and each exact durable receipt, events, summaries and named PCM journals using the frozen native verifier. An incomplete slice only reports NOT_READY; it creates no partial accuracy index.

Inputs: parent job manifest, one or more exact candidate IDs, new label. Outputs: an immutable subset manifest and COMPLETE result index in completed_slices/epoch, once every requested original job is verified. This does not mark the parent batch complete or count reused receipts as extra native runs.

PowerShell from repository root:

```powershell
$sim = Join-Path (Get-Location) 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& '.\.edge-speech-env\python.exe' "$sim\scripts\s6c_completed_slice.py" --manifest "$sim\reports\S6C\20260910T123540Z\jobs\epoch2\recipes_v1.json" --candidates C065 --label N01_panel_v1
```

Anaconda Prompt / CMD:

```bat
set "SIM=%CD%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
".edge-speech-env\python.exe" "%SIM%\scripts\s6c_completed_slice.py" --manifest "%SIM%\reports\S6C\20260910T123540Z\jobs\epoch2\recipes_v1.json" --candidates C065 --label N01_panel_v1
```

The same command may be retried after NOT_READY. Existing completed outputs are immutable. Failed attempts require diagnosis in the native workflow; this helper never replaces them or uses incomplete data.
