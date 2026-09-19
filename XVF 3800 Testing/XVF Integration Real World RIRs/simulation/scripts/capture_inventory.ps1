param([Parameter(Mandatory=$true)][string]$Report)
# Read-only desktop/Git snapshot. Run before other stages; see ../README.md.
$ErrorActionPreference = 'Stop'
$S0Sim = Split-Path $PSScriptRoot -Parent
$S0Project = Split-Path $S0Sim -Parent
$S0Repo = Split-Path (Split-Path $S0Project -Parent) -Parent
New-Item -ItemType Directory -Force -Path $Report | Out-Null
if (Test-Path -LiteralPath (Join-Path $Report 'git_before.json')) { throw 'Snapshot exists; use a new report directory.' }
$S0Git = @{}
foreach ($S0Pair in @(@('main',$S0Repo),@('nested',$S0Project))) {
    $S0Commit = & git -C $S0Pair[1] rev-parse --verify --quiet HEAD
    $S0Git[$S0Pair[0]] = @{root=$S0Pair[1];commit=if($LASTEXITCODE -eq 0){$S0Commit}else{$null};branch=(& git -C $S0Pair[1] branch --show-current);status=@(& git -C $S0Pair[1] status --porcelain=v1)}
}
$S0Git | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Report 'git_before.json') -Encoding utf8
$S0Observation=@{
    timestamp_utc=[DateTime]::UtcNow.ToString('o')
    cpu=Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
    memory=Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory
    drives=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace,VolumeName)
    disks=@(Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size)
    gpu=@(& nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader)
    conda_environments=@(Get-Content -LiteralPath 'C:\Users\amiri\.conda\environments.txt')
    existing_python_processes=@(Get-Process python -ErrorAction SilentlyContinue | Select-Object Id,Path)
    port8767=@(Get-NetTCPConnection -LocalPort 8767 -ErrorAction SilentlyContinue | Select-Object State,OwningProcess)
}
$S0Observation | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Report 'resource_observations.json') -Encoding utf8
