[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet("machine_a", "machine_b")][string]$MachineId,
    [Parameter(Mandatory = $true)][ValidateSet("cpu", "cuda")][string]$Device,
    [switch]$PreflightOnly,
    [switch]$ResumeStopped
)

. (Join-Path $PSScriptRoot "worker_common.ps1")
trap {
    [Console]::Error.WriteLine("[FAIL] Worker launch: $($_.Exception.Message)")
    exit 2
}
$context = Get-ProductionWorkerContext -MachineId $MachineId -Device $Device
$arguments = @("-ExecutionPolicy", "Bypass", "-File", $context.LaunchScript)
if ($PreflightOnly) { $arguments += "-PreflightOnly" }
if ($ResumeStopped) { $arguments += "-ResumeStopped" }
Invoke-ProductionChecked -FilePath "powershell" -Arguments $arguments -WorkingDirectory $context.EvaluationRoot
