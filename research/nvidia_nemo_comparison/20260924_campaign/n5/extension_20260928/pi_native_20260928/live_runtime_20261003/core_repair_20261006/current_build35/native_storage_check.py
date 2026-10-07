"""Private31-session native storage check; see README_NATIVE_STORAGE_CHECK.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import zipfile


def run_checks(data_root, policy):
    """Only a fresh explicit private root; retain all proof except chosen fixtures."""
    from storage import SessionStore, StorageError
    root=Path(data_root)
    if root.exists() or root.is_symlink() or root.parent.resolve(strict=True)!=root.parent:
        raise ValueError('Fresh canonical private fixture root required')
    root.mkdir(mode=0o700)
    sentinel=root/'unrelated-private-sentinel.txt'
    sentinel.write_bytes(b'preserve unrelated data\n')
    store=SessionStore(root/'recordings',policy)
    ids=[];expected={}
    spec=dict(sample_rate=16000,duration_seconds=.01,fixture='synthetic; no capture or model')
    try:
        for index in range(31):
            spool=store.begin(dict(spec,title='Storage fixture %02d'%(index+1)))
            count=64 if index==30 else 32
            raw=struct.pack('<f',index/32)*count
            spool.append_processed(0,raw[:64]);spool.append_processed(16,raw[64:])
            spool.stop(count);spool.keep()
            ids.append(spool.session_id);expected[spool.session_id]=hashlib.sha256(raw).hexdigest()
        if len(set(ids))!=31:raise AssertionError('Persistent IDs were reused')
        store.close();store=SessionStore(root/'recordings',policy)
        seen=[];cursor=None;pages=0
        while True:
            page=store.history(limit=7,before=cursor);pages+=1
            if len(page['items'])>7:raise AssertionError('Unbounded History page')
            seen.extend(row['session_id'] for row in page['items'])
            cursor=page['next_cursor']
            if cursor is None:break
        if seen!=ids[::-1] or pages!=5:raise AssertionError('Restart/History timeline differs')
        replay_digest=hashlib.sha256();replay_samples=0
        for start,raw in store.iter_processed(ids[-1],block_samples=8):
            if start!=replay_samples:raise AssertionError('Full recording replay has a gap')
            replay_digest.update(raw);replay_samples+=len(raw)//4
        if replay_samples!=64 or replay_digest.hexdigest()!=expected[ids[-1]]:
            raise AssertionError('Full recording replay readback differs')
        exports=root/'exports';exports.mkdir()
        for name,selected in (('single.zip',[ids[-1]]),('selected.zip',[ids[0],ids[-1]])):
            destination=exports/name;store.export(selected,destination)
            with zipfile.ZipFile(destination) as archive:
                if {name.split('/')[0] for name in archive.namelist()}!=set(selected):
                    raise AssertionError('Export escaped the selected session set')
        deleted=ids[1]
        try:store.delete(deleted)
        except StorageError:pass
        else:raise AssertionError('Deletion lacked deliberate confirmation')
        store.delete(deleted,confirm=True)
        if store.read(ids[0])['status']!='kept' or sentinel.read_bytes()!=b'preserve unrelated data\n':
            raise AssertionError('Individual deletion modified unrelated data')
        receipt_ids=[]
        for failure in (False,True):
            spool=store.begin(spec);spool.append_processed(0,struct.pack('<f',0))
            spool.fail('intentional private fixture failure') if failure else spool.cancel()
            receipt_ids.append(spool.session_id)
        spool=store.begin(spec);spool.append_processed(0,struct.pack('<f',.5));spool.stop(1)
        discarded=spool.session_id;spool.discard()
        # Repeated closed receipts do not consume a global recording slot.
        spool=store.begin(spec);spool.append_processed(0,struct.pack('<f',.25));spool.stop(1);spool.keep()
        subsequent=spool.session_id
        return dict(status='STORAGE_CHECK_PASSED',synthetic=True,model_executed=False,capture_executed=False,
            data_root=str(root),primary_sessions=31,sessions_created=35,unique_ids=ids,
            paged_after_restart=True,page_size=7,pages=pages,selected_export_checked=True,single_export_checked=True,
            complete_replay_samples=replay_samples,complete_replay_sha256=replay_digest.hexdigest(),
            deliberate_deleted_id=deleted,unrelated_sentinel_preserved=True,
            failed_cancelled_receipt_ids=receipt_ids,discarded_id=discarded,subsequent_kept_id=subsequent,
            global_session_slots_used=None,automatic_personal_data_cleanup=False)
    finally:store.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binding',type=Path,required=True)
    ap.add_argument('--package-manifest-sha256',required=True)
    ap.add_argument('--unit',required=True)
    ap.add_argument('--unit-ownership',type=Path,required=True)
    ap.add_argument('--owner-directory',type=Path,required=True)
    ap.add_argument('--data-root',type=Path,required=True)
    args=ap.parse_args()
    if platform.system()!='Linux' or platform.machine()!='aarch64':
        raise RuntimeError('Native storage entry requires the owned CM5 wrapper; use host tests on PC')
    os.sched_setaffinity(0,{3})
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,128*1024**2))
    resource.setrlimit(resource.RLIMIT_STACK,(1024**2,1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    args.owner_directory.mkdir(mode=0o700,exist_ok=False)
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
               boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    with (args.owner_directory/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(owner,stream);stream.flush();os.fsync(stream.fileno())
    from runtime_support import publish,strict,verify_owned_unit
    from native_scope import verified_inventory
    from storage import StoragePolicy
    package=Path(__file__).resolve().parent
    verified_inventory(package,args.package_manifest_sha256)
    unit=verify_owned_unit(args.unit,args.unit_ownership)
    if args.binding!=package/'BINDING.json' or args.data_root!=args.owner_directory/'fixtures':
        raise ValueError('Exact package and private fixture destination required')
    binding=strict(args.binding.read_bytes())
    result=None
    try:
        result=run_checks(args.data_root,StoragePolicy(**binding.get('storage_policy',{})))
        result.update(owner=owner,unit=unit,native_executed=True)
    except BaseException as error:
        result=dict(status='STORAGE_CHECK_FAILED',owner=owner,unit=unit,native_executed=True,
                    capture_executed=False,model_executed=False,failure=repr(error))
    publish(args.owner_directory/'STORAGE_RESULT.json',result)
    return 0 if result['status']=='STORAGE_CHECK_PASSED' else 1


if __name__=='__main__':raise SystemExit(main())
