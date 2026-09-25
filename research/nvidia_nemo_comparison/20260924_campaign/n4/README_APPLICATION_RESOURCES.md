# Bounded application resource observation

Purpose: provide the later actual N4 application runner with process-tree memory,
CPU work, thread counts and lifecycle observations. `application_resources.py`
imports no application, model, audio or GUI code and never signals a target.
It measures the caller and all sampled children, retaining exact PID/creation
identities so previously observed children remain included after reparenting.
Reused PIDs are separate owners; a reused or missing root invalidates the run.
No full process-list scan is used. The original resources.py remains unchanged.

Inputs: a fresh private output directory, sampling interval (0.1–10 s, default
0.5 s), duration limit (at most one hour), and byte budget (1 KiB–64 MiB, default
32 MiB). All observations inherit the caller's admitted CPU affinity. Start the
observer before constructing the GUI/gallery/models when measuring startup:

```python
observer = ApplicationResources(private_output).start()
# At the actual corresponding lifecycle points, in this exact order:
observer.mark('gui_ready')
observer.mark('gallery_ready')
observer.mark('starting')
observer.mark('running')
observer.mark('draining')
observer.mark('closed')
receipt = observer.close()
```

The real runner must call close in its cleanup path even after failure. Phase
marks record caller intent; they do not certify that any GUI/model/source ran.
Missing marks are explicit. Record separate cold/warm session identities and
join these observations to actual startup/source/closure receipts. Sampling
starts in bootstrap; a sample spanning a phase change is labelled transition.
The observer has one bounded-lifetime thread, waits interruptibly, flushes one
sample at a time and retains only phase aggregates and at most 256 identities.
Byte/duration/census/clock failures preserve the prefix and cannot become success.

Outputs: private SAMPLES.jsonl (phase marks and process observations), RESULT.json
(sampled per-phase peaks, first/last observations, process census, CPU deltas,
sampling gaps/durations, error/scope flags and the log hash). Windows RSS sums
can double-count shared pages; USS excludes shared pages; private commit is not
resident memory. Linux PSS is kept separately or unavailable. Incomplete samples
cannot replace valid phase peaks/first/last with partial totals. CPU work sums
each identity's last minus first observed counter, a lower bound: early/late
CPU work and children living entirely between samples can be missed. Observed
exits do not establish that all unobserved external workers are gone.

The observer's own overhead is included. No subtraction turns pacing failures
into successes. WSL/cgroup/external-service memory, model/cache/weight attribution,
GPU allocator/device usage, swap behaviour, controlled isolation and CM5 results
require separate evidence. CUDA_VISIBLE_DEVICES is recorded as an environment
fact only. This helper always leaves controlled_whole_stack_qualified and
target_qualified false; a reviewed full-run receipt must make any stronger claim.
No RAM tier is assigned by the development qualification.

## Model-free qualification

`probe_application_resources.py` runs seven tests: exact identity/CPU reuse,
unavailable versus zero memory, missing/duplicate roots, counter/clock/census
failure, incomplete/transition samples, retained children, storage/deadline
failures and an actual hidden child allocating 16 MiB before normal exit. Its
phase marks are fixtures. No GUI, source, model, microphone, USB, playback or Pi
access occurs. This small CPU14 helper can run alongside admitted CPU4 component
collection; it is explicitly not a fair whole-application resource measurement.
All seven tests must pass; logs, admissions, actual-tree evidence and deliberately
failed prefix fixtures remain in a fresh private directory. Existing evidence
and bound code remain immutable; later repairs use a derivative and fresh output.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n4\probe_application_resources.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\application-resources-v1'
```

## CMD / Anaconda Prompt

Use the pinned existing interpreter without installing or activating a new environment.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_application_resources.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\application-resources-v1
```

The launcher pins CPU14/BelowNormal, one math thread and GPU visibility off,
checks campaign storage floors/allowance with 6 GiB reserved, and observes the
packaging cutoff. Future actual neural/resource sessions must wait until the
current model owner and all other evaluation helpers have exited, and use the
admitted application CPU configuration. Helper qualification grants no N4/N5
acceptance, full application result or target performance claim.
