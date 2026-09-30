# Independent installed artifact review and private backup

Purpose: review existing field-artifact-install-v1/v2 evidence without importing the tested implementation or rerunning installed execution. The V1 branch verifies the UTF-8 controller import failure, seven early config negatives, partial health and released outer lease, and reports failure only. V2 requires real controller/native-factory/archive effective bounds, zero models/capture/GUI, constructor-before-archive binding, eight rejections, closed worker/borrower/outer lease, exact config/baseline/old-release hashes and code package inventory. It parses actual installed UTF-8 bytes, rather than decoded source strings. Owner PID/start/boot and live units/leases/capture are independently checked. Repaired hashes must equal the immutable V1 intended UTF-8 hashes.

Inputs: `--run field-artifact-install-v1` or `--run field-artifact-install-v2`, existing admission/result/code/config/resource/owner receipts and current Pi identity. Outputs: exclusive private REVIEW.json, then exact target backup/tar/file-hash verification and BACKUP.json. Review is CPU14 on host/CPU3 with512MiB AS on Pi. Backup counts all failure files and enforces16MiB target/32MiB combined admission. No audio playback, waveform copy beyond any existing target backup, models, source, GUI, baseline mutation or retry occurs. Private data stays outside Git. A V1 failure never becomes a whole pass because later repaired code succeeds.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_artifact_install_v1.py --run field-artifact-install-v2
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_artifact_install_v1.py --run field-artifact-install-v2
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_artifact_install_v1.py --run field-artifact-install-v2
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_artifact_install_v1.py --run field-artifact-install-v2
```

Use v1 only for an unreviewed retained failure; completed reviews/backups are exclusive and must not be rerun. The V1 run README's missing `--run` examples are corrected here separately.
