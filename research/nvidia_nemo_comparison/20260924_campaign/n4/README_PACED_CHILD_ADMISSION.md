# Child admission and renewable parent permission

Purpose: `paced_child_admission.py` implements the future fixed application's
child-side checks before model or source acquisition. It verifies an immutable
permit tied to exact supervisor/coordinator/application identities, commands,
run, private desktop, nonce, reviewed-plan digest, fixed worker code and a bound
input. The input is the existing planner's audio-only execution allowlist; no
evaluator truth, full comparison report or selection rationale is copied into it.

The gate itself never creates an application, acquires a model, reads waveform
samples, enumerates devices or changes supervision. Its source-prime branch
hashes saved files but does not decode audio. No actual production permit is
created by the development probe. The successful supervised child admission and
source-prime branches remain unexecuted; passing refusal/fixture tests cannot
qualify real model execution or any N4 acceptance.

Inputs: one immutable PERMIT.json, launch nonce from the bound command, actual
observed desktop name, exact fixed worker dependency list, INPUT.json and the
coordinator's renewable LEASE.json. Internal `ChildAdmission` requires CPU4 and
the exact direct CPU14 coordinator recorded by the active supervisor. The caller
must observe its own desktop through Windows, not accept a user-supplied label.
The production coordinator must first verify both complete score reviews and
panel plan, acquire `ExclusiveApplicationSlot`, start its fixed child suspended,
register it, write the permit/first lease, then resume it. This module cannot
establish those parent-side prerequisites by itself.

Layout: a fresh private cell directory contains `transport` and `application`.
Create `PrivateApplicationProcess(.../transport)` so its CANCEL file and lifetime
receipt share the transport directory with INPUT.json, PERMIT.json and LEASE.json.
The application output must not exist until the child creates its ApplicationCell.
All paths stay below the campaign's private local/n4 directory. Existing reparse
components and path escapes are refused. Per-read byte limits are 256 KiB for
input/permit and 4 KiB for the lease; asset/code/source manifest counts are bounded.

After every successful parent `slot.check()`, its coordinator may call
`write_lease(path, permit, permit_sha256, sequence)`. `permit_sha256` is the
canonical `common.fingerprint(permit)` content digest, not the JSON-file byte
hash. Renewal uses a private temporary file and atomic replacement, never the
shared campaign ledger. Only the exact CPU14 coordinator can write through this
API. Sequence must increase for new renewals; repeated reads of the same sequence
are allowed. The child rejects rollback, changed ownership/nonce/run/permit,
revocation, future timestamps or permission older than five seconds. Use the
same host's monotonic clock. The parent must keep renewing while the child hashes
assets, prepares, loads models and runs/drains, and stop renewing on any refusal.

`ChildAdmission.check(job, contract)` verifies the immutable permit, cancellation,
fresh supervision, exact live ancestry/commands/CPU, renewable lease, original
packaging cutoff, CPU/GPU policy and disk reserves. Call before starting source
and at the existing once-per-second source callback. The parent separately owns
the competing-runtime census, output bounds and shared payload allowance. A fresh
lease represents that parent's successful guard check; this is trusted local
coordination, not a security boundary against arbitrary same-account processes.

`prime()` additionally verifies all source/runtime/model/gallery/catalog bindings,
the frozen source manifest, the actual backend/mode contract and saved audio hash.
It returns the verified source path for the future fixed worker's imports. It
checks ownership again afterwards. Model payload hashes are not recomputed in
the per-second hot path. Always retain the parent's owned-job cleanup even when
the child cannot run its own cancellation handler.

Outputs: check/prime return records or explicit refusal exceptions. The module
has no direct launch CLI. The probe creates private ADMISSION.json, immutable
source snapshots, tests.txt and RESULT.json or FAILED.json. It uses the existing
helper lock and shared resource/deadline guard on CPU14 alongside current CPU4
ASR. Do not run it during controlled whole-application measurements. Every attempt
requires a new output directory; preserve failures and their exact source hashes.

Nine tests cover the input truth/policy firewall, exact permit identity/desktop,
schema/count/digest bounds, lease expiry/future dates, lease ownership/rollback,
bounded file reads, output containment, refusal of the actual CPU14 development
helper before source/input acquisition, and refusal of a foreign lease writer.
Synthetic valid dictionaries test schema rules only. No real production permit,
successful child admission, asset priming or application run occurs.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B "$jpCode\probe_paced_child_admission.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-child-admission-probe-v1'
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B "%JP_CODE%\probe_paced_child_admission.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-child-admission-probe-v1"
```
