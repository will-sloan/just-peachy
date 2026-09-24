# See README_PI_LOGIN.md. Never pass a password on the command line.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[D-Zd-z]$')][string]$DriveLetter,
    [Parameter(Mandatory=$true)][long]$ExpectedDiskBytes,
    [string]$OpenSSL = 'C:\Program Files\Git\usr\bin\openssl.exe',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$jpBootRoot = $DriveLetter.ToUpperInvariant() + ':\'

function Assert-PiBootTarget {
    $jpPartition = Get-Partition -DriveLetter $DriveLetter
    $jpDisk = Get-Disk -Number $jpPartition.DiskNumber
    $jpVolume = Get-Volume -DriveLetter $DriveLetter
    if ($jpDisk.BusType -ne 'USB' -or $jpDisk.FriendlyName.Trim() -ne 'mmcblk0' -or
        $jpDisk.Size -ne $ExpectedDiskBytes -or $jpDisk.IsSystem -or $jpDisk.IsBoot -or
        $jpPartition.PartitionNumber -ne 1 -or $jpVolume.FileSystemLabel -ne 'bootfs' -or
        $jpVolume.FileSystem -ne 'FAT32') { throw 'Target is not the expected CM5 USB boot partition.' }
    foreach ($jpRequired in @('config.txt','cmdline.txt','bcm2712-rpi-cm5-cm5io.dtb')) {
        if (-not (Test-Path -LiteralPath (Join-Path $jpBootRoot $jpRequired) -PathType Leaf)) {
            throw 'Expected Raspberry Pi CM5 boot files are missing.'
        }
    }
    foreach ($jpExisting in @('userconf','userconf.txt','firstrun.sh','custom.toml','user-data')) {
        if (Test-Path -LiteralPath (Join-Path $jpBootRoot $jpExisting)) {
            throw "Existing $jpExisting found; inspect it before creating another account configuration."
        }
    }
    foreach ($jpMarker in @('ssh','ssh.txt')) {
        $jpMarkerPath = Join-Path $jpBootRoot $jpMarker
        if ((Test-Path -LiteralPath $jpMarkerPath) -and
            ((Get-Item -LiteralPath $jpMarkerPath).PSIsContainer -or
             (Get-Item -LiteralPath $jpMarkerPath).Length -ne 0)) { throw 'Unexpected SSH marker; inspect before proceeding.' }
    }
}

function Get-PiPasswordHash([string]$PlainText) {
    $jpHashProcess = New-Object System.Diagnostics.Process
    $jpHashProcess.StartInfo.FileName = $OpenSSL
    $jpHashProcess.StartInfo.Arguments = 'passwd -6 -stdin'
    $jpHashProcess.StartInfo.UseShellExecute = $false
    $jpHashProcess.StartInfo.CreateNoWindow = $true
    $jpHashProcess.StartInfo.RedirectStandardInput = $true
    $jpHashProcess.StartInfo.RedirectStandardOutput = $true
    $jpHashProcess.StartInfo.RedirectStandardError = $true
    $jpPasswordBytes = $null
    try {
        [void]$jpHashProcess.Start()
        # Windows PowerShell 5.1 lacks ProcessStartInfo.StandardInputEncoding.
        # Write UTF-8 directly to the pipe, with no BOM or console codepage conversion.
        $jpPasswordBytes = [Text.Encoding]::UTF8.GetBytes($PlainText + "`n")
        $jpHashProcess.StandardInput.BaseStream.Write($jpPasswordBytes, 0, $jpPasswordBytes.Length)
        $jpHashProcess.StandardInput.BaseStream.Flush()
        $jpHashProcess.StandardInput.Close()
        if (-not $jpHashProcess.WaitForExit(10000)) { $jpHashProcess.Kill(); throw 'Password hashing timed out.' }
        $jpHash = $jpHashProcess.StandardOutput.ReadToEnd().Trim()
        if ($jpHashProcess.ExitCode -ne 0 -or $jpHash -notmatch '^\$6\$[./0-9A-Za-z]{1,16}\$[./0-9A-Za-z]{86}$') {
            throw 'OpenSSL did not produce a valid SHA-512 crypt password hash.'
        }
        return $jpHash
    } finally {
        if ($null -ne $jpPasswordBytes) { [Array]::Clear($jpPasswordBytes, 0, $jpPasswordBytes.Length) }
        $jpHashProcess.Dispose()
    }
}

function Write-NewBootFile([string]$Path, [byte[]]$Bytes) {
    $jpOutput = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try { $jpOutput.Write($Bytes, 0, $Bytes.Length); $jpOutput.Flush($true) } finally { $jpOutput.Dispose() }
}

try {
    Assert-PiBootTarget
    if (-not (Test-Path -LiteralPath $OpenSSL -PathType Leaf)) { throw 'Git for Windows OpenSSL was not found.' }
    # Exercise the real hash implementation using public synthetic text; no disk write.
    $jpProbeHash = Get-PiPasswordHash 'JustPeachy-nonsecret-preflight'
    if ($CheckOnly) { Write-Output 'PASS: CM5 boot target and OpenSSL validated; no files written.'; exit 0 }
    $Host.UI.RawUI.WindowTitle = 'Just Peachy - create Raspberry Pi login'
    Write-Host 'Create your Raspberry Pi login without reflashing.'
    Write-Host 'Password entry is private in this window. Do not paste it into chat.'
    Write-Host "Target: $jpBootRoot on CM5 mmcblk0 ($ExpectedDiskBytes bytes)."
    $jpUserName = Read-Host 'Username (press Enter for peachy)'
    if ([string]::IsNullOrWhiteSpace($jpUserName)) { $jpUserName = 'peachy' }
    $jpUserName = $jpUserName.ToLowerInvariant()
    if ($jpUserName -cnotmatch '^[a-z][a-z0-9-]{0,30}$' -or $jpUserName -eq 'root') {
        throw 'Use 1-31 lowercase letters/digits/hyphens, starting with a letter; not root.'
    }
    $jpFirst = Read-Host 'Password' -AsSecureString
    $jpSecond = Read-Host 'Repeat password' -AsSecureString
    $jpFirstPtr = [IntPtr]::Zero
    $jpSecondPtr = [IntPtr]::Zero
    try {
        $jpFirstPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($jpFirst)
        $jpSecondPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($jpSecond)
        $jpPlainFirst = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($jpFirstPtr)
        $jpPlainSecond = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($jpSecondPtr)
        if ($jpPlainFirst.Length -eq 0 -or $jpPlainFirst -cne $jpPlainSecond -or $jpPlainFirst -match '[\r\n\x00]') {
            throw 'Passwords must match, be nonempty, and contain no newline or NUL.'
        }
        $jpUserHash = Get-PiPasswordHash $jpPlainFirst
    } finally {
        if ($jpFirstPtr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($jpFirstPtr) }
        if ($jpSecondPtr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($jpSecondPtr) }
        $jpPlainFirst = $null; $jpPlainSecond = $null
        $jpFirst.Dispose(); $jpSecond.Dispose()
    }
    Assert-PiBootTarget
    $jpUserConfig = $jpUserName + ':' + $jpUserHash + "`n"
    Write-NewBootFile (Join-Path $jpBootRoot 'userconf.txt') ([Text.Encoding]::ASCII.GetBytes($jpUserConfig))
    if (-not (Test-Path -LiteralPath (Join-Path $jpBootRoot 'ssh'))) {
        Write-NewBootFile (Join-Path $jpBootRoot 'ssh') ([byte[]]@())
    }
    if ([IO.File]::ReadAllText((Join-Path $jpBootRoot 'userconf.txt')) -cne $jpUserConfig -or
        (Get-Item -LiteralPath (Join-Path $jpBootRoot 'ssh')).Length -ne 0) { throw 'Boot file verification failed.' }
    $jpUserHash = $null; $jpUserConfig = $null
    Write-Host "SUCCESS: login '$jpUserName' and SSH are prepared for the next Pi boot." -ForegroundColor Green
    Write-Host 'Tell Codex the username and that this succeeded. Do not send your password.'
    Write-Host 'Leave the USB connection in place until the boot files have been checked.'
    [void](Read-Host 'Press Enter to close this window')
} catch {
    Write-Host ('STOP: ' + $_.Exception.Message) -ForegroundColor Red
    if (-not $CheckOnly) { [void](Read-Host 'Press Enter to close; report the error without any password') }
    exit 1
}
