param(
 [Parameter(Mandatory=$true)][string]$DllDirectory,
 [string]$OutputDirectory,
 [double]$Seconds = 30,
 [double]$RateHz = 20,
 [double]$GainHz = 2,
 [double]$SlowHz = 0.2,
 [string]$StopFile,
 [switch]$CompileOnly,
 [switch]$SelfTest,
 [switch]$InspectOnly
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) { throw 'Use 32-bit Windows PowerShell for official Win32 DLLs.' }
Add-Type -Path (Join-Path $PSScriptRoot 'S6DQueuedTelemetry.cs') -ReferencedAssemblies 'System.Web.Extensions','System.Core'
if ($CompileOnly) { Write-Output '{"status":"COMPILED_ONLY","hardware_calls":0,"dll_calls":0}'; exit 0 }
if ($SelfTest) { [S6DQueuedTelemetry]::SelfTests(); exit 0 }
if ($InspectOnly) {
 [S6DQueuedTelemetry]::Inspect($DllDirectory)
 exit 0
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { throw 'Specify a new output directory.' }
$ResultCode = [S6DQueuedTelemetry]::Run($DllDirectory,[IO.Path]::GetFullPath($OutputDirectory),$Seconds,$false,$StopFile,$RateHz,$GainHz,$SlowHz)
exit $ResultCode
