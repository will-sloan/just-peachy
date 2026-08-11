[CmdletBinding()]
param(
    [switch]$ResumeStopped,
    [switch]$PreflightOnly
)

. (Join-Path $PSScriptRoot "launch_common.ps1")
$context = Get-LaunchContext `
    -WorkerId "machine_a" `
    -CampaignId "campaign_06_massive_release_cuda" `
    -EnvironmentProfile "core-cuda" `
    -PythonRelativePath ".stage8-envs\core-cuda\Scripts\python.exe" `
    -Device "cuda:0" `
    -Dtype "float32" `
    -EstimatedRtf 0.1951 `
    -EstimatedRtfLow 0.16 `
    -EstimatedRtfHigh 0.30
Show-LaunchIdentity -Context $context
Invoke-WorkerPreflight -Context $context
if ($PreflightOnly) {
    Write-Host "[PASS] Machine A CUDA preflight completed; inference was not started."
    return
}

$arguments = @(
    (Join-Path $context.EvaluationRoot "run_evaluation.py"),
    "campaign", "run-assignment",
    "--campaign-root", $context.CampaignRoot,
    "--assignment", $context.Assignment,
    "--environment-profile", $context.EnvironmentProfile
)
if ($ResumeStopped) {
    $arguments += "--resume-stopped"
}
Invoke-Checked -FilePath $context.Python -Arguments $arguments
