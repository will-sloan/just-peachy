[CmdletBinding()]
param(
    [switch]$Follow,
    [switch]$AllModels,
    [string]$BackendCsv = '',
    [string]$ControllerTag = 'primary'
)

$Runner = Join-Path $PSScriptRoot 'run_speaker_enrollment_live_v2.ps1'
do {
    Clear-Host
    if ($AllModels) {
        Write-Output '===== PRIMARY: WeSpeaker + ReDimNet2-B2 ====='
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Runner -Action Status `
            -ControllerTag primary -BackendCsv 'wespeaker,redimnet2_b2_speaker_embedding'
        Write-Output '===== REFERENCE: SpeechBrain ECAPA + ERes2Net Base ====='
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Runner -Action Status `
            -ControllerTag reference_models -BackendCsv 'speechbrain_ecapa,eres2net_base_speaker_embedding'
    }
    else {
        $Arguments = @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Runner,
            '-Action', 'Status', '-ControllerTag', $ControllerTag
        )
        if ($BackendCsv) { $Arguments += @('-BackendCsv', $BackendCsv) }
        & powershell.exe @Arguments
    }
    if ($Follow) { Start-Sleep -Seconds 15 }
} while ($Follow)
