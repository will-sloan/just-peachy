[CmdletBinding()]
param(
    [ValidateSet(
        'Plan','PrepareCalibration','RunCalibration','FreezePolicies',
        'PrepareQualification','RunQualification','PrepareDevelopment',
        'QualifyRestarts','FinalizeQualification','RunDevelopment',
        'PrepareResources','RunResources','Status','Stop',
        'CombineEvidence','AnalyzeDevelopment','FreezeDevelopment',
        'PlanQualification','ValidateQualification','Analyze','Collect'
    )]
    [string]$Action = 'Plan',
    [string]$WorkspaceRoot,
    [string]$PolicyRegistryPath,
    [ValidateRange(0,[int]::MaxValue)]
    [int]$Seed = 5107,
    [string]$PlanPath,
    [string]$QualificationPath,
    [string]$QualificationEvidenceRoot,
    [string]$AnalysisPath,
    [string]$CampaignManifest,
    [string]$FrozenConfigRoot,
    [string]$OutputRoot
)

$ErrorActionPreference = 'Stop'
$InvocationRoot = (Get-Location).Path
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Management Python is unavailable: $Python"
}
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    if ($Action -in @(
        'Plan','PrepareCalibration','RunCalibration','FreezePolicies',
        'PrepareQualification','RunQualification','PrepareDevelopment',
        'QualifyRestarts','FinalizeQualification','RunDevelopment',
        'PrepareResources','RunResources','Status','Stop',
        'CombineEvidence','AnalyzeDevelopment','FreezeDevelopment'
    )) {
        $WorkspaceRoot = Join-Path $ToolRoot 'automated_runs\full_pipeline_development_v1'
    }
    else {
        $WorkspaceRoot = Join-Path $ToolRoot 'automated_runs\full_speech_pipeline_v1'
    }
}

function Resolve-InvocationPath([string]$Value, [string]$DefaultValue) {
    $Selected = if ([string]::IsNullOrWhiteSpace($Value)) { $DefaultValue } else { $Value }
    if ([System.IO.Path]::IsPathRooted($Selected)) {
        return [System.IO.Path]::GetFullPath($Selected)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $Selected))
}

$WorkspaceRoot = Resolve-InvocationPath $WorkspaceRoot $WorkspaceRoot
$PlanPath = Resolve-InvocationPath $PlanPath (Join-Path $WorkspaceRoot 'development\qualification_plan.json')
$QualificationPath = Resolve-InvocationPath $QualificationPath (Join-Path $WorkspaceRoot 'development\qualification.json')
$QualificationEvidenceRoot = Resolve-InvocationPath $QualificationEvidenceRoot (Split-Path -Parent $QualificationPath)
$AnalysisPath = Resolve-InvocationPath $AnalysisPath (Join-Path $WorkspaceRoot 'analysis\analysis.json')
$CampaignManifest = Resolve-InvocationPath $CampaignManifest (Join-Path $WorkspaceRoot 'campaign_manifest.json')
$FrozenConfigRoot = Resolve-InvocationPath $FrozenConfigRoot (Join-Path $WorkspaceRoot 'frozen_pipeline_configs')
$OutputRoot = Resolve-InvocationPath $OutputRoot (Join-Path $ToolRoot 'JustPeachyResearchSummaries\full_pipeline\development\full_speech_pipeline_v1')

$ActionMap = @{
    Plan = 'plan'
    PrepareCalibration = 'prepare-calibration'
    RunCalibration = 'run-calibration'
    FreezePolicies = 'freeze-policies'
    PrepareQualification = 'prepare-qualification'
    RunQualification = 'run-qualification'
    QualifyRestarts = 'qualify-restarts'
    FinalizeQualification = 'finalize-qualification'
    PrepareDevelopment = 'prepare-development'
    RunDevelopment = 'run-development'
    PrepareResources = 'prepare-resources'
    RunResources = 'run-resources'
    CombineEvidence = 'combine-evidence'
    AnalyzeDevelopment = 'combine-evidence'
    FreezeDevelopment = 'freeze-development'
    Status = 'status'
    Stop = 'stop'
    PlanQualification = 'plan-qualification'
    ValidateQualification = 'validate-qualification'
    Analyze = 'analyze'
    Collect = 'collect'
}
$Arguments = @('-m', 'app.full_pipeline_development.cli', $ActionMap[$Action])
$OrchestrationActions = @(
    'Plan','PrepareCalibration','RunCalibration','FreezePolicies',
    'PrepareQualification','RunQualification','PrepareDevelopment',
    'QualifyRestarts','FinalizeQualification','RunDevelopment',
    'PrepareResources','RunResources','Status','Stop',
    'CombineEvidence','AnalyzeDevelopment','FreezeDevelopment'
)
if ($Action -in $OrchestrationActions) {
    $Arguments += @('--workspace-root', $WorkspaceRoot)
    if ($Action -in @('PrepareCalibration','PrepareQualification','PrepareDevelopment','PrepareResources')) {
        $Arguments += @('--seed', [string]$Seed)
    }
    if (-not [string]::IsNullOrWhiteSpace($PolicyRegistryPath)) {
        $ResolvedPolicyRegistryPath = Resolve-InvocationPath $PolicyRegistryPath $PolicyRegistryPath
        $Arguments += @('--policy-registry-path', $ResolvedPolicyRegistryPath)
    }
}
elseif ($Action -eq 'PlanQualification') {
    $Arguments += @('--plan-path', $PlanPath)
}
elseif ($Action -eq 'ValidateQualification') {
    $Arguments += @(
        '--plan-path', $PlanPath,
        '--qualification-path', $QualificationPath,
        '--qualification-evidence-root', $QualificationEvidenceRoot
    )
}
elseif ($Action -eq 'Analyze') {
    $Arguments += @(
        '--plan-path', $PlanPath,
        '--qualification-path', $QualificationPath,
        '--qualification-evidence-root', $QualificationEvidenceRoot,
        '--analysis-path', $AnalysisPath,
        '--campaign-manifest', $CampaignManifest,
        '--frozen-config-root', $FrozenConfigRoot,
        '--output-root', $OutputRoot
    )
}
elseif ($Action -eq 'Collect') {
    $Arguments += @('--output-root', $OutputRoot)
}

Push-Location $ToolRoot
try {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Full-pipeline development action failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
