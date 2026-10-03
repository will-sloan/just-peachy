# Desktop startup and Exit

The current runtime is **field-runtime-v28**. The Pi is left at the desktop with
capture off. Login autostart is disabled, including the baseline startup copy
used by this release's rollback. Choose any of the ten current desktop profile
shortcuts to open the app idle; recording still requires New and Start.

To leave the application, press **Exit to desktop** at the bottom of the main
profile manager. From a recording screen, Stop, Save if wanted, Return to modes,
and close the recording broker first. Wait for the local backup to finish; Exit
refuses to close an active recording. Then select another shortcut as needed.

Exit and one actual shortcut reopening were verified on the Pi. The final state
is no manager process, capture closed and hardware/research leases free. All ten
shortcut targets were checked. No recording, model test or reboot was performed
for this edit. The disabled login entry was read back from disk; physical reboot
validation remains separate.

The former v27 session had been interrupted by a reboot. Its entire manager tree
and completed recording were copied and verified without fabricating an EXIT or
editing its journal. Eleven old desktop icons were backed up and preserved under
the v28 profiles directory. The desktop now has ten v28 profiles plus rollback.

The same mounted BMI270 and audio/model capsule is retained. Read MODE_GUIDE and
MOTION_GUIDE for backend choices and motion limitations. Four recording slots and
fourteen manager/helper launch slots remain after this UI check; existing 120s
microphone/Chunk52,30s saved Streaming and24h idle limits remain unchanged.

The older `renew_motion_runtime.py` wrapper predates desktop-first startup and
expects a Close label. Do not use it unchanged for v28. The desktop-aware installer
and previous-batch binder are in `desktop_exit_20261003`; its README documents the
executed one-time deployment. A future batch renewal must preserve the disabled
autostart and Exit button and use fresh version/owner/resource bindings. Never
replay the consumed v28 deployment commands or overwrite a closed runtime.

DESKTOP_RELEASE_INDEX.json identifies the current deployment and receipts.
DESKTOP_HANDOFF_RECEIPT.json identifies the refreshed small ChatGPT archive.
Older motion/model evidence and all previous archives remain preserved.
