# Actual component probes and factorial comparison

This runner executes the real optional H2 profiles on the frozen 36-scene screening panel, both saved XVF taps. It performs 720 fresh full-pipeline branches: ten component/interaction profiles × 36 scenes × two outputs. A profile changing endpoints or audio always gets a new stateful recognizer. Model weights remain unchanged. Screening results guide S6B; they are not all-bank superiority claims.

Inputs are `PROBE_PANEL.json`, all-bank `JOB_MANIFEST.json`, `profiles/PROFILE_INDEX.json`, and sanitized `CUE_DELIVERY_INDEX.json`. Metadata includes arrived sensor values only. True participants, transcripts, source schedules and room labels never enter the predictor. Already gained probe FLOAT files are read at unity.

PowerShell, from the simulation scripts directory:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' .\s6a_probe_resume.py --workers 2 --limit 2
& 'C:\Users\amiri\anaconda3\python.exe' .\s6a_probe_resume.py --workers 2
```

Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s6a_probe_resume.py --workers 2 --limit 2
"C:\Users\amiri\anaconda3\python.exe" s6a_probe_resume.py --workers 2
```

The same command resumes only exact code/profile/audio/telemetry identities. One coordinator lock and bounded child pool enforce ownership. Each failed attempt stays local; one identical retry is allowed. Children have 360-second timeouts and PID/creation-time cleanup. Do not edit application or runner files used by active jobs. A STOP_REQUEST.json in the report directory stops new launches. The fixed launch cutoff preserves at least45 minutes for closure.

The supported public entry point is s6a_probe_resume.py. It rehashes every declared current code, profile, raw/gained audio, telemetry and model-asset binding before entering the unchanged native runner, even when file size and mtime were preserved. The underlying s6a_probes.py entry point is internal and requires verified immutable dependencies. Use --verify-only to check bytes without inference; use up to --workers 4 only within the coordinator's resource allocation. README_s6a_probe_resume.md documents guard receipts, isolated mutation tests and the invocation-boundary limitation. Do not edit any dependency during the run. Existing native job keys and completed results remain unchanged.

The current manifest is `PROBE_JOB_MANIFEST_V2.json`. Reports are in `simulation\reports\S6A\20260909T202250Z\probes_v2`; full native audio/events/vectors remain in `G:\Just_Peachy_S6A\20260909T202250Z\probes_v2`. The 48 successful jobs under the earlier `probes` namespace are preserved and excluded after a reviewed overlap-display fix. `PROBE_V1_CLOSURE.json` identifies their archived code and reports; profile settings and the panel did not change. Full logs/vectors are excluded from the compact handoff. Per-attempt resources distinguish RSS, private resident USS and Windows private committed memory. Accelerated wall time is an offline throughput measurement; the separate paced experiment provides desktop queue evidence.

After the runner completes, analyze in PowerShell:

```powershell
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' .\s6a_probe_analysis.py
```

From Anaconda Prompt or Command Prompt:

```bat
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6a_probe_analysis.py
```

Use `--interim` only for a partial diagnostic snapshot. Final analysis requires720 successful native outputs. It writes `probe_metrics_v4` (earlier interim directories are preserved), COMPONENT_PROBE_RESULTS.csv and JOINT_FACTORIAL_RESULTS.csv. Counts are pooled before computing rates. Shared causal tracking metrics score first available labels with their expiry; short-turn evidence and coarse segmentation retain source-based denominators. Endpoint variants are scored from their newly decoded words. Prototype input windows crossing different known source envelopes are counted separately, not labelled clean voice evidence. Modeled source availability assumes already-resident models; cold loading and accelerated wall scheduling are reported separately. Native displayed labels can also depend on concurrent worker scheduling and are not a deterministic source-clock benchmark.

Final ASR compute totals include regular dispatch, partial tail dispatch and EOF drain; punctuation and model loading remain separate. Unavailable memory samples are null, never zero. Interim factorial estimates are suppressed until the full matched panel is complete. See README_S6A_PROBE_REPORT.md for paired interpretation commands.
