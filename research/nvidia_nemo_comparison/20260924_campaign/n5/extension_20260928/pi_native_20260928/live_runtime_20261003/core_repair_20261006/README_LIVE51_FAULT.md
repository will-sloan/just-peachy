# Exact Live51 source failure inspection

Purpose: read the actual closed source and host metadata after Live51 reproduced
AEC_MIC_ARRAY_TYPE255. This helper does not reset firmware, open capture, retry
the failed session or alter evidence. Inputs are the fixed actual session/launch
IDs and the guarded current-boot BASELINE. Output is bounded metadata, hashes and
identities in the dispatch RESULT. No audio, captions or gallery data is read.

Back up this source and README plus independent restore before use. Through the
existing guarded dispatcher, with a fresh label and an empty JSON payload:

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$d/host_core_operations_v11.py" --stage34-admission "$d/CORE_STAGE34_ROOT_ADMISSION.json" --stage34-admission-sha256 '3808827ccba4d7560e8d9f1a3e655caf542dd440c848c309b8df3d69fb6d93f6' --label core-live51-fault-inspect-01 --action "$d/inspect_live51_fault.py" --payload 'REPLACE_WITH_BACKED_EMPTY_PAYLOAD.json'
```

Command Prompt and Anaconda Prompt: run `pwsh -NoProfile`, then the same block.
Use the pinned interpreter without installing dependencies. Preserve natural
exit, exact utility/host closure and all raw errors. This inspection alone does
not prove recovery or a functioning microphone.
