"""Focused host storage/terminal/lease-failure check V2; see README_STORAGE.md."""
import ctypes
import os
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.GetCurrentProcess.restype=ctypes.c_void_p
kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
handle=kernel.GetCurrentProcess()
if not kernel.SetProcessAffinityMask(handle,1<<14):raise ctypes.WinError(ctypes.get_last_error())
stamps=[ctypes.c_ulonglong() for _ in range(4)]
if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in stamps)):
    raise ctypes.WinError(ctypes.get_last_error())
import argparse
import json
import time
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--baseline',type=Path,required=True)
parser.add_argument('--stats-file',type=Path,required=True)
parser.add_argument('--work-stats-file',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir()
started=time.time();written=0
MAXIMUM=128*1024**2
def put(name,value):
    global written
    raw=value if isinstance(value,bytes) else json.dumps(value,sort_keys=True,allow_nan=False).encode()
    if len(raw)>262144 or written+len(raw)>MAXIMUM or time.time()-started>60:
        raise ValueError('Finite storage repair review budget exceeded')
    with (args.output/name).open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short review write')
        stream.flush();os.fsync(stream.fileno())
    written+=len(raw)
    if (args.output/name).read_bytes()!=raw:raise OSError('Independent review readback differs')
owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),
    create_time=(stamps[0].value-116444736000000000)/10000000,
    creation_filetime=stamps[0].value,cpu=14,affinity_mask=16384)
put('REGISTERED_OWNER.json',owner)
put('HOST_SCOPE.json',dict(issued_unix=started,maximum_seconds=60,maximum_bytes=MAXIMUM,
    native_action=False,synthetic_volume_and_host_lease_faults=True))
import ast
import hashlib
import importlib.util
import shutil
import sys
status='FAILED';groups=[];rejects=[]
def denied(label,call,types):
    try:call()
    except types:rejects.append(label)
    else:raise AssertionError('Expected rejection: '+label)
def load(name,raw):
    spec=importlib.util.spec_from_loader(name,loader=None)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    exec(compile(raw,name,'exec'),module.__dict__)
    return module
def definitions(raw):
    result={}
    for node in ast.parse(raw.decode('utf-8')).body:
        if isinstance(node,ast.FunctionDef):result[node.name]=ast.dump(node,include_attributes=False)
        elif isinstance(node,ast.ClassDef):
            for member in node.body:
                if isinstance(member,ast.FunctionDef):
                    result[node.name+'.'+member.name]=ast.dump(member,include_attributes=False)
    return result
try:
    pins=[];raws={}
    paths=[args.source/'storage.py',args.source/'README_STORAGE.md',Path(__file__),
           args.baseline/'storage.py',args.baseline/'runtime_support.py',args.stats_file,args.work_stats_file]
    for index,path in enumerate(paths):
        raw=path.read_bytes()
        if path.is_symlink() or len(raw)>262144:raise ValueError('Bounded regular source/stats input required')
        put('SOURCE_%02d.backup'%index,raw)
        restored=(args.output/('SOURCE_%02d.backup'%index)).read_bytes()
        put('SOURCE_%02d.restore'%index,restored)
        if restored!=raw or path.read_bytes()!=raw:raise OSError('Independent source restore differs')
        pins.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        raws[str(path)]=raw
    put('SOURCE_CLOSED.json',dict(pins=pins,closed_unix=time.time(),backup_and_independent_restore=True,before_check=True))
    for drive,floor in (('C:/',50*1024**3),('G:/',75*1024**3)):
        if shutil.disk_usage(drive).free-MAXIMUM<floor:raise ValueError('Actual host free-space floor required')
    stats=json.loads(raws[str(args.stats_file)])['action_result']
    if stats['session_id']!='8c5d357f0acc4640bfcda4697d7e325b' or stats['processed_samples']!=808000:
        raise ValueError('Actual failed19 numeric session pin required')
    if stats['metadata_usage']!=dict(used_bytes=9598100,limit_bytes=9830400):
        raise ValueError('Actual immutable failed19 meter differs')
    work_stats=json.loads(raws[str(args.work_stats_file)])['action_result']
    if (work_stats['session_id']!=stats['session_id'] or work_stats['work_total_bytes']!=15646953
            or work_stats['file_contents_returned'] is not False):
        raise ValueError('Actual bounded failed19 work producer statistics required')
    old=raws[str(args.baseline/'storage.py')];new=raws[str(args.source/'storage.py')]
    a,b=definitions(old),definitions(new)
    changed={key for key in a if a[key]!=b[key]}
    expected={'StoragePolicy.estimate_bytes','metadata_limits','_Lease.close','SessionStore.__init__',
        'SessionStore._charge_metadata','SessionStore.delete','SessionSpool._release','SessionSpool.fail'}
    if changed!=expected or set(b)-set(a)!={'SessionStore.write_terminal_event'} or set(a)-set(b):
        raise ValueError('Unexpected storage method AST change: '+repr((changed,set(b)-set(a))))
    sys.dont_write_bytecode=True
    legacy=load('speech_storage_old',old);current=load('speech_storage_new',new)
    spec=dict(duration_seconds=70,sample_rate=16000,mode='processed',
        metadata_reserve_bytes=2*(16*1024**2+70*256*1024),metadata_split='text1_sqlite1_v2',
        terminal_metadata_reserve_bytes=256*1024)
    limits=current.metadata_limits(spec,1024**2)
    if limits!=dict(text_bytes=35127296,sqlite_bytes=36175872,terminal_sqlite_bytes=262144):
        raise AssertionError('Fresh disjoint70s plan differs')
    old_spec={**spec,'metadata_split':'text3_sqlite1_v1','metadata_reserve_bytes':35127296}
    old_spec.pop('terminal_metadata_reserve_bytes')
    if current.metadata_limits(old_spec,1024**2)['sqlite_bytes']!=9830400:
        raise AssertionError('Old explicit split was upgraded')
    if current.metadata_limits({'metadata_reserve_bytes':600},60)['sqlite_bytes']!=160:
        raise AssertionError('Legacy absent split changed')
    old_plan=legacy.StoragePolicy().estimate_bytes(old_spec)
    new_plan=current.StoragePolicy().estimate_bytes(spec)
    if new_plan-old_plan!=35127296+262144:raise AssertionError('Fresh enlarged reserve and terminal pool not charged exactly once')
    raw_spec={**spec,'mode':'raw_processed','raw':dict(sample_rate=16000,channels=4,sample_width_bytes=4,
        encoding='pcm32le',qualification=dict(qualified=True,evidence='synthetic-plan-calculator-only'))}
    raw_plan=current.StoragePolicy().estimate_bytes(raw_spec)+32*1024**2
    if new_plan!=78371636 or raw_plan!=129903412 or raw_plan>=160*1024**2:
        raise AssertionError('Full raw70s plan under fresh160MiB differs')
    groups.append('fresh_plan_explicitly_charges_enlarged_pools_and_preserves_old_policy')
    support=load('speech_storage_runtime_support',raws[str(args.baseline/'runtime_support.py')])
    # Existing aggregate text writer, observed producer bytes extrapolated to70s.
    # This is synthetic disk I/O; it does not replay private text or sensor data.
    text_target=(work_stats['work_total_bytes']*70*16000+stats['processed_samples']-1)//stats['processed_samples']
    text_budget=support.DiskBudget(limits['text_bytes'])
    text_writer=support.SegmentedText(args.output/'synthetic-producer-volume.jsonl',
        maximum_bytes=limits['text_bytes'],budget=text_budget)
    accepted=0
    try:
        while accepted<text_target:
            count=min(128*1024,text_target-accepted)
            while text_writer.pending+count>2*1024**2:
                if text_writer.error or time.time()-started>55:raise RuntimeError('Text fixture writer failed/deadline')
                time.sleep(.001)
            text_writer.write('s'*(count-1)+'\n');accepted+=count
        text_writer.close()
    finally:
        if not text_writer.closed:text_writer.close()
    text_metrics=text_writer.metrics()
    if text_metrics['completed']!=text_target or text_budget.accepted!=text_target:
        raise AssertionError('Complete finite synthetic text producer volume missing')
    groups.append('aggregate_text_writer_complete_observed_rate70s_volume')
    # This is synthetic public-writer load. It uses no audio or private captions.
    # Two reversible hash streams make compression/charging representative rather
    # than filling SQLite with repeated zeroes. Every caption revision is retained.
    noise=''.join(hashlib.sha256(('fixture-%d'%i).encode()).hexdigest() for i in range(145))
    provenance=dict(synthetic_fixture=True,ui_projection=dict(numeric_fixture=noise))
    source_payload=dict(synthetic_fixture=True,blocks=[dict(sequence=i,clock=i/100,
        numeric_fixture=noise[i*128:(i+1)*128]) for i in range(10)])
    observations=[]
    for module,label,this_spec in ((legacy,'old',old_spec),(current,'new',spec)):
        store=module.SessionStore(args.output/(label+'-volume'),module.StoragePolicy(reserve_fraction=0))
        spool=store.begin(this_spec);failed=None;completed=0
        for tick in range(700):
            try:
                store.write_event(spool.session_id,'source_batch',{**source_payload,'sequence':tick})
                if tick<600:
                    store.write_caption(spool.session_id,'synthetic-%02d'%(tick%19),tick*1600,(tick+1)*1600,
                        'Synthetic fixture %d'%tick,provenance={**provenance,'revision_tick':tick})
            except module.CapacityError as error:
                failed=str(error);break
            completed+=1
            if tick%50==0 and time.time()-started>55:raise RuntimeError('Focused check deadline exceeded')
        with store._db() as db:
            used,limit=db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',
                                 (spool.session_id,)).fetchone()
        observations.append(dict(policy=label,completed_ticks=completed,used_bytes=used,limit_bytes=limit,
            metadata_error=failed,private_audio_or_text=False))
        if label=='old':
            if failed is None or completed>=600:raise AssertionError('Actual old cap was not exercised')
            spool.fail('Synthetic volume allocation failure')
        else:
            if failed is not None or completed!=700:raise AssertionError('Complete changed volume failed')
            spool.stop(0)
        store.close()
    groups.append('complete70s_synthetic_public_caption_and_source_volume')
    store=current.SessionStore(args.output/'terminal',current.StoragePolicy(reserve_fraction=0));spool=store.begin(spec)
    ordinary_limit=limits['sqlite_bytes']-262144
    # Exhaust through the real persistent meter once; terminal writes still use
    # the public API and are independently charged, rather than bypassing guards.
    with store._db() as db:store._charge_metadata(db,spool.session_id,ordinary_limit)
    denied('ordinary_full',lambda:store.write_event(spool.session_id,'health',{}),current.CapacityError)
    ordinary_before=None
    with store._db() as db:ordinary_before=tuple(db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',(spool.session_id,)).fetchone())
    for kind in ('source_closure','session_cleanup','saved_spatial_closed'):
        row=store.write_terminal_event(spool.session_id,kind,dict(synthetic_fixture=True,physical_process_closed=False))
        if store.write_terminal_event(spool.session_id,kind,dict(synthetic_fixture=True,physical_process_closed=False))!=row:
            raise AssertionError('Terminal idempotence lost')
    denied('contradict_terminal',lambda:store.write_terminal_event(spool.session_id,'source_closure',{'changed':True}),current.StorageError)
    denied('unknown_terminal_kind',lambda:store.write_terminal_event(spool.session_id,'health',{}),ValueError)
    denied('oversized_terminal',lambda:store.write_terminal_event(spool.session_id,'session_failure',{'too_big':'x'*16384}),ValueError)
    spool.fail('Synthetic full-volume failure')
    if not spool.closed or spool._session_lock.file is not None or spool._lease.file is not None:
        raise AssertionError('Failed spool leases remain held')
    with store._db() as db:
        ordinary_after=tuple(db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',(spool.session_id,)).fetchone())
        terminal_usage=tuple(db.execute('SELECT used_bytes,limit_bytes FROM terminal_metadata_usage WHERE session_id=?',(spool.session_id,)).fetchone())
        terminal_count=db.execute('SELECT COUNT(*) FROM terminal_events WHERE session_id=?',(spool.session_id,)).fetchone()[0]
    if ordinary_after!=ordinary_before or terminal_count!=4 or terminal_usage[0]>terminal_usage[1] or terminal_usage[1]!=262144:
        raise AssertionError('Terminal and ordinary pools overlap or lose terminal facts')
    if store.read(spool.session_id)['status']!='failed':raise AssertionError('Terminal cleanup cleared original failure')
    store.close();groups.append('ordinary_exhaustion_independent_terminal_and_fail_release')
    old_store=current.SessionStore(args.output/'old-session',current.StoragePolicy(reserve_fraction=0));old_spool=old_store.begin(old_spec)
    denied('old_session_no_terminal_upgrade',lambda:old_store.write_terminal_event(old_spool.session_id,'session_cleanup',{}),current.CapacityError)
    old_spool.cancel();old_store.close()
    denied('bool_terminal_reserve',lambda:current.metadata_limits({**spec,'terminal_metadata_reserve_bytes':True},0),ValueError)
    denied('unreviewed_terminal_size',lambda:current.metadata_limits({**spec,'terminal_metadata_reserve_bytes':262145},0),ValueError)
    groups.append('strict_spec_and_legacy_no_upgrade')
    fault_store=current.SessionStore(args.output/'lease-fault',current.StoragePolicy(reserve_fraction=0));fault=fault_store.begin(spec)
    first=fault._session_lock;real_kernel=first._kernel
    class FailingUnlock:
        def UnlockFileEx(self,*args):ctypes.set_last_error(5);return 0
    first._kernel=FailingUnlock()
    denied('unlock_failure_retained',lambda:fault._release(),OSError)
    if not fault.closed or first.file is not None or fault._lease.file is not None:
        raise AssertionError('Unlock fault skipped another resource release')
    # Kernel close releases actual locks even though the explicit unlock failed.
    with current._Lease(fault_store.root/'active.lock'):
        with fault_store._session_lease(fault.session_id):pass
    fault_store.close();groups.append('windows_unlock_fault_closes_both_actual_leases')
    publish_store=current.SessionStore(args.output/'terminal-publication-fault',current.StoragePolicy(reserve_fraction=0))
    publish_spool=publish_store.begin(spec)
    def fail_terminal(*args,**kwargs):raise OSError('Synthetic terminal write fault')
    publish_store.write_terminal_event=fail_terminal
    denied('terminal_publication_failure_retained',lambda:publish_spool.fail('Original synthetic run failure'),OSError)
    if not publish_spool.closed or publish_store.read(publish_spool.session_id)['status']!='failed':
        raise AssertionError('Terminal publication fault cleared failure or retained leases')
    with current._Lease(publish_store.root/'active.lock'):
        with publish_store._session_lease(publish_spool.session_id):pass
    publish_store.close();groups.append('terminal_write_failure_preserves_failure_and_releases_leases')
    for path in paths:
        if path.read_bytes()!=raws[str(path)]:raise ValueError('Source changed after backup')
    total=sum(path.stat().st_size for path in args.output.rglob('*') if path.is_file())
    if total>MAXIMUM:raise ValueError('Measured host output exceeds full scope')
    status='PASS_CHANGED_SPEECH_STORAGE_POOL_AND_TERMINAL_CLEANUP'
    put('RESULT.json',dict(status=status,groups=groups,rejects=rejects,source_sha256=hashlib.sha256(new).hexdigest(),
        source_bytes=len(new),changed_methods=sorted(changed),added_methods=sorted(set(b)-set(a)),unchanged_methods=len(a)-len(changed),
        actual19_numeric_basis=dict(processed_samples=808000,used_bytes=9598100,limit_bytes=9830400,
            caption_count=19,caption_revision_count=420,source_batch_count=504,work_total_bytes=15646953,
            work_inventory_sha256=work_stats['inventory_sha256']),
        synthetic_public_writer_volume=observations,terminal_usage=terminal_usage,ordinary_usage_unchanged=True,
        synthetic_text_writer_metrics=text_metrics,synthetic_text_bytes=text_target,
        terminal_is_process_death_proof=False,native_runtime_tested=False,storage_spec=spec,
        full_processed_plan_bytes=new_plan,complete_raw70s_plan_with32MiB_margin_bytes=raw_plan,
        fresh_independent_target_pc_reservation_bytes=160*1024**2,
        complete_output_bytes=total,seconds=time.time()-started))
    print(json.dumps(dict(status=status,output=str(args.output),groups=len(groups),rejects=len(rejects),source_sha256=hashlib.sha256(new).hexdigest())))
finally:
    put('EXIT_INTENT.json',dict(owner=owner,status=status,physical_closure_claimed=False))
