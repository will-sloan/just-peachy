# Native broker staging and supervision, V1

Status: PREPARED. The native initializer, ledger, broker writer, CLI and outer gate have not been executed. This is not an installed user launcher or an offline release.

Purpose: connect the reserved recording slot to the actual interactive parent V8 / entry V7, with independent recording archives and a common systemd resource envelope. The CLI supplies the real local staging callback; it does not automate audio New, Start, Save or data actions. Streaming and Chunk52 live remain unavailable. Saved qualifications remain separate.

Inputs: a fresh reviewed immutable broker policy; exact code/config manifest; full child template retaining the 18 mode Registry dependencies and the separate live D1 binding; current owner, baseline, resource and target-inclusive census; verified backups. The initializer takes one bounded JSON line on stdin. Its request has policy, manifest and base64 files. No request/admission for this version has been issued.

Outputs: independent STAGE_OWNER, GATE_OWNER, gate ACK/envelope, broker OWNER/RESULT, gate RESULT, bounded logs/telemetry, immutable slot lifecycle records, and the original full recording tree. All failed or partial roots are preserved.

Selected files:
- broker_layout_v2 / broker_files_v2 / session_plan_v3 / session_ledger_v4
- broker_common_v1 / broker_initialize_v1 / broker_stage_v1 / broker_entry_v1 / broker_gate_v1
- broker_v2 / chooser_v2 / history_v2
- broker_streamed_mirror_v1 / broker_ssh_mirror_v1
All names above begin with field_operator_. The earlier versions remain immutable provenance.

Two-session proposed reservation: 298,296,408 bytes on Pi and 306,685,016 bytes independently on the host; total 604,981,424 bytes. This is 196,608 bytes above the V125 proposal, for three 16KiB supervision receipts and their separate pending copies on both sides. No policy increase has been admitted. Each recording retains 146,919,980 / 151,114,284 bytes, 256 files, 64 directories and a 32MiB member ceiling. Failed/deleted/small recordings give no reuse credit. Outer code stays at 64 files / 2MiB / 128KiB member. Mirror framing stays 16KiB chunks and 256KiB metadata; the new whole-tree census additionally enforces every original recording limit.

The metadata writer locks the existing broker directory with a bounded two-second flock acquisition before any mutation. Shared inspection waits for active publication; a pending file left after lock release still rejects. No mutation is retried. These native semantics are unqualified until exercised on the Pi; this is not a kernel quota or power-loss guarantee.

PowerShell host check, using a NEW output directory:
~~~powershell
$native = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$native\check_field_operator_broker_mirror_v1.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\NEW-approved-check'
~~~

CMD / Anaconda Prompt (the explicit interpreter avoids depending on the activated environment):
~~~bat
set "NATIVE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%NATIVE%\check_field_operator_broker_mirror_v1.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\NEW-approved-check"
~~~

The check registers its CPU14 owner before project imports. It uses synthetic inventory to test the changed whole-tree partition limits; it does not run a native writer or copy media. Do not rerun a passed unchanged check just for a version.

Native invocation shape, only after a fresh policy, exact initial staging, complete host supervision and full-tree exporter/mirror are reviewed and backed:
~~~sh
PY=/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python
"$PY" -B "$ROOT/code/field_operator_broker_gate_v1.py" --root "$ROOT" --policy-sha256 "$POLICY_SHA"
~~~
ROOT must be the newly admitted field-operator-sessions-vN path; POLICY_SHA is the SHA256 of its exact RELEASE.json. The gate creates a shared 200% CPU / Tasks64 / CPU2,3 / 768MiB AS / 1MiB stack systemd unit. Never invoke broker_entry directly to bypass its required gate ACK. Initializer bootstrap and host dispatcher/exporter glue are still required before dispatch; these illustrative arguments are not an authorization or a runnable frozen trial.

Host mirrors must call the new broker framing with independently pinned full membership, verify all actual native owners dead and capture closed, and publish BACKUP only after exact exporter closure. The existing single-root exporter is not compatible. General repeated operation, recovery, offline, nonempty captions, gallery, physical touch and noisy human validation remain open.
