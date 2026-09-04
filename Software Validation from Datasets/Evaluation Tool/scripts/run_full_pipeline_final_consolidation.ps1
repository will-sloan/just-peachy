[CmdletBinding()]
param(
    [ValidateSet('RunAll','Stop','Status','ValidateCompletion')]
    [string]$Action = 'Status',
    [string]$WorkspaceRoot,
    [string]$OutputRoot,
    [string]$ZipPath,
    [string]$Prompt7Marker,
    [string]$AmendmentPath,
    [string]$ExecutionPolicyPath,
    [string]$AdapterRegistryPath,
    [string]$PiDeploymentSteeringPath,
    [string]$ProgramStatePath,
    [string]$MatrixPath,
    [string]$RuntimePath,
    [string]$LicenseDocumentPath,
    [string]$CompletionRecord,
    [string]$ProgressRecord,
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

$Defaults = @{
    WorkspaceRoot = Join-Path $ToolRoot 'automated_runs\full_pipeline_final_consolidation_reduced_8day_v1'
    OutputRoot = Join-Path $ToolRoot 'JustPeachyResearchSummaries\full_pipeline\final\full_pipeline_program_reduced_8day_v1'
    ZipPath = Join-Path $ToolRoot 'JustPeachyResearchSummaries\full_pipeline\final\full_pipeline_program_reduced_8day_v1.zip'
    AmendmentPath = Join-Path $ToolRoot 'runs\full_pipeline_program\EIGHT_DAY_SCOPE_AMENDMENT.json'
    ExecutionPolicyPath = Join-Path $ToolRoot 'runs\full_pipeline_program\EIGHT_DAY_EXECUTION_POLICY_ADDENDUM.json'
    AdapterRegistryPath = Join-Path $ToolRoot 'runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json'
    PiDeploymentSteeringPath = Join-Path $ToolRoot 'runs\full_pipeline_program\RASPBERRY_PI_DEPLOYMENT_STEERING.json'
    ProgramStatePath = Join-Path $ToolRoot 'runs\full_pipeline_program\PROGRAM_STATE.json'
    MatrixPath = Join-Path $ToolRoot 'configs\automated_evaluation\full_pipeline_matrix.v1.yaml'
    RuntimePath = Join-Path $ToolRoot 'configs\automated_evaluation\full_pipeline_runtime.v1.yaml'
    LicenseDocumentPath = Join-Path $ToolRoot 'docs\full_pipeline\LICENSE_AND_ASSET_MANIFEST.md'
}
foreach ($Name in $Defaults.Keys) {
    $Value = Get-Variable -Name $Name -ValueOnly
    if ([string]::IsNullOrWhiteSpace($Value)) {
        Set-Variable -Name $Name -Value $Defaults[$Name]
    } elseif (-not [System.IO.Path]::IsPathRooted($Value)) {
        Set-Variable -Name $Name -Value ([System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $Value)))
    }
}

$PathsToCheck = @(
    $WorkspaceRoot, $OutputRoot, $ZipPath, $AmendmentPath, $ExecutionPolicyPath,
    $AdapterRegistryPath, $PiDeploymentSteeringPath, $ProgramStatePath,
    $MatrixPath, $RuntimePath, $LicenseDocumentPath
)
foreach ($Optional in @('Prompt7Marker','CompletionRecord','ProgressRecord')) {
    $Value = Get-Variable -Name $Optional -ValueOnly
    if (-not [string]::IsNullOrWhiteSpace($Value)) {
        if (-not [System.IO.Path]::IsPathRooted($Value)) {
            $Value = [System.IO.Path]::GetFullPath((Join-Path $InvocationRoot $Value))
            Set-Variable -Name $Optional -Value $Value
        }
        $PathsToCheck += $Value
    }
}
foreach ($PathToCheck in $PathsToCheck) {
    $Absolute = [System.IO.Path]::GetFullPath($PathToCheck)
    if ([System.IO.Path]::GetPathRoot($Absolute) -ne 'C:\') {
        throw "Prompt 8 is C:-only; rejected path: $Absolute"
    }
}

$StageTemp = Join-Path $WorkspaceRoot 'temp'
New-Item -ItemType Directory -Force -Path $StageTemp | Out-Null
$env:TEMP = $StageTemp
$env:TMP = $StageTemp

$ActionMap = @{
    RunAll='run-all'; Stop='stop'; Status='status'; ValidateCompletion='validate-completion'
}
$Arguments = @(
    '-m', 'app.full_pipeline_final_consolidation', $ActionMap[$Action],
    '--workspace-root', $WorkspaceRoot,
    '--output-root', $OutputRoot,
    '--zip-path', $ZipPath,
    '--amendment-path', $AmendmentPath,
    '--execution-policy-path', $ExecutionPolicyPath,
    '--adapter-registry-path', $AdapterRegistryPath,
    '--pi-deployment-steering-path', $PiDeploymentSteeringPath,
    '--program-state-path', $ProgramStatePath,
    '--matrix-path', $MatrixPath,
    '--runtime-path', $RuntimePath,
    '--license-document-path', $LicenseDocumentPath
)
if (-not [string]::IsNullOrWhiteSpace($Prompt7Marker)) {
    $Arguments += @('--prompt7-marker', $Prompt7Marker)
}
if (-not [string]::IsNullOrWhiteSpace($CompletionRecord)) {
    $Arguments += @('--completion-record', $CompletionRecord)
}
if (-not [string]::IsNullOrWhiteSpace($ProgressRecord)) {
    $Arguments += @('--progress-record', $ProgressRecord)
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
        throw "Prompt-8 final consolidation action failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
