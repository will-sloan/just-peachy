[CmdletBinding()]
param(
    [ValidateSet('ValidatePrerequisites','Select','PrepareHardening','RunHardening','ValidateHardening','Package','UpdateProgramState','RunAll','Stop','Status','ValidateCompletion','ValidateCandidate','Health','ServeHealth','MaterialPaths')]
    [string]$Action = 'Status',
    [string]$WorkspaceRoot,
    [string]$Prompt6Marker,
    [string]$Prompt5Marker,
    [string]$AmendmentPath,
    [string]$ProgramStatePath,
    [string]$PiDeploymentSteeringPath,
    [string]$PredecessorRecord,
    [string]$CompletionRecord,
    [string]$AdapterId,
    [string]$AdapterContractSha256,
    [ValidateSet('primary','fallback','alternative')]
    [string]$CandidateRole,
    [string]$PipelineId,
    [string]$Bind = '127.0.0.1',
    [ValidateRange(1,65535)]
    [int]$Port = 8767
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
    $WorkspaceRoot = Join-Path $ToolRoot 'automated_runs\full_pipeline_production_candidate_hardening_reduced_8day_v1'
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
if ([string]::IsNullOrWhiteSpace($Prompt6Marker) -and -not [string]::IsNullOrWhiteSpace($env:JP8_PREDECESSOR_COMPLETION_PATH)) {
    $Prompt6Marker = $env:JP8_PREDECESSOR_COMPLETION_PATH
}
if ([string]::IsNullOrWhiteSpace($PredecessorRecord) -and -not [string]::IsNullOrWhiteSpace($Prompt6Marker)) {
    $PredecessorRecord = $Prompt6Marker
}

$PathVariables = @('Prompt6Marker','Prompt5Marker','PredecessorRecord','CompletionRecord')
foreach ($VariableName in $PathVariables) {
    $Value = Get-Variable -Name $VariableName -ValueOnly
    if (-not [string]::IsNullOrWhiteSpace($Value) -and -not [System.IO.Path]::IsPathRooted($Value)) {
        Set-Variable -Name $VariableName -Value ([System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $Value)))
    }
}
$PathsToCheck = @($WorkspaceRoot, $AmendmentPath, $ProgramStatePath, $PiDeploymentSteeringPath)
foreach ($VariableName in $PathVariables) {
    $Value = Get-Variable -Name $VariableName -ValueOnly
    if (-not [string]::IsNullOrWhiteSpace($Value)) { $PathsToCheck += $Value }
}
foreach ($PathToCheck in $PathsToCheck) {
    $FullPath = [System.IO.Path]::GetFullPath($PathToCheck)
    if (-not [System.IO.Path]::GetPathRoot($FullPath).Equals('C:\', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Prompt 7 is C:-only; rejected path: $FullPath"
    }
}

$StageTemp = Join-Path $WorkspaceRoot 'temp'
New-Item -ItemType Directory -Force -Path $StageTemp | Out-Null
$env:TEMP = $StageTemp
$env:TMP = $StageTemp
$env:TMPDIR = $StageTemp

$ActionMap = @{
    ValidatePrerequisites='validate-prerequisites'; Select='select'
    PrepareHardening='prepare-hardening'; RunHardening='run-hardening'
    ValidateHardening='validate-hardening'; Package='package'
    UpdateProgramState='update-program-state'; RunAll='run-all'; Stop='stop'
    Status='status'; ValidateCompletion='validate-completion'
    ValidateCandidate='validate-candidate'; Health='health'
    ServeHealth='serve-health'; MaterialPaths='material-paths'
}
$Arguments = @(
    '-m', 'app.full_pipeline_production_hardening', $ActionMap[$Action],
    '--workspace-root', $WorkspaceRoot,
    '--amendment-path', $AmendmentPath,
    '--program-state-path', $ProgramStatePath,
    '--pi-deployment-steering-path', $PiDeploymentSteeringPath,
    '--bind', $Bind,
    '--port', [string]$Port
)
if (-not [string]::IsNullOrWhiteSpace($Prompt6Marker)) { $Arguments += @('--prompt6-marker', $Prompt6Marker) }
if (-not [string]::IsNullOrWhiteSpace($Prompt5Marker)) { $Arguments += @('--prompt5-marker', $Prompt5Marker) }
if (-not [string]::IsNullOrWhiteSpace($PredecessorRecord)) { $Arguments += @('--predecessor-record', $PredecessorRecord) }
if (-not [string]::IsNullOrWhiteSpace($CompletionRecord)) { $Arguments += @('--completion-record', $CompletionRecord) }
if (-not [string]::IsNullOrWhiteSpace($AdapterId)) { $Arguments += @('--adapter-id', $AdapterId) }
if (-not [string]::IsNullOrWhiteSpace($AdapterContractSha256)) { $Arguments += @('--adapter-contract-sha256', $AdapterContractSha256) }
if (-not [string]::IsNullOrWhiteSpace($CandidateRole)) { $Arguments += @('--candidate-role', $CandidateRole) }
if (-not [string]::IsNullOrWhiteSpace($PipelineId)) { $Arguments += @('--pipeline-id', $PipelineId) }

Push-Location $ToolRoot
try {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Prompt-7 production hardening action failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
