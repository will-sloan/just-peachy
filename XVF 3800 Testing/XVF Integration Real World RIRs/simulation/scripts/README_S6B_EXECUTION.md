# S6B native neural recipes

`s6b_execution.py` freezes executable source, runs actual H2 model recipes on accepted XVF mono files, and stores reusable causal neural evidence. It uses up to four persistent CPU workers; model objects persist within a recipe, while each scene receives a fresh stream and session state. Tracker-only comparisons later reuse these exact features through the same application scheduler.

Inputs: completed S6B admission/input indexes, validated `NEURAL_RECIPE_REGISTRY.json`, the application source and fixed model files. Outputs: immutable execution snapshot/manifest; per-scene native journals, event logs, compressed vectors and receipts on G:; atomic heartbeat and completion/resource indexes in the S6B report directory. No hardware, network, RIR generation or training occurs.

Current execution is epoch2 with the separately frozen atomic_io_v1 persistence adapter. Epoch1 was never executed; final review prospectively corrected B20's cadence. The adapter handles transient Windows sharing-denial errors without changing frozen application/inference dependencies. See `README_S6B_LAUNCH.md` and `EXECUTION_FAULT_LEDGER.md` for the exact repair boundary. The64-output pilot passed; challenge expansion is admitted.

Before a new execution epoch, complete code tests and recipe validation, then freeze once with the live script. The existing epoch2 is already frozen. Never edit an active snapshot or recompile its bound profile registry. A changed predictor implementation requires a new named epoch, preserving earlier attempts.

PowerShell:

```powershell
$s6bSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6bPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:JP_S6B_SIM = $s6bSim
& $s6bPython "$s6bSim\staging\s6b\20260909T230840Z\atomic_io_v1\s6b_launch.py" run --epoch epoch2 --panel challenge --workers 4
```

Anaconda Prompt / CMD (uses the existing edge environment directly):

```bat
set "JP_S6B_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_S6B_SIM%\staging\s6b\20260909T230840Z\atomic_io_v1\s6b_launch.py" run --epoch epoch2 --panel challenge --workers 4
```

Use `--limit 4` for a bounded smoke invocation (the requested scope remains explicit); use `--recipes R0 R1` to select named recipes and `--panel all` for all 240 scenes/two taps. Exact completed jobs are reused only after full content/identity verification. Failed or incomplete attempts stop expansion for diagnosis; no automatic accuracy-driven retries occur.

The completed balanced admission command is `run --epoch epoch2 --panel pilot --recipes R0 R1 R2 R3 R4 R5 R6 R7 --workers 4`. It selects one fixed challenge scene from each of isolated speech, short handoffs, overlap and silent relocation families, on both taps:64 actual recipe outputs. These exact outputs are reused during challenge expansion. `PILOT_ADMISSION_AND_ETA.json` admits18 exact recipes on44 scenes/both taps and records engineering ETA bounds. `PROSPECTIVE_R0_FULL_CONFIRMATION.md` admits full240/two-tap R0 reuse across all23 inexpensive core tracker/control profiles; other full-bank recipes require the comparison's selection ledger.

Create `STOP_REQUEST` or `STOP_REQUEST.json` in `reports\S6B\20260909T230840Z` to stop new launches while owned work drains. Remove only that explicit request after deciding to resume. The same frozen command resumes exact successful receipts. The coordinator also stops launches for memory/disk limits or the 45-minute reporting reserve of this invocation. `HEARTBEAT.json` reports current recipe/scene/tap, counts, resources and conditional ETA every 20 seconds.
