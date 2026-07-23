$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
$WorkspaceRoot = Split-Path -Parent $ProjectRoot

function Move-ToTimestampedBackup {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $backupName = "{0}_{1}" -f $Label, (Get-Date -Format "yyyyMMdd_HHmmss")
    $backupPath = Join-Path $ProjectRoot $backupName
    Move-Item -LiteralPath $Path -Destination $backupPath
    Write-Host "Moved $Path to $backupPath"
    return $backupPath
}

function Get-RelativeProjectPath {
    param(
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    $projectFull = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd('\') + '\'
    $targetFull = (Resolve-Path -LiteralPath $TargetPath).Path
    if (Test-Path -LiteralPath $TargetPath -PathType Container) {
        $targetFull = $targetFull.TrimEnd('\') + '\'
    }
    $projectUri = [Uri]$projectFull
    $targetUri = [Uri]$targetFull
    $relative = [Uri]::UnescapeDataString($projectUri.MakeRelativeUri($targetUri).ToString()).Replace('\', '/')
    return $relative.TrimEnd('/')
}

function Find-UniqueReleaseFile {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Description,
        [string[]]$PreferredPattern = @()
    )

    $matches = @(Get-ChildItem -LiteralPath $WorkspaceRoot -Filter $Name -File -Recurse -ErrorAction SilentlyContinue)
    if ($matches.Count -eq 0) {
        throw "$Description was not found below $WorkspaceRoot. Copy the complete just-peachy folder, including the XMOS release folders."
    }

    foreach ($pattern in $PreferredPattern) {
        $preferred = @($matches | Where-Object { $_.FullName -match $pattern })
        if ($preferred.Count -eq 1) { return $preferred[0] }
        if ($preferred.Count -gt 1) {
            $paths = ($preferred | ForEach-Object FullName) -join "`n  "
            throw "$Description has multiple preferred matches:`n  $paths"
        }
    }

    if ($matches.Count -gt 1) {
        $paths = ($matches | ForEach-Object FullName) -join "`n  "
        throw "$Description has multiple matches. Update the discovery rule or remove only the unwanted duplicate release copy:`n  $paths"
    }
    return $matches[0]
}

function Get-XmosTuningDirectory {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot
    )

    $expected = Join-Path $SourceRoot "modules\fwk_xvf\modules\tuning"
    if (Test-Path -LiteralPath $expected -PathType Container) { return (Get-Item -LiteralPath $expected) }

    $matches = @(Get-ChildItem -LiteralPath $SourceRoot -Directory -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "tuning" -and (Test-Path -LiteralPath (Join-Path $_.FullName "__init__.py")) })
    if ($matches.Count -eq 1) { return $matches[0] }
    if ($matches.Count -eq 0) { throw "The XMOS tuning Python module was not found below $SourceRoot." }
    $paths = ($matches | ForEach-Object FullName) -join "`n  "
    throw "Multiple XMOS tuning Python modules were found. Resolve the release layout before running tests:`n  $paths"
}

$pythonVersion = (& py -3.10 --version 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $pythonVersion -notmatch "Python 3\.10\.") {
    throw "Python 3.10 is required. py -3.10 --version returned: $pythonVersion"
}

$venvPath = Join-Path $ProjectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$recreateVenv = $false
if (Test-Path -LiteralPath $venvPath -PathType Container) {
    if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        Move-ToTimestampedBackup -Path $venvPath -Label ".venv_incomplete" | Out-Null
    } else {
        $venvCheck = (& $venvPython -c "import sys; print(sys.version_info[0]); print(sys.version_info[1]); print(sys.executable)" 2>&1 | Out-String).Trim()
        $venvCheckExit = $LASTEXITCODE
        $venvCfg = Join-Path $venvPath "pyvenv.cfg"
        $venvHomeMissing = $false
        if (Test-Path -LiteralPath $venvCfg) {
            $homeLine = Select-String -LiteralPath $venvCfg -Pattern '^home\s*=\s*(.+)$' | Select-Object -First 1
            if ($homeLine) {
                $venvHome = $homeLine.Matches[0].Groups[1].Value.Trim()
                if (-not (Test-Path -LiteralPath (Join-Path $venvHome "python.exe") -PathType Leaf)) { $venvHomeMissing = $true }
            }
        }
        if ($venvCheckExit -ne 0 -or $venvCheck -notmatch '(?m)^3\r?\n10\r?\n' -or $venvHomeMissing) {
            $recreateVenv = $true
        }
    }
}
if ($recreateVenv -and (Test-Path -LiteralPath $venvPath)) {
    Move-ToTimestampedBackup -Path $venvPath -Label ".venv_stale" | Out-Null
}
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    & py -3.10 -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw "py -3.10 -m venv failed with exit code $LASTEXITCODE" }
}

& $venvPython --version
if ($LASTEXITCODE -ne 0) { throw "The project virtual environment cannot run: $venvPython" }

$xvfHost = Find-UniqueReleaseFile -Name "xvf_host.exe" -Description "xvf_host.exe" -PreferredPattern @("XVF3800-Binary_v3_2_1", "v3[._-]?2[._-]?1")
$xvfTools = Find-UniqueReleaseFile -Name "xvf_tools.py" -Description "xvf_tools.py" -PreferredPattern @("[\\/]sources[\\/]xvf_tools\.py")
$xmosSourceRoot = $xvfTools.Directory.FullName
$xmosTuning = Get-XmosTuningDirectory -SourceRoot $xmosSourceRoot
Write-Host "Discovered xvf_host.exe: $($xvfHost.FullName)"
Write-Host "Discovered xvf_tools.py: $($xvfTools.FullName)"
Write-Host "Discovered XMOS source root: $xmosSourceRoot"
Write-Host "Discovered XMOS tuning module: $($xmosTuning.FullName)"

$configPath = Join-Path $ProjectRoot "config.json"
$examplePath = Join-Path $ProjectRoot "config.example.json"
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    if (-not (Test-Path -LiteralPath $examplePath -PathType Leaf)) { throw "Neither config.json nor config.example.json exists." }
    Copy-Item -LiteralPath $examplePath -Destination $configPath
    Write-Host "Created config.json from config.example.json"
} else {
    Copy-Item -LiteralPath $configPath -Destination (Join-Path $ProjectRoot ("config_backup_{0}.json" -f (Get-Date -Format "yyyyMMdd_HHmmss")))
}

try {
    $configData = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
} catch {
    throw "config.json is not valid JSON: $($_.Exception.Message)"
}

# Keep machine-specific locations out of the copied project. The runner resolves these paths
# relative to config.json, so the same config works under any username, drive, or clone path.
$configData.workspace_root = Get-RelativeProjectPath -TargetPath $WorkspaceRoot
$configData.xvf_host_path = Get-RelativeProjectPath -TargetPath $xvfHost.FullName
$configData.xvf_tools_path = Get-RelativeProjectPath -TargetPath $xvfTools.FullName
$configData.python_executable = ".venv/Scripts/python.exe"
$configData.xmos_source_root = Get-RelativeProjectPath -TargetPath $xmosSourceRoot
$configData.xmos_pythonpath = Get-RelativeProjectPath -TargetPath $xmosTuning.FullName
$configJson = $configData | ConvertTo-Json -Depth 10
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($configPath, $configJson, $utf8NoBom)
Write-Host "Normalized config.json to portable project-relative paths."

New-Item -ItemType Directory -Path (Join-Path $ProjectRoot "setup_logs") -Force | Out-Null
$ErrorActionPreference = "Continue"
& $venvPython -m pip install --upgrade pip setuptools wheel 2>&1 | Tee-Object -FilePath (Join-Path $ProjectRoot "setup_logs\pip_tools_upgrade.log")
$pipToolsExit = $LASTEXITCODE
& $venvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt") 2>&1 | Tee-Object -FilePath (Join-Path $ProjectRoot "setup_logs\pip_requirements_install.log")
$pipRequirementsExit = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($pipToolsExit -ne 0) { throw "pip packaging-tool upgrade failed with exit code $pipToolsExit" }
if ($pipRequirementsExit -ne 0) { throw "requirements.txt installation failed with exit code $pipRequirementsExit" }

& $venvPython -m pip freeze | Tee-Object -FilePath (Join-Path $ProjectRoot "environment_freeze.txt")
if ($LASTEXITCODE -ne 0) { throw "pip freeze failed with exit code $LASTEXITCODE" }

Write-Host "Environment ready: $venvPython"
Write-Host "List devices: & `"$venvPython`" `"$ProjectRoot\xvf_test_runner.py`" devices --config `"$configPath`""
