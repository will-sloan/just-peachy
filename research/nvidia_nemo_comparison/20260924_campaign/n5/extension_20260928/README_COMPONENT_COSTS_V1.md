# Cumulative component call accounting

Purpose: retain complete call counts and timing totals independently of rotating event journals. A fresh derivative of reviewed `ui-error-v1` adds bounded counters for ASR accept/reset/finish, D1 push/finish including empty-frame results, and E0 embedding windows. Setup/acquisition counters are separate. No decoding, chunking, thresholds, identity logic, audio selection or inference/drain gates change. Only A0/D1/E0 and A2/D1/E0 accounting is targeted; D0 speaker accounting is not implemented here.

Inputs: hash-verified parent source, extension window and fresh storage/ownership census. The builder copies source only into `local/n5/research-extension-20260928/derivatives/component-costs-v1`; existing sources and evidence remain unchanged. Output: derivative manifest and census, cumulative `component_costs` in engine telemetry and the existing atomic session summary. No waveform, vector, text, individual call list or error content enters the counters. Eight fixed keys keep memory bounded. Each new engine starts fresh counters; resident model reuse remains unchanged.

Times measure application call boundaries, including adapter work. They are not pure kernel time. Journal waits, pacing, publication and counter-lock bookkeeping are outside those boundaries. Calling-thread CPU excludes native worker CPU. `model_setup` combines ASR/E0 acquisition and stream creation; `diarizer_setup` includes D1 load or reset. Do not add concurrent wall-call totals and call them session elapsed time. Embedding sample totals count overlapping submitted windows, not unique source audio. Failed calls retain elapsed cost and attempted samples but add no successful samples; in-flight counts prevent incomplete snapshots from appearing complete. Existing session elapsed time remains separately labelled. Model-free tests check zero-frame calls, exception propagation, in-flight/concurrent snapshots, fixed memory structure and exact accounting. Actual full-file parity and count conservation are still required before numerical results qualify.

PowerShell / Anaconda PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928'
$researchPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $researchPython -B -c "import psutil,unittest; psutil.Process().cpu_affinity([14]); unittest.main(module='test_component_costs_v1',verbosity=2)"
& $researchPython -B build_component_costs_v1.py
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
set "RESEARCH_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%RESEARCH_PY%" -B -c "import psutil,unittest; psutil.Process().cpu_affinity([14]); unittest.main(module='test_component_costs_v1',verbosity=2)"
"%RESEARCH_PY%" -B build_component_costs_v1.py
```

Use the existing interpreter; no install or download. The builder refuses an existing derivative, pins CPU14, retains exact ownership/storage checks, and performs no inference or device access. Run numerical validation only through a fresh supervised admission described by `README_COST_RUN_V1.md`; the builder alone is not a functional pass. Resources remain CPUs4/14 total, native threads1, GPU off, no hardware/capture/playback/training/enrollment, original storage floors and combined output allowance. Full N4/N5 and native CM5 acceptance remain separate gates.
