[CmdletBinding()]
param(
    [ValidateSet('Audit', 'Prepare', 'Plan', 'Validate', 'Smoke', 'RunDevelopment', 'AnalyzeDevelopment', 'Freeze', 'RunEvaluation', 'Status', 'Analyze', 'Collect')]
    [string]$Action = 'Plan',
    [string]$SpeakerBackend = '',
    [string]$DiarizationPipeline = '',
    [string]$EnrollmentPolicy = '',
    [string]$BenchmarkRoot = '',
    [string]$ProtocolRoot = '',
    [string]$GeneratedRoot = '',
    [string]$DiarizationResultRoot = '',
    [string]$ResultRoot = '',
    [string]$AnalysisRoot = '',
    [string]$CollectRoot = '',
    [string]$FrozenDiarizationConfig = '',
    [string]$FrozenHybridConfig = '',
    [string]$DevelopmentConfigurationId = '',
    [string]$DecisionNote = '',
    [double]$Threshold = [double]::NaN,
    [double]$ScoreMargin = [double]::NaN,
    [double]$MinimumEvidenceSec = [double]::NaN,
    [ValidateSet('', 'normalized_mean', 'duration_weighted_mean')]
    [string]$ClusterAggregation = '',
    [ValidateSet('', 'include_predicted_overlap', 'exclude_predicted_overlap_segments')]
    [string]$OverlapPolicy = '',
    [int]$MaxCases = 0,
    [switch]$ReuseDiarizationOnly,
    [switch]$VerifyAudioHashes,
    [string]$ManagementPython = ''
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
if (-not $ManagementPython) { $ManagementPython = Join-Path $RepoRoot '.venv\Scripts\python.exe' }
if (-not $BenchmarkRoot) { $BenchmarkRoot = Join-Path $ToolRoot 'benchmarks\stage11\controlled_diarization_v1' }
if (-not $ProtocolRoot) { $ProtocolRoot = Join-Path $ToolRoot 'benchmarks\hybrid_speaker_attribution\hybrid_speaker_attribution_v1' }
if (-not $GeneratedRoot) {
    $Base = if ($env:JP_GENERATED_DATA_ROOT) { $env:JP_GENERATED_DATA_ROOT } else { Join-Path $ToolRoot 'JustPeachyGeneratedData' }
    $GeneratedRoot = Join-Path $Base 'controlled_diarization_v1'
}
if (-not $DiarizationResultRoot) {
    $DiarizationResultRoot = Join-Path $ToolRoot 'JustPeachyResults\diarization\controlled_diarization_v1'
}
if (-not $ResultRoot) { $ResultRoot = Join-Path $ToolRoot 'JustPeachyResults\hybrid_speaker_attribution' }
if (-not $AnalysisRoot) { $AnalysisRoot = Join-Path $ResultRoot 'analysis' }
if (-not (Test-Path -LiteralPath $ManagementPython -PathType Leaf)) { throw "Management Python is missing: $ManagementPython" }

function Invoke-Management {
    param([string[]]$Arguments)
    & $ManagementPython $Launcher @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Hybrid attribution command failed with exit code $LASTEXITCODE" }
}

function Require-Selection {
    if (-not $SpeakerBackend) { throw "Action $Action requires -SpeakerBackend." }
    if (-not $DiarizationPipeline) { throw "Action $Action requires -DiarizationPipeline." }
    if (-not $EnrollmentPolicy) { throw "Action $Action requires -EnrollmentPolicy." }
}

function Get-SelectionArguments {
    return @(
        '--speaker-backend', $SpeakerBackend,
        '--diarization-pipeline', $DiarizationPipeline,
        '--enrollment-policy', $EnrollmentPolicy,
        '--benchmark-root', $BenchmarkRoot,
        '--protocol-root', $ProtocolRoot,
        '--generated-root', $GeneratedRoot
    )
}

function Get-RunArguments {
    $Arguments = @(Get-SelectionArguments) + @(
        '--diarization-result-root', $DiarizationResultRoot,
        '--result-root', $ResultRoot
    )
    if ($FrozenDiarizationConfig) { $Arguments += @('--frozen-diarization-config', $FrozenDiarizationConfig) }
    if ($FrozenHybridConfig) { $Arguments += @('--frozen-hybrid-config', $FrozenHybridConfig) }
    if ($MaxCases -gt 0) { $Arguments += @('--max-cases', [string]$MaxCases) }
    if ($ReuseDiarizationOnly) { $Arguments += '--reuse-diarization-only' }
    if (-not [double]::IsNaN($Threshold)) { $Arguments += @('--threshold', [string]$Threshold) }
    if (-not [double]::IsNaN($ScoreMargin)) { $Arguments += @('--score-margin', [string]$ScoreMargin) }
    if (-not [double]::IsNaN($MinimumEvidenceSec)) { $Arguments += @('--minimum-evidence-sec', [string]$MinimumEvidenceSec) }
    if ($ClusterAggregation) { $Arguments += @('--cluster-aggregation', $ClusterAggregation) }
    if ($OverlapPolicy) { $Arguments += @('--overlap-policy', $OverlapPolicy) }
    return $Arguments
}

switch ($Action) {
    'Audit' {
        Require-Selection
        Invoke-Management (@('hybrid-attribution', 'audit') + @(Get-SelectionArguments))
    }
    'Prepare' {
        Invoke-Management @('hybrid-attribution', 'prepare', '--benchmark-root', $BenchmarkRoot, '--protocol-root', $ProtocolRoot)
    }
    'Plan' {
        Require-Selection
        Invoke-Management (@('hybrid-attribution', 'plan') + @(Get-SelectionArguments) + @('--diarization-result-root', $DiarizationResultRoot))
    }
    'Validate' {
        $Arguments = @('hybrid-attribution', 'validate', '--benchmark-root', $BenchmarkRoot, '--protocol-root', $ProtocolRoot, '--generated-root', $GeneratedRoot)
        if ($VerifyAudioHashes) { $Arguments += '--verify-audio-hashes' }
        Invoke-Management $Arguments
    }
    'Smoke' {
        Require-Selection
        $Arguments = @('hybrid-attribution', 'smoke') + @(Get-RunArguments)
        if ($MaxCases -eq 0) { $Arguments += @('--max-cases', '1') }
        Invoke-Management $Arguments
    }
    'RunDevelopment' {
        Require-Selection
        Invoke-Management (@('hybrid-attribution', 'run-development') + @(Get-RunArguments))
    }
    'AnalyzeDevelopment' {
        Invoke-Management @('hybrid-attribution', 'analyze-development', '--result-root', $ResultRoot, '--output-root', $AnalysisRoot)
    }
    'Freeze' {
        Require-Selection
        if (-not $DevelopmentConfigurationId) { throw 'Freeze requires -DevelopmentConfigurationId.' }
        if (-not $FrozenDiarizationConfig) { throw 'Freeze requires -FrozenDiarizationConfig.' }
        if (-not $FrozenHybridConfig) { throw 'Freeze requires -FrozenHybridConfig as the output path.' }
        if (-not $DecisionNote) { throw 'Freeze requires -DecisionNote.' }
        if ([double]::IsNaN($Threshold)) { throw 'Freeze requires the development-selected -Threshold.' }
        $Arguments = @('hybrid-attribution', 'freeze') + @(Get-SelectionArguments) + @(
            '--development-configuration-id', $DevelopmentConfigurationId,
            '--development-result-root', $ResultRoot,
            '--frozen-diarization-config', $FrozenDiarizationConfig,
            '--output', $FrozenHybridConfig,
            '--decision-note', $DecisionNote,
            '--threshold', [string]$Threshold
        )
        if (-not [double]::IsNaN($ScoreMargin)) { $Arguments += @('--score-margin', [string]$ScoreMargin) }
        if (-not [double]::IsNaN($MinimumEvidenceSec)) { $Arguments += @('--minimum-evidence-sec', [string]$MinimumEvidenceSec) }
        if ($ClusterAggregation) { $Arguments += @('--cluster-aggregation', $ClusterAggregation) }
        if ($OverlapPolicy) { $Arguments += @('--overlap-policy', $OverlapPolicy) }
        Invoke-Management $Arguments
    }
    'RunEvaluation' {
        Require-Selection
        if (-not $FrozenDiarizationConfig -or -not $FrozenHybridConfig) { throw 'RunEvaluation requires both frozen configurations.' }
        if (-not [double]::IsNaN($Threshold) -or -not [double]::IsNaN($ScoreMargin) -or -not [double]::IsNaN($MinimumEvidenceSec) -or $ClusterAggregation -or $OverlapPolicy) {
            throw 'Evaluation rejects ad hoc attribution overrides; use the exact frozen hybrid configuration.'
        }
        Invoke-Management (@('hybrid-attribution', 'run-evaluation') + @(Get-RunArguments))
    }
    'Status' { Invoke-Management @('hybrid-attribution', 'status', '--result-root', $ResultRoot) }
    'Analyze' { Invoke-Management @('hybrid-attribution', 'analyze', '--result-root', $ResultRoot, '--output-root', $AnalysisRoot) }
    'Collect' {
        if (-not $CollectRoot) { throw 'Collect requires -CollectRoot.' }
        $Arguments = @('hybrid-attribution', 'collect', '--analysis-root', $AnalysisRoot, '--output-root', $CollectRoot, '--protocol-root', $ProtocolRoot)
        if ($FrozenHybridConfig) { $Arguments += @('--frozen-hybrid-config', $FrozenHybridConfig) }
        Invoke-Management $Arguments
    }
}
