# Read-only inspection of the actual manual-stop production unit

Purpose: give the root coordinator exact metadata before/during/after a normal
production Start, Stop and Discard, without replacing the application's policy
or service-room check. The existing finite Live51 helper still tests basic native
Start/Stop/workspace behavior with its own short policy; it does not prove normal
capacity-controlled recording. This action inspects an independently launched,
activated production unit whose actual systemd RuntimeMaxUSec is infinity and
whose genuine ownership receipt declares manual_stop_storage_guarded.

State: source-only prepared, unexecuted and not host compiled. No package34 PIN
or future owner is invented. This file is an injected native action, not a
standalone CLI: the guarded root dispatcher supplies PAYLOAD and BASELINE after
its early owner/resource registration, and the action returns RESULT.
It does not import runtime/models, recover a database, acquire a conflicting
lease, perform GUI clicks, send Stop, kill a process, save or discard anything.
The coordinator must explicitly admit read-only inspection of this exact active
unit; the usual no-active-project gate cannot be bypassed implicitly.

Inputs: schema `just-peachy.normal-manual-unit-inspection.v1`; actual activated
`package` and `package_manifest_sha256`; current `boot_id` and a fresh finite
`expires_unix` no more than600 seconds ahead; canonical
`data_root=/home/peachyprototype/JustPeachy/data/runtime-v29`; exact production
`unit_ownership` path under data_root/unit-owners/UUID/UNIT_OWNERSHIP.json and its
`unit_ownership_sha256`; `expected_app_owner` with exact pid/start_ticks/boot_id;
`phase` idle/running/stopped/discarded; and for nonidle phases the already
observed `expected_worker_owner`, `launch_id` and `session_id`. Those three
fields are null for idle. Owner/launch IDs come from actual receipts; never
manufacture a future worker/JOB. Package inventory and receipt bytes are
verified before inspection.

Outputs: RESULT contains exact app/worker identities, actual unit envelope,
normal worker policy (manual stop, None backlog, source-capacity-equal finite
drain), and bounded read-only SQLite session/caption/segment/event/artifact/
projection counts plus scalar source/cursor/lag/drop/RAM/VM measurements.
No text, roster, vector or audio content is returned. Discarded phase requires
all selected content rows and its session directory absent; it performs no
deletion itself. SQLite uses mode=ro/query_only,256KiB cache and a3-second VM
deadline; it is never opened immutable while active and no recovery or journal
deletion is attempted. A locked/unavailable snapshot is a failed inspection,
not a successful proof. Each systemd query is bounded to5seconds.

Procedure:

1. Root verifies the final package/stage/focused native check and activates it
   with exact desktop compare-and-swap. Preserve the prior Desktop30 rollback.
2. Launch the actual production desktop/native_scope route. Keep its genuine
   manual unit lifetime and service-room checks. A separate bounded external
   coordinator controls the acceptance window (for example190seconds) and
   retains authority to stop only the exact owned unit if the window expires.
   This external window must never be recorded as the product unit's lifetime.
3. Obtain actual UNIT ownership/app PID/creation tick and seal an idle payload.
   Use this action only through the explicitly authorized read-active dispatcher.
4. Operate actual GUI Start, observe visible capture and lag, obtain exact
   request/worker/session receipts, then seal a running inspection payload.
5. Operate actual GUI Stop. Wait for exact worker closure and the application's
   stopped state, then inspect stopped. Operate actual Discard, return to the
   chooser using the existing callback, and inspect discarded plus actual GUI
   chooser visibility separately. The action does not prove GUI actions by itself.
6. Close the GUI/unit, independently verify exact owner absence/cgroup empty,
   and complete the usual full mirror/readback. If normal production behavior
   fails, restore the approved Desktop30 pointer and repair in a fresh candidate.

PowerShell source preparation/hash review (host-only, no native execution):

```powershell
[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
Get-FileHash -LiteralPath (Join-Path $d 'inspect_normal_manual_unit.py') -Algorithm SHA256
Get-FileHash -LiteralPath (Join-Path $d 'README_NORMAL_MANUAL_INSPECTION.md') -Algorithm SHA256
```

Command Prompt or Anaconda Prompt may invoke that same PowerShell source review:

```bat
powershell -NoProfile -Command "[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384; Get-FileHash -LiteralPath 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/inspect_normal_manual_unit.py' -Algorithm SHA256"
```

Native dispatch is deliberately not provided as an executable unreviewed CLI.
Once the root coordinator seals an actual payload and adds the exact source SHA
and read-active action to its guarded dispatcher, use its documented
`--label FRESH --action inspect_normal_manual_unit.py --payload SEALED.json`
read-only route. Do not use --writes, run this file directly in Anaconda/Python,
reuse a stale admission, or substitute a finite qualification unit.
