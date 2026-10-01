# Native local journal qualification V2

Purpose: qualify the prepared Journal V2 metadata primitive on the CM5. This does not activate a release, start an application, capture audio, or implement local automatic recovery.

field_local_journal_check_v1.py runs exactly one of create/reopen/fault/fenced in a fresh native process. The first two publish real current OWNER and METADATA_WORK_FINISHED intent records. EXIT is an intent while the process is alive; the coordinator separately checks actual process death before proceeding. The third injects a three-byte metadata write followed by an OSError. It preserves the pending file and checks the instance latch through a read-only inspect call. The fourth independently attempts read-only reopen and requires rejection with the same pending bytes. No failed mutation is retried.

field_local_journal_native_v1.py is an admission-bound staging/coordinator/export program supplied with a REQUEST global by the host dispatcher. It verifies baseline pins, actual CM5/2GB/32GB identities, capture off, both leases, earlier process death, target-inclusive allocation, installed source pins and actual systemd bounds. It creates a unique root, stages exact source bytes and manifest, then invokes the four phases. It exports all metadata/code files in at most16KiB chunks and includes empty directories. The host must verify the complete membership/digests and exact coordinator/child death before declaring backup complete. There is no standalone permissive SSH command.

Inputs: fresh qualification operation ending within600seconds and before2026-10-01T17:42:44Z, exact release policy and source manifest, measured allowance including the full proposed recording/local-mirror/host reservation, physical pins, prior closed identities, unique unit/root. Outputs: early owners, actual systemd properties, phase events, injected failure evidence, complete tree export, explicit scoped result. stdout/host-phase cap262144bytes; native tree export cap262144bytes/64entries and code input131072bytes. Production idle lifetime is not admitted. No recording CLOSED/BACKUP/ACTIVATION fact is fabricated.

Selected sources: field_local_journal_check_v1.py, field_local_journal_native_v2.py and dispatch_field_local_journal_v1.py. V1 native coordinator remains an unexecuted draft; V2 additionally records actual systemd values before assertions. The dispatcher contains a bounded read-only closure utility that verifies exact child/coordinator death, inactive unit/MainPID0, capture off, free leases and baseline pins. That utility and its closure verifier must also be closed before BACKUP.

PowerShell (from this source directory):
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\dispatch_field_local_journal_v1.py --preparation G:\PATH\PREPARATION --census G:\PATH\HOST_CENSUS.json --resources G:\PATH\NATIVE_RESOURCES.json --closure G:\PATH\NATIVE_CLOSURE.json --extra G:\PATH\EXTRA_OWNER_CLOSURE.json --output G:\PATH\FRESH-ADMISSION

Command Prompt or Anaconda Prompt (from this source directory):
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_local_journal_v1.py --preparation G:\PATH\PREPARATION --census G:\PATH\HOST_CENSUS.json --resources G:\PATH\NATIVE_RESOURCES.json --closure G:\PATH\NATIVE_CLOSURE.json --extra G:\PATH\EXTRA_OWNER_CLOSURE.json --output G:\PATH\FRESH-ADMISSION

This dispatcher binds field-local-release-v1 and jp-local-journal-v1. Once used it is historical and cannot be rerun. The recording broker root field-operator-sessions-v7 is reserved in the policy but is not created or authorized for a later app attempt. All native modules are API-only. No production launcher command exists yet.

For syntax-only inspection from PowerShell:
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); import ast,pathlib; [ast.parse(pathlib.Path(n).read_text()) for n in ('field_local_journal_check_v1.py','field_local_journal_native_v1.py')]"

Command Prompt or Anaconda Prompt (from this source directory):
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import ast,pathlib; [ast.parse(pathlib.Path(n).read_text()) for n in ('field_local_journal_check_v1.py','field_local_journal_native_v1.py')]"

Syntax checks do not execute the modules or establish native behavior. Host coordinators must set CPU14 before project reads and register their exact identity. Current source is PREPARED until an actual native result and full verified backup are recorded. Local full recording backup, production supervisor, activation/rollback, network isolation, physical touch, nonempty captions and noisy human validation remain separate open requirements.
