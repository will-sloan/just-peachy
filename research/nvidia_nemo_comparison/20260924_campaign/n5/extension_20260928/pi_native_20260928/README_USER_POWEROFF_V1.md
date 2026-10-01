# User-requested clean Pi shutdown V1

Purpose: preserve the three exact current configuration pointers and schedule one clean OS poweroff after the user's explicit October 1 disconnect request. This is not firmware reset, production acceptance, or proof of physical power removal.

Inputs: a fresh private output directory with HOST_SCOPE_V1.json, completed current census/owner/lease review, and the original boot/baseline identities. The inspect phase verifies CM5/2GB/aarch64, storage/RAM floors, idle capture, leases, research units, install/config/display hashes and noninteractive shutdown permission. It creates private exact backup and independent restore copies. Schedule requires those receipts, independent readback and inspection no older than120seconds, rechecks native state, syncs filesystems and requests shutdown -P +1 exactly once. A successful command is acknowledgement; later reachability checks and user-visible halt remain separate evidence. No capture, playback, enrollment, downloads or firmware command.

Outputs: private early host/native identities, bounded raw streams, phase/result receipts and configuration backups. Original sources and older receipts remain immutable. Each phase has native CPU3/128MiBAS/1MiBstack/FSIZE0/30second alarm and host40second deadline. CPU14 is set before host project reads. The containing600second scope and17:42:44Z hard deadline must retain120seconds for closure. Do not reuse this boot-bound script after a reboot or rerun a failed/consumed phase.

PowerShell, from this source directory, replacing G:\PRIVATE\FRESH with the reviewed private output:
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\prepare_user_poweroff_v1.py --phase inspect --output G:\PRIVATE\FRESH
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\prepare_user_poweroff_v1.py --phase schedule --output G:\PRIVATE\FRESH

CMD / Anaconda Prompt, from this source directory:
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prepare_user_poweroff_v1.py --phase inspect --output G:\PRIVATE\FRESH
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prepare_user_poweroff_v1.py --phase schedule --output G:\PRIVATE\FRESH

Review actual inspection, backup and current owner closure before invoking schedule. No missing evidence may be relabelled passed. After reconnection collect the new boot/PIDs and verify saved270degree display and microphone/startup behavior through a fresh bounded lifecycle; older fixed-baseline guards are invalid.

