[CmdletBinding()]
param(
    [ValidateSet('ValidateFreeze','PrepareReduced','RunAccuracy','ValidateAccuracy','PrepareResources','RunResources','ValidateResources','Analyze','Collect','UpdateProgramState','RunAll','ValidateCompletion','Status','Stop')]
    [string]$Action = 'Status',
    [string]$WorkspaceRoot,
    [string]$Prompt4Marker,
    [string]$AmendmentPath,
    [string]$ProgramStatePath,
    [string]$PiDeploymentSteeringPath,
    [ValidateRange(1,2)]
    [int]$ParallelJobs = 2,
    [string]$PredecessorRecord,
    [string]$AdapterId,
    [string]$AdapterContractSha256
)

$ErrorActionPreference = 'Stop'
$InvocationRoot = (Get-Location).Path
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository Python is unavailable: $Python"
}
if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Join-Path $ToolRoot 'automated_runs\full_pipeline_core_evaluation_reduced_8day_v1'
} elseif (-not [System.IO.Path]::IsPathRooted($WorkspaceRoot)) {
    $WorkspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $WorkspaceRoot))
}
if ([string]::IsNullOrWhiteSpace($AmendmentPath)) {
    $AmendmentPath = Join-Path $ToolRoot 'runs\full_pipeline_program\EIGHT_DAY_SCOPE_AMENDMENT.json'
} elseif (-not [System.IO.Path]::IsPathRooted($AmendmentPath)) {
    $AmendmentPath = [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $AmendmentPath))
}
if ([string]::IsNullOrWhiteSpace($ProgramStatePath)) {
    $ProgramStatePath = Join-Path $ToolRoot 'runs\full_pipeline_program\PROGRAM_STATE.json'
} elseif (-not [System.IO.Path]::IsPathRooted($ProgramStatePath)) {
    $ProgramStatePath = [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $ProgramStatePath))
}
if ([string]::IsNullOrWhiteSpace($PiDeploymentSteeringPath)) {
    $PiDeploymentSteeringPath = Join-Path $ToolRoot 'runs\full_pipeline_program\RASPBERRY_PI_DEPLOYMENT_STEERING.json'
} elseif (-not [System.IO.Path]::IsPathRooted($PiDeploymentSteeringPath)) {
    $PiDeploymentSteeringPath = [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $PiDeploymentSteeringPath))
}

$PathsToCheck = @($WorkspaceRoot, $AmendmentPath, $ProgramStatePath, $PiDeploymentSteeringPath)
if (-not [string]::IsNullOrWhiteSpace($Prompt4Marker)) {
    if (-not [System.IO.Path]::IsPathRooted($Prompt4Marker)) {
        $Prompt4Marker = [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $Prompt4Marker))
    }
    $PathsToCheck += $Prompt4Marker
}
if (-not [string]::IsNullOrWhiteSpace($PredecessorRecord)) {
    if (-not [System.IO.Path]::IsPathRooted($PredecessorRecord)) {
        $PredecessorRecord = [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $PredecessorRecord))
    }
    $PathsToCheck += $PredecessorRecord
}
foreach ($PathToCheck in $PathsToCheck) {
    $ResolvedForDrive = [System.IO.Path]::GetFullPath($PathToCheck)
    if ([System.IO.Path]::GetPathRoot($ResolvedForDrive) -ne 'C:\') {
        throw "Prompt 5 is C:-only; rejected path: $ResolvedForDrive"
    }
}

$StageTemp = Join-Path $WorkspaceRoot 'temp'
New-Item -ItemType Directory -Force -Path $StageTemp | Out-Null
$env:TEMP = $StageTemp
$env:TMP = $StageTemp

$ActionMap = @{
    ValidateFreeze='validate-freeze'; PrepareReduced='prepare-reduced'
    RunAccuracy='run-accuracy'; ValidateAccuracy='validate-accuracy'
    PrepareResources='prepare-resources'; RunResources='run-resources'
    ValidateResources='validate-resources'; Analyze='analyze'; Collect='collect'
    UpdateProgramState='update-program-state'; RunAll='run-all'
    ValidateCompletion='validate-completion'; Status='status'; Stop='stop'
}
$Arguments = @(
    '-m', 'app.full_pipeline_core_evaluation', $ActionMap[$Action],
    '--workspace-root', $WorkspaceRoot,
    '--amendment-path', $AmendmentPath,
    '--program-state-path', $ProgramStatePath,
    '--pi-deployment-steering-path', $PiDeploymentSteeringPath
)
if (-not [string]::IsNullOrWhiteSpace($Prompt4Marker)) {
    $Arguments += @('--prompt4-marker', $Prompt4Marker)
}
if ($Action -in @('RunAccuracy','RunAll')) {
    $Arguments += @('--parallel-jobs', [string]$ParallelJobs)
}
if (-not [string]::IsNullOrWhiteSpace($PredecessorRecord)) {
    $Arguments += @('--predecessor-record', $PredecessorRecord)
}
if (-not [string]::IsNullOrWhiteSpace($AdapterId)) {
    $Arguments += @('--adapter-id', $AdapterId)
}
if (-not [string]::IsNullOrWhiteSpace($AdapterContractSha256)) {
    $Arguments += @('--adapter-contract-sha256', $AdapterContractSha256)
}

Push-Location $ToolRoot
try {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Prompt-5 core evaluation action failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
