[CmdletBinding()]
param(
    [ValidateSet('Prepare', 'Plan', 'Validate', 'Run', 'Status', 'Collect')]
    [string]$Action = 'Plan',
    [string[]]$Backends = @(),
    [string]$ProtocolRoot = '',
    [string]$ResultBase = '',
    [string]$CollectRoot = '',
    [string]$ManagementPython = ''
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
if (-not $ProtocolRoot) {
    $ProtocolRoot = Join-Path $ToolRoot 'benchmarks\speaker_breadth\commonvoice_60plus_v1'
}
if (-not $ManagementPython) {
    $ManagementPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $ManagementPython -PathType Leaf)) {
    throw "Management Python is missing: $ManagementPython"
}
if (-not $ResultBase) {
    if ($env:JP_SPEAKER_BREADTH_RESULT_ROOT) {
        $ResultBase = $env:JP_SPEAKER_BREADTH_RESULT_ROOT
    }
    else {
        $ResultBase = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'JustPeachyResults\speaker_breadth\commonvoice_60plus_v1'
    }
}

function Invoke-Management {
    param([string[]]$Arguments)
    & $ManagementPython $Launcher @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Evaluation management command failed with exit code $LASTEXITCODE"
    }
}

function Get-ProtocolSummary {
    $Path = Join-Path $ProtocolRoot 'protocol_summary.json'
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Frozen protocol is missing. Run -Action Prepare first: $ProtocolRoot"
    }
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Test-ValidResult {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $false
    }
    & $ManagementPython $Launcher speaker-protocol validate --result-root $Path *> $null
    return $LASTEXITCODE -eq 0
}

function Test-ValidExtraction {
    param([string]$Path, [string]$Backend)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return $false
    }
    & $ManagementPython $Launcher speaker-breadth validate-extraction --protocol-root $ProtocolRoot --extraction-root $Path --backend $Backend *> $null
    return $LASTEXITCODE -eq 0
}

function Get-BackendRuntime {
    param([string]$Backend)
    $Text = & $ManagementPython $Launcher speaker-breadth backend-runtime --backend $Backend
    if ($LASTEXITCODE -ne 0) {
        throw "Could not resolve qualified runtime for backend: $Backend"
    }
    return ($Text | Out-String | ConvertFrom-Json)
}

function Require-Backends {
    if ($Backends.Count -eq 0) {
        throw "Action $Action requires -Backends with one or more Stage 10 finalist IDs."
    }
}

switch ($Action) {
    'Prepare' {
        Invoke-Management @('speaker-breadth', 'prepare', '--protocol-root', $ProtocolRoot)
    }
    'Plan' {
        $Arguments = @('speaker-breadth', 'plan', '--protocol-root', $ProtocolRoot)
        foreach ($Backend in $Backends) {
            $Arguments += @('--backend', $Backend)
        }
        Invoke-Management $Arguments
    }
    'Validate' {
        Invoke-Management @('speaker-breadth', 'validate', '--protocol-root', $ProtocolRoot, '--verify-audio-hashes')
    }
    'Status' {
        Require-Backends
        $Summary = Get-ProtocolSummary
        Write-Output "Protocol: $($Summary.protocol_id)"
        Write-Output "Protocol artifacts: $ProtocolRoot"
        Write-Output ('{0,-42} {1}' -f 'BACKEND', 'STATUS')
        foreach ($Backend in $Backends) {
            $BackendRoot = Join-Path (Join-Path $ResultBase $Summary.protocol_id) $Backend
            $ExtractionRoot = Join-Path $BackendRoot 'extraction'
            $ResultRoot = Join-Path $BackendRoot 'result'
            if (Test-ValidResult $ResultRoot) {
                $Status = 'VALID'
            }
            elseif (Test-Path -LiteralPath $BackendRoot) {
                $Status = 'PARTIAL'
            }
            else {
                $Status = 'NOT_RUN'
            }
            Write-Output ('{0,-42} {1}' -f $Backend, $Status)
            Write-Output "  extraction: $ExtractionRoot"
            Write-Output "  result:     $ResultRoot"
        }
    }
    'Run' {
        Require-Backends
        Invoke-Management @('speaker-breadth', 'validate', '--protocol-root', $ProtocolRoot, '--verify-audio-hashes')
        $Summary = Get-ProtocolSummary
        foreach ($Backend in $Backends) {
            $Runtime = Get-BackendRuntime $Backend
            $BackendRoot = Join-Path (Join-Path $ResultBase $Summary.protocol_id) $Backend
            $ExtractionRoot = Join-Path $BackendRoot 'extraction'
            $ResultRoot = Join-Path $BackendRoot 'result'
            New-Item -ItemType Directory -Force -Path $BackendRoot | Out-Null
            if (Test-ValidResult $ResultRoot) {
                Write-Output "[REUSE] $Backend"
                continue
            }
            if (Test-ValidExtraction $ExtractionRoot $Backend) {
                Write-Output "[REUSE EXTRACTION] $Backend"
            }
            else {
                Write-Output "[EXTRACT] $Backend using $($Runtime.environment_profile)"
                & $Runtime.python $Launcher speaker-protocol extract --manifest-root $ProtocolRoot --component $Backend --output-root $ExtractionRoot
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "[FAIL] extraction failed for $Backend"
                    continue
                }
                if (-not (Test-ValidExtraction $ExtractionRoot $Backend)) {
                    Write-Warning "[FAIL] extraction bundle is invalid for $Backend"
                    continue
                }
            }
            if (Test-Path -LiteralPath $ResultRoot) {
                $Quarantine = "$ResultRoot.invalid-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
                Move-Item -LiteralPath $ResultRoot -Destination $Quarantine
                Write-Output "[PRESERVE PARTIAL] $Quarantine"
            }
            Write-Output "[EVALUATE] $Backend"
            & $ManagementPython $Launcher speaker-protocol evaluate --manifest-root $ProtocolRoot --observation-bundle (Join-Path $ExtractionRoot 'observations.npz') --backend-identity (Join-Path $ExtractionRoot 'backend_identity.json') --output-root $ResultRoot
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "[FAIL] evaluation failed for $Backend"
                continue
            }
            Write-Output "[VALIDATE] $Backend"
            if (Test-ValidResult $ResultRoot) {
                Write-Output "[PASS] $Backend"
            }
            else {
                Write-Warning "[FAIL] result validation failed for $Backend"
            }
        }
    }
    'Collect' {
        Require-Backends
        $Summary = Get-ProtocolSummary
        if (-not $CollectRoot) {
            $CollectRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) "JustPeachyResearchSummaries\speaker_breadth_commonvoice_60plus_$($Summary.protocol_id)"
        }
        $Arguments = @('speaker-breadth', 'collect', '--protocol-root', $ProtocolRoot, '--result-base', $ResultBase, '--output-root', $CollectRoot)
        foreach ($Backend in $Backends) {
            $Arguments += @('--backend', $Backend)
        }
        Invoke-Management $Arguments
    }
}
