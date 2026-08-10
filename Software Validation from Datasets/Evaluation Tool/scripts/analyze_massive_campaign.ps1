[CmdletBinding()]
param([string]$PrerequisiteEvidence = "")

. (Join-Path $PSScriptRoot "launch_common.ps1")
$context = Get-LaunchContext -WorkerId "machine_a"
Show-LaunchIdentity -Context $context
$runEvaluation = Join-Path $context.EvaluationRoot "run_evaluation.py"
Invoke-Checked -FilePath $context.Python -Arguments @(
    $runEvaluation, "analysis", "index", "--campaign-root", $context.CampaignRoot
)
Invoke-Checked -FilePath $context.Python -Arguments @(
    $runEvaluation, "analysis", "validate", "--campaign-root", $context.CampaignRoot
)
$runArguments = @($runEvaluation, "analysis", "run", "--campaign-root", $context.CampaignRoot)
if ($PrerequisiteEvidence) {
    $runArguments += @("--prerequisite-evidence", [System.IO.Path]::GetFullPath($PrerequisiteEvidence))
} else {
    Write-Warning "No passed standard-gate evidence was supplied; analysis will run, but the large release gate must remain blocked."
}
Invoke-Checked -FilePath $context.Python -Arguments $runArguments
Invoke-Checked -FilePath $context.Python -Arguments @(
    $runEvaluation, "analysis", "coverage", "--campaign-root", $context.CampaignRoot
)
$releaseArguments = @($runEvaluation, "analysis", "release-status", "--campaign-root", $context.CampaignRoot)
if ($PrerequisiteEvidence) {
    $releaseArguments += @("--prerequisite-evidence", [System.IO.Path]::GetFullPath($PrerequisiteEvidence))
}
Invoke-Checked -FilePath $context.Python -Arguments $releaseArguments
Write-Host "Final report: $(Join-Path $context.CampaignRoot 'analysis\report\campaign_report.md')"
