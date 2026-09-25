# V3: observe the actual bounded event inbox

Purpose: retain the qualified research gallery facade while handling the actual
EventInbox used after full session startup. V2's engine-constructor tests used
the initial plain queue. Source inspection found that full startup replaces it
with EventInbox, which adds consumer timing and coalesces obsolete same-utterance
partial events. V2 remains preserved as method-only qualification and must not
be used to certify a full application clock.

`paced_adapters_v3.py` accepts and validates the actual publication and consumer
timestamps separately from the original source origin. It records strictly
increasing publication sequences and counts gaps. After actual consumer drain,
`reconcile_inbox()` requires an actual EventInbox, depth zero, exact consumed
counts, published serial equality and gaps equal to the inbox's own recorded
obsolete-partial coalescence. Unaccounted missing events fail explicitly. It
does not pretend every emitted partial reached the GUI or replace source time
with receipt time. Full source delivery, journal/finalization/archive closure,
publication audit, latency and N4 acceptance remain separate required evidence.

Call install after the prior engine is released and before a fresh start. Keep
one observer per scene, call reconcile_inbox after the actual consumer exits,
and detach only after ownership-safe closure. Refer to README_PACED_ADAPTERS.md
and V2 for the fixed research roster, exact route and unmodified score behavior.
Reference adaptation, alternate scoring and enhancement remain off; the adapter
provides no enrollment or mutation operation.

Nine tests include the prior 160 saved gallery/mode/tap cases, all three real
engine `_emit` to EventInbox to Controller drain paths, actual permitted partial
coalescence, and an intentionally unaccounted missing-event rejection. The
source-start payloads are fixtures. No FileSource, audio, model, GUI, microphone,
USB or playback is run; model acquisition remains forbidden during tests.

Inputs: immutable n4-catalog-v3 source, prepared N4 research galleries and the
two existing runtime manifests. Outputs in a fresh private local/n4 directory:
ADMISSION.json, unittest.txt, CHECKS.json, RESULT.json and isolated Controller
artifacts. Keep all private artifacts out of Git. The launcher pins CPU14, one
math thread, GPU off and below-normal priority, preserving shared resource,
drive-floor and packaging-reserve checks. It is not a controlled timing run.

## PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'research\nvidia_nemo_comparison\20260924_campaign\n4\probe_paced_adapters_v3.py' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-adapters-v3'
```

## CMD / Anaconda Prompt

No environment activation or installation is required with the pinned Python.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n4\probe_paced_adapters_v3.py --output G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-adapters-v3
```

Preserve every attempted run and its bound code. Use a new derivative/output
for a repair; this probe grants no source-paced, physical or whole-stage pass.
