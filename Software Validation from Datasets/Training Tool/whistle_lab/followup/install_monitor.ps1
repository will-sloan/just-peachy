# Register only this campaign's recovery task; training starts through its gate.
$ErrorActionPreference = 'Stop'
$taskName = 'JustPeachy Whistle Experiment Monitor'
$launcher = Join-Path $PSScriptRoot 'launch.ps1'
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $launcher + '" -Action watch'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $PSScriptRoot
$logon = New-ScheduledTaskTrigger -AtLogOn -User $account
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $account -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($logon,$repeat) -Principal $principal -Settings $settings -Description 'Keep the bounded local Whistle follow-up supervisor available; respects pause and original-run completion.' -Force | Select-Object TaskName,State
& $launcher -Action watch
