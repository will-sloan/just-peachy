[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("machine_a", "machine_b")]
    [string]$MachineId,

    [Parameter(Mandatory = $true)]
    [ValidateSet("cpu", "cuda")]
    [string]$Device,

    [string]$DatasetRoot = "",
    [switch]$Recreate
)

. (Join-Path $PSScriptRoot "worker_common.ps1")
trap {
    [Console]::Error.WriteLine("[FAIL] Worker setup: $($_.Exception.Message)")
    exit 2
}
$context = Get-ProductionWorkerContext -MachineId $MachineId -Device $Device
Assert-ProductionContextPaths -Context $context
$insideWorktree = @(& git -C $context.RepositoryRoot rev-parse --is-inside-work-tree 2>&1)
if ($LASTEXITCODE -ne 0 -or ($insideWorktree -join "").Trim() -ne "true") {
    throw "Production setup requires a valid Git checkout: $($context.RepositoryRoot)"
}
$worktreeChanges = @(& git -C $context.RepositoryRoot status --porcelain --untracked-files=all 2>&1)
if ($LASTEXITCODE -ne 0) {
    throw "Git status failed for the production checkout."
}
if ($worktreeChanges.Count -gt 0) {
    throw "Production setup requires a clean checkout. Preserve or commit local changes first."
}
Write-Host "[PASS] Repository checkout is clean: $(& git -C $context.RepositoryRoot rev-parse HEAD)"
$rawFolderName = "Raw Datasets (Not formatted)"
$localDatasetRoot = Join-Path $context.ProjectRoot $rawFolderName
$requiredFolders = @(
    "AMI Meeting Corpus", "CHiME 6", "CMU Arctic", "Hi Fi TTS",
    "LibreSpeech", "MIT 271 RIRs", "VOiCES"
)
$productionModelHashes = [ordered]@{
    "models\cache\whisper\tiny.pt" = "65147644A518D12F04E32D6F3B26FACC3F8DD46E5390956A9424A650C0CE22B9"
    "models\cache\whisper\base.pt" = "ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E"
    "models\cache\whisper\small.pt" = "9ECF779972D90BA49C06D968637D720DD632C55BBF19D441FB42BF17A411E794"
    "models\cache\speechbrain\spkrec-ecapa-voxceleb\embedding_model.ckpt" = "0575CB64845E6B9A10DB9BCB74D5AC32B326B8DC90352671D345E2EE3D0126A2"
}
$productionRirs = @(
    [pscustomobject]@{
        id = "dining_room_h025"
        relative_path = "MIT 271 RIRs\Audio\h025_Diningroom_8txts.wav"
        sha256 = "940D761A280DCD8FAAB077074E02BADE649E64E47461D80A4F927A01ABBEF5E2"
    },
    [pscustomobject]@{
        id = "restaurant_h093"
        relative_path = "MIT 271 RIRs\Audio\h093_Restaurant_2txts.wav"
        sha256 = "C2CA8A07002943409D31A2C6D6D07BA826AA428FE6EF6CECF2C4FF33D7D4A8A8"
    }
)

function Remove-InvalidProductionModelCache {
    $cacheRoot = [System.IO.Path]::GetFullPath((Join-Path $context.RepositoryRoot "models\cache"))
    $cachePrefix = $cacheRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    foreach ($entry in $productionModelHashes.GetEnumerator()) {
        $path = [System.IO.Path]::GetFullPath((Join-Path $context.RepositoryRoot $entry.Key))
        if (-not $path.StartsWith($cachePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to manage a production model outside the cache: $path"
        }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
        if ($actual -eq $entry.Value) {
            Write-Host "[PASS] Reusing verified production model: $($entry.Key)"
            continue
        }
        Remove-Item -LiteralPath $path -Force
        Write-Host "[INFO] Removed invalid production model for automatic reacquisition: $($entry.Key)"
    }
}

function Test-DatasetCandidate {
    param([Parameter(Mandatory = $true)][string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path)
    $missing = @($requiredFolders | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $full $_) -PathType Container)
    })
    foreach ($rir in $productionRirs) {
        $rirPath = Join-Path $full $rir.relative_path
        if (-not (Test-Path -LiteralPath $rirPath -PathType Leaf)) {
            $missing += $rir.relative_path
            continue
        }
        $actualRirHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $rirPath).Hash
        if ($actualRirHash -ne $rir.sha256) {
            $missing += "$($rir.relative_path) (SHA-256 mismatch; no substitution allowed)"
        }
    }
    return [pscustomobject]@{ Path = $full; Ready = $missing.Count -eq 0; Missing = @($missing) }
}

function Resolve-DatasetCandidate {
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($DatasetRoot) { $candidates.Add($DatasetRoot) }
    if ($env:JUST_PEACHY_DATASET_ROOT) { $candidates.Add($env:JUST_PEACHY_DATASET_ROOT) }
    $candidates.Add($localDatasetRoot)
    $cloneParent = Split-Path -Parent $context.RepositoryRoot
    foreach ($clone in Get-ChildItem -LiteralPath $cloneParent -Directory -ErrorAction SilentlyContinue) {
        if ($clone.FullName -ne $context.RepositoryRoot) {
            $candidates.Add((Join-Path $clone.FullName "Software Validation from Datasets\$rawFolderName"))
        }
    }
    $assessments = @()
    foreach ($candidate in $candidates | Select-Object -Unique) {
        $assessment = Test-DatasetCandidate -Path $candidate
        $assessments += $assessment
        if ($assessment.Ready) { return $assessment }
    }
    $details = @($assessments | ForEach-Object {
        "$($_.Path): missing $($_.Missing -join ', ')"
    }) -join [Environment]::NewLine
    throw "Licensed production datasets were not found. Supply -DatasetRoot once on this machine. Checked:$([Environment]::NewLine)$details"
}

$prepareArguments = @(
    "-ExecutionPolicy", "Bypass", "-File",
    (Join-Path $context.RepositoryRoot "scripts\prepare_execution_mode.ps1"),
    "-Mode", $Device, "-InstallFFmpeg", "-DownloadModels"
)
if ($Recreate) { $prepareArguments += "-Recreate" }
Remove-InvalidProductionModelCache
Invoke-ProductionChecked -FilePath "powershell" -Arguments $prepareArguments -WorkingDirectory $context.RepositoryRoot

$dataset = Resolve-DatasetCandidate
if ($dataset.Path -ne [System.IO.Path]::GetFullPath($localDatasetRoot)) {
    if (Test-Path -LiteralPath $localDatasetRoot) {
        $item = Get-Item -LiteralPath $localDatasetRoot -Force
        $children = @(Get-ChildItem -LiteralPath $localDatasetRoot -Force -ErrorAction SilentlyContinue)
        if ($item.LinkType -or $children.Count -gt 0) {
            throw "Local dataset path exists and cannot be replaced safely: $localDatasetRoot"
        }
        Remove-Item -LiteralPath $localDatasetRoot
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $localDatasetRoot) -Force | Out-Null
    New-Item -ItemType Junction -Path $localDatasetRoot -Target $dataset.Path | Out-Null
    Write-Host "[PASS] Linked licensed datasets: $localDatasetRoot -> $($dataset.Path)"
} else {
    Write-Host "[PASS] Licensed datasets are already available in this clone."
}

Invoke-ProductionChecked -FilePath $context.Python -Arguments @(
    "scripts\production_release.py", "materialize",
    "--device", $Device, "--machine-id", $MachineId, "--bind-current-commit"
) -WorkingDirectory $context.EvaluationRoot

$launchPackage = Join-Path $context.EvaluationRoot $(if ($Device -eq "cuda") {
    "configs\automated_evaluation\launch_package.gpu.v1.yaml"
} else {
    "configs\automated_evaluation\launch_package.v1.yaml"
})
$bindingReport = Join-Path $context.EvaluationRoot "artifacts\launch_readiness\${MachineId}_${Device}_release_binding.json"
Invoke-ProductionChecked -FilePath $context.Python -Arguments @(
    "scripts\validate_release_binding.py",
    "--campaign-root", $context.CampaignRoot,
    "--repository-root", $context.RepositoryRoot,
    "--environment-profile", $context.Profile,
    "--worker-id", $MachineId,
    "--launch-package", $launchPackage,
    "--output", $bindingReport
) -WorkingDirectory $context.EvaluationRoot

$reportRoot = Join-Path $context.EvaluationRoot "artifacts\production_setup"
New-Item -ItemType Directory -Path $reportRoot -Force | Out-Null
$releaseBindingPath = Join-Path $context.CampaignRoot "worker_assignments\release_binding.json"
$releaseBinding = Get-Content -Raw -LiteralPath $releaseBindingPath | ConvertFrom-Json
$selectedAssignment = $releaseBinding.assignments.$MachineId
$modelSpecs = @(
    [pscustomobject]@{ name = "whisper_tiny"; relative_path = "models\cache\whisper\tiny.pt" },
    [pscustomobject]@{ name = "whisper_base"; relative_path = "models\cache\whisper\base.pt" },
    [pscustomobject]@{ name = "whisper_small"; relative_path = "models\cache\whisper\small.pt" },
    [pscustomobject]@{ name = "speechbrain_ecapa"; relative_path = "models\cache\speechbrain\spkrec-ecapa-voxceleb\embedding_model.ckpt" }
)
$models = $modelSpecs | ForEach-Object {
    $path = Join-Path $context.RepositoryRoot $_.relative_path
    [ordered]@{
        name = $_.name
        path = $path
        bytes = (Get-Item -LiteralPath $path).Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    }
}
$rirs = $productionRirs | ForEach-Object {
    $path = Join-Path $localDatasetRoot $_.relative_path
    [ordered]@{
        id = $_.id
        path = $path
        bytes = (Get-Item -LiteralPath $path).Length
        sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    }
}
$report = [ordered]@{
    schema_version = "production-worker-setup.v1"
    completed_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    machine_id = $MachineId
    device = $Device
    environment_profile = $context.Profile
    python = $context.Python
    dataset_root = $localDatasetRoot
    dataset_source = $dataset.Path
    production_models = $models
    production_rirs = $rirs
    packaged_model_components = @(
        [ordered]@{ name = "silero_vad"; source = "pinned silero-vad Python package" }
    )
    campaign_id = $context.CampaignId
    campaign_manifest_sha256 = $releaseBinding.campaign_manifest_sha256
    release_binding_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $releaseBindingPath).Hash
    assignment_id = $selectedAssignment.assignment_id
    assignment_sha256 = $selectedAssignment.assignment_sha256
    assigned_scenario_count = $selectedAssignment.scenario_count
    credentials_required = @()
    status = "PASS"
}
$reportPath = Join-Path $reportRoot "${MachineId}_${Device}.json"
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding utf8
Write-Host "[PASS] Worker setup complete: $MachineId / $Device"
Write-Host "Setup report: $reportPath"
