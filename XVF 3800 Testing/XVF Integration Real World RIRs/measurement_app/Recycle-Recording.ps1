param([Parameter(Mandatory=$true)][string]$RunPath,
      [Parameter(Mandatory=$true)][string]$ExperimentRoot)
$ErrorActionPreference = 'Stop'
$VerifiedRoot = (Resolve-Path -LiteralPath $ExperimentRoot).Path
$VerifiedRun = (Resolve-Path -LiteralPath $RunPath).Path
if ([IO.Path]::GetDirectoryName($VerifiedRun) -ne $VerifiedRoot) {
    throw 'Recording must be directly inside the experiment directory.'
}
$RunName = [IO.Path]::GetFileName($VerifiedRun)
if ($RunName -notmatch '^(JPXVF_|TAKE_)') { throw 'Not a recording folder.' }
Add-Type -AssemblyName Microsoft.VisualBasic
[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
    $VerifiedRun,
    [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
    [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin)
if (Test-Path -LiteralPath $VerifiedRun) { throw 'Recording still exists.' }
