# Native local journal qualification V1

Purpose: qualify the prepared Journal V2 metadata primitive on the CM5. This does not activate a release, start an application, capture audio, or implement local automatic recovery.

field_local_journal_check_v1.py runs exactly one of create/reopen/fault/fenced in a fresh native process. The first two publish real current OWNER and METADATA_WORK_FINISHED intent records. EXIT is an intent while the process is alive; the coordinator separately checks actual process death before proceeding. The third injects a three-byte metadata write followed by an OSError. It preserves the pending file and checks the instance latch through a read-only inspect call. The fourth independently attempts read-only reopen and requires rejection with the same pending bytes. No failed mutation is retried.

field_local_journal_native_v1.py is an admission-bound staging/coordinator/export program supplied with a REQUEST global by the host dispatcher. It verifies baseline pins, actual CM5/2GB/32GB identities, capture off, both leases, earlier process death, target-inclusive allocation, installed source pins and actual systemd bounds. It creates a unique root, stages exact source bytes and manifest, then invokes the four phases. It exports all metadata/code files in at most16KiB chunks and includes empty directories. The host must verify the complete membership/digests and exact coordinator/child death before declaring backup complete. There is no standalone permissive SSH command.

Inputs: fresh qualification operation ending within600seconds and before2026-10-01T17:42:44Z, exact release policy and source manifest, measured allowance including the full proposed recording/local-mirror/host reservation, physical pins, prior closed identities, unique unit/root. Outputs: early owners, actual systemd properties, phase events, injected failure evidence, complete tree export, explicit scoped result. stdout/host-phase cap262144bytes; native tree export cap262144bytes/64entries and code input131072bytes. Production idle lifetime is not admitted. No recording CLOSED/BACKUP/ACTIVATION fact is fabricated.

PowerShell, Command Prompt and Anaconda Prompt: use the reviewed host dispatcher documented in the next version of this README after its source/backup closes. These native modules are API-only and must not be invoked directly from a Windows prompt. The future command takes a fresh --output directory, --census, --resources, --closure and --extra receipts. Existing closed roots must never be reused.

For syntax-only inspection from PowerShell:
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import ast,pathlib; [ast.parse(pathlib.Path(n).read_text()) for n in ('field_local_journal_check_v1.py','field_local_journal_native_v1.py')]"

Command Prompt or Anaconda Prompt (from this source directory):
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import ast,pathlib; [ast.parse(pathlib.Path(n).read_text()) for n in ('field_local_journal_check_v1.py','field_local_journal_native_v1.py')]"

Syntax checks do not execute the modules or establish native behavior. Host coordinators must set CPU14 before project reads and register their exact identity. Current source is PREPARED until an actual native result and full verified backup are recorded. Local full recording backup, production supervisor, activation/rollback, network isolation, physical touch, nonempty captions and noisy human validation remain separate open requirements.
