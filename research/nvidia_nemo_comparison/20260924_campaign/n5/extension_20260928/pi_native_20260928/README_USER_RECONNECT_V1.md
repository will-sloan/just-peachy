# Read-only user reconnect inspection V1

Purpose: after the user explicitly reports reconnection, collect a fresh boot,
current project PID/start-tick identities, saved install/live/display config hashes,
actual wlr-randr output, sound-card/capture status, free leases, RAM/disk and research
unit state. This does not start an app, capture audio, change configuration, reset
firmware, or establish physical touch, unplugged operation or field readiness.
The old fixed baseline identities are not assumed to survive reboot.

Input: a NEW private output directory containing HOST_SCOPE_V1.json with fresh
aware started_utc/expires_utc (<=600-second preparation window), hard_deadline and
user_reported_reconnection=true. This flag records the actual user message and
must not be invented by an unattended reachability loop. Source backup plus an
independent restore-copy readback and fresh complete host ownership precheck
must precede execution. All previous attempts are preserved; no retry of a
consumed output.

Host CPU14 and native CPU3,128MiB hard/soft AS,1MiB stack,FSIZE0,30-second alarm
are applied. Existing strict SSH identity and host-key options are reused.
Native early owner is printed before project reads and retained even when later
guards fail. The bounded host helper saves raw stdout/stderr and I/O status;
after natural exit a separate bounded PID-absence check is retained in full.
No native payload files are written. Source/project process command lines stay
private and must not be published to Git. No current-baseline certification is
issued automatically from arbitrary matched processes.

Outputs: actual host and native owner, INSPECT_STDOUT/STDERR/PHASE, full closure
stdout/stderr/phase, and RESULT on success. Config hash drift is reported, not
silently repaired. Actual display output must be reviewed for270 before a later
native admission. Microphone presence/closed status is not an audio test.

PowerShell (replace the output with your admitted fresh private directory):

```powershell
$P = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$P\inspect_user_reconnect_v1.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\user-reconnect-20261001-v2'
```

Command Prompt and Anaconda Prompt (same explicit existing interpreter):

```bat
set "P=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%P%\inspect_user_reconnect_v1.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\user-reconnect-20261001-v2"
```
