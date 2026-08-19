[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('BenchmarkProtocol', 'RecordBenchmark', 'Run', 'Status')]
    [string]$Action,

    [string[]]$ExperimentId,
    [ValidateSet(1, 2)]
    [int]$MaxParallelAdapterJobs = 1,
    [string]$MetricsPath,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = if ($env:JP_REPO_ROOT) {
    (Resolve-Path -LiteralPath $env:JP_REPO_ROOT).Path
} else {
    (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
}
$ToolRoot = Join-Path $RepositoryRoot 'Software Validation from Datasets\Training Tool'
$Python = Join-Path $RepositoryRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository Python environment is unavailable: $Python"
}

Push-Location $ToolRoot
try {
    switch ($Action) {
        'BenchmarkProtocol' {
            & $Python -m training_data.parallel_adapter benchmark-protocol
        }
        'RecordBenchmark' {
            if (-not $MetricsPath) { throw '-MetricsPath is required.' }
            & $Python -m training_data.parallel_adapter record-benchmark --metrics $MetricsPath
        }
        'Status' {
            & $Python -m training_data.parallel_adapter status
        }
        'Run' {
            if (-not $ExperimentId) { throw '-ExperimentId is required.' }
            $Arguments = @('-m', 'training_data.parallel_adapter', 'run', '--max-parallel', $MaxParallelAdapterJobs)
            foreach ($IdValue in $ExperimentId) {
                foreach ($Id in $IdValue.Split(',', [System.StringSplitOptions]::RemoveEmptyEntries)) {
                    $Arguments += @('--experiment-id', $Id.Trim())
                }
            }
            if ($Apply) { $Arguments += '--apply' }
            & $Python @Arguments
        }
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
