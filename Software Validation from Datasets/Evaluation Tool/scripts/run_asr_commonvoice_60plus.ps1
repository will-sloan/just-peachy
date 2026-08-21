[CmdletBinding()]
param(
    [ValidateSet('Audit', 'Prepare', 'Plan', 'Validate', 'Run', 'Status', 'Analyze', 'Collect')]
    [string]$Action = 'Plan',
    [string]$ProtocolRoot = '',
    [string]$ResultRoot = '',
    [string]$CollectionRoot = '',
    [switch]$Smoke,
    [switch]$VerifyAudioHashes,
    [switch]$NoZip,
    [ValidateRange(1, 3)]
    [int]$ParallelModels = 1,
    [switch]$AutoExport
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
$CorePython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$OnnxPython = Join-Path $RepoRoot '.stage8-envs\onnx\Scripts\python.exe'
if (-not $ProtocolRoot) { $ProtocolRoot = Join-Path $ToolRoot 'benchmarks\asr_commonvoice\commonvoice_60plus_asr_v1' }
foreach ($Python in @($CorePython, $OnnxPython)) {
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Required environment is missing: $Python" }
}

function Get-CommonArguments {
    $Arguments = @('asr-commonvoice', '--protocol-root', $ProtocolRoot)
    if ($ResultRoot) { $Arguments += @('--result-root', $ResultRoot) }
    if ($CollectionRoot) { $Arguments += @('--collection-root', $CollectionRoot) }
    if ($VerifyAudioHashes) { $Arguments += '--verify-audio-hashes' }
    if ($NoZip) { $Arguments += '--no-zip' }
    if ($Smoke) { $Arguments += '--smoke' }
    return $Arguments
}

function Invoke-Core {
    param([string]$Command)
    $Arguments = @('asr-commonvoice', $Command) + @((Get-CommonArguments) | Select-Object -Skip 1)
    & $CorePython $Launcher @Arguments
    if ($LASTEXITCODE -ne 0) { throw "ASR Common Voice $Command failed with exit code $LASTEXITCODE" }
}

switch ($Action) {
    'Audit' { Invoke-Core 'audit' }
    'Prepare' { Invoke-Core 'prepare' }
    'Plan' { Invoke-Core 'plan' }
    'Validate' { Invoke-Core 'validate' }
    'Status' { Invoke-Core 'status' }
    'Analyze' { Invoke-Core 'analyze' }
    'Collect' { Invoke-Core 'collect' }
    'Run' {
        Invoke-Core 'validate'
        $Runs = @(
            @{ Python = $OnnxPython; Component = 'sherpa_onnx' },
            @{ Python = $OnnxPython; Component = 'sherpa_onnx_libri_giga_zipformer_2023_06_21' },
            @{ Python = $CorePython; Component = 'whisper_small' }
        )
        $Failures = @()
        if ($ParallelModels -eq 1) {
            foreach ($Run in $Runs) {
                Write-Output "[RUN] $($Run.Component)"
                $Arguments = @('asr-commonvoice', 'run-backend') + @((Get-CommonArguments) | Select-Object -Skip 1) + @('--component-id', $Run.Component, '--parallel-models', '1')
                & $Run.Python $Launcher @Arguments
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "[FAILED; CONTINUING] $($Run.Component)"
                    $Failures += $Run.Component
                }
                else { Write-Output "[PASS] $($Run.Component)" }
            }
        }
        else {
            Write-Output "[PARALLEL] At most $ParallelModels model processes; each backend keeps its registered inference settings."
            $Pending = [System.Collections.Queue]::new()
            foreach ($Run in $Runs) { $Pending.Enqueue($Run) }
            $Active = @()
            while ($Pending.Count -gt 0 -or $Active.Count -gt 0) {
                while ($Pending.Count -gt 0 -and $Active.Count -lt $ParallelModels) {
                    $Run = $Pending.Dequeue()
                    $Arguments = @('asr-commonvoice', 'run-backend') + @((Get-CommonArguments) | Select-Object -Skip 1) + @('--component-id', $Run.Component, '--parallel-models', [string]$ParallelModels)
                    $ProcessArguments = @($Launcher) + $Arguments
                    $Quoted = @($ProcessArguments | ForEach-Object { '"' + ([string]$_).Replace('"', '\"') + '"' })
                    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
                    $StartInfo.FileName = $Run.Python
                    $StartInfo.Arguments = $Quoted -join ' '
                    $StartInfo.WorkingDirectory = $RepoRoot
                    $StartInfo.UseShellExecute = $false
                    $StartInfo.CreateNoWindow = $true
                    $Process = [System.Diagnostics.Process]::Start($StartInfo)
                    $Active += [pscustomobject]@{ Component = $Run.Component; Process = $Process }
                    Write-Output "[RUN PARALLEL] $($Run.Component) PID=$($Process.Id)"
                }
                $StillActive = @()
                foreach ($Entry in $Active) {
                    if ($Entry.Process.HasExited) {
                        $Entry.Process.WaitForExit()
                        if ($Entry.Process.ExitCode -eq 0) { Write-Output "[PASS] $($Entry.Component)" }
                        else {
                            Write-Warning "[FAILED; CONTINUING] $($Entry.Component) exit=$($Entry.Process.ExitCode)"
                            $Failures += $Entry.Component
                        }
                    }
                    else { $StillActive += $Entry }
                }
                $Active = $StillActive
                if ($Pending.Count -gt 0 -or $Active.Count -gt 0) { Start-Sleep -Seconds 2 }
            }
        }
        if ($Failures.Count -gt 0) { throw "Backend failure(s): $($Failures -join ', ')" }
        if ($AutoExport) {
            Write-Output '[AUTO EXPORT] Analyzing all three validated backends.'
            Invoke-Core 'analyze'
            Write-Output '[AUTO EXPORT] Collecting compact package and ZIP.'
            Invoke-Core 'collect'
        }
    }
}
