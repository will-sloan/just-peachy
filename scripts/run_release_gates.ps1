[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet("cpu", "cuda")][string]$Device,
    [ValidateSet("canary", "small", "standard", "all")][string]$Through = "all"
)

. (Join-Path $PSScriptRoot "worker_common.ps1")
trap {
    [Console]::Error.WriteLine("[FAIL] Release gates: $($_.Exception.Message)")
    exit 2
}
$context = Get-ProductionWorkerContext -MachineId "machine_a" -Device $Device
Invoke-ProductionChecked -FilePath $context.Python -Arguments @(
    "scripts\production_release.py", "run-gates", "--device", $Device,
    "--through", $Through
) -WorkingDirectory $context.EvaluationRoot
