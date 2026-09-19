param(
    [string]$ReportRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z',
    [string]$Namespace = 'remaining_batches_after_c118_v3',
    [string]$QueueName = 'PACED_RUNTIME_QUEUE_AFTER_C118_V3.json'
)
$ErrorActionPreference = 'Stop'
function ReadSharedJson([string]$Path, [long]$Cap = 8388608) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    try {
        if ($stream.Length -gt $Cap) { throw 'Metadata exceeds read cap' }
        $reader = [IO.StreamReader]::new($stream)
        try { return ($reader.ReadToEnd() | ConvertFrom-Json) } finally { $reader.Dispose() }
    } finally { $stream.Dispose() }
}
function OwnerState($Owner) {
    if ($null -eq $Owner) { return $null }
    $answer = [ordered]@{pid=$Owner.pid; recorded_creation_time=$Owner.creation_time; actual_creation_time=$null; exact_alive=$null; error=$null}
    $process = $null
    try {
        if ($Owner.pid -le 0 -or $Owner.creation_time -le 0 -or [double]::IsNaN([double]$Owner.creation_time) -or [double]::IsInfinity([double]$Owner.creation_time)) { throw 'Invalid recorded process identity' }
        $process = $null
        try { $process = [Diagnostics.Process]::GetProcessById([int]$Owner.pid) } catch [ArgumentException] { $answer.exact_alive=$false }
        if ($null -eq $process) { $answer.exact_alive=$false }
        else {
            $created = ([DateTimeOffset]$process.StartTime).ToUnixTimeMilliseconds()/1000.0
            $answer.actual_creation_time=$created
            $answer.exact_alive=([Math]::Abs($created-$Owner.creation_time) -lt 0.05)
        }
    } catch { $answer.error=$_.Exception.Message } finally { if ($null -ne $process) { $process.Dispose() } }
    return [pscustomobject]$answer
}
$directory = Join-Path (Join-Path $ReportRoot 'serial_paced_dispatcher') $Namespace
$resultPath = Join-Path $directory 'RESULT.json'
$resultPresent = Test-Path -LiteralPath $resultPath
$snapshotPath = $null
$skipped = 0
$observation = $null
if ($resultPresent) {
    $observation = ReadSharedJson $resultPath
    $childOwner = $observation.possible_child
} else {
    $blocks = @(Get-ChildItem -LiteralPath (Join-Path $directory 'heartbeats') -Directory | Where-Object {$_.Name -match '^0[01][0-9]$'} | Sort-Object Name -Descending)
    foreach ($block in $blocks) {
        $files = @(Get-ChildItem -LiteralPath $block.FullName -File -Filter 'HEARTBEAT_?????.json' | Sort-Object Name -Descending)
        if ($files.Count -gt 1000) { throw 'Unexpected snapshot block size' }
        foreach ($file in $files) {
            try {
                $candidate = ReadSharedJson $file.FullName 16384
                if ($candidate.status -ne 'RUNNING' -or $null -eq $candidate.owner -or $null -eq $candidate.child) { throw 'Invalid snapshot shape' }
                $observation=$candidate; $snapshotPath=$file.FullName; break
            } catch { $skipped++ }
        }
        if ($null -ne $observation) { break }
    }
    if ($null -eq $observation) { throw 'No readable dispatcher snapshot; inspect admission and original owners without relaunching' }
    $childOwner = $observation.child
}
$queue = ReadSharedJson (Join-Path (Join-Path $ReportRoot 'design') $QueueName)
$item = @($queue.items | Where-Object item_id -EQ $observation.active_item | Select-Object -First 1)
$child = $null
if ($item.Count -eq 1 -and $null -ne $childOwner) {
    foreach ($path in @((Join-Path $item[0].output_root 'HEARTBEAT.json'), (Join-Path $ReportRoot ('paced_controls\'+$observation.active_item+'\HEARTBEAT.json')))) {
        if (Test-Path -LiteralPath $path) { $child=ReadSharedJson $path; break }
    }
}
[pscustomobject]@{
    checked_utc=[DateTime]::UtcNow.ToString('o'); status=$observation.status
    snapshot_path=$snapshotPath; skipped_unreadable_snapshots=$skipped
    heartbeat_time=$observation.created_utc; ended_utc=$observation.ended_utc
    completed_batches=$observation.completed_batches; requested_batches=$observation.requested_batches
    completed_batch_cells=$observation.completed_cells; active_item=$observation.active_item
    child_status=$child.status; child_completed=$child.completed; child_requested=$child.requested; job=$child.job_id
    dispatcher_owner=OwnerState $observation.owner; child_owner=OwnerState $childOwner
    result_present=$resultPresent; dispatcher_error=$observation.error
    quiet_lease_present=(Test-Path -LiteralPath (Join-Path $ReportRoot 'PACED_QUIET_OWNER.json'))
    scope='Read-only status observation. A stale heartbeat or absent PID does not prove original batch closure or scientific completion.'
} | ConvertTo-Json -Depth 5
