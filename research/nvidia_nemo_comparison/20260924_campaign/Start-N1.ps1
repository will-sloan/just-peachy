param(
  [string]$Python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe',
  [string]$SourceRoot = 'G:\Just_Peachy_N1\20260924_campaign\local\Installed Baseline\releases\n1-common-20260924-v1',
  [string]$DataRoot = 'G:\Just_Peachy_N1\20260924_campaign\local\manual-baseline',
  [string]$ModelsRoot = 'C:\Users\amiri\JustPeachy\shared\models'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Existing Python runtime not found; set -Python.' }
$EntryPoint = Join-Path $SourceRoot 'main.py'
if (-not (Test-Path -LiteralPath $EntryPoint -PathType Leaf)) { throw 'Install/stage the N1 release first or set -SourceRoot.' }
& $Python -B $EntryPoint gui --data-root $DataRoot --models $ModelsRoot
exit $LASTEXITCODE
