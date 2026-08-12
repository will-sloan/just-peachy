[CmdletBinding()]
param(
    [ValidateSet("Plan", "Run", "Resume", "Status", "Stop")]
    [string]$Action = "Plan",
    [string[]]$CampaignId = @(),
    [switch]$IncludeOptional,
    [string]$WorkerId = "amir",
    [int]$MaxScenarios = 0
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$EvaluationRoot = Join-Path $RepositoryRoot "Software Validation from Datasets\Evaluation Tool"
$CorePython = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$QueuePath = Join-Path $EvaluationRoot "benchmarks\edge_research\edge_research_queue.json"
$AutomatedRuns = Join-Path $EvaluationRoot "automated_runs"
$ProfilePython = @{
    "core-cpu" = $CorePython
    "edge-cpu" = Join-Path $RepositoryRoot ".stage8-envs\edge-cpu\Scripts\python.exe"
    "moonshine-edge" = Join-Path $RepositoryRoot ".stage8-envs\moonshine-edge\Scripts\python.exe"
    "onnx" = Join-Path $RepositoryRoot ".stage8-envs\onnx\Scripts\python.exe"
}

function Invoke-Checked {
    param([string]$FilePath, [string[]]$Arguments, [switch]$Capture)
    if ($Capture) {
        $Output = & $FilePath @Arguments | Out-String
        if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')" }
        return $Output
    }
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')" }
}

if (-not (Test-Path -LiteralPath $CorePython -PathType Leaf)) {
    throw "Core interpreter is missing. Run scripts\prepare_edge_research.ps1."
}

Push-Location $EvaluationRoot
try {
    Invoke-Checked $CorePython @("-m", "app.edge_research.cli", "plan")
    Invoke-Checked $CorePython @("-m", "app.edge_research.cli", "verify")
    $Queue = Get-Content -LiteralPath $QueuePath -Raw | ConvertFrom-Json
    $Jobs = @($Queue.jobs | Where-Object { $_.kind -eq "asr_campaign" })
    if ($CampaignId.Count -gt 0) {
        $Jobs = @($Jobs | Where-Object { $_.campaign_id -in $CampaignId })
        $Missing = @($CampaignId | Where-Object { $_ -notin $Jobs.campaign_id })
        if ($Missing.Count -gt 0) { throw "Unknown ASR campaign ID(s): $($Missing -join ', ')" }
    } elseif (-not $IncludeOptional) {
        $Jobs = @($Jobs | Where-Object { $_.enabled_by_default })
    }
    if ($Jobs.Count -eq 0) { throw "No ASR campaign jobs were selected." }

    # Global preflight: all selected jobs pass before anything is materialized or run.
    foreach ($Job in $Jobs) {
        $Interpreter = $ProfilePython[[string]$Job.environment_profile]
        if (-not $Interpreter -or -not (Test-Path -LiteralPath $Interpreter -PathType Leaf)) {
            throw "Interpreter unavailable for $($Job.campaign_id): $Interpreter"
        }
        $CatalogPath = Join-Path $EvaluationRoot ([string]$Job.catalog)
        $ObservedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $CatalogPath).Hash
        if ($ObservedHash -ne [string]$Job.catalog_sha256) { throw "Catalog hash mismatch for $($Job.campaign_id)" }
        $RawPlan = Invoke-Checked $CorePython @(
            "run_evaluation.py", "campaign", "plan", "--catalog", $CatalogPath,
            "--campaign-id", ([string]$Job.campaign_id), "--dry-run"
        ) -Capture
        $DryPlan = $RawPlan | ConvertFrom-Json
        if ([int]$DryPlan.scenario_count -ne [int]$Job.expected_scenario_count) {
            throw "Dry-plan count mismatch for $($Job.campaign_id)"
        }
        Write-Host "[PLAN] $($Job.campaign_id): $($DryPlan.scenario_count) scenarios; profile=$($Job.environment_profile)"
    }
    if ($Action -eq "Plan") {
        Write-Host "[PASS] Every selected campaign dry-planned with its exact frozen count. No inference started."
        return
    }

    foreach ($Job in $Jobs) {
        $CampaignRoot = Join-Path $AutomatedRuns ([string]$Job.campaign_id)
        if ($Action -eq "Status") {
            if (Test-Path -LiteralPath (Join-Path $CampaignRoot "campaign_manifest.json")) {
                Invoke-Checked $CorePython @("run_evaluation.py", "campaign", "status", "--campaign-root", $CampaignRoot)
            } else { Write-Host "[NOT MATERIALIZED] $($Job.campaign_id)" }
            continue
        }
        if ($Action -eq "Stop") {
            if (Test-Path -LiteralPath (Join-Path $CampaignRoot "campaign_manifest.json")) {
                Invoke-Checked $CorePython @(
                    "run_evaluation.py", "campaign", "stop", "--campaign-root", $CampaignRoot,
                    "--reason", "edge research operator request"
                )
            }
            continue
        }

        $CatalogPath = Join-Path $EvaluationRoot ([string]$Job.catalog)
        Invoke-Checked $CorePython @(
            "run_evaluation.py", "campaign", "plan", "--catalog", $CatalogPath,
            "--campaign-id", ([string]$Job.campaign_id)
        )
        Invoke-Checked $CorePython @("run_evaluation.py", "campaign", "validate", "--campaign-root", $CampaignRoot)
        $Command = if ($Action -eq "Resume") { "resume" } else { "run" }
        $RunArguments = @(
            "run_evaluation.py", "campaign", $Command, "--campaign-root", $CampaignRoot,
            "--worker-id", $WorkerId, "--telemetry"
        )
        if ($MaxScenarios -gt 0) { $RunArguments += @("--max-scenarios", [string]$MaxScenarios) }
        Invoke-Checked $ProfilePython[[string]$Job.environment_profile] $RunArguments
        Invoke-Checked $CorePython @("run_evaluation.py", "campaign", "validate", "--campaign-root", $CampaignRoot)
        Invoke-Checked $CorePython @("run_evaluation.py", "campaign", "validate-artifacts", "--campaign-root", $CampaignRoot)
    }
} finally {
    Pop-Location
}
