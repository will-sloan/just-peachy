# One-shortcut activation and exact rollback

Current injected consolidation uses [README_DESKTOP_CONSOLIDATION_V2.md](README_DESKTOP_CONSOLIDATION_V2.md) and `desktop_consolidation_action_v2.py`, which establish exact manifest-pinned metadata imports. The original transaction and all11 original shortcut/startup pins are preserved.

This workflow uses existing `prepare_package.py`, `install_candidate.py`,
`host_operations_v4.py`, native job-monitor and release-authorization interfaces.
`desktop_activation_action.py` supplies the guarded activation entry and complete
closed host readback; `launch_production_idle_action.py` checks the exact activated
desktop command through unchanged native_scope and actual Tk Exit. Their inputs,
commands and limits are in README_GUARDED_ACTIVATION.md.
`desktop_rollback_action.py` adds the explicit inverse for one launcher. Nothing
in this document activates, launches, rotates or contacts a device by itself.
Existing user authorization applies; each native mutation still needs fresh
machine-state admission and exact reviewed inputs, not a repeated permission.

## Concrete activation sequence

1. Finish the exact candidate's raw, selected full-pipeline, storage and GUI
   checks. Preserve failures. Correctness of one source-only trial does not
   imply sustained throughput, GUI quality or acceptance of every profile.
2. Verify the selected release/user-data full backup independently, including
   the exact retained v27/v28 package/desktop files and user recordings. Pin its
   manifest, completion/closure and bytes in production acceptance. Do not
   replace this with a benchmark-output mirror or silently broaden its scope.
3. Prepare a fresh production package with the complete accepted selections,
   policy ceilings, asset pins and expected existing desktop SHA256 using
   `README_RELEASE_AUTHORIZATION.md`. Stage at a fresh build root with
   `install_candidate.stage_archive`; never overwrite v27/v28 or a prior build.
4. Under a fresh full process/lease/free-space baseline with all prior source,
   worker and cgroup owners closed, dispatch `desktop_activation_action.py`
   through `host_operations_v4.py --writes` using README_GUARDED_ACTIVATION.md.
   It preserves the fresh in-memory inspector baseline twice, validates exact
   import origins and calls this unchanged installer function:

   `install_candidate.activate(target, manifest_sha256, desktop, previous_sha256, baseline_path, baseline_sha256)`.

   All values come from the exact staged package and current baseline.
   `desktop` is the one existing file in `/home/peachyprototype/Desktop`; do not
   guess its filename or make another shortcut. Qualification admission cannot
   satisfy the installer's production gate.
5. Read back `DESKTOP_ACTIVATED_NOT_STARTED`, the exact current desktop bytes,
   and both independent `.backup`/`.restore` files in the returned unique
   `field-runtime-v29-desktop-backup-<uuid>` directory. Retain `ACTIVATION_PLAN.json`.
   This replaces only the selected shortcut. It does not launch or install an
   autostart entry, change desktop rotation, or modify retained release/data.
6. Complete `README_DESKTOP_CONSOLIDATION.md` after the selected activation.
   The actual retained desktop has11owned shortcuts. The separately guarded
   action requires all11exact originals in the accepted full backup, makes
   independent native before/restore copies, keeps the activated unified
   launcher and archives only the other ten outside Desktop. Its explicit
   all11restore replaces the one-file rollback for this consolidated state.
   Verify final membership/hash and copy its complete archive independently;
   replacing the selected file alone is not one-shortcut completion.
7. Verify desktop-first boot behavior separately; the installer makes no boot
   setting change. The existing270-degree desktop must remain. Launching the
   single shortcut opens the unified selector with microphone off. Exit to
   desktop waits for Stop/drain/exact source-worker closure. Native
   `native_gui_driver.py` records actual fullscreen480×800+0+0, scroll-visible
   controls, Start/Stop, Save/Discard and full History Replay when selected.
   Programmatic checks are not physical-touch or visual-quality evidence.

## Exact rollback action

`desktop_rollback_action.py` is injected by `host_operations_v4.py`; do not run it
as an unguarded native command. Its JSON payload contains:

```json
{
  "boot_id": "<fresh native baseline boot ID>",
  "expires_unix": "<numeric fresh Unix deadline, at most 600 seconds away>",
  "package": "/exact/staged/field-runtime-v29-build-NN",
  "package_manifest_sha256": "<exact current manifest SHA256>",
  "desktop": "/home/peachyprototype/Desktop/<existing-one-shortcut>.desktop",
  "backup": "/exact/campaign/field-runtime-v29-desktop-backup-<activation UUID>",
  "expected_current_sha256": "<ACTIVATION_PLAN next_sha256>"
}
```

The action refuses active project owners, verifies the candidate inventory and
installer source, verifies both previous-launcher copies agree, checks the
activation plan and current launcher hash, then atomically restores that one
file and fsyncs/readbacks it. It preserves all releases and user recordings.
It writes `ROLLBACK_RESULT.json` to the activation backup and starts no process.
A later edited shortcut or mismatched backup fails rather than being replaced.
The action requires a fresh current-boot payload, retains the 5 GiB free-space
floor, and refuses to overwrite an existing rollback receipt. Replace the
illustrative `expires_unix` string with an actual JSON number before admission.
Restoring other files from the full backup is a separate explicitly reviewed
recovery; this action cannot erase or downgrade stored audio.

## PowerShell / Command Prompt / Anaconda

Use the qualified interpreter and early CPU14 owner wrapper shown in
`README_QUALIFICATION_DISPATCH.md`, then call `host_operations_v4.py` with the exact
reviewed payload. The host wrapper must register before reading project code.
The action argument is `desktop_rollback_action.py`; activation continues to use
the existing inspector's `install_candidate.activate` interface above.

PowerShell command **inside that registered wrapper**:

```text
host_operations_v4.py --label desktop-rollback-NN --action desktop_rollback_action.py --payload G:/PRIVATE/REVIEWED_ROLLBACK_PAYLOAD.json --writes
```

Command Prompt and Anaconda Prompt use the identical arguments and the pinned
`C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe`.
Use actual receipt paths/hashes instead of placeholders. Inputs are private
reviewed JSON and current baseline; outputs are host-operation receipts, exact
desktop readback, unchanged retained backups, and the native rollback result.
No new package installation or model execution is needed.

For host-only validation, use the same CPU14 early-owner test wrapper documented
in `README_NATIVE_GUI_DRIVER.md`, replacing `test_native_gui_driver` with
`test_desktop_rollback` in its PowerShell or Command Prompt/Anaconda command.
The test operates on synthetic byte strings and owned temporary fixture files,
checking mismatched copies, edited launcher bytes, incorrect paths/pins,
oversized reads and shared-hardlink refusal. It
does not access a desktop or perform a native rollback.
