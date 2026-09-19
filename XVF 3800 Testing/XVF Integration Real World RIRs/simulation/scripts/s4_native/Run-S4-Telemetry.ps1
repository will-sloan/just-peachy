param(
 [Parameter(Mandatory=$true)][string]$DllDirectory,
 [string]$OutputDirectory,
 [double]$Seconds = 30,
 [double]$RateHz = 20,
 [string]$StopFile,
 [switch]$InspectOnly
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) { throw 'Use 32-bit Windows PowerShell for official Win32 DLLs.' }
Add-Type -Path (Join-Path $PSScriptRoot 'S4QueuedTelemetry.cs') -ReferencedAssemblies 'System.Web.Extensions','System.Core'
if ($InspectOnly) {
 [S4QueuedTelemetry]::Inspect($DllDirectory)
 exit 0
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { throw 'Specify a new output directory.' }
$ResultCode = [S4QueuedTelemetry]::Run($DllDirectory,[IO.Path]::GetFullPath($OutputDirectory),$Seconds,$false,$StopFile,$RateHz)
exit $ResultCode
