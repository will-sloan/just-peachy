<# Register or remove only the N1 owned cheap scheduled probes. See README.md. #>
[CmdletBinding()]
param(
 [string]$StateRoot='G:\Just_Peachy_N1\20260924_campaign\local\supervision',
 [string]$Python='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\pythonw.exe',
 [ValidateSet('Register','Remove','Inspect')][string]$Action='Register',
 [string]$Prefix='JustPeachy-N1-20260924'
)
$ErrorActionPreference='Stop'
if ($Prefix -notmatch '^JustPeachy-N1-20260924(?:-test)?$') { throw 'Unexpected task namespace' }
$jpScript=Join-Path $PSScriptRoot 'supervisor.py'
$jpRoot=[IO.Path]::GetFullPath($StateRoot)
if (-not (Test-Path -LiteralPath $jpRoot)) { throw 'Initialize the state directory first' }
$jpSchedule=@{setup=10;inference=15;replay=30}
$jpReceipts=@()
foreach ($jpPhase in @('setup','inference','replay')) {
 $jpName="$Prefix-$jpPhase"
 if ($Action -eq 'Remove') {
  if (Get-ScheduledTask -TaskName $jpName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $jpName -Confirm:$false }
  $jpReceipts+=@{name=$jpName;removed= -not [bool](Get-ScheduledTask -TaskName $jpName -ErrorAction SilentlyContinue)}
 } elseif ($Action -eq 'Register') {
  $jpArgs='-B "'+$jpScript+'" probe --root "'+$jpRoot+'" --expected-phase '+$jpPhase
  $jpTaskAction=New-ScheduledTaskAction -Execute $Python -Argument $jpArgs -WorkingDirectory $PSScriptRoot
  $jpTrigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $jpSchedule[$jpPhase])
  $jpSettings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
  $jpPrincipal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $jpName -Action $jpTaskAction -Trigger $jpTrigger -Settings $jpSettings -Principal $jpPrincipal -Description 'N1 code-only status probe. No LLM, no microphone, no desktop control. Phase gated.' -Force | Out-Null
  $jpReceipts+=@{name=$jpName;interval_minutes=$jpSchedule[$jpPhase];registered=$true;expected_phase=$jpPhase}
 } else {
  $jpTask=Get-ScheduledTask -TaskName $jpName
  $jpInfo=Get-ScheduledTaskInfo -TaskName $jpName
  $jpReceipts+=@{name=$jpName;state=[string]$jpTask.State;last_result=$jpInfo.LastTaskResult;last_run=$jpInfo.LastRunTime.ToUniversalTime().ToString('o');next_run=$jpInfo.NextRunTime.ToUniversalTime().ToString('o')}
 }
}
$jpReceipt=@{utc=(Get-Date).ToUniversalTime().ToString('o');action=$Action;tasks=$jpReceipts;llm_invoked=$false;credentials_saved=$false;logged_in_user_required=$true}
$jpReceipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $jpRoot ('scheduler-'+$Action.ToLowerInvariant()+'.json')) -Encoding utf8
$jpReceipt | ConvertTo-Json -Depth 6
