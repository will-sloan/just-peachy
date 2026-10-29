# Separate CPU-only reporting task. Does not alter either training supervisor.
$ErrorActionPreference = 'Stop'
$taskName = 'JustPeachy Whistle Findings Report'
$launcher = Join-Path $PSScriptRoot 'update_report.ps1'
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $launcher + '"'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $PSScriptRoot
$logon = New-ScheduledTaskTrigger -AtLogOn -User $account
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(15) -RepetitionInterval (New-TimeSpan -Minutes 15)
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($logon,$repeat) -Principal $principal -Settings $settings -Description 'Append completed Whistle findings and interpretation to the local Word report; no GPU, dataset scan or model calls.' -Force | Select-Object TaskName,State
