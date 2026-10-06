# Exact speech19 database and session restoration

Purpose: independently restore and read back the closed production-backup-09
scope before the changed runtime uses the existing history database. It copies
46 files (47,256,339 bytes) and eight directories. The scope contains the shared
database and the failed speech19 session; it is not a fresh backup of all user
data. The original failed session and backup are preserved.

Inputs: exact private production-backup-09-reconcile-01 manifest, completion,
job, closure and payload pins. No arguments, database connection, content
display, SSH, microphone or native action. Outputs: a fresh CPU14-owned private
directory with source backup/independent restore, complete independently copied
payload and compact result. Maximum 128 MiB including directory reserves and
600 seconds; C50GiB/G75GiB floors remain enforced. Every file is streamed in
64KiB chunks, fsynced and separately read back. Source identity/membership is
checked before and after; incomplete output is preserved on failure.

PowerShell:
```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
& $py -B "$s/verify_speech19_backup_restore_v2.py"
```

CMD or Anaconda Prompt:
```cmd
set JP_SOURCE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/verify_speech19_backup_restore_v2.py"
```

The caller retains natural return status and independently checks the exact
registered host PID/start time after exit. This host result does not upgrade the
failed speech recording to success or authorize a native mutation.

V2 compares stable device/inode/size/mtime/ctime identity, allowing Windows access time to change during reads. V1 failed before payload copying and remains preserved. V2 uses the complete typed host owner schema; no old receipts are modified.
