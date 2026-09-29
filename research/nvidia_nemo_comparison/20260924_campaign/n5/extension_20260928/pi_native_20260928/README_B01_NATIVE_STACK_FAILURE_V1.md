# B01 native-stack failure review

Purpose: independently inspect the already closed `b01-native-stack-v2` trial. It does not run models, repair a failed process, or qualify passage. It verifies admission/source hashes, boot/PID/start identity, systemd SIGABRT state, missing finalization, observed captions, zero probability output and sampled memory. The terminal 2 MiB native allocation failure is preserved alongside earlier journal failures. Read sampled memory as observations, not the exact instant of failure.

Inputs: existing private launch receipts plus Pi run `~/JustPeachy/research/nemotron-20260928/b01-native-stack-v2`. Strict SSH configuration is inherited from `dispatch_geometry_v2.py`; no credentials are printed. Outputs: new private `FAILURE_AUDIT_INPUTS.json` and `REVIEW.json`, with a matching stage review receipt on the Pi. Existing receipts are never overwritten. A failure review is not acceptance or clean application finalization.

PowerShell, from the campaign worktree:

```powershell
$p = 'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' "$p/review_b01_native_stack_failure_v1.py"
```

CMD or Anaconda Prompt, from the campaign worktree:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_b01_native_stack_failure_v1.py
```

No activation, installation, microphone access, playback, download, accuracy scoring or cap increase occurs. The reader uses host CPU14 and remote CPU3; all numerical workers must already be closed. To review a new run, create a fresh version with its exact identities; do not modify this reader after binding its evidence.
