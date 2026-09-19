# Explicit registered native panel jobs

`s6c_explicit_panel_jobs_v1.py` builds exact original native jobs against the
SHA-pinned epoch4 via the reviewed V3 admission wrapper. It calls the unchanged
frozen `make_job` and `validate_job`; it does not launch models. The prospective
panel proposal is SHA-pinned. Only its declared case lists become job inputs;
evaluator-only people/roster/coverage metadata does not enter the predictor.

Inputs: admitted epoch, fixed proposal, `gate6`, `paced16` or `repeat4`, explicit
candidate IDs for paced panels, simple attempt label and repetition number.
Gate6 requires all eight exact pairs: C117/118, C065/079, C119/120, C121/122,
C123/124, C125/126, C127/128 and C129/130. Each uses N01, the registered structural
mode, no gallery, cue-off/on and both same-tap routes: 192 whole native jobs.

Paced16 selects all16 fixed cases once. Repeat4 selects the fixed four repeat
cases for repetition2..4. Each manifest contains one execution per cell; a repeat
retains the original same-source job identity but has a separate attempt folder.
This is deliberate physical repetition, not a new neural recipe or cache hit.
Even repeats reverse the fixed profile/route and case lists for balance. Never
combine repeated identical keys into one native manifest. Paced jobs require one
quiet model worker; preparation itself does not reserve or start that worker.

Outputs: `reports/S6C/20260910T123540Z/jobs/epoch4/explicit_<panel>_<attempt>_repN.json`.
Exact reruns preserve the original manifest; changed settings or selection reject.
The builder never creates native job payload folders. Tests emit a separate
bound fixture receipt. Original native run/attempt/worker schemas remain valid.

PowerShell:

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:JP_S6C_SIM = $s6cSimulation
$env:PYTHONDONTWRITEBYTECODE = '1'
& $s6cPython "$s6cSimulation\scripts\s6c_explicit_panel_jobs_v1.py" test --epoch epoch4 --attempt v2
& $s6cPython "$s6cSimulation\scripts\s6c_explicit_panel_jobs_v1.py" build --epoch epoch4 --panel gate6 --attempt v2 --repetition 1
# Later, replace these example IDs with the explicitly approved finalists:
& $s6cPython "$s6cSimulation\scripts\s6c_explicit_panel_jobs_v1.py" build --epoch epoch4 --panel paced16 --candidates C065 C079 --attempt finalist_example --repetition 1
& $s6cPython "$s6cSimulation\scripts\s6c_explicit_panel_jobs_v1.py" build --epoch epoch4 --panel repeat4 --candidates C065 C079 --attempt finalist_example --repetition 2
```

Anaconda Prompt / CMD:

```bat
set "JP_S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set PYTHONDONTWRITEBYTECODE=1
"%S6C_PYTHON%" "%JP_S6C_SIM%\scripts\s6c_explicit_panel_jobs_v1.py" test --epoch epoch4 --attempt v2
"%S6C_PYTHON%" "%JP_S6C_SIM%\scripts\s6c_explicit_panel_jobs_v1.py" build --epoch epoch4 --panel gate6 --attempt v2 --repetition 1
REM Later only after the finalists are approved; these two IDs are examples.
"%S6C_PYTHON%" "%JP_S6C_SIM%\scripts\s6c_explicit_panel_jobs_v1.py" build --epoch epoch4 --panel paced16 --candidates C065 C079 --attempt finalist_example --repetition 1
"%S6C_PYTHON%" "%JP_S6C_SIM%\scripts\s6c_explicit_panel_jobs_v1.py" build --epoch epoch4 --panel repeat4 --candidates C065 C079 --attempt finalist_example --repetition 2
```

After independently reviewing the exact manifest, use the separate V3 wrapper
prepare/run commands in README_S6C_ORCHESTRATOR_SCAN_V3.md. This builder is
metadata validation, not evidence that a model, paced trial or hardware ran.
The initial gate v1 manifest was prepared but never executed; it and its source
snapshot remain preserved after prospective coordinator guards were tightened.
The reviewed launch uses the separately prepared gate v2 metadata namespace.
