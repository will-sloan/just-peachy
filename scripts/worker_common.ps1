Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Initialize-ProductionProcessPath {
    # A parent terminal does not automatically inherit PATH changes made by a
    # nested WinGet process. Refresh every high-level command from the current
    # machine/user values so setup can be followed immediately by verification.
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machinePath;$userPath;$env:Path"
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { return }

    $wingetLinks = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
    if (Test-Path -LiteralPath (Join-Path $wingetLinks "ffmpeg.exe") -PathType Leaf) {
        $env:Path = "$wingetLinks;$env:Path"
        return
    }
    $packageRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    $candidate = Get-ChildItem -Path (Join-Path $packageRoot "Gyan.FFmpeg_*\ffmpeg-*\bin\ffmpeg.exe") `
        -File -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($candidate) {
        $env:Path = "$($candidate.DirectoryName);$env:Path"
    }
}

Initialize-ProductionProcessPath

function Get-ProductionWorkerContext {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("machine_a", "machine_b")]
        [string]$MachineId,

        [Parameter(Mandatory = $true)]
        [ValidateSet("cpu", "cuda")]
        [string]$Device
    )

    $repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
    $projectRoot = Join-Path $repositoryRoot "Software Validation from Datasets"
    $evaluationRoot = Join-Path $projectRoot "Evaluation Tool"
    if ($Device -eq "cuda") {
        $python = Join-Path $repositoryRoot ".stage8-envs\core-cuda\Scripts\python.exe"
        $profile = "core-cuda"
        $campaignId = "campaign_06_massive_release_cuda"
        $launchSuffix = "_gpu"
    } else {
        $python = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
        $profile = "core-cpu"
        $campaignId = "campaign_05_massive_release"
        $launchSuffix = ""
    }
    $workerName = if ($MachineId -eq "machine_a") { "machine_a" } else { "machine_b" }
    return [pscustomobject]@{
        MachineId = $MachineId
        WorkerName = $workerName
        Device = $Device
        Profile = $profile
        CampaignId = $campaignId
        RepositoryRoot = $repositoryRoot
        ProjectRoot = $projectRoot
        EvaluationRoot = $evaluationRoot
        Python = $python
        CampaignRoot = Join-Path $evaluationRoot "automated_runs\$campaignId"
        Assignment = Join-Path $evaluationRoot "automated_runs\$campaignId\worker_assignments\$workerName.yaml"
        LaunchScript = Join-Path $evaluationRoot "scripts\launch_campaign_${workerName}${launchSuffix}.ps1"
        ExportScript = Join-Path $evaluationRoot "scripts\export_${workerName}${launchSuffix}_results.ps1"
        MergeScript = Join-Path $evaluationRoot $(if ($Device -eq "cuda") { "scripts\merge_gpu_campaign.ps1" } else { "scripts\merge_massive_campaign.ps1" })
        AnalyzeScript = Join-Path $evaluationRoot $(if ($Device -eq "cuda") { "scripts\analyze_gpu_campaign.ps1" } else { "scripts\analyze_massive_campaign.ps1" })
    }
}

function Invoke-ProductionChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string]$WorkingDirectory = ""
    )

    if ($WorkingDirectory) { Push-Location $WorkingDirectory }
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
        }
    } finally {
        if ($WorkingDirectory) { Pop-Location }
    }
}

function Assert-ProductionContextPaths {
    param([Parameter(Mandatory = $true)]$Context)
    foreach ($required in @($Context.RepositoryRoot, $Context.ProjectRoot, $Context.EvaluationRoot)) {
        if (-not (Test-Path -LiteralPath $required -PathType Container)) {
            throw "Required production path is missing: $required"
        }
    }
}
