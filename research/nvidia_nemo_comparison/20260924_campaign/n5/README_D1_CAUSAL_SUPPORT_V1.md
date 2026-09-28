# Availability-aware ASR support replay

Purpose: refine the offline workload diagnostic with partial/final ASR support
that was available by a bounded decision deadline. Inputs: completed
`local/n5/d1-workload-v1/RECEIPT.json` and rows, its verified ASR result/event
bindings, prepared PCM16 saved audio and estimated activity truth. Run the
parent first using `README_D1_WORKLOAD_V1.md`.

For every 20ms frame, keep the existing -45dBFS energy cue OR any intersecting
nonempty ASR observation known by frame end plus 0.22/1/2/4 seconds. Observations
use their recorded `available_at_sec`; partials count, and retractions cannot
retroactively remove work. Positive support includes 200ms pre-roll and 400ms
hangover. Late recognition cannot recover a previously discarded frame. The
energy gate needs at least 220ms lookahead for its pre-roll/frame decision.

This is causal with respect to the recorded modeled component clock, not a
measured integrated execution clock. Truth is evaluated separately. No audio
is sent to a model; speaker-state correctness, optimized RTF, thermal behavior,
native Pi performance and label accuracy are untested. Linear cost simulation
inherits the parent's optimistic omissions. Estimated activity is not gold.

Outputs: fresh private rows/receipt with input and code hashes, plus aggregate
public JSON without audio, transcripts or identity data. One logical CPU14,
one numerical thread, below-normal priority, no GPU/download/devices, ten-minute
budget checked per trace and C:50/G:75GiB free-space checks. Inspect exact worker
identities first; the supervisor snapshot must be completed. Existing output
paths are refused. Four tests exercise deadline boundaries, late recognition,
energy fallback and invalid source-clock refusal.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -m unittest test_d1_causal_support_v1 -v
& $py assess_d1_causal_support_v1.py --output-dir G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-causal-support-v1 --public-output D1_CAUSAL_SUPPORT_V1.json
```

CMD or Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -m unittest test_d1_causal_support_v1 -v
"%PY%" assess_d1_causal_support_v1.py --output-dir G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-causal-support-v1 --public-output D1_CAUSAL_SUPPORT_V1.json
```

Use new output names for repeats. Do not deploy a gate or choose production
thresholds solely from this reused comparison bank.
