# Deterministic A1 portable screen and application-runtime checks

`run_asr_a1.py` is a derivative of the existing saved-audio runner. It adds the
explicit A1 ONNX bundle and an inference-only A1 reference frontend; original
run_asr.py and its results stay unchanged. Inputs, exact sample accounting,
independent source-speed producer, tail flush, text/event rows and per-cell
locks follow README_RUN.md. The ONNX path requires nominal right context 1,
records NumPy/SciPy/ONNX Runtime versions and rejects importing Torch or NeMo.
The runtime verifies every bundle asset; no model or vocabulary is downloaded.

This new A1 screen is necessary because the original reference service created
its separate feature processor in training mode with random dither. The new
nominal uses inference-only features and an actual ONNX service whose encoder,
decoder, cache, token and EOU outputs must first pass strict fresh-reference
checks. Old A1 predictions remain historical evidence, not reused results.
Unchanged A0/A2/A3 screen evidence is hash-bound for matched rescoring.

`prepare_a1_screen.py` takes `--parent-plan` (v4), `--service-plan` (the exact
accepted service parity attempt), and fresh alphanumeric `--version`. It
requires the terminal service queue, all five saved-audio/replay parity cases
and its exact bundle. Outputs: private plan and worker specification. Six jobs
run serially: two-cell application-Python smoke, 96-cell portable screen,
eight regressions, four source-paced cells, then updated lexical/text reports.
All full screen/regression/paced rows require actual new inference. No new
GUI or ARM64/CM5 claim is made. The earlier two-cell smoke is separate coverage.

`test_a1_stream.py` tests empty input, exact one-sample PCM tail padding,
idempotent finish, closed-stream refusal, words on both sides of EOU and exact
event replay with a deterministic stub. These are model-free protocol tests,
not substitutes for actual neural parity or the application-runtime smoke.

PowerShell, from the worktree:

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_a1_stream.py
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_a1_screen.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json --service-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1servicev2.json --version a1nominalv1
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1nominalv1.json
```

CMD/Anaconda Prompt (no activation required):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_a1_stream.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_a1_screen.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json --service-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1servicev2.json --version a1nominalv1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1nominalv1.json
```

Use README_QUEUE.md's hidden wait launch once only after inspecting exact live
ownership. Do not race an existing queued plan: let the prior queue dispatch
before registering this next waiter. One candidate owns the numerical slot;
CPU4 only and no GPU. Existing disk reserves, saved-audio/privacy constraints,
packaging cutoff and campaign deadline remain enforced. No desktop input/focus,
visible launch, microphone, playback or Pi access is used.
