# Final S6C storage and RAM snapshot

Purpose: one metadata-only directory walk of the S6C report, staging and G: payload
namespaces, with logical bytes by extension, start/end free disk and RAM, and
Windows-reported physical-disk health. No audio/models/vectors are read. H2 is
untouched. Reparse points and filesystem errors remain explicit and prevent a
complete-cap claim. Report writers can change files during this non-atomic scan.

Inputs: the three fixed20260910T123540Z namespaces, psutil and Get-PhysicalDisk.
Output: reports/S6C/20260910T123540Z/storage/FINAL_RESOURCE_SNAPSHOT_V1.json.
Existing output rejects. The120GiB namespace cap, C:50GiB/G:75GiB disk reserves
and12GiB RAM reserve are unchanged. This snapshot is not a drive stress test.

PowerShell:

~~~powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& "$s6cRepo\.edge-speech-env\python.exe" -B "$s6cSim\scripts\s6c_final_resource_snapshot_v1.py"
~~~

Anaconda Prompt / CMD:

~~~bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%S6C_REPO%\.edge-speech-env\python.exe" -B "%S6C_SIM%\scripts\s6c_final_resource_snapshot_v1.py"
~~~

Run once during final reporting, not periodically during native timing. Inspect
the actual errors, guard results and observation interval before interpreting.

