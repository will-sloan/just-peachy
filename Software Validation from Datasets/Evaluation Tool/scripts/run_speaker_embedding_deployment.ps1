[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Validate', 'Run', 'Status', 'Analyze', 'Collect')]
    [string]$Action = 'Plan',
    [string]$Config = '',
    [string]$ResultRoot = '',
    [string]$AnalysisRoot = '',
    [string]$CollectionRoot = '',
    [ValidateRange(1, 4)]
    [int]$ParallelModels = 2,
    [switch]$AutoExport,
    [switch]$NoZip
)

$ErrorActionPreference = 'Stop'
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$Launcher = Join-Path $ToolRoot 'run_evaluation.py'
if (-not $Config) { $Config = Join-Path $ToolRoot 'configs\automated_evaluation\speaker_embedding_deployment.v1.yaml' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw "Management environment is missing: $Python" }

function Get-Arguments {
    param([string]$Command)
    $Values = @('speaker-deployment', $Command, '--config', $Config)
    if ($ResultRoot) { $Values += @('--result-root', $ResultRoot) }
    if ($AnalysisRoot) { $Values += @('--analysis-root', $AnalysisRoot) }
    if ($CollectionRoot) { $Values += @('--collection-root', $CollectionRoot) }
    if ($NoZip) { $Values += '--no-zip' }
    return $Values
}

function Invoke-Study {
    param([string]$Command)
    & $Python $Launcher @(Get-Arguments $Command)
    if ($LASTEXITCODE -ne 0) { throw "Speaker deployment $Command failed with exit code $LASTEXITCODE" }
}

switch ($Action) {
    'Plan' { Invoke-Study 'plan' }
    'Validate' { Invoke-Study 'validate' }
    'Status' { Invoke-Study 'status' }
    'Analyze' { Invoke-Study 'analyze' }
    'Collect' { Invoke-Study 'collect' }
    'Run' {
        Invoke-Study 'validate'
        $BackendText = & $Python -c "import sys,yaml; print(','.join(yaml.safe_load(open(sys.argv[1], encoding='utf-8'))['backends']))" $Config
        $Backends = @(([string]$BackendText).Split(',') | Where-Object { $_ })
        if ($LASTEXITCODE -ne 0 -or $Backends.Count -eq 0) { throw 'Could not read frozen backend list.' }
        $Pending = [System.Collections.Queue]::new()
        foreach ($Backend in $Backends) { $Pending.Enqueue([string]$Backend) }
        $Active = @()
        $Failures = @()
        while ($Pending.Count -gt 0 -or $Active.Count -gt 0) {
            while ($Pending.Count -gt 0 -and $Active.Count -lt $ParallelModels) {
                $Backend = $Pending.Dequeue()
                $Arguments = @(Get-Arguments 'run-backend') + @('--backend', $Backend)
                $Quoted = @($Launcher) + $Arguments | ForEach-Object { '"' + ([string]$_).Replace('"', '\"') + '"' }
                $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
                $StartInfo.FileName = $Python
                $StartInfo.Arguments = $Quoted -join ' '
                $StartInfo.WorkingDirectory = $RepoRoot
                $StartInfo.UseShellExecute = $false
                $StartInfo.CreateNoWindow = $true
                $StartInfo.EnvironmentVariables['OMP_NUM_THREADS'] = '1'
                $StartInfo.EnvironmentVariables['MKL_NUM_THREADS'] = '1'
                $Process = [System.Diagnostics.Process]::Start($StartInfo)
                $Active += [pscustomobject]@{ Backend = $Backend; Process = $Process }
                Write-Output "[RUN PARALLEL] $Backend PID=$($Process.Id)"
            }
            $StillActive = @()
            foreach ($Entry in $Active) {
                if ($Entry.Process.HasExited) {
                    $Entry.Process.WaitForExit()
                    if ($Entry.Process.ExitCode -eq 0) { Write-Output "[PASS] $($Entry.Backend)" }
                    else {
                        Write-Warning "[FAIL] $($Entry.Backend) exit=$($Entry.Process.ExitCode)"
                        $Failures += $Entry.Backend
                    }
                }
                else { $StillActive += $Entry }
            }
            $Active = $StillActive
            if ($Pending.Count -gt 0 -or $Active.Count -gt 0) { Start-Sleep -Seconds 1 }
        }
        if ($Failures.Count -gt 0) { throw "Backend replay failure(s): $($Failures -join ', ')" }
        if ($AutoExport) {
            Invoke-Study 'analyze'
            Invoke-Study 'collect'
        }
    }
}
