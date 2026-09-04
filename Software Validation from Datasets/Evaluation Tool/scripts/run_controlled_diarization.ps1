[CmdletBinding()]
param(
    [ValidateSet('Audit', 'Prepare', 'Plan', 'Validate', 'Smoke', 'Run', 'Status', 'Analyze', 'Collect', 'Freeze', 'Stop')]
    [string]$Action = 'Plan',
    [ValidateSet('smoke', 'development', 'evaluation')]
    [string]$Tier = 'evaluation',
    [string[]]$Pipelines = @(),
    [string]$SourceSpeakerPool = '',
    [string]$BenchmarkRoot = '',
    [string]$GeneratedRoot = '',
    [string]$ResultRoot = '',
    [string]$AnalysisRoot = '',
    [string]$CollectRoot = '',
    [string]$FrozenPipelineConfig = '',
    [string]$DecisionNote = '',
    [int]$MaxCases = 0,
    [switch]$OracleSpeakerCountDiagnostic,
    [string]$ManagementPython = ''
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
$Config = Join-Path $ToolRoot 'configs\automated_evaluation\controlled_diarization_benchmark.v1.yaml'
if (-not $ManagementPython) {
    $ManagementPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
}
if (-not $BenchmarkRoot) {
    $BenchmarkRoot = Join-Path $ToolRoot 'benchmarks\stage11\controlled_diarization_v1'
}
if (-not $GeneratedRoot) {
    if ($env:JP_GENERATED_DATA_ROOT) {
        $GeneratedRoot = Join-Path $env:JP_GENERATED_DATA_ROOT 'controlled_diarization_v1'
    }
    else {
        $GeneratedRoot = Join-Path $ToolRoot 'JustPeachyGeneratedData\controlled_diarization_v1'
    }
}
if (-not $ResultRoot) {
    if ($env:JP_DIARIZATION_RESULT_ROOT) {
        $ResultRoot = Join-Path $env:JP_DIARIZATION_RESULT_ROOT 'controlled_diarization_v1'
    }
    else {
        $ResultRoot = Join-Path $ToolRoot 'JustPeachyResults\diarization\controlled_diarization_v1'
    }
}
if (-not $SourceSpeakerPool) {
    $SourceSpeakerPool = Join-Path $ToolRoot 'benchmarks\speaker_breadth\commonvoice_60plus_v1\speaker_protocol_manifest.json'
}
if (-not (Test-Path -LiteralPath $ManagementPython -PathType Leaf)) {
    throw "Management Python is missing: $ManagementPython"
}

function Invoke-Management {
    param([string[]]$Arguments)
    & $ManagementPython $Launcher @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Controlled diarization command failed with exit code $LASTEXITCODE"
    }
}

function Add-PipelineArguments {
    param([string[]]$Arguments)
    $Result = @($Arguments)
    foreach ($Pipeline in $Pipelines) {
        $Result += @('--pipeline', $Pipeline)
    }
    return $Result
}

function Require-Pipelines {
    if ($Pipelines.Count -eq 0) {
        throw "Action $Action requires -Pipelines with one or more exact pipeline IDs."
    }
}

$Common = @(
    '--config', $Config,
    '--benchmark-root', $BenchmarkRoot,
    '--generated-root', $GeneratedRoot
)

switch ($Action) {
    'Audit' {
        Invoke-Management @(
            'diarization-benchmark', 'audit', '--config', $Config,
            '--source-speaker-pool', $SourceSpeakerPool
        )
    }
    'Prepare' {
        Invoke-Management (@('diarization-benchmark', 'prepare') + $Common + @(
            '--source-speaker-pool', $SourceSpeakerPool
        ))
    }
    'Validate' {
        Invoke-Management (@('diarization-benchmark', 'validate') + $Common + @('--verify-source-hashes'))
    }
    'Plan' {
        $Arguments = Add-PipelineArguments (@('diarization-benchmark', 'plan') + $Common + @('--tier', $Tier))
        Invoke-Management $Arguments
    }
    'Smoke' {
        Require-Pipelines
        $Arguments = Add-PipelineArguments (@(
            'diarization-benchmark', 'smoke'
        ) + $Common + @('--result-root', $ResultRoot))
        if ($MaxCases -gt 0) { $Arguments += @('--max-cases', [string]$MaxCases) }
        Invoke-Management $Arguments
    }
    'Run' {
        Require-Pipelines
        if ($Tier -eq 'evaluation' -and -not $FrozenPipelineConfig) {
            throw 'Frozen evaluation requires -FrozenPipelineConfig from the post-development decision gate.'
        }
        Invoke-Management (@('diarization-benchmark', 'validate') + $Common)
        $Arguments = Add-PipelineArguments (@(
            'diarization-benchmark', 'run'
        ) + $Common + @('--tier', $Tier, '--result-root', $ResultRoot))
        if ($FrozenPipelineConfig) {
            $Arguments += @('--frozen-pipeline-config', $FrozenPipelineConfig)
        }
        if ($MaxCases -gt 0) { $Arguments += @('--max-cases', [string]$MaxCases) }
        if ($OracleSpeakerCountDiagnostic) { $Arguments += '--oracle-speaker-count-diagnostic' }
        Invoke-Management $Arguments
    }
    'Status' {
        Require-Pipelines
        $Arguments = Add-PipelineArguments @(
            'diarization-benchmark', 'status', '--config', $Config,
            '--benchmark-root', $BenchmarkRoot, '--result-root', $ResultRoot,
            '--tier', $Tier
        )
        Invoke-Management $Arguments
    }
    'Analyze' {
        Require-Pipelines
        if (-not $AnalysisRoot) { $AnalysisRoot = Join-Path $ResultRoot 'analysis' }
        $Arguments = Add-PipelineArguments @(
            'diarization-benchmark', 'analyze', '--config', $Config,
            '--benchmark-root', $BenchmarkRoot, '--result-root', $ResultRoot,
            '--output-root', $AnalysisRoot, '--tier', $Tier
        )
        Invoke-Management $Arguments
    }
    'Collect' {
        Require-Pipelines
        if (-not $AnalysisRoot) { $AnalysisRoot = Join-Path $ResultRoot 'analysis' }
        $Arguments = Add-PipelineArguments @(
            'diarization-benchmark', 'collect', '--benchmark-root', $BenchmarkRoot,
            '--generated-root', $GeneratedRoot, '--result-root', $ResultRoot,
            '--analysis-root', $AnalysisRoot, '--tier', $Tier
        )
        if ($CollectRoot) { $Arguments += @('--output-root', $CollectRoot) }
        Invoke-Management $Arguments
    }
    'Freeze' {
        Require-Pipelines
        if (-not $DecisionNote) { throw 'Freeze requires -DecisionNote documenting the operator decision.' }
        if (-not $FrozenPipelineConfig) {
            $FrozenPipelineConfig = Join-Path $ResultRoot 'frozen_pipeline_configuration.json'
        }
        if (-not $AnalysisRoot) { $AnalysisRoot = Join-Path $ResultRoot 'analysis' }
        $Arguments = Add-PipelineArguments @(
            'diarization-benchmark', 'freeze-pipelines', '--config', $Config,
            '--benchmark-root', $BenchmarkRoot, '--result-root', $ResultRoot,
            '--analysis-root', $AnalysisRoot, '--decision-note', $DecisionNote,
            '--output', $FrozenPipelineConfig
        )
        Invoke-Management $Arguments
    }
    'Stop' {
        New-Item -ItemType Directory -Force -Path $ResultRoot | Out-Null
        $StopPath = Join-Path $ResultRoot 'STOP_REQUESTED'
        Set-Content -LiteralPath $StopPath -Value "operator stop requested $(Get-Date -Format o)"
        Write-Output "Stop requested. The sequential runner will stop before the next case: $StopPath"
    }
}
