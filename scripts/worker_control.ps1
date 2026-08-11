[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet("status", "stop", "resume")][string]$Action,
    [Parameter(Mandatory = $true)][ValidateSet("machine_a", "machine_b")][string]$MachineId,
    [Parameter(Mandatory = $true)][ValidateSet("cpu", "cuda")][string]$Device,
    [string]$Reason = "operator requested controlled stop"
)

. (Join-Path $PSScriptRoot "worker_common.ps1")
trap {
    [Console]::Error.WriteLine("[FAIL] Worker control: $($_.Exception.Message)")
    exit 2
}
$context = Get-ProductionWorkerContext -MachineId $MachineId -Device $Device
if ($Action -eq "resume") {
    Invoke-ProductionChecked -FilePath "powershell" -Arguments @(
        "-ExecutionPolicy", "Bypass", "-File",
        (Join-Path $context.RepositoryRoot "scripts\launch_worker.ps1"),
        "-MachineId", $MachineId, "-Device", $Device, "-ResumeStopped"
    ) -WorkingDirectory $context.RepositoryRoot
    return
}
$arguments = @(
    "run_evaluation.py", "campaign", $Action,
    "--campaign-root", $context.CampaignRoot
)
if ($Action -eq "status") { $arguments += @("--assignment", $context.Assignment) }
if ($Action -eq "stop") { $arguments += @("--reason", $Reason) }
Invoke-ProductionChecked -FilePath $context.Python -Arguments $arguments -WorkingDirectory $context.EvaluationRoot
