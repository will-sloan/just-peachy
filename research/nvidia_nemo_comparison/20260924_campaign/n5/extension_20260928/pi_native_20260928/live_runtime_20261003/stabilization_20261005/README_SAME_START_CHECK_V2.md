# Focused same-Start readiness check V2

Purpose/inputs/outputs and the original 2MiB/600-second CPU14/FILETIME scope,
PowerShell/CMD/Anaconda setup and synthetic-execution limits are described in
`README_SAME_START_CHECK.md`. V2 is the selected checker.

The first checker failed before its first group because its synthetic closure
omitted `result.source_facts`, required by the final strict runtime predicate.
Its exact source/independent restores and failure traceback remain preserved;
the runtime did not fail and no native action occurred. V2 additionally reads
the full hash-matching actual `worker/RESULT.json` from the same inspection,
selects the identical source owner and uses its unchanged source facts in the
in-memory closures. It does not invent a physical-process-closed flag. Exact
independent owner probes remain synthetic HOST callbacks.

V2 also verifies that a later explicit user Start clears a previous Stop's
transient cancellation only after the owned helper has joined. The eight
groups and six unit rejects remain focused on the changed Start/lifetime
behavior; no duplicate suite or model/native test is added.

## PowerShell

```powershell
$S='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$S/check_same_start_readiness_v2.py" --failure-inspection "$Q/operation-first-start-diagnostics-02/dispatch/RESULT.json" --source-owner-pid 1421 --source-owner-ticks 2715 --source-boot-id 31ead85c-17cf-49c3-909a-8f2e1108a151
```

## CMD and Anaconda Prompt

```bat
set "S=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005"
set "Q=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/check_same_start_readiness_v2.py" --failure-inspection "%Q%/operation-first-start-diagnostics-02/dispatch/RESULT.json" --source-owner-pid 1421 --source-owner-ticks 2715 --source-boot-id 31ead85c-17cf-49c3-909a-8f2e1108a151
```

Only the HOST coordinator is an actual process. Helpers/workers/units/owners,
authorization, control files and completion are synthetic/in memory. A pass
does not qualify Pi source audio, firmware recovery or real-world accuracy.

