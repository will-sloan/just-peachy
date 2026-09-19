# Windows atomic-write recovery checks

Purpose: reproduce transient and persistent destination locks using fault injection around the actual S6C JSON writer. Checks bounded retries, eventual full-file replacement, preservation of the previous durable artifact on persistent failure, retained temporary data, immediate failure of other OS errors and worker startup placement inside its failure handler.

Inputs: current live S6C common/execution sources; no model/audio inputs. Outputs: eight check results and preserved fixture files under reports/S6C/20260910T123540Z/io_recovery_checks/v1. This named test directory must be new; do not overwrite its evidence.

PowerShell from repository root:

```powershell
& '.\.edge-speech-env\python.exe' '.\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_io_recovery_checks.py'
```

Anaconda Prompt / CMD:

```bat
".edge-speech-env\python.exe" "XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_io_recovery_checks.py"
```

No Windows security service or unrelated process is stopped. Real filesystem results still remain strict and separately validated in native runs.
