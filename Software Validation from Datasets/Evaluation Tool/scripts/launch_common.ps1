Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-LaunchContext {
    param([Parameter(Mandatory = $true)][ValidateSet("machine_a", "machine_b")][string]$WorkerId)

    $evaluationRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
    $projectRoot = [System.IO.Path]::GetFullPath((Join-Path $evaluationRoot ".."))
    $repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot ".."))
    $python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
    $campaignRoot = Join-Path $evaluationRoot "automated_runs\campaign_05_massive_release"
    $assignment = Join-Path $campaignRoot "worker_assignments\$WorkerId.yaml"
    $profile = Join-Path $evaluationRoot "artifacts\launch_readiness\${WorkerId}_profile.json"
    $preflight = Join-Path $evaluationRoot "artifacts\launch_readiness\${WorkerId}_assignment_preflight.json"
    foreach ($required in @($python, (Join-Path $evaluationRoot "run_evaluation.py"), $campaignRoot, $assignment)) {
        if (-not (Test-Path -LiteralPath $required)) {
            throw "Required launch path is missing: $required"
        }
    }
    return [pscustomobject]@{
        WorkerId = $WorkerId
        RepositoryRoot = $repositoryRoot
        ProjectRoot = $projectRoot
        EvaluationRoot = $evaluationRoot
        Python = $python
        CampaignRoot = $campaignRoot
        Assignment = $assignment
        Profile = $profile
        Preflight = $preflight
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

function Show-LaunchIdentity {
    param([Parameter(Mandatory = $true)]$Context)
    Write-Host "Repository: $($Context.RepositoryRoot)"
    Write-Host "Campaign: campaign_05_massive_release"
    Write-Host "Worker: $($Context.WorkerId)"
    Invoke-Checked -FilePath "git" -Arguments @("-C", $Context.RepositoryRoot, "rev-parse", "HEAD")
    Invoke-Checked -FilePath $Context.Python -Arguments @("-c", "import sys; print(sys.executable); print(sys.version)")
}

function Invoke-WorkerPreflight {
    param([Parameter(Mandatory = $true)]$Context)
    $probe = Join-Path $Context.EvaluationRoot "scripts\launch_readiness_probe.py"
    $runEvaluation = Join-Path $Context.EvaluationRoot "run_evaluation.py"
    $otherWorker = if ($Context.WorkerId -eq "machine_a") { "machine_b" } else { "machine_a" }
    $otherAssignment = Join-Path $Context.CampaignRoot "worker_assignments\$otherWorker.yaml"

    Invoke-Checked -FilePath $Context.Python -Arguments @(
        $runEvaluation, "campaign", "validate", "--campaign-root", $Context.CampaignRoot
    )
    Invoke-Checked -FilePath $Context.Python -Arguments @(
        $runEvaluation, "campaign", "validate-assignments",
        "--campaign-root", $Context.CampaignRoot,
        "--assignment", $Context.Assignment,
        "--assignment", $otherAssignment
    )
    Invoke-Checked -FilePath $Context.Python -Arguments @(
        $probe, "machine",
        "--machine-id", $Context.WorkerId,
        "--repository-root", $Context.RepositoryRoot,
        "--project-root", $Context.ProjectRoot,
        "--environment-profile", "core-cpu",
        "--output-root", $Context.CampaignRoot,
        "--output", $Context.Profile
    )
    Invoke-Checked -FilePath $Context.Python -Arguments @(
        $probe, "assignment",
        "--machine-id", $Context.WorkerId,
        "--repository-root", $Context.RepositoryRoot,
        "--project-root", $Context.ProjectRoot,
        "--environment-profile", "core-cpu",
        "--output-root", $Context.CampaignRoot,
        "--campaign-root", $Context.CampaignRoot,
        "--assignment", $Context.Assignment,
        "--machine-profile", $Context.Profile,
        "--output", $Context.Preflight
    )
}
