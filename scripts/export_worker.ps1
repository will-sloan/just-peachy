[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet("machine_a", "machine_b")][string]$MachineId,
    [Parameter(Mandatory = $true)][ValidateSet("cpu", "cuda")][string]$Device,
    [string]$Destination = ""
)

. (Join-Path $PSScriptRoot "worker_common.ps1")
trap {
    [Console]::Error.WriteLine("[FAIL] Worker export: $($_.Exception.Message)")
    exit 2
}
$context = Get-ProductionWorkerContext -MachineId $MachineId -Device $Device
$arguments = @("-ExecutionPolicy", "Bypass", "-File", $context.ExportScript)
if ($Destination) { $arguments += @("-Destination", $Destination) }
Invoke-ProductionChecked -FilePath "powershell" -Arguments $arguments -WorkingDirectory $context.EvaluationRoot
