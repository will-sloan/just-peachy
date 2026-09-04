param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PipelineArguments
)

$ErrorActionPreference = "Stop"
$EvaluationRoot = Split-Path -Parent $PSScriptRoot
$RepositoryRoot = Split-Path -Parent (Split-Path -Parent $EvaluationRoot)
$Candidates = @(
    (Join-Path $RepositoryRoot ".edge-speech-env\python.exe"),
    (Join-Path $RepositoryRoot ".edge-speech-env\Scripts\python.exe"),
    (Join-Path $RepositoryRoot ".stage8-envs\credential-diarization\Scripts\python.exe")
)
$Python = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Python) {
    throw "No compatible environment was found. Run scripts\setup_edge_speech_pipeline.ps1 first."
}
if (-not $PipelineArguments -or $PipelineArguments.Count -eq 0) {
    $PipelineArguments = @("gui")
}
Set-Location -LiteralPath $EvaluationRoot
& $Python -m app.edge_speech_pipeline @PipelineArguments
exit $LASTEXITCODE
