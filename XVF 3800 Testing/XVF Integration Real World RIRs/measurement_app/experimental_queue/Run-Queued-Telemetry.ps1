param(
    [string]$OutputDirectory,
    [double]$Seconds = 30,
    [switch]$Sequential,
    [string]$StopFile,
    [switch]$InspectOnly
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    throw 'Run this file with C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe (32-bit).'
}
$WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$DllDirectory = Join-Path $WorkspacePath 'tools\xvf321\binary\host_v3.0.0\win32'
$SourcePath = Join-Path $PSScriptRoot 'QueuedTelemetry.cs'
Add-Type -Path $SourcePath -ReferencedAssemblies 'System.Web.Extensions','System.Core'
if ($InspectOnly) {
    [QueuedTelemetry]::Inspect($DllDirectory)
    exit 0
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) { throw 'Specify a new -OutputDirectory.' }
$ResolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
$ExitResult = [QueuedTelemetry]::Run($DllDirectory, $ResolvedOutput, $Seconds, [bool]$Sequential, $StopFile)
exit $ExitResult
