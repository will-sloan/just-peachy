# D1 saved-bank workload diagnostic

Purpose: assess whether silence/activity gating could remove enough work to
offset D1's measured desktop CPU cost. This does not change a backend, run a
neural model, or validate a discontinuous Nemotron stream. No Pi is contacted.

Inputs are the existing accepted-plan ASR/D1 reviews and their hash-verified
results, 480 hash-verified mono PCM16 saved WAVs, the private estimated activity
truth and public 240-scene catalogue. Only A0, A2 and E0 are used. No transcripts,
audio, embeddings or identities are exported in the public summary. Truth is
used only after cue construction for evaluation and an explicitly marked oracle.

The fixed experiment uses 20ms RMS energy at -55/-45/-35 dBFS, 200ms pre-roll
and 400ms hangover. RMS is not a speech VAD. Nonempty final ASR support with
the same padding, and its union with -45dB energy, are offline diagnostics.
Neither final ASR nor the oracle can implement causal gating. An energy gate
could implement this support with a 220ms decision buffer; this script computes
the support offline and does not certify a streaming implementation.

Outputs: fresh private `ROWS.json` and `RECEIPT.json` (all input/code hashes),
and a fresh public aggregate JSON. Existing outputs are refused. Aggregates
report retained audio, estimated speech/overlap loss, completely lost short
turns (at most 1s active reference), and an optimistic FIFO workload simulation.
The simulation scales each file's observed full D1/E0 desktop collection time
linearly by retained audio, dispatches 20ms retained work after a fixed 220ms
delay, and preserves gaps as time in which work can drain. It omits new gate
cost, native chunk granularity, context replay, state repair and fusion. Results
are NOT measured optimized RTF or Pi performance. Complete-reference speech
loss excludes incomplete ambient scenes; workload includes every scene. Two
taps are paired representations of the same 240 scenarios.

Run after checking exact numerical worker identities/ownership. The script
requires a terminal supervisor snapshot, pins itself to logical CPU14 below
normal priority with one thread, checks C:50/G:75GiB free, and checks a ten-minute
budget between files. It imports no app/device/neural-model code. Its bound is
480 files and existing finite event archives. No downloads or audio playback.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -m unittest test_d1_workload_v1 -v
& $py assess_d1_workload_v1.py --output-dir G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-workload-v1 --public-output D1_WORKLOAD_ASSESSMENT_V1.json
```

CMD or Anaconda Prompt (use the pinned interpreter even when Conda is active):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -m unittest test_d1_workload_v1 -v
"%PY%" assess_d1_workload_v1.py --output-dir G:\Just_Peachy_N1\20260924_campaign\local\n5\d1-workload-v1 --public-output D1_WORKLOAD_ASSESSMENT_V1.json
```

For repetition choose new private and public output names. The five arithmetic
tests cover overlapping intervals, partial final audio frames, queue growth,
burstiness despite equal duty cycle, and distinct-speaker overlap accounting.
Do not choose a threshold from this bank and claim independent validation.
