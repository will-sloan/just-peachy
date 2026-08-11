[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet("merge", "analyze")][string]$Action,
    [Parameter(Mandatory = $true)][ValidateSet("cpu", "cuda")][string]$Device,
    [string]$MachineATransfer = "",
    [string]$MachineBTransfer = "",
    [string]$PrerequisiteEvidence = ""
)

. (Join-Path $PSScriptRoot "worker_common.ps1")
trap {
    [Console]::Error.WriteLine("[FAIL] Coordinator: $($_.Exception.Message)")
    exit 2
}
$context = Get-ProductionWorkerContext -MachineId "machine_a" -Device $Device
if ($Action -eq "merge") {
    $arguments = @("-ExecutionPolicy", "Bypass", "-File", $context.MergeScript)
    if ($MachineATransfer) { $arguments += @("-MachineATransfer", $MachineATransfer) }
    if ($MachineBTransfer) { $arguments += @("-MachineBTransfer", $MachineBTransfer) }
} else {
    $arguments = @("-ExecutionPolicy", "Bypass", "-File", $context.AnalyzeScript)
    if ($PrerequisiteEvidence) { $arguments += @("-PrerequisiteEvidence", $PrerequisiteEvidence) }
}
Invoke-ProductionChecked -FilePath "powershell" -Arguments $arguments -WorkingDirectory $context.EvaluationRoot
