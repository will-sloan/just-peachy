param([Parameter(Mandatory=$true)][string]$DllDirectory)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) { throw 'Use 32-bit Windows PowerShell.' }
Add-Type -Path (Join-Path $PSScriptRoot 'S4QueuedTelemetry.cs') -ReferencedAssemblies 'System.Web.Extensions','System.Core'
# Inspect loads metadata exports only. Neither this script nor DecodeForTest
# invokes control_init_usb/control_read_command or opens an audio endpoint.
$Inspection = [S4QueuedTelemetry]::Inspect($DllDirectory) | ConvertFrom-Json
$NoSpeech = [S4QueuedTelemetry]::DecodeForTest(2,[byte[]](0,0,0,192,127,0,0,0,0)) | ConvertFrom-Json
if ($null -ne $NoSpeech.values[0] -or $NoSpeech.values[1] -ne 0 -or $NoSpeech.finite[0] -or -not $NoSpeech.finite[1]) { throw 'NaN/zero decoding regression.' }
if ($NoSpeech.invalid_reasons[0] -ne 'documented_no_fixed_beam_speech') { throw 'No-speech reason regression.' }
$Infinity = [S4QueuedTelemetry]::DecodeForTest(2,[byte[]](0,0,0,128,127,0,0,0,0)) | ConvertFrom-Json
if ($Infinity.invalid_reasons[0] -ne 'nonfinite_infinity') { throw 'Infinity must not mean no speech.' }
$Energy = [S4QueuedTelemetry]::DecodeForTest(1,[byte[]](0,0,0,128,63,0,0,0,64,0,0,64,64,0,0,128,64)) | ConvertFrom-Json
if (($Energy.values -join ',') -ne '1,2,3,4') { throw 'Energy count/order regression.' }
$Rejected = 0
foreach ($InvalidBytes in @([byte[]](0,0),[byte[]](64,0,0,192,127,0,0,0,0))) {
    try { [void][S4QueuedTelemetry]::DecodeForTest(2,$InvalidBytes) } catch { $Rejected += 1 }
}
if ($Rejected -ne 2) { throw 'Partial/retry reply must not be decoded as a measurement.' }
[ordered]@{
    status = 'PASS'
    no_usb_initialization = $true
    tests = @('official_command_map_contract','selected_nan_null_reason_and_zero_distinction','infinity_not_no_speech','four_energy_values_in_order','partial_reply_rejected','retry_reply_rejected')
    test_count = 6
    inspection = $Inspection
    selected_nan_fixture = $NoSpeech
    selected_infinity_fixture = $Infinity
    energy_fixture = $Energy
} | ConvertTo-Json -Depth 12
