# Manager receiver transport V1

Status: prepared host transport with changed PC subprocess checks. The native
manager exporter, joint dispatcher, resource issuer and exact native closure
utility are not wired by this module. This is not a dispatch command or a
production launcher. Keep old sources and consumed output directories unchanged.

## Purpose, inputs and outputs

`field_local_manager_transport_v1.run` operates one bounded binary protocol
process. Inputs are an explicit argument vector, one <=262144-byte pinned
bootstrap payload, a <=105-second phase, and reviewed callbacks for admission
resource checks, durable early-owner storage, consumer, exact native closure
and bounded stopping of the one admitted unit. It saves no files itself.

The early actual identity is delivered to the persistence callback before any
payload write. Its successful durable publication must return exactly True.
The next HELLO must match all PID/start-tick/boot fields. A Channel provides
strict duplicate-key JSON frames, <=16KiB reads/writes and sequential bounded
writer threads. Stderr retains at most65536bytes; overflow fails explicitly.

The consumer receives `(channel, owner, close)`. Census consumers validate the
CENSUS/NO_TARGET_ROOT admission binding and call close. Export consumers validate
READY, send the owner ACK, and pass channel to the existing manager receiver;
its verify_process_closed callback is close. The receiver's BACKUP publication
remains after close. The wrapper's admission, source SHA/origin, current lifecycle,
unit, host writer allocation and native closure integrations remain required.

close demands stdout EOF, natural process return0, joined readers/writer and a
True result from independently verifying the exact native identity. It does not
treat natural SSH exit, timeout or a synthetic callback as native process death.
A consumer cannot return successfully without closing. Failure stops the exact
owned unit through the caller's bounded callback, kills only the launched local
process if still present, reaps and joins. No retry or deletion occurs.

Returns `(consumer_result, receipt)`. TransportFailure carries a receipt with
bounded stderr, identity, stage flags, errors and actual local process status.
Caller must persist failures within an admitted HostStore allocation and may not
certify a backup after any failure. All callbacks are trusted reviewed code and
must return within their assigned deadline; this is not an arbitrary-code sandbox.
The watchdog cannot make an unbounded caller callback safe.

The wire ceiling155669036+2097152 is a protocol bound only. It does not authorize
additional disk writes or enlarge the full independent manager-tree155669036 or
joint617760944 allocations. Host metadata partitioning remains a joint-issuer
integration gate. No old policy, unit or consumed root may be reused.

## Host verification

Use the existing environment with psutil. No installation or download is needed.
Choose a new output folder; a previously attempted output rejects. The test sets
CPU14 before project reads and registers its actual PC owner and every PC child.
It launches only local Python fixtures. Their Pi-shaped identities and closure
callback are explicitly synthetic. No SSH, native model, microphone or GUI runs.

PowerShell:

```powershell
$P = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$P\check_field_local_manager_transport_v1.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\operator-local-receiver-v1-preparation\transport-check-v1'
```

Command Prompt:

```bat
set "P=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%P%\check_field_local_manager_transport_v1.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\operator-local-receiver-v1-preparation\transport-check-v1"
```

Anaconda Prompt uses the same Command Prompt command and explicit interpreter;
do not assume another conda environment has the pinned dependencies.

Outputs: REGISTERED_OWNER, actual CHILD_OWNER receipts, explicitly SYNTHETIC_EARLY
fixture receipts and RESULT.json. Positive census/export handshake cases and
changed rejection paths qualify PC transport only. Never rerun a passed output
solely for a version change. Source backup and independent restore must precede
running these checks. Native use additionally requires a fresh measured admission,
the whole pinned graph/bootstrap/exporter and a complete exact closure wrapper.
