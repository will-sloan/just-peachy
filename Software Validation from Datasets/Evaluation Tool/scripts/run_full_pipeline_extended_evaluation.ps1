[CmdletBinding()]
param(
    [ValidateSet(
        'ValidatePrerequisite','Prepare','RunAccuracy','RunResources',
        'ValidateTerminal','Analyze','Collect','Finalize','RunAll',
        'ValidateCompletion','Status','Stop'
    )]
    [string]$Action = 'Status',
    [string]$WorkspaceRoot,
    [string]$PredecessorRecord,
    [string]$PredecessorSha256,
    [string]$AmendmentPath,
    [string]$ProgramStatePath,
    [string]$PiDeploymentSteeringPath,
    [string]$PiDeploymentSteeringSha256,
    [ValidateRange(1,2)]
    [int]$ParallelJobs = 2,
    [string]$AdapterId,
    [string]$AdapterContractSha256,
    [string]$CompletionRecord
)

$ErrorActionPreference = 'Stop'
$InvocationRoot = (Get-Location).Path
$ToolRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepoRoot = (Resolve-Path (Join-Path $ToolRoot '..\..')).Path
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Repository Python is unavailable: $Python"
}

function Resolve-InvocationPath([string]$Value) {
    if ([System.IO.Path]::IsPathRooted($Value)) {
        return [System.IO.Path]::GetFullPath($Value)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $Value))
}

if ([string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $WorkspaceRoot = Join-Path $ToolRoot 'automated_runs\full_pipeline_extended_evaluation_reduced_8day_v1'
}
if ([string]::IsNullOrWhiteSpace($AmendmentPath)) {
    $AmendmentPath = Join-Path $ToolRoot 'runs\full_pipeline_program\EIGHT_DAY_SCOPE_AMENDMENT.json'
}
if ([string]::IsNullOrWhiteSpace($ProgramStatePath)) {
    $ProgramStatePath = Join-Path $ToolRoot 'runs\full_pipeline_program\PROGRAM_STATE.json'
}
if ([string]::IsNullOrWhiteSpace($PiDeploymentSteeringPath)) {
    $PiDeploymentSteeringPath = [Environment]::GetEnvironmentVariable('JP8_PI_DEPLOYMENT_STEERING_PATH')
}
if ([string]::IsNullOrWhiteSpace($PiDeploymentSteeringPath)) {
    $PiDeploymentSteeringPath = Join-Path $ToolRoot 'runs\full_pipeline_program\RASPBERRY_PI_DEPLOYMENT_STEERING.json'
}
if ([string]::IsNullOrWhiteSpace($PiDeploymentSteeringSha256)) {
    $PiDeploymentSteeringSha256 = [Environment]::GetEnvironmentVariable('JP8_PI_DEPLOYMENT_STEERING_SHA256')
}
if ([string]::IsNullOrWhiteSpace($PiDeploymentSteeringSha256)) {
    $PiDeploymentSteeringSha256 = 'f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4'
}
$WorkspaceRoot = Resolve-InvocationPath $WorkspaceRoot
$AmendmentPath = Resolve-InvocationPath $AmendmentPath
$ProgramStatePath = Resolve-InvocationPath $ProgramStatePath
$PiDeploymentSteeringPath = Resolve-InvocationPath $PiDeploymentSteeringPath

if (-not [string]::IsNullOrWhiteSpace($PredecessorRecord)) {
    $PredecessorRecord = Resolve-InvocationPath $PredecessorRecord
}
if (-not [string]::IsNullOrWhiteSpace($CompletionRecord)) {
    $CompletionRecord = Resolve-InvocationPath $CompletionRecord
}

$PathsToCheck = @($WorkspaceRoot, $AmendmentPath, $ProgramStatePath, $PiDeploymentSteeringPath)
if (-not [string]::IsNullOrWhiteSpace($PredecessorRecord)) {
    $PathsToCheck += $PredecessorRecord
}
if (-not [string]::IsNullOrWhiteSpace($CompletionRecord)) {
    $PathsToCheck += $CompletionRecord
}
foreach ($EnvironmentPathName in @(
    'JP8_PREDECESSOR_COMPLETION_PATH',
    'JP8_PREDECESSOR_RECORD_PATH',
    'JP8_COMPLETION_RECORD'
)) {
    $EnvironmentPath = [Environment]::GetEnvironmentVariable($EnvironmentPathName)
    if (-not [string]::IsNullOrWhiteSpace($EnvironmentPath)) {
        $PathsToCheck += (Resolve-InvocationPath $EnvironmentPath)
    }
}
foreach ($PathToCheck in $PathsToCheck) {
    $ResolvedForDrive = [System.IO.Path]::GetFullPath($PathToCheck)
    if ([System.IO.Path]::GetPathRoot($ResolvedForDrive) -ne 'C:\') {
        throw "Prompt 6 is C:-only; rejected path: $ResolvedForDrive"
    }
}
if ($PiDeploymentSteeringSha256 -notmatch '^[0-9a-fA-F]{64}$') {
    throw 'Prompt 6 Raspberry Pi steering SHA-256 must contain exactly 64 hexadecimal characters.'
}
$AuthoritativePiSteeringSha256 = 'f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4'
if ($PiDeploymentSteeringSha256.ToLowerInvariant() -ne $AuthoritativePiSteeringSha256) {
    throw 'Prompt 6 requires the exact authoritative Raspberry Pi steering SHA-256.'
}
$ActualPiSteeringSha256 = (Get-FileHash -LiteralPath $PiDeploymentSteeringPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualPiSteeringSha256 -ne $PiDeploymentSteeringSha256.ToLowerInvariant()) {
    throw "Prompt 6 Raspberry Pi steering hash differs: $PiDeploymentSteeringPath"
}

$StageTemp = Join-Path $WorkspaceRoot 'temp'
New-Item -ItemType Directory -Force -Path $StageTemp | Out-Null
$env:TEMP = $StageTemp
$env:TMP = $StageTemp

$ActionMap = @{
    ValidatePrerequisite = 'validate-prerequisite'
    Prepare = 'prepare'
    RunAccuracy = 'run-accuracy'
    RunResources = 'run-resources'
    ValidateTerminal = 'validate-terminal'
    Analyze = 'analyze'
    Collect = 'collect'
    Finalize = 'finalize'
    RunAll = 'run-all'
    ValidateCompletion = 'validate-completion'
    Status = 'status'
    Stop = 'stop'
}
$Arguments = @(
    '-m', 'app.full_pipeline_extended_evaluation', $ActionMap[$Action],
    '--workspace-root', $WorkspaceRoot,
    '--amendment-path', $AmendmentPath,
    '--program-state-path', $ProgramStatePath,
    '--pi-deployment-steering-path', $PiDeploymentSteeringPath,
    '--pi-deployment-steering-sha256', $PiDeploymentSteeringSha256
)
if ($Action -in @('RunAccuracy','RunAll')) {
    $Arguments += @('--parallel-jobs', [string]$ParallelJobs)
}
if (-not [string]::IsNullOrWhiteSpace($PredecessorRecord)) {
    $Arguments += @('--predecessor-record', $PredecessorRecord)
}
if (-not [string]::IsNullOrWhiteSpace($PredecessorSha256)) {
    $Arguments += @('--predecessor-sha256', $PredecessorSha256)
}
if (-not [string]::IsNullOrWhiteSpace($AdapterId)) {
    $Arguments += @('--adapter-id', $AdapterId)
}
if (-not [string]::IsNullOrWhiteSpace($AdapterContractSha256)) {
    $Arguments += @('--adapter-contract-sha256', $AdapterContractSha256)
}
if (-not [string]::IsNullOrWhiteSpace($CompletionRecord)) {
    $Arguments += @('--completion-record', $CompletionRecord)
}

Push-Location $ToolRoot
try {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Bounded Prompt-6 action failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
