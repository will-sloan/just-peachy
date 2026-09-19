param(
 [string]$ReportRoot='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z',
 [string]$Namespace='five_prepared_long_v1',
 [string]$QueuePath=''
)
$ErrorActionPreference='Stop'
if($Namespace -ne 'five_prepared_long_v1'){throw 'Exact five-session dispatcher namespace required'}
if(-not $QueuePath){$QueuePath=Join-Path $ReportRoot 'serial_long_dispatcher\preparation_v1\QUEUE.json'}
function ReadSharedDocument([string]$Path,[int]$Cap=8388608){
 $resolved=[IO.Path]::GetFullPath($Path)
 $stream=[IO.File]::Open($resolved,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
 try{
  if($stream.Length -gt $Cap){throw 'Metadata exceeds byte cap'}
  $reader=[IO.BinaryReader]::new($stream)
  try{$raw=$reader.ReadBytes($Cap+1)}finally{$reader.Dispose()}
  if($raw.Length -gt $Cap){throw 'Metadata grew beyond byte cap'}
  $sha=[Security.Cryptography.SHA256]::Create()
  try{$hash=([BitConverter]::ToString($sha.ComputeHash($raw))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
  return [pscustomobject]@{value=([Text.Encoding]::UTF8.GetString($raw)|ConvertFrom-Json);binding=[pscustomobject]@{path=$resolved;bytes=$raw.Length;sha256=$hash}}
 }finally{$stream.Dispose()}
}
function SameBinding($a,$b){return $null -ne $a -and $null -ne $b -and $a.path -ceq $b.path -and $a.bytes -eq $b.bytes -and $a.sha256 -ceq $b.sha256}
function OwnerState($Owner){
 if($null -eq $Owner){return $null}
 $answer=[ordered]@{pid=$Owner.pid;recorded_creation_time=$Owner.creation_time;actual_creation_time=$null;alive_within_50ms=$null;error=$null};$process=$null
 try{
  if($Owner.pid -le 0 -or $Owner.creation_time -le 0 -or [double]::IsNaN([double]$Owner.creation_time) -or [double]::IsInfinity([double]$Owner.creation_time)){throw 'Invalid recorded identity'}
  try{$process=[Diagnostics.Process]::GetProcessById([int]$Owner.pid)}catch [ArgumentException]{$answer.alive_within_50ms=$false}
  if($null -ne $process){$created=([DateTimeOffset]$process.StartTime).ToUnixTimeMilliseconds()/1000.0;$answer.actual_creation_time=$created;$answer.alive_within_50ms=([Math]::Abs($created-$Owner.creation_time)-lt0.05)}
 }catch{$answer.error=$_.Exception.Message}finally{if($null -ne $process){$process.Dispose()}}
 return [pscustomobject]$answer
}
function ValidObservation($o,$isResult){
 if($null -eq $o.owner -or $o.requested_batches -ne 5 -or $o.completed_batches -lt 0 -or $o.completed_batches -gt 5 -or $o.completed_cells -ne $o.completed_batches){return $false}
 if($isResult){return $o.schema -eq 's6c-serial-long-dispatch-result.v1' -and $o.status -in @('DISPATCH_QUEUE_COMPLETE','STOPPED_REQUIRES_ROOT_REVIEW') -and ($o.status -ne 'DISPATCH_QUEUE_COMPLETE' -or $o.completed_batches -eq 5)}
 return $o.status -eq 'RUNNING' -and $null -ne $o.child
}
$queueDoc=ReadSharedDocument $QueuePath
$queue=$queueDoc.value
if($queue.schema -ne 's6c-serial-long-queue.v1' -or $queue.status -ne 'REGISTERED_FINITE_QUEUE' -or $queue.namespace -ne $Namespace -or $queue.total_sessions -ne 5 -or (($queue.items.candidate_id -join ',') -cne 'C065,C067,C088,C091,B36')){throw 'Exact five-session queue required'}
$directory=Join-Path (Join-Path $ReportRoot 'serial_long_dispatcher') $Namespace
$admissionPath=Join-Path $directory 'ADMISSION.json';$resultPath=Join-Path $directory 'RESULT.json';$observation=$null;$snapshotPath=$null;$skipped=0;$readErrors=@();$childOwner=$null;$status='PREPARED_NOT_STARTED'
$admission=$null
if(Test-Path -LiteralPath $directory){$status='ADMISSION_UNAVAILABLE'}
if(Test-Path -LiteralPath $admissionPath){
 $admission=(ReadSharedDocument $admissionPath).value
 if($admission.status -ne 'DISPATCHER_STARTED' -or -not (SameBinding $admission.queue $queueDoc.binding)){throw 'Dispatcher admission/queue binding differs'}
 $status='ADMITTED_AWAITING_FIRST_OBSERVATION'
 if(Test-Path -LiteralPath $resultPath){
  try{$candidate=(ReadSharedDocument $resultPath).value;if(-not (ValidObservation $candidate $true) -or -not (SameBinding $candidate.queue $queueDoc.binding)){throw 'Incomplete/invalid result'};$observation=$candidate;$snapshotPath=$resultPath;$childOwner=$candidate.possible_child}
  catch{$readErrors+=@{path=$resultPath;error=$_.Exception.Message}}
 }
 if($null -eq $observation){
  $heartbeatRoot=Join-Path $directory 'heartbeats'
  if(Test-Path -LiteralPath $heartbeatRoot){
   $blocks=@(Get-ChildItem -LiteralPath $heartbeatRoot -Directory|Where-Object {$_.Name -match '^0[01][0-9]$'}|Sort-Object Name -Descending)
   foreach($block in $blocks){
    $files=@(Get-ChildItem -LiteralPath $block.FullName -File -Filter 'HEARTBEAT_?????.json'|Sort-Object Name -Descending)
    if($files.Count -gt 1000){throw 'Snapshot block exceeds original bound'}
    foreach($file in $files){
     try{
      if($file.Name -notmatch '^HEARTBEAT_(\d{5})\.json$'){throw 'Invalid snapshot filename'};$sequence=[int]$Matches[1]
      if($sequence -lt 1 -or $sequence -gt 20000 -or [Math]::Floor(($sequence-1)/1000) -ne [int]$block.Name){throw 'Snapshot outside original sequence block'}
      $candidate=(ReadSharedDocument $file.FullName 16384).value
      if(-not (ValidObservation $candidate $false)){throw 'Invalid snapshot shape'}
      $observation=$candidate;$snapshotPath=$file.FullName;$childOwner=$candidate.child;break
     }catch{$skipped++}
    }
    if($null -ne $observation){break}
   }
  }
 }
}
if($null -ne $observation){
 if($observation.owner.pid -ne $admission.owner.pid -or $observation.owner.creation_time -ne $admission.owner.creation_time){throw 'Observation dispatcher owner differs'}
 if(@($queue.items|Where-Object item_id -EQ $observation.active_item).Count -ne 1){throw 'Observation active item outside exact queue'}
 $status=$observation.status
}
[pscustomobject]@{
 checked_utc=[DateTime]::UtcNow.ToString('o');status=$status;snapshot_path=$snapshotPath;skipped_unreadable_snapshots=$skipped;result_read_errors=$readErrors
 heartbeat_utc=$observation.created_utc;ended_utc=$observation.ended_utc;completed_sessions=$observation.completed_batches;requested_sessions=5;active_item=$observation.active_item
 dispatcher_owner=OwnerState $(if($null -ne $observation){$observation.owner}else{$admission.owner});child_owner=OwnerState $childOwner
 queue=$queueDoc.binding;result_present=(Test-Path -LiteralPath $resultPath);dispatcher_error=$observation.error;quiet_lease_present=(Test-Path -LiteralPath (Join-Path $ReportRoot 'PACED_QUIET_OWNER.json'))
 scope='Read-only immutable dispatcher metadata. One count means one continuous session. No original wrapper heartbeat, native artifact, PCM or event read. Process observations use50ms creation-time tolerance and never prove native/lease/scientific closure. Partial newest snapshots fall back to older readable snapshots; their age remains explicit.'
}|ConvertTo-Json -Depth 7
