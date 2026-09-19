# S6D all240 direction replay

Purpose: `s6d_application_direction_replay.py` evaluates V0/V1/V2 single, set, all, and V3 over the exact960 frozen original C088/A15+C091/B15 predictions:240 scenes, both taps, both original15 galleries. It shares the fixed opaque selected IDs from the earlier bound focus plan. It evaluates actual current policy without a neural call or hardware action.

Inputs: exact S6C name-analysis/index/gallery/support authorities, original sanitized S6B telemetry and the bound focus plan. The controller receives predictions plus sanitized telemetry; reference truth is used separately to score diagnostic exposure. It does not fabricate telemetry source spans, streams, route IDs, speech-evidence IDs or beam/voice associations from timestamps, seats or truth. V1 is global mono speech gating; V2/V3 require independent matching stream/source/route and explicit speech+voice evidence links.

Outputs: a predeclared PLAN.json; PER_CASE.csv retaining every scene/mode, missing-field counts, suppression reasons, timing-tick counts and diagnostic arrow exposure; RESULT.json with exact bindings, coverage and adverse aggregates. Sampling is every0.1 seconds on saved host-aligned availability, not GUI or physical latency. Exposure outside referenced active speech uses complete support only; incomplete cases remain unclassified. Right-name/right-direction coverage and error are null when association is unavailable; zero arrows cannot become a successful V2/V3 gate. The complete original transcript and audio remain untouched.

PowerShell:
```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_application_direction_replay.py" --focus-plan "$s6dSim\reports\S6D\20260913T195357Z\application\focus_replay_v1\PLAN.json" --output "$s6dSim\reports\S6D\20260913T195357Z\application\direction_replay_v1"
```
Anaconda Prompt / CMD (same installed interpreter, no activation needed):
```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_application_direction_replay.py" --focus-plan "%S6D_SIM%\reports\S6D\20260913T195357Z\application\focus_replay_v1\PLAN.json" --output "%S6D_SIM%\reports\S6D\20260913T195357Z\application\direction_replay_v1"
```

Use a fresh suffix when repeating. This is a bounded model-free replay; no firmware, training, raw recording, playback, output deletion, native beam qualification or CM5 claim occurs. The actual Tk canvas/expiry tests are in the application checks and are a separate evidence scope.
