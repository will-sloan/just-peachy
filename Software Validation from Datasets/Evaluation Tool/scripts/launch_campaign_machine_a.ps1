[CmdletBinding()]
param(
    [switch]$ResumeStopped,
    [switch]$PreflightOnly
)

. (Join-Path $PSScriptRoot "launch_common.ps1")
$context = Get-LaunchContext -WorkerId "machine_a"
Show-LaunchIdentity -Context $context
Invoke-WorkerPreflight -Context $context
if ($PreflightOnly) {
    Write-Host "[PASS] Machine A CPU preflight completed; inference was not started."
    return
}

$arguments = @(
    (Join-Path $context.EvaluationRoot "run_evaluation.py"),
    "campaign", "run-assignment",
    "--campaign-root", $context.CampaignRoot,
    "--assignment", $context.Assignment,
    "--environment-profile", "core-cpu"
)
if ($ResumeStopped) {
    $arguments += "--resume-stopped"
}
Invoke-Checked -FilePath $context.Python -Arguments $arguments
