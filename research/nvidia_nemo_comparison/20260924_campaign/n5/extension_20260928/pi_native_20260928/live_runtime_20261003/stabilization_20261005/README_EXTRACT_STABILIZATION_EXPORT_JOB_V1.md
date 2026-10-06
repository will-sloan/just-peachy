# Actual selected-export JOB extraction

Purpose: persist the real recording-export-10 JOB from the successful build25
native wrapper result for the existing closed-output monitor. A launch is not an
export or offload pass. The source derives the bounded read/write/CPU14 ownership
pattern from extract_stabilization_job_v5.py; it validates the exact export JOB
schema, unchanged backed exporter source, actual closed preparation, current boot,
package pin, session UUID and full independent 256MiB native/PC allocation.

Input: actual operation-stabilization-recording-export10-launch/dispatch/RESULT.json.
Outputs: fresh private source/action-input backups and independent restores, full
original wrapper result, JOB copies, and recording-export-10-JOB.json. Existing
files are never overwritten. Scope is 1MiB/600s with host storage floors. All reads
follow early CPU14 PID/create-time/FILETIME registration. No SSH, recording,
model, desktop change or native operation is performed. The caller records exact
host-owner absence after natural exit; then the existing complete unit monitor
copies and verifies actual export output before any offload claim.

PowerShell:
```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
& $py -B "$s/extract_stabilization_export_job_v1.py" --result "$q/operation-stabilization-recording-export10-launch/dispatch/RESULT.json" --label recording-export-10
```
CMD and Anaconda Prompt: set JP_SOURCE and JP_PRIVATE to the same directories.
```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/extract_stabilization_export_job_v1.py" --result "%JP_PRIVATE%/operation-stabilization-recording-export10-launch/dispatch/RESULT.json" --label recording-export-10
```
Only this actual selected export is accepted; later operations need fresh exact
bindings. Neither launch nor the original wrapper's closure proves the export
worker has closed or its ZIP has been independently read back.
