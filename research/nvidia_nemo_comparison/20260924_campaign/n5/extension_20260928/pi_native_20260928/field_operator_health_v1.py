"""Read-only native broker health; README_FIELD_OPERATOR_HEALTH_V1.md."""
from datetime import datetime,timezone
import fcntl
import os
from pathlib import Path
import resource
import shutil
import stat
import time
from field_operator_session_ledger_v4 import read,file_pin,identity,ticks
from field_operator_session_plan_v3 import validate_policy,state

def inspect_closed(root,policy_sha256):
    """Inspect expired evidence without constructing Ledger/Store or authorizing writes."""
    root=Path(root).absolute()
    if os.uname().machine!='aarch64' or os.sched_getaffinity(0)!={3}:
        raise ValueError('Read-only native CPU3 utility required')
    if resource.getrlimit(resource.RLIMIT_AS)!=(134217728,)*2 or resource.getrlimit(resource.RLIMIT_STACK)!=(1048576,)*2 or resource.getrlimit(resource.RLIMIT_FSIZE)!=(0,)*2:
        raise ValueError('Read-only utility resource envelope')
    campaign=Path.home()/'JustPeachy/research/nemotron-20260928'
    if root.parent!=campaign or root.resolve()!=root:raise ValueError('Canonical existing broker root')
    policy=read(root/'RELEASE.json')
    if file_pin(root/'RELEASE.json')['sha256']!=policy_sha256 or policy['root']!=str(root):
        raise ValueError('Exact historical policy binding')
    validate_policy(policy,now=datetime.fromisoformat(policy['issued_utc']))
    # Taking a shared lock on an existing directory creates no lease or files.
    fd=os.open(root/'broker',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
        result=_inspect(root,policy,policy_sha256)
    finally:os.close(fd)
    return result

def _inspect(root,policy,policy_sha256):
    from field_operator_broker_files_v2 import inspect
    inspect(root)
    manifest=read(root/'broker/MANIFEST.json',131072)
    if file_pin(root/'broker/MANIFEST.json')['sha256']!=policy['release_manifest_sha256']:
        raise ValueError('Historical capsule manifest pin')
    paths=set()
    for row in manifest['files']:
        parts=Path(row['path']).parts
        if len(parts)!=2 or parts[0] not in ('broker','code') or '..' in parts or row['path'] in paths:
            raise ValueError('Exact unique capsule members')
        paths.add(row['path'])
        if file_pin(root/row['path'])!=dict(bytes=row['bytes'],sha256=row['sha256']):
            raise ValueError('Historical capsule bytes changed')
    if {p.name for p in (root/'code').iterdir()}!={Path(p).name for p in paths if p.startswith('code/')}:
        raise ValueError('Unpinned historical code')
    now=identity();owners=[];gaps=[];slots=[];complete=True
    def owner_at(path,required=True):
        if not path.exists():
            if required:gaps.append(path.relative_to(root).as_posix()+': missing identity')
            return None
        row=read(path,16384)
        if set(row)!={'pid','boot_id','start_ticks'} or any(type(row[k]) is not int or row[k]<=0 for k in ('pid','start_ticks')):
            raise ValueError('Exact recorded native identity')
        observed=ticks(row['pid']);alive=now['boot_id']==row['boot_id'] and observed==row['start_ticks']
        owners.append(dict(path=path.relative_to(root).as_posix(),owner=row,exact_alive=alive))
        return row
    for name in ('STAGE_OWNER.json','GATE_OWNER.json','OWNER.json'):owner_at(root/'broker'/name)
    for slot in policy['allocation']['slot_names']:
        directory=root/slot;recording=root/'recordings'/slot
        records={p.stem:read(p,16384) for p in directory.iterdir()}
        phase=state(records)
        for value in records.values():
            if value.get('slot')!=slot or value.get('policy_sha256')!=policy_sha256:raise ValueError('Historical slot policy pin')
        info=dict(slot=slot,state=phase,source_samples=None,saved=False)
        if phase=='UNUSED':complete=False;slots.append(info);continue
        if phase!='CLOSED':complete=False
        if 'STAGED' in records:
            owner_at(recording/'control/OWNER.json')
            child_path=recording/'parent_control/OWNER.json'
            # Missing child could be pre-constructor failure, never a fabricated identity.
            if child_path.exists():owner_at(child_path)
        if (recording/'source/CHILD_OWNER.json').exists():owner_at(recording/'source/CHILD_OWNER.json')
        if phase=='CLOSED':
            closed=records['CLOSED']
            for name,pin in closed['pins'].items():
                path=recording/name
                if path.resolve()!=path or not path.is_relative_to(recording) or file_pin(path)!=pin:
                    raise ValueError('Exact closed-receipt pin')
            parent=read(recording/'parent_control/RESULT.json')
            app=read(recording/'receipts/APPLICATION_CLOSURE.json')
            actual=read(recording/'receipts/RESULT.json')
            if not (parent['child_reaped'] and parent['capture_closed'] and app['controller_closed'] and app['worker_joined'] and app['capture_closed']) or app['pending_commands'] or app['physical']['open_writable_descriptors'] or app['physical']['failures']:
                raise ValueError('Actual physical closure receipts')
            if actual.get('actual_capture_started'):
                if not (recording/'source/CHILD_OWNER.json').exists():raise ValueError('Captured source identity absent')
                model=read(recording/'receipts/MODEL_CLOSURE.json');stop=read(recording/'receipts/GUI_STOP.json')
                samples=actual['source_samples']
                if not model['closed'] or not model['finish_observed'] or model['samples']!=samples or stop['archive']['recorded_samples']!=samples or not stop['archive']['closed'] or stop['archive']['archive_error'] is not None:
                    raise ValueError('Closed source/model/archive accounting')
                info['source_samples']=samples
            folders=list((recording/'data/conversations').iterdir())
            if len(folders)>1:raise ValueError('Independent single recording')
            if folders:
                folder=folders[0]
                if folder.is_symlink() or not folder.is_dir():raise ValueError('Historical recording path')
                meta=read(folder/'conversation.json')
                info['saved']=meta.get('state')=='SAVED' and meta.get('pinned') is True
                info['metadata_pin']=file_pin(folder/'conversation.json')
        slots.append(info)
    active=[o for o in owners if o['exact_alive']]
    capture_closed=Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    leases=[]
    for path in (root.parent/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock'):
        with path.open('rb') as handle:
            try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:leases.append(dict(path=str(path),free=False))
            else:fcntl.flock(handle,fcntl.LOCK_UN);leases.append(dict(path=str(path),free=True))
    quiescent=not active and capture_closed and all(x['free'] for x in leases)
    status='CLOSED_HISTORY_AVAILABLE' if complete and quiescent and not gaps else 'FENCED_PRESERVED'
    return dict(schema='just-peachy.closed-broker-health.v1',status=status,root=str(root),policy_sha256=policy_sha256,
        checked_utc=datetime.now(timezone.utc).isoformat(),current_boot=now['boot_id'],owners=owners,
        identity_gaps=gaps,slots=slots,capture_closed=capture_closed,leases=leases,quiescent=quiescent,
        minimum_free_floor_met=shutil.disk_usage(root).free>=5*1024**3,
        policy_expired=datetime.now(timezone.utc)>=datetime.fromisoformat(policy['expires_utc']),
        original_ledger_write_authorized=False,failure_cleared=False,new_capture_authorized=False,
        physical_touch_tested=False,offline_boot_tested=False)
