# Actual neural prefix and delivery checks

This bounded engineering regression runs two fresh native PipelineEngine instances with P1X0 and the existing Sherpa ASR, Pyannote, ReDimNet2 and punctuation models. Both files have the same exact 12-second recorded O0 prefix and different six-second futures. Files play at real-time pace in an isolated output directory. No hardware, training, reference text, source identity, or XVF telemetry is supplied to the predictor.

It compares the raw ASR partial/final sequence, native endpoint decisions, segmentation posterior summaries/gates, real normalized ReDim vectors, tracker decisions and native displayed speaker labels separately. It also analyzes the completed runtime CPU V2 50/100 ms dispatch pairs for contiguous sample coverage, lost or repeated spans, final words, endpoint counts and numerical vector parity.

This is a regression fixture for these recordings. It cannot establish all possible timing schedules or future audio. First displayed labels are reported independently because the live ASR worker can only consult speaker history already appended by the concurrent speaker worker. Different measured model cost changes modeled availability and can affect labels without future audio leakage.

## Inputs

- Existing S6A profiles/P1X0.json, unchanged.
- Completed runtime_cpu_v2/INPUT_CONTRACT.json and RUNTIME_EXPERIMENT.json.
- Exact existing native O0 PCM16 journals selected by the runtime experiment (lexically first two cases in the preselected probe panel).
- Existing frozen app code and local model assets; no downloads.
- Existing .edge-speech-env with soundfile, NumPy, psutil, Sherpa and ONNX Runtime.
- s6a_runtime_profile.py in the same scripts directory. Its controlled worker is reused without changing app code.

The first future is the first recording's samples 12–18 seconds. The second is samples 0–6 seconds from the second recording. The common prefix is first recording samples 0–12 seconds. This artificial splice is for software causality, not accuracy evaluation.

## Run in PowerShell

~~~powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$report = Join-Path $sim 'reports\S6A\20260909T202250Z'
$runtime = Join-Path $sim 'staging\s6a\20260909T202250Z\runtime_cpu_v2'
$out = Join-Path $sim 'staging\s6a\20260909T202250Z\neural_causality_v1'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6a_causality_checks.py" --repo "$repo" --report "$report" --runtime "$runtime" --output "$out"
~~~

## Run in Anaconda Prompt or Windows Command Prompt

The command uses the existing isolated interpreter, so conda activation is not required.

~~~bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "REPORT=%SIM%\reports\S6A\20260909T202250Z"
set "RUNTIME=%SIM%\staging\s6a\20260909T202250Z\runtime_cpu_v2"
set "OUT=%SIM%\staging\s6a\20260909T202250Z\neural_causality_v1"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6a_causality_checks.py" --repo "%REPO%" --report "%REPORT%" --runtime "%RUNTIME%" --output "%OUT%"
~~~

Allow roughly one minute. The two 18-second files run sequentially in one owned worker at a time. OMP, OpenBLAS, MKL and NumExpr pools are explicitly set to one before numerical imports; profile model thread counts remain effective.

## Outputs and resume

- MANIFEST.json binds the app, both runner files, profile, inputs and source journals.
- FUTURE_A.wav and FUTURE_B.wav preserve the exact shared prefix.
- Each FUTURE_A/FUTURE_B subdirectory contains launch PID and creation time, worker receipt, complete receipt, native session, and stdout log.
- CAUSALITY_DELIVERY_RECEIPT.json in this output and report directory contains the compact comparison.
- Full local native event logs retain measured clocks, first labels and vectors. Do not package complete vectors or audio into the handoff ZIP.
- CLEANUP.json records worker closure. Coordinator lock uses PID plus creation time; stale locks are renamed rather than deleted.
- Exact completed jobs can resume. Changed code/profile/input hashes fail closed; use a new versioned output folder for changed code.
- Workers have a 90-second internal timeout and 160-second coordinator bound. Failure cleanup addresses only recorded PID plus creation-time identities.

A COMPLETE status means measurements finished. The separate engineering_prefix_check_pass and first_displayed_label_invariance_observed fields report the actual findings; a label mismatch is retained rather than hidden. Numeric feature/posterior/decision comparisons use an absolute tolerance of 1e-5; raw text, labels, source spans and dispatch decisions use exact equality. Only enumerated measured/model availability clocks are omitted from semantic comparison, while source/receptive spans remain checked.

