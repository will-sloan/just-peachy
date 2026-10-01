# Native local recording backup preparation V1

Purpose: copy a fully closed broker tree to an independent local Pi destination, preserving every file and empty directory and reading all copied bytes back twice. This is an API preparation, not a deployed local manager or accepted offline launcher.

Inputs: canonical existing broker source, fresh disjoint destination below the campaign, exact source policy SHA256, exact owned source service name, complete independently pinned file manifest, fresh LOCAL_RELEASE_QUALIFICATION operation (at most600seconds including cleanup/backup), monotonic deadline, and the full original broker target allocation. A separately reviewed enclosing admission must include this entire local copy and complete host backup in target/output/payload totals. Historical source policy grants no new work authority.

Output: unpublished COMPLETE_LOCAL_COPY_READBACK receipt with files, directories, exact owners, unit observations, actual chunk count and allocation. No BACKUP journal record is automatically published. The caller must verify and bind this receipt before allowing another recording. Any copy failure leaves the complete or partial destination consumed; no delete, overwrite, retry or failure clearing exists.

The worker checks actual recorded owner death, source capsule and CLOSED pins, controller/model/archive closure, gate success, current unit inactive/dead, capture off, research and hardware leases, and5GiB free floor. It holds source shared directory lock and both existing hardware/research leases while copying. Per-recording256files/64directories/146919980bytes, whole broker bounds,32MiB member,16KiB chunks and256KiB receipt remain. File fsync, directory fsync, source stability checks and independent full destination readback precede the returned receipt. The old read-only health public entry retains FSIZE0; this new API separately enforces nativeCPU3/128MiB AS/1MiB stack/32MiB FSIZE.

## How to inspect from Windows

Open the source directory in PowerShell:
    Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); import ast,pathlib; ast.parse(pathlib.Path('field_local_broker_backup_v1.py').read_text())"

Command Prompt or Anaconda Prompt:
    cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import ast,pathlib; ast.parse(pathlib.Path('field_local_broker_backup_v1.py').read_text())"

## Native integration

There is no approved bare SSH execution command. A bounded native supervisor must register its exact owner before project reads, validate a fresh measured allowance, capture actual systemd properties, bind source_unit to the historical dispatch receipt, stage a verified code capsule, and call:
    copy_closed(source, destination, policy_sha256, source_unit, pinned_files,
                operation=operation, deadline=deadline, maximum_bytes=full_broker_target)

This module does not construct models, source, GUI, Journal, Store or Controller. It does not certify the caller's supplied service-name binding or resource admission. Native copy/failure qualification, failed-source preservation backup, Journal3 consumer, production admission, activation/rollback, local automatic recovery and offline rehearsal remain open. No physical disk-full, power-loss, arbitrary concurrent writer or kernel quota claim follows from this source.
