# README_RUNTIME_OPERATOR_V1.md documents inputs, outputs and prepared-host scope.
[CmdletBinding()]
param(
    [ValidateRange(24,9999)][int]$Version = 24,
    [ValidateRange(23,9998)][int]$PreviousVersion = 23,
    [switch]$Plan
)
$ErrorActionPreference = 'Stop'
$pythonExe = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$privateRoot = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928'
$localRoot = 'G:/Just_Peachy_N1/20260924_campaign/local'
$workRoot = Join-Path $privateRoot 'deployable-runtime-resume-v1'
$previousInstall = Join-Path $privateRoot "field-runtime-v$PreviousVersion-install"
$previousCopy = Join-Path $privateRoot "field-runtime-v$PreviousVersion-batch-preservation-v$Version"
$newInstall = Join-Path $privateRoot "field-runtime-v$Version-install"
$inspection = Join-Path $workRoot ("install-inspection-v" + (10000 + $Version))
$scopePath = Join-Path $workRoot "OPERATOR_SCOPE_V$Version.json"
$prepName = if ($Plan) { "operator-plan-v$Version" } else { "operator-preparation-v$Version" }
$preparation = Join-Path $workRoot $prepName
$prior = Join-Path $workRoot 'PREINSTALL_PRIOR_BINDING_V6.json'
function Invoke-Stage([string]$Name,[string[]]$Arguments) {
    & $pythonExe -B (Join-Path $PSScriptRoot $Name) @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Stopped at $Name (exit $LASTEXITCODE). Evidence is preserved. Do not retry a failed output or clear it." }
}
$prepareArgs = @('--private',$privateRoot,'--work',$workRoot,'--sources',$PSScriptRoot,'--previous-install',$previousInstall,'--output',$preparation,'--scope',$scopePath,'--version',"$Version")
if ($Plan) { $prepareArgs += '--plan' }
Invoke-Stage 'prepare_runtime_operator_v1.py' $prepareArgs
if ($Plan) { return }
$commonArgs = @('--local',$localRoot,'--private',$privateRoot,'--prior-closure',$prior,'--scope',$scopePath)
Invoke-Stage 'preserve_runtime_batch_v1.py' ($commonArgs + @('--candidate-install',$previousInstall,'--previous-inspection',$previousInstall,'--output',$previousCopy))
Invoke-Stage 'inspect_runtime_reprovision_v1.py' ($commonArgs + @('--previous-inspection',$previousCopy,'--previous-install',$previousInstall,'--previous-preservation',$previousCopy,'--output',$inspection))
Invoke-Stage 'provision_field_runtime_v1.py' ($commonArgs + @('--assets',(Join-Path $privateRoot 'runtime-titanet-v1-install/assets-restore'),'--inputs',(Join-Path $workRoot 'boot-launch-inputs-v1'),'--inspection',$inspection,'--previous-install',$previousInstall,'--previous-preservation',$previousCopy,'--output',$newInstall,'--version',"$Version"))
Write-Output "Fresh batch installed: $newInstall. Open its versioned Pi shortcut; it starts idle. Four recording slots are available."

