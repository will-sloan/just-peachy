# Independent artifact review and exact private backup

`review_field_artifact_limits_v1.py --run field-artifact-limits-v1|field-artifact-limits-v2` reads closed native receipts under CPU3/512MiB. It checks exact source hashes, original release membership/hashes, live systemd properties, natural owner closure, baseline identities and free leases. A failed protocol is reported only as failure. On success it independently decodes literal journal records/footer/sequence and reconstructs every deterministic float/PCM sample with Python struct, checks WAV headers and epoch hashes, preserved partial statuses/count gaps and joined workers. It never imports the tested implementation, captures, plays audio, runs models or retries the protocol.

`backup_field_artifact_limits_v1.py --run ...` verifies closed identities, inventories every file, transfers one bounded tar stream and validates every byte/hash into a new private target directory. Target32MiB/combined64MiB and all prior evidence remain counted. Outputs are exclusive REVIEW.json/BACKUP.json and the exact private target tree. Reader source SHA is included in review. Neither success nor physical handle closure clears a write error or qualifies installed/live/endurance behavior.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_artifact_limits_v1.py --run field-artifact-limits-v2
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_artifact_limits_v1.py --run field-artifact-limits-v2
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_artifact_limits_v1.py --run field-artifact-limits-v2
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_artifact_limits_v1.py --run field-artifact-limits-v2
```

For the preserved early failure select `field-artifact-limits-v1`. Existing output paths deliberately reject repeated publication. Both host tools set CPU14 before reads. No private synthetic artifacts, transcripts, audio, model weights or profiles belong in Git.
