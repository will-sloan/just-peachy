# S6A paced resident CPU experiment

s6a_runtime_profile.py executes four real, paced application sessions on CPU with unchanged model weights. It crosses ASR/speaker thread counts 1 and 2 with host ASR dispatch 50 and 100 ms. Punctuation remains one thread; cues are disabled and the voice/time tracker is anonymous. It does not access audio hardware.

Version 2 explicitly sets OMP_NUM_THREADS, OPENBLAS_NUM_THREADS, MKL_NUM_THREADS and NUMEXPR_NUM_THREADS to 1 before imports and child startup. Each worker logs and checks those values. The earlier v1 run inherited unset numeric-library limits and is preserved as an adverse resource screen, with its exact executed runner/README under runtime_cpu_v1. V2 uses runtime_cpu_v2 and cannot reuse v1 job identities.

Inputs are --repo, the existing S6A --report, and a versioned --output directory. The script selects the lexically first two cases in the preselected 36-case panel, reads their completed S5 O0 native PCM16 journals, and concatenates both complete inputs without gain or sample changes. The combined duration must be 60–90 seconds. This artificial file boundary is explicitly an engineering workload, never an accuracy benchmark.

One coordinator starts one worker at a time. Each worker owns one resident instance of Sherpa, Pyannote, ReDim and punctuation throughout its paced file. Application code is read-only. Completed jobs resume only when exact profile, input and code identities match. Active coordinator locks fail closed. Every owned worker PID and creation time is recorded; timeout cleanup targets only those identities. Failures and logs remain.

Run from PowerShell:

~~~powershell
& "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6a_runtime_profile.py" --repo "C:\Users\amiri\Documents\GitHub\just-peachy" --report "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6A\20260909T202250Z" --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s6a\20260909T202250Z\runtime_cpu_v2"
~~~

Run the same quoted command in Anaconda Prompt or ordinary CMD without the initial PowerShell &. No environment installation is required. The exact same command resumes incomplete work; do not use the internal --worker option manually.

Outputs include INPUT_CONTRACT.json, MANIFEST.json, four profile files, per-worker launch/identity/live/final receipts, full native local sessions, resource samples, heartbeat/cleanup receipts and aggregate RUNTIME_EXPERIMENT.json. A compact copy of RUNTIME_EXPERIMENT.json is also written into the S6A report. Keep local waveform, full event logs and vectors out of the compact handoff.

Resource sampling covers the complete application process tree every second. RSS sums are an upper bound because shared pages may be repeated. USS is private resident memory. RSS minus USS estimates shared resident pages without deduplicating them. Windows private commit is virtual committed memory, not physical resident RAM. OS headroom, CPU, I/O writes, actual source progress and per-lane backlog are recorded. The external research coordinator's memory is shown separately.

The experiment compares exact final words, native PCM16 and matching embedding vectors across the four settings. Thread changes use a 1e-4 maximum absolute vector difference diagnostic; attribution races are not numerical-parity claims. Results reflect the measured desktop and concurrent research load. They cannot establish CM5 speed, thermals, sustained multi-hour behavior or final 2 GB deployment fit.
