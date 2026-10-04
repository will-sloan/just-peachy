# Post-soak baseline snapshot

`post_soak_baseline_action.py` is an injected read-only action for the existing
`host_operations.py` dispatcher. It runs only after the preceding owned job and
its monitor have closed. The normal dispatcher first verifies all current and
historical owners, leases, display, hardware and disk/RAM floors.

Input JSON contains only `expected_boot_id`, copied from the freshly verified
current job. The action verifies that boot against the actual fresh baseline.
Output adds a timestamped, bounded `vcgencmd get_throttled` response and available
temperature/CPU2/CPU3 frequency values to the existing complete baseline result.
Unavailable commands/timeouts are recorded, never converted to zero flags.
This is a post-run snapshot, not continuous clock/throttling measurement. It
changes no firmware, clock, swap, display, capture or model setting.

PowerShell, using the pinned interpreter and a fresh private payload:

```powershell
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$N/host_operations.py" --label post-soak-baseline-UNIQUE --action "$N/post_soak_baseline_action.py" --payload 'G:/PRIVATE/FRESH/PAYLOAD.json'
```

Command Prompt and Anaconda Prompt use the same installed interpreter:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\host_operations.py" --label post-soak-baseline-UNIQUE --action "%N%\post_soak_baseline_action.py" --payload "G:\PRIVATE\FRESH\PAYLOAD.json"
```

The dispatcher pins CPU14, registers its actual owner before project reads and
backs up/readbacks the action and payload before SSH. It supplies the strict
known-host SSH configuration and native CPU3/128MiB/1MiB-stack/read-only envelope.
Do not invoke the action directly, reuse a closed output label, or launch it
alongside an active test. The full result remains private under the fresh
`operation-post-soak-baseline-*` folder. The action itself writes no Pi files.
