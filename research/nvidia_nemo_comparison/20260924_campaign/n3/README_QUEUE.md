# Prepare and supervise N3

V3 has now completed its 32-job attempt: 15 jobs completed, three failed, and
14 were skipped through failed dependencies. A0/A1 inference and the FP32
reference panels remain valid evidence. V4 repairs native C-ABI geometry and
the A1 export input inventory; see README_REUSE.md for fresh recovery commands.
Eleven unchanged jobs are imported with explicit reuse receipts, not rerun or
represented as newly measured. Actual source, native/export and aggregate
checks run again. No existing output directory is overwritten.

N5 continuation found that v2's initial source check failed before neural work:
the N3 addition selector had admitted `app/__pycache__/n3_models.cpython-311.pyc`.
Mutable bytecode is now excluded both from inherited names and additions. A
temporary-tree regression proves the actual freeze preserves Python source and
omits both cache-directory and legacy adjacent bytecode. V2 evidence remains
untouched. The fresh replacement is `--version v3`, with `plan-v3.json`,
`n3-common-v3` and `numerical-v3`; do not overwrite or re-launch v2. The commands
below are historical v2 examples: substitute v3 only when its output does not
already exist. Later user N4/N5 requests supersede the older stage-only closing
sentence about N4 authorization; numerical prerequisites still apply.

`prepare.py` copies only the reviewed prototype release inventory and N3 source
additions, verifies the frozen UI, binds models/runtime/configuration, and emits
a sequential numerical plan. Inputs are the existing campaign paths, verified
N3 assets and a fresh version. Outputs are a private frozen release, native CPU
and CUDA catalogs, fixed four-row audio panel, worker specification and plan.
It does not launch inference. Its default paths are specific to this campaign.

`supervise_n3.py wait` is a lightweight background owner. It checks the exact N2 run
and finalizer contracts, all 422 cells, passing final checks, process creation
times and released OS locks before using the existing supervisor to start N3.
It blocks on failures or changed source. It does not resume an LLM. A single
N3 numerical child runs at a time, on CPU4 or CPU14; CUDA has one owner. The
shared disk reserves and September 28 02:48 UTC packaging cutoff apply.
Timeout handling stops only the verified owned child tree. No desktop input,
device enumeration, playback, microphone access or Pi access is performed.

PowerShell, from the campaign worktree:

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_queue.py
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare.py --version v2
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v2.json
```

CMD or Anaconda Prompt (the explicit interpreter needs no activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_queue.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare.py --version v2
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v2.json
```

Preparation requires fresh paths; do not rerun it over an admitted release.
After checking `QUEUE_RESULT.json` and actual process ownership to exclude an
existing waiter, launch `supervise_n3.py wait --plan <absolute plan>` with the same
Python and worktree. Use a hidden background process (`Start-Process
-WindowStyle Hidden` in PowerShell) and redirect stdout/stderr to private files.
Do not directly use `supervise_n3.py run` while N2 owns resources: it is the supervisor
worker entry point. Only one numerical coordinator may own its OS lock.

The plan includes the frozen prototype suite, real smoke tests, A1 dynamic
stateful export attempt, CPU native conformance, reference/native fixed panels,
source-paced cases, A0-A3 paired 96-cell screens and 8-cell regressions, separate
A2/A3 three-cell actual GUI panels, lexical scoring and P0/ITN diagnostics.
The sole lower-buffer contrast for A2/A3 uses right context 0 on the fixed
four-row panel. Nominal is 1; A1 stays at its trained [70,1] setting.

Outputs are private `numerical-v2/RESULT.json`, per-job logs, hash-bound raw
partial/final events, metrics, GUI captures and `MANUAL_RESUME.json`. Raw audio
is referenced in place. `READY_FOR_REVIEW` means the queue finished attempting
its plan; inspect each job and denominator. It never means N3 acceptance.
`test_queue.py` tests fail-closed admission without launching any worker.

Resume in the exact existing task: inspect ownership and receipts, review
failures and pending portable A1 qualification, and run only missing work with
a newly reviewed plan. Preserve failed cells and old evidence. Complete the
analysis handoff and verify Git backup before N4. N4 is not authorized here.
