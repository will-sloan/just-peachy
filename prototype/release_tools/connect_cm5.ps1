# Interactive bootstrap only. See README_CM5_CONNECT.md.
[CmdletBinding()]
param(
    [string]$PiHost = '192.168.2.57',
    [string]$UserName = 'peachyprototype',
    [string]$IdentityFile = "$env:USERPROFILE\.ssh\just_peachy_cm5_ed25519"
)
$ErrorActionPreference = 'Stop'
try {
    if ($PiHost -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$' -or
        $UserName -cnotmatch '^[a-z][a-z0-9-]{0,30}$' -or $UserName -eq 'root') {
        throw 'Expected an explicit Pi hostname/address and ordinary lowercase username.'
    }
    if (-not (Test-Path -LiteralPath $IdentityFile -PathType Leaf)) { throw 'Dedicated private key is missing.' }
    $jpPublicKey = [IO.File]::ReadAllText($IdentityFile + '.pub').Trim()
    if ($jpPublicKey -notmatch '^ssh-ed25519 [A-Za-z0-9+/=]+(?: .*)?$') { throw 'Expected Ed25519 public key.' }
    $jpPublicKey64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($jpPublicKey))
    $jpRemote = @'
import base64, json, os, pathlib, platform, socket
model = pathlib.Path('/proc/device-tree/model').read_text().rstrip('\x00')
if not model.startswith('Raspberry Pi Compute Module 5'):
    raise SystemExit('Refusing key setup: connected hardware is not a CM5: ' + model)
if os.getuid() == 0:
    raise SystemExit('Refusing root account')
key = base64.b64decode('PUBLIC_KEY_BASE64').decode('ascii').strip()
home = pathlib.Path.home()
ssh_dir = home / '.ssh'
keys = ssh_dir / 'authorized_keys'
if ssh_dir.is_symlink() or keys.is_symlink():
    raise SystemExit('Refusing symlinked SSH paths')
ssh_dir.mkdir(mode=0o700, exist_ok=True)
os.chmod(ssh_dir, 0o700)
existing = keys.read_text() if keys.exists() else ''
if key not in existing.splitlines():
    old_umask = os.umask(0o077)
    try:
        with keys.open('a') as output:
            output.write(('\n' if existing and not existing.endswith('\n') else '') + key + '\n')
            output.flush()
            os.fsync(output.fileno())
    finally:
        os.umask(old_umask)
os.chmod(keys, 0o600)
print(json.dumps({'status':'CM5_KEY_INSTALLED','model':model,'hostname':socket.gethostname(),
    'architecture':platform.machine(),'python':platform.python_version(),'uid':os.getuid()}))
'@
    $jpRemote = $jpRemote.Replace('PUBLIC_KEY_BASE64', $jpPublicKey64)
    $jpEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($jpRemote))
    $jpCommand = "printf %s $jpEncoded | base64 -d | python3"
    $Host.UI.RawUI.WindowTitle = 'Just Peachy - first CM5 SSH connection'
    Write-Host "Connecting to your confirmed Raspberry Pi: ${UserName}@${PiHost}"
    Write-Host 'SSH may ask you to trust this host on the first connection.'
    Write-Host 'Enter your Pi password here when asked. Characters will not appear.'
    Write-Host 'The remote command verifies CM5 hardware, then appends only your dedicated public key.'
    & ssh.exe -t -o StrictHostKeyChecking=ask -o ConnectTimeout=10 -o PreferredAuthentications=password,keyboard-interactive -o PubkeyAuthentication=no "$UserName@$PiHost" $jpCommand
    if ($LASTEXITCODE -ne 0) { throw 'SSH setup failed; inspect the message above. No successful setup is claimed.' }
    Write-Host 'SUCCESS: dedicated CM5 SSH key installed. Tell Codex this completed.' -ForegroundColor Green
    [void](Read-Host 'Press Enter to close')
} catch {
    Write-Host ('STOP: ' + $_.Exception.Message) -ForegroundColor Red
    [void](Read-Host 'Press Enter to close; report the error without passwords')
    exit 1
}
