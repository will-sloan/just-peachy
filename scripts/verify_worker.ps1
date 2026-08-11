[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet("machine_a", "machine_b")][string]$MachineId,
    [Parameter(Mandatory = $true)][ValidateSet("cpu", "cuda")][string]$Device
)

. (Join-Path $PSScriptRoot "worker_common.ps1")
trap {
    [Console]::Error.WriteLine("[FAIL] Worker verification: $($_.Exception.Message)")
    exit 2
}
$context = Get-ProductionWorkerContext -MachineId $MachineId -Device $Device
Assert-ProductionContextPaths -Context $context
if (-not (Test-Path -LiteralPath $context.Python -PathType Leaf)) {
    throw "The $Device environment is missing. Run scripts\setup_worker.ps1 first."
}

Invoke-ProductionChecked -FilePath $context.Python -Arguments @(
    "scripts\verify_install.py", "--profile", "dev", "--device", $Device,
    "--cache-root", (Join-Path $context.RepositoryRoot "models\cache"),
    "--whisper", "tiny,base,small", "--require-models"
) -WorkingDirectory $context.RepositoryRoot

Invoke-ProductionChecked -FilePath $context.Python -Arguments @(
    "scripts\verify_production_worker.py", "--machine-id", $MachineId,
    "--device", $Device
) -WorkingDirectory $context.EvaluationRoot

Invoke-ProductionChecked -FilePath "powershell" -Arguments @(
    "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $context.RepositoryRoot "scripts\launch_worker.ps1"),
    "-MachineId", $MachineId, "-Device", $Device, "-PreflightOnly"
) -WorkingDirectory $context.RepositoryRoot
Write-Host "[PASS] Worker verification complete: $MachineId / $Device"
