[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Diagnose', 'Configure', 'MaterializeData', 'VerifyData', 'BootstrapEnvironment', 'VerifyModels', 'Qualify', 'Summary')]
    [string]$Action,

    [string]$WslDistro,
    [string]$RepoRoot,
    [string]$DataRoot,
    [string]$TrainingRoot,
    [string]$ModelRoot,
    [string]$RunRoot,
    [switch]$Apply
)

$ErrorActionPreference = 'Stop'
$DefaultRepo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$Roots = [ordered]@{
    JP_REPO_ROOT = if ($RepoRoot) { $RepoRoot } elseif ($env:JP_REPO_ROOT) { $env:JP_REPO_ROOT } else { $DefaultRepo }
    JP_DATA_ROOT = if ($DataRoot) { $DataRoot } elseif ($env:JP_DATA_ROOT) { $env:JP_DATA_ROOT } else { Join-Path $DefaultRepo 'Software Validation from Datasets' }
    JP_TRAINING_ROOT = if ($TrainingRoot) { $TrainingRoot } elseif ($env:JP_TRAINING_ROOT) { $env:JP_TRAINING_ROOT } else { Join-Path $DefaultRepo 'training' }
    JP_MODEL_ROOT = if ($ModelRoot) { $ModelRoot } elseif ($env:JP_MODEL_ROOT) { $env:JP_MODEL_ROOT } else { Join-Path $DefaultRepo 'models' }
    JP_RUN_ROOT = if ($RunRoot) { $RunRoot } elseif ($env:JP_RUN_ROOT) { $env:JP_RUN_ROOT } else { Join-Path $DefaultRepo 'training\runs' }
}
foreach ($Pair in $Roots.GetEnumerator()) { Set-Item -Path "Env:$($Pair.Key)" -Value $Pair.Value }
if ($WslDistro) { $env:JP_WSL_DISTRO = $WslDistro }

$Python = Join-Path $Roots.JP_REPO_ROOT '.venv\Scripts\python.exe'
$ToolRoot = Join-Path $Roots.JP_REPO_ROOT 'Software Validation from Datasets\Training Tool'

function Get-ValidatedWslDistro {
    if ($env:JP_WSL_DISTRO) { $Name = $env:JP_WSL_DISTRO }
    else {
        # Windows PowerShell can expose wsl.exe's UTF-16 output with embedded
        # NUL characters. Normalize it before looking for the default marker.
        $WslLines = @(& wsl.exe --list --verbose) | ForEach-Object { $_ -replace "`0", '' }
        $Default = $WslLines | Where-Object { $_.TrimStart().StartsWith('*') }
        if (@($Default).Count -ne 1) { throw 'Set -WslDistro or JP_WSL_DISTRO; no unique WSL default was found.' }
        $Name = (($Default -replace '^\s*\*\s*', '') -split '\s+')[0]
    }
    & wsl.exe -d $Name -- test -x /usr/bin/wslpath
    if ($LASTEXITCODE -ne 0) { throw "WSL distro lacks /usr/bin/wslpath: $Name" }
    return $Name
}

function Convert-ToWslPath([string]$Path, [string]$Distro) {
    $ForwardSlashPath = $Path.Replace('\', '/')
    $Converted = & wsl.exe -d $Distro -- wslpath -u -a $ForwardSlashPath
    if ($LASTEXITCODE -ne 0 -or -not $Converted.StartsWith('/')) { throw "wslpath failed for: $Path" }
    return $Converted.Trim()
}

switch ($Action) {
    'Diagnose' {
        $Distro = Get-ValidatedWslDistro
        $Gpu = & wsl.exe -d $Distro -- nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
        [ordered]@{ WSL_DISTRO = $Distro; WSLPATH = 'VALID'; GPU = $Gpu; ROOTS = $Roots; APPLY = $Apply.IsPresent } | ConvertTo-Json -Depth 4
    }
    'Configure' {
        $PreferredCv = Join-Path $Roots.JP_DATA_ROOT 'Raw Datasets (Not formatted)\Common Voice\cv-corpus-26.0-2026-06-12\prepared\en'
        $LegacyCv = Join-Path $Roots.JP_TRAINING_ROOT 'datasets\common_voice\english\cv-corpus-26.0-2026-06-12\prepared\en'
        if ($Apply) {
            foreach ($Pair in $Roots.GetEnumerator()) {
                New-Item -ItemType Directory -Path $Pair.Value -Force | Out-Null
                [Environment]::SetEnvironmentVariable($Pair.Key, $Pair.Value, 'User')
            }
            if ($env:JP_WSL_DISTRO) { [Environment]::SetEnvironmentVariable('JP_WSL_DISTRO', $env:JP_WSL_DISTRO, 'User') }
            if ((Test-Path -LiteralPath $PreferredCv -PathType Container) -and -not (Test-Path -LiteralPath $LegacyCv)) {
                New-Item -ItemType Directory -Path (Split-Path $LegacyCv -Parent) -Force | Out-Null
                New-Item -ItemType Junction -Path $LegacyCv -Target $PreferredCv | Out-Null
            }
        }
        [ordered]@{ ACTION = 'Configure'; APPLY = $Apply.IsPresent; ROOTS = $Roots; COMMON_VOICE_ALIAS = [ordered]@{ LEGACY = $LegacyCv; PREFERRED = $PreferredCv } } | ConvertTo-Json -Depth 5
    }
    'MaterializeData' {
        if (-not (Test-Path -LiteralPath $Python)) { throw "Python is unavailable: $Python" }
        $Parent = Join-Path $Roots.JP_TRAINING_ROOT 'registries\training_data_freeze_manifest.json'
        $Corrected = Join-Path $Roots.JP_TRAINING_ROOT 'successors\ami_cc_by_4_0_2017_04_10'
        if (-not $Apply) {
            [ordered]@{
                ACTION = 'MaterializeData'
                APPLY = $false
                NOTE = 'Use -Apply only after every external dataset and the pinned Common Voice archive are present.'
                STEPS = @('Phase2', 'AMI licence-correction successor', 'Common Voice Phase3 selective materialization', 'shared-root consolidation', 'Phase4', 'portable successor')
            } | ConvertTo-Json -Depth 4
            break
        }
        Push-Location $ToolRoot
        try {
            & $Python -m training_data.cli build
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.cli build --output-root $Corrected --parent-freeze $Parent --correction-reason ami_cc_by_4_0_relicensing_2017_04_10
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.cli verify-freeze --path (Join-Path $Corrected 'registries\training_data_freeze_manifest.json')
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.common_voice phase3-run
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & (Join-Path $PSScriptRoot 'consolidate_common_voice_assets.ps1') -Action Apply
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.common_voice phase3-verify
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.phase4 run
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.phase4 verify
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.handoff build-successor
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.handoff verify-successor
            exit $LASTEXITCODE
        } finally { Pop-Location }
    }
    'VerifyData' {
        if (-not (Test-Path -LiteralPath $Python)) { throw "Python is unavailable: $Python" }
        Push-Location $ToolRoot
        try {
            & $Python -m training_data.common_voice phase3-verify
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.phase4 verify
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.asset_layout verify
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & $Python -m training_data.handoff build-successor
            exit $LASTEXITCODE
        } finally { Pop-Location }
    }
    'BootstrapEnvironment' {
        $Distro = Get-ValidatedWslDistro
        $Script = Convert-ToWslPath (Join-Path $PSScriptRoot 'bootstrap_wsl_training_environment.sh') $Distro
        $WslRepo = Convert-ToWslPath $Roots.JP_REPO_ROOT $Distro
        if (-not $Apply) {
            [ordered]@{ ACTION = 'BootstrapEnvironment'; APPLY = $false; DISTRO = $Distro; SCRIPT = $Script; JP_REPO_ROOT = $WslRepo } | ConvertTo-Json
        } else {
            if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
                $Launcher = Get-Command py.exe -ErrorAction SilentlyContinue
                if ($Launcher) { & $Launcher.Source -3.11 -m venv (Join-Path $Roots.JP_REPO_ROOT '.venv') }
                else { & python.exe -m venv (Join-Path $Roots.JP_REPO_ROOT '.venv') }
                if ($LASTEXITCODE -ne 0) { throw 'Could not create the Windows control environment.' }
            }
            & $Python -m pip install -r (Join-Path $ToolRoot 'requirements.handoff_control.txt')
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
            & wsl.exe -d $Distro -- env "JP_REPO_ROOT=$WslRepo" bash $Script
            exit $LASTEXITCODE
        }
    }
    'VerifyModels' {
        if (-not (Test-Path -LiteralPath $Python)) { throw "Python is unavailable: $Python" }
        Push-Location $ToolRoot
        try { & $Python -m training_data.handoff verify-models; exit $LASTEXITCODE } finally { Pop-Location }
    }
    'Qualify' {
        if (-not $Apply) {
            [ordered]@{ ACTION = 'Qualify'; APPLY = $false; NOTE = 'Use -Apply on the RTX 3090 to run the two bounded canaries.' } | ConvertTo-Json
        } else {
            & (Join-Path $PSScriptRoot 'run_adapter_research.ps1') -Action Qualify -WslDistro $WslDistro
            exit $LASTEXITCODE
        }
    }
    'Summary' {
        [ordered]@{
            ROOTS = $Roots
            WSL_DISTRO = if ($env:JP_WSL_DISTRO) { $env:JP_WSL_DISTRO } else { 'runtime discovery' }
            DEFAULT_MAX_PARALLEL_ADAPTER_JOBS = 1
            GPU_LARGE_EVALUATION_CONCURRENT_WITH_TRAINING = $false
            NEXT = @('BootstrapEnvironment -Apply', 'MaterializeData -Apply', 'VerifyData', 'VerifyModels', 'Qualify -Apply', 'Plan', 'Estimate')
        } | ConvertTo-Json -Depth 5
    }
}
