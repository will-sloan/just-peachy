# Stopped application transport review

`review_application_transport.py` connects the immutable input, child permit,
final lease, private Windows process lifetime, child/application terminal
receipts, initial slot census and parent cleanup for one stopped application
cell. It detects a swapped file, wrong input, reused PID identity, changed
command/code, forced termination, late parent error or mismatched slot release.
It only reads saved evidence and queries exact process identities. It never
launches an application, creates a desktop, opens audio, enumerates devices,
signals a process or changes the campaign supervisor.

The internal `review_cell(folder, payload=..., plan_sha256=..., coordinator=...,
code=..., executable=..., coordinator_argv=..., state=...)` API requires the
future full-panel reviewer to independently reconstruct the qualified plan and
terminal run census. Its expectations must come from that reconstruction,
not from the cell's own permit. There is deliberately no standalone production
acceptance command that would substitute arbitrary caller expectations for a
reviewed plan. The fixed runner's source remains unchanged.

Inputs are a closed cell directory plus exact expected context. Output is a
private dictionary with bound evidence, identity/census joins, limitations and
status `PASS_APPLICATION_TRANSPORT_JOINS_ONLY`. Do not publish private cell
payloads. JSON records are limited to 1 MiB; duplicate keys, non-finite constants
and reparse paths are refused. Bound code/interpreter files are rechecked.
The coordinator and all observed application process identities must be gone;
access uncertainty is propagated rather than treated as an exited process.

The saved final lease is checked at its recorded issuance time, including its
permit, sequence and lifetime join. This does **not** re-establish continuous
freshness: the runner retains no complete renewal history. Windows job totals
can exceed the identities observed at close, for example for a short-lived
console helper. The difference stays explicit; zero active job members does
not create missing historical identities. Input desktop equality is the
recorded before/after observation, not a continuous focus monitor.

This check does not review source delivery, worker/consumer drain, archive
integrity, viewport contents, naming correctness, latency or measured resources.
The prepared geometry fields are joined declarations, not a new UI measurement.
It never increases accepted N4 cells or establishes a deployment tier. Compose
it with the separately qualified closure, viewport and resource reviews and
the still-required full-panel content/timing/scoring review.

`test_application_transport_review.py` uses inert private fixtures for transport
joins and tampering regressions. Synthetic process existence is mocked only in
those fixtures. Seven previously recorded real native process lifetimes are
also classified with fresh exact-identity exit checks: two normal resumed
closures pass this contract and five failed/forced/unresumed cases are refused.
No new native fixture or speech process is started.

`probe_application_transport_review.py` pins its helper to CPU14, verifies the
existing active D1 owner on CPU4 and its supervisor identities, uses the existing
metric helper lock, and preserves source snapshots and failures. It enforces
the campaign disk floors, shared allocation reserve and deadline through the
existing guard. Its output contains `ADMISSION.json`, source snapshots, retained
synthetic fixtures, `tests.txt` and `RESULT.json`, or a preserved `FAILED.json`.
The probe is currently bound to the active D1 component phase; a later phase
needs an explicit versioned probe/admission update, not a fabricated RUNNING
record. Choose a fresh output directory for every attempt.

PowerShell, from any working directory:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_transport_review.py" --output "$jpLocal\n4\application-transport-review-probe-v2"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly; no
environment activation or installation is needed):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_transport_review.py" --output "%JP_LOCAL%\n4\application-transport-review-probe-v2"
```

The first probe attempt stopped before tests because it looked for D1 code
bindings at the wrong admission level. Its exact source snapshots and preflight
failure remain in `application-transport-review-probe-v1`. The repair verifies
the D1 and predecessor ASR component contracts' code and dependencies. Use
`application-transport-review-probe-v2` as the fresh output shown above for the
repaired probe; never overwrite V1.

Successful development qualification produces only
`PASS_APPLICATION_TRANSPORT_REVIEW_CHECKS_ONLY`. The public redacted receipt
binds the private result and tested source, retaining zero integrated acceptance.
Actual production panels have not yet been collected or reviewed by this code.
