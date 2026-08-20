[CmdletBinding()]
param(
    [ValidateSet('Audit', 'Prepare', 'Plan', 'Validate', 'Run', 'Status', 'Analyze', 'Collect', 'Smoke')]
    [string]$Action = 'Plan',
    [ValidateSet('All', 'EnrollmentCount', 'EnrollmentDuration', 'Aggregation', 'ProbeDuration', 'JointFrontier')]
    [string]$Phase = 'All',
    [string[]]$Backends = @(),
    [string]$SourceProtocolRoot = '',
    [string]$ProtocolRoot = '',
    [string]$ResultBase = '',
    [string]$AnalysisRoot = '',
    [string]$CollectRoot = '',
    [string]$ReferenceEnrollmentConfigId = '',
    [string]$DecisionGate = '',
    [string]$ManagementPython = ''
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
if (-not $SourceProtocolRoot) {
    $SourceProtocolRoot = Join-Path $ToolRoot 'benchmarks\speaker_breadth\commonvoice_60plus_v1'
}
if (-not $ProtocolRoot) {
    $ProtocolRoot = Join-Path $ToolRoot 'benchmarks\speaker_enrollment\speaker_enrollment_duration_v1'
}
if (-not $ManagementPython) {
    $ManagementPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $ManagementPython -PathType Leaf)) {
    throw "Management Python is missing: $ManagementPython"
}
if (-not $ResultBase) {
    if ($env:JP_SPEAKER_ENROLLMENT_RESULT_ROOT) {
        $ResultBase = $env:JP_SPEAKER_ENROLLMENT_RESULT_ROOT
    }
    else {
        $ResultBase = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'JustPeachyResults\speaker_enrollment'
    }
}

function Invoke-Management {
    param([string[]]$Arguments)
    & $ManagementPython $Launcher @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Speaker enrollment management command failed with exit code $LASTEXITCODE"
    }
}

function Get-ProtocolSummary {
    $Path = Join-Path $ProtocolRoot 'protocol_summary.json'
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Frozen protocol is missing. Run -Action Prepare first: $ProtocolRoot"
    }
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Get-ProtocolResultBase {
    $Summary = Get-ProtocolSummary
    return Join-Path $ResultBase $Summary.protocol_id
}

function Require-Backends {
    if ($Backends.Count -eq 0) {
        throw "Action $Action requires -Backends with one or more selected finalist IDs."
    }
}

function Get-BackendRuntime {
    param([string]$Backend)
    $Text = & $ManagementPython $Launcher speaker-enrollment backend-runtime --backend $Backend
    if ($LASTEXITCODE -ne 0) {
        throw "Could not resolve qualified runtime for backend: $Backend"
    }
    return ($Text | Out-String | ConvertFrom-Json)
}

function Add-PhaseSelectionArguments {
    param([System.Collections.ArrayList]$Arguments)
    [void]$Arguments.Add('--phase')
    [void]$Arguments.Add($Phase)
    if ($ReferenceEnrollmentConfigId) {
        [void]$Arguments.Add('--reference-enrollment-configuration-id')
        [void]$Arguments.Add($ReferenceEnrollmentConfigId)
    }
    if ($DecisionGate) {
        [void]$Arguments.Add('--decision-gate')
        [void]$Arguments.Add($DecisionGate)
    }
}

switch ($Action) {
    'Audit' {
        Invoke-Management @('speaker-enrollment', 'audit', '--source-protocol-root', $SourceProtocolRoot)
    }
    'Prepare' {
        Invoke-Management @('speaker-enrollment', 'prepare', '--source-protocol-root', $SourceProtocolRoot, '--protocol-root', $ProtocolRoot)
    }
    'Plan' {
        $Arguments = [System.Collections.ArrayList]@('speaker-enrollment', 'plan', '--source-protocol-root', $SourceProtocolRoot, '--protocol-root', $ProtocolRoot, '--phase', $Phase)
        foreach ($Backend in $Backends) {
            [void]$Arguments.Add('--backend')
            [void]$Arguments.Add($Backend)
        }
        Invoke-Management $Arguments
    }
    'Validate' {
        $Arguments = [System.Collections.ArrayList]@('speaker-enrollment', 'validate', '--source-protocol-root', $SourceProtocolRoot, '--protocol-root', $ProtocolRoot)
        foreach ($Backend in $Backends) {
            [void]$Arguments.Add('--backend')
            [void]$Arguments.Add($Backend)
        }
        Invoke-Management $Arguments
    }
    'Run' {
        Require-Backends
        if ($Phase -eq 'All') {
            throw 'Run requires one explicit -Phase. Run phases sequentially so poor configurations can be stopped early.'
        }
        $ValidateArguments = [System.Collections.ArrayList]@('speaker-enrollment', 'validate', '--source-protocol-root', $SourceProtocolRoot, '--protocol-root', $ProtocolRoot)
        foreach ($Backend in $Backends) {
            [void]$ValidateArguments.Add('--backend')
            [void]$ValidateArguments.Add($Backend)
        }
        Invoke-Management $ValidateArguments
        $ProtocolResultBase = Get-ProtocolResultBase
        foreach ($Backend in $Backends) {
            $Runtime = Get-BackendRuntime $Backend
            $BackendRoot = Join-Path $ProtocolResultBase $Backend
            $CacheRoot = Join-Path $BackendRoot 'embeddings'
            $PlanRoot = Join-Path $BackendRoot 'plans'
            $SliceList = Join-Path $PlanRoot ("{0}_required_slices.txt" -f $Phase)
            New-Item -ItemType Directory -Force -Path $PlanRoot | Out-Null
            $SliceArguments = [System.Collections.ArrayList]@('speaker-enrollment', 'required-slices', '--protocol-root', $ProtocolRoot, '--source-protocol-root', $SourceProtocolRoot, '--output', $SliceList)
            Add-PhaseSelectionArguments $SliceArguments
            Invoke-Management $SliceArguments
            Push-Location $ToolRoot
            try {
                & $Runtime.python -m app.speaker_enrollment.worker --protocol-root $ProtocolRoot --component $Backend --cache-root $CacheRoot --slice-list $SliceList
            }
            finally {
                Pop-Location
            }
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "[FAIL] extraction failed for $Backend / $Phase"
                continue
            }
            $CacheArguments = [System.Collections.ArrayList]@('speaker-enrollment', 'validate-cache', '--protocol-root', $ProtocolRoot, '--source-protocol-root', $SourceProtocolRoot, '--backend', $Backend, '--cache-root', $CacheRoot)
            Add-PhaseSelectionArguments $CacheArguments
            Invoke-Management $CacheArguments
            $EvaluationArguments = [System.Collections.ArrayList]@('speaker-enrollment', 'evaluate', '--protocol-root', $ProtocolRoot, '--source-protocol-root', $SourceProtocolRoot, '--backend', $Backend, '--cache-root', $CacheRoot, '--result-root', $BackendRoot)
            Add-PhaseSelectionArguments $EvaluationArguments
            Invoke-Management $EvaluationArguments
        }
    }
    'Status' {
        Require-Backends
        $ProtocolResultBase = Get-ProtocolResultBase
        $Arguments = [System.Collections.ArrayList]@('speaker-enrollment', 'status', '--result-base', $ProtocolResultBase)
        foreach ($Backend in $Backends) {
            [void]$Arguments.Add('--backend')
            [void]$Arguments.Add($Backend)
        }
        Invoke-Management $Arguments
    }
    'Analyze' {
        Require-Backends
        $ProtocolResultBase = Get-ProtocolResultBase
        if (-not $AnalysisRoot) {
            $AnalysisRoot = Join-Path $ProtocolResultBase 'analysis'
        }
        $Arguments = [System.Collections.ArrayList]@('speaker-enrollment', 'analyze', '--protocol-root', $ProtocolRoot, '--result-base', $ProtocolResultBase, '--output-root', $AnalysisRoot)
        foreach ($Backend in $Backends) {
            [void]$Arguments.Add('--backend')
            [void]$Arguments.Add($Backend)
        }
        Invoke-Management $Arguments
    }
    'Collect' {
        Require-Backends
        $Summary = Get-ProtocolSummary
        $ProtocolResultBase = Get-ProtocolResultBase
        if (-not $AnalysisRoot) {
            $AnalysisRoot = Join-Path $ProtocolResultBase 'analysis'
        }
        if (-not $CollectRoot) {
            $CollectRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) ("JustPeachyResearchSummaries\speaker_enrollment_duration_{0}" -f $Summary.protocol_id)
        }
        $Arguments = [System.Collections.ArrayList]@('speaker-enrollment', 'collect', '--protocol-root', $ProtocolRoot, '--source-protocol-root', $SourceProtocolRoot, '--result-base', $ProtocolResultBase, '--analysis-root', $AnalysisRoot, '--output-root', $CollectRoot)
        foreach ($Backend in $Backends) {
            [void]$Arguments.Add('--backend')
            [void]$Arguments.Add($Backend)
        }
        Invoke-Management $Arguments
    }
    'Smoke' {
        $SmokeRoot = Join-Path $ToolRoot 'artifacts\speaker_enrollment_smoke\non_scientific'
        Invoke-Management @('speaker-enrollment', 'smoke', '--protocol-root', $ProtocolRoot, '--output-root', $SmokeRoot)
    }
}
