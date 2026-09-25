# Closure V2: source-clock ownership join

Purpose: join the verified V1 lifecycle check to the exact source-clock observer,
engine, consumer, session and admitted file. V1 passed its seven lifecycle tests
and nine historical receipt checks; its evidence stays immutable. This small
derivative delegates lifecycle and archive validation to V1 and adds the missing
cross-session binding, so a clock from another run cannot certify the shutdown.

Use application_closure_v2.capture_engine / capture_archive / validate_complete
for future full runs, with the same retained owners and lifecycle described in
README_APPLICATION_CLOSURE.md. The collector records whether the observer owns
this engine and whether the same consumer is retained or has been released by
the closed Controller. Validation also joins the source payload/session/path,
unchanged origin, unique source-start count and publication/consumption/coalescence
census. A matching sample count alone cannot establish that join.

Inputs: the original closure implementation, the frozen application source,
accepted N3 reports, and the new V3 source-clock contract. Outputs and resource
bounds are identical to V1, in a new private directory. Nine tests rerun the
seven original checks through this derivative and add cross-run clock mismatch
rejections and explicit scope checks. The partial startup still runs only bounded
writers/policy/trace and then cancels: no source, models, GUI or hardware starts.
Historical sessions are read, not replayed. All receipts and fixtures stay private.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n4\probe_application_closure_v2.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\application-closure-v2'
```

## CMD / Anaconda Prompt

Use the existing pinned interpreter without a new environment or installation.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_application_closure_v2.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\application-closure-v2
```

The launcher keeps CPU14/one-thread/GPU-off and existing disk/payload/deadline
bounds. Preserve attempted outputs and all bound source. Successful closure does
not establish full publication content, inference accuracy, real-time throughput,
viewport latency, a complete N4 application run or CM5 qualification.
