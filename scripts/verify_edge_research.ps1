[CmdletBinding()]
param([switch]$SkipSmoke)

$ErrorActionPreference = "Stop"
$RepositoryRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$EvaluationRoot = Join-Path $RepositoryRoot "Software Validation from Datasets\Evaluation Tool"
$CorePython = Join-Path $RepositoryRoot ".venv\Scripts\python.exe"
$ProfilePython = @{
    "edge-cpu" = Join-Path $RepositoryRoot ".stage8-envs\edge-cpu\Scripts\python.exe"
    "moonshine-edge" = Join-Path $RepositoryRoot ".stage8-envs\moonshine-edge\Scripts\python.exe"
    "onnx" = Join-Path $RepositoryRoot ".stage8-envs\onnx\Scripts\python.exe"
}

function Invoke-Checked {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')" }
}

foreach ($Path in @($CorePython) + @($ProfilePython.Values)) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required interpreter is missing: $Path. Run scripts\prepare_edge_research.ps1 first."
    }
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "FFmpeg is not available on PATH. Install it with install.ps1 -InstallFFmpeg."
}

Push-Location $EvaluationRoot
try {
    Invoke-Checked $CorePython @("scripts\inventory_stage8_assets.py")
    Invoke-Checked $CorePython @("-m", "app.edge_research.cli", "plan")
    Invoke-Checked $CorePython @("-m", "app.edge_research.cli", "verify")
    if (-not $SkipSmoke) {
        Invoke-Checked $ProfilePython["edge-cpu"] @(
            "scripts\qualify_extended_backends.py", "--profile", "edge-cpu", "--backend", "fsmn_vad",
            "--output", "runs\edge_backend_qualification\edge-cpu.json"
        )
        Invoke-Checked $ProfilePython["moonshine-edge"] @(
            "scripts\qualify_extended_backends.py", "--profile", "moonshine-edge",
            "--backend", "moonshine_streaming_tiny", "--backend", "moonshine_streaming_small",
            "--backend", "moonshine_streaming_medium",
            "--output", "runs\edge_backend_qualification\moonshine-edge.json"
        )
        Invoke-Checked $ProfilePython["onnx"] @(
            "scripts\qualify_extended_backends.py", "--profile", "onnx",
            "--backend", "sherpa_onnx_streaming_zipformer_20m_int8",
            "--backend", "campplus_speaker_embedding", "--backend", "eres2net_base_speaker_embedding",
            "--output", "runs\edge_backend_qualification\onnx-edge.json"
        )
        Invoke-Checked $ProfilePython["onnx"] @(
            "run_evaluation.py", "speaker-protocol", "smoke",
            "--backend", "campplus_speaker_embedding", "--backend", "eres2net_base_speaker_embedding",
            "--output-root", "runs\edge_speaker_protocol_smoke", "--rerun"
        )
    }
    Invoke-Checked $CorePython @("-m", "app.edge_research.cli", "verify")
    Write-Host "[PASS] Edge research preflight is complete. No campaign was started."
} finally {
    Pop-Location
}
