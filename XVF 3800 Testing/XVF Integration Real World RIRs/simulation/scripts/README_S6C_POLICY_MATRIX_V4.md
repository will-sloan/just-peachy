# Policy replay with a complete native-worker dependency boundary

`s6c_policy_matrix_v4.py` runs the same frozen v3 tracker/name scheduler on actual native observations, with zero neural-model or playback calls. The entire native `s6c_execution.py` and `s6c_common.py` bytes must match between source and target epochs. APP, models, Python/packages, canonical inputs, extraction, frontend, stateful schedule and recomputed execution digests are also checked. Embedded profiles must equal their hash-bound validated registries. V3 outputs remain preserved.

Inputs: frozen target epoch; explicitly declared source epoch manifests; ordered complete native result indexes; exact candidate IDs; challenge/all population; fresh output label. The first compatible supplied source is selected without outcome selection. Changed waveform/decoder/window/stateful cadence requires corresponding actual inference. Uncertainty or cue-driven cadence requires exact full profile, cues and gallery.

Outputs: bound policy plan, progress and final index under the REPORT epoch, with compressed predictions under the isolated G: payload. Each prediction binds actual observations/upstream availability, profile, gallery condition/tier/manifest, cues and orchestrator. Policy cost remains separate from native cost and paced latency. Ordinary prediction gets no reference person IDs/text. Nominal geometry is explicitly diagnostic.

After epoch4 is frozen with V5 profiles and the additive V2 gallery index, this example executes six common-roster controls on the genuine N01 panel. Do not run it before freezing and checking that epoch.

PowerShell:

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cReport = "$s6cSimulation\reports\S6C\20260910T123540Z"
$env:JP_S6C_SIM = $s6cSimulation
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$s6cSimulation\staging\s6c\20260910T123540Z\epoch4\scripts\s6c_policy_matrix_v4.py" --epoch epoch4 --source-epochs "$s6cReport\EPOCH2_EXECUTION_MANIFEST.json" --indices "$s6cReport\completed_slices\epoch2\N01_panel_v1_RESULTS.json" --label common_duration_panel_v1 --candidates C141 C142 C143 C144 C145 C146
```

Anaconda Prompt / CMD:

```bat
set "JP_S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_REPORT=%JP_S6C_SIM%\reports\S6C\20260910T123540Z"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_S6C_SIM%\staging\s6c\20260910T123540Z\epoch4\scripts\s6c_policy_matrix_v4.py" --epoch epoch4 --source-epochs "%S6C_REPORT%\EPOCH2_EXECUTION_MANIFEST.json" --indices "%S6C_REPORT%\completed_slices\epoch2\N01_panel_v1_RESULTS.json" --label common_duration_panel_v1 --candidates C141 C142 C143 C144 C145 C146
```

For all-240 confirmation, use `--panel all` and complete full-grid native results. Missing source cells fail before output. N00 uses its separate legacy-support replay. Omitting candidate IDs selects every non-N00 profile and needs all matching native recipes/split/state-dependent sources; explicit subsets are preferred.

Completed-index resume verifies output byte bindings. Interrupted payloads without a complete index are compared with fresh shared-policy output before reuse. Gallery limits apply on every request, including resident hits. Changed code/dependencies require a new version/epoch, and changed selection requires a new label. Rollback selects an older source lineage for future work without replacing evidence. No production defaults, private galleries or audio are changed.

