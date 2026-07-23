param(
    [string]$MonoFile = "",
    [string]$Label = "digital_mono_processed_duplicate_4mic",
    [ValidateSet("DuplicateMics", "SingleMic", "FarEndReference")]
    [string]$Mode = "DuplicateMics",
    [ValidateRange(0,3)]
    [int]$MicIndex = 0,
    [switch]$FarEndReference,
    [switch]$ASROutput
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
. (Join-Path $ProjectRoot "select_wav_file.ps1")
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) { throw "Project virtual environment is missing: $PythonExe. Run .\setup_environment.ps1 first." }
if ([string]::IsNullOrWhiteSpace($MonoFile)) {
    $MonoFile = Select-XvfWavFile -ProjectRoot $ProjectRoot -Title "Select a WAV for the digital mono test"
    Write-Host "Selected WAV: $MonoFile"
} elseif (-not [IO.Path]::IsPathRooted($MonoFile)) {
    $MonoFile = Join-Path $ProjectRoot $MonoFile
}
if (-not (Test-Path -LiteralPath $MonoFile -PathType Leaf)) { throw "Mono input WAV not found: $MonoFile" }
$MonoFile = (Resolve-Path -LiteralPath $MonoFile).Path
if ($FarEndReference) { $Mode = "FarEndReference" }
$argsList = @(
    (Join-Path $ProjectRoot "xvf_test_runner.py"),
    "digital-mono",
    "--config", (Join-Path $ProjectRoot "config.json"),
    "--label", $Label,
    "--mode", $Mode,
    "--mic-index", $MicIndex,
    $MonoFile
)
if ($ASROutput) { $argsList += "--asr-output" }
& $PythonExe @argsList
if ($LASTEXITCODE -ne 0) { throw "Digital mono test failed with exit code $LASTEXITCODE" }
