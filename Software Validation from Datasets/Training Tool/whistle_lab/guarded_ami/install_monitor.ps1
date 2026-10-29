$ErrorActionPreference = 'Stop'
$taskName = 'JustPeachy Whistle Exploratory Monitor'
$labRoot = (Get-Item -LiteralPath $PSScriptRoot).Parent.FullName
$repoRoot = (Get-Item -LiteralPath $labRoot).Parent.Parent.Parent.FullName
$pythonWindowless = Join-Path $repoRoot '.venv\Scripts\pythonw.exe'
$controller = Join-Path $PSScriptRoot 'control.py'
$taskAction = New-ScheduledTaskAction -Execute $pythonWindowless -Argument ('"' + $controller + '" monitor') -WorkingDirectory $PSScriptRoot
$repeatTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(15) -RepetitionInterval (New-TimeSpan -Minutes 15)
$loginTrigger = New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger @($repeatTrigger,$loginTrigger) -Settings $settings -Principal $principal -Description 'Continues one owned exploratory Whistle adaptation from saved state; no fresh trials; respects user pause.' -Force | Select-Object TaskName,State
