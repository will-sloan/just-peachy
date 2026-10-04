"""One finite native model process per recording. See README.md."""
# Standard library only until affinity, limits and early identity are persisted.
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time


def bootstrap(directory):
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        raise RuntimeError('Native worker requires the CM5; desktop execution is not qualification')
    import resource
    import shutil
    os.sched_setaffinity(0, {2, 3})
    for kind, value in ((resource.RLIMIT_AS, 768*1024**2), (resource.RLIMIT_STACK, 1024**2),
                        (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(kind, (value, value))
    threading.stack_size(1024**2)
    sys.dont_write_bytecode = True
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        if os.environ.get(key) != '1':
            raise RuntimeError('Single-thread model environment required')
    directory.mkdir(exist_ok=False)
    identity = dict(pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
                    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    with (directory/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(identity, stream); stream.flush(); os.fsync(stream.fileno())
    for key,value in {'MALLOC_ARENA_MAX':'1','MALLOC_MMAP_THRESHOLD_':'131072','MALLOC_TRIM_THRESHOLD_':'131072'}.items():
        if os.environ.get(key)!=value:
            raise RuntimeError('Retained pre-exec allocator setting missing: '+key)
    ceiling = shutil.disk_usage(directory.parent).free - 5*1024**3
    _, inherited_hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    if inherited_hard != resource.RLIM_INFINITY:
        ceiling = min(ceiling, inherited_hard)
    if ceiling < 32*1024**2:
        raise OSError('Bootstrap file allowance cannot preserve the 5 GiB storage floor')
    resource.setrlimit(resource.RLIMIT_FSIZE, (32*1024**2, ceiling))
    return identity


def file_size_plan(data_root, metadata_reserve_bytes, storage_policy, usage=None):
    """Finite SQLite/native per-file ceiling derived after request validation."""
    import shutil
    root = Path(data_root)
    usage = usage or shutil.disk_usage(root)
    database = root/'history.sqlite3'
    if database.is_symlink() or any(path.is_symlink() for path in database.parents):
        raise ValueError('Real owned history database required')
    existing = database.stat().st_size if database.exists() else 0
    metadata = int(metadata_reserve_bytes) + storage_policy.metadata_allowance_bytes
    if metadata <= 0:
        raise ValueError('Positive finite session metadata reservation required')
    # Charge a second metadata copy for SQLite pages/journal plus bounded header
    # overhead. Existing history contributes to the file size, never to slots.
    journal_overhead = metadata + 8*1024**2
    requested = max(existing + metadata + journal_overhead, metadata)
    available = max(0, usage.free-storage_policy.reserve(usage.total))
    if requested > available:
        raise OSError('Derived per-file allowance cannot preserve actual free-space reserve')
    return dict(existing_history_bytes=existing, metadata_bytes=metadata,
                journal_overhead_bytes=journal_overhead, file_limit_bytes=requested,
                available_above_reserve=available)


def run_owned_session(store, spool, session, owner_directory):
    """Run/drain one injected session; retain failures even during finalization."""
    from runtime_support import publish
    stop_watch = threading.Event()
    def controls():
        while not stop_watch.wait(.1):
            if (owner_directory/'STOP').exists():
                session.stop_event.set()
                return
    controller = threading.Thread(target=controls, name='v29-stop-control', daemon=True)
    controller.start()
    result = None
    failure = None
    def record_failure(stage, exc):
        nonlocal failure
        detail = stage + ': ' + repr(exc)
        failure = (failure + '; ' + detail) if failure else detail
    try:
        try:
            result = session.run()
        except BaseException as exc:
            record_failure('run', exc)
            try:
                session.fail(failure)
            except BaseException as secondary:
                record_failure('failure callback', secondary)
        finally:
            try:
                session.close()
            except BaseException as exc:
                record_failure('cleanup', exc)
            stop_watch.set()
            controller.join(2)
            if controller.is_alive():
                record_failure('cleanup', RuntimeError('Stop controller remains owned'))
        try:
            # Stream owned metadata paths; no recording-sized list or sorting.
            for path in session.work.rglob('*'):
                if path.is_symlink():
                    raise ValueError('Symlink in owned native metadata')
                if path.is_file():
                    store.register_artifact(spool.session_id, path.relative_to(spool.directory).as_posix(), role='native')
        except BaseException as exc:
            record_failure('artifact registration', exc)
        try:
            if failure:
                spool.fail(failure)
            else:
                spool.stop(final_sample=spool.processed_samples)
        except BaseException as exc:
            record_failure('storage finalization', exc)
            try:
                spool.fail(failure)
            except BaseException as secondary:
                record_failure('storage failure receipt', secondary)
        publish(owner_directory/'RESULT.json', dict(result=result, failure=failure,
            session_id=spool.session_id, post_stop_choice_pending=failure is None,
            logical_cleanup_complete=failure is None, physical_process_closed=False))
    finally:
        store.close()
    return 1 if failure else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--request', type=Path, required=True)
    ap.add_argument('--owner-directory', type=Path, required=True)
    args = ap.parse_args()
    identity = bootstrap(args.owner_directory)
    from runtime_support import strict, publish, digest, resource_snapshot, Lease
    from profiles import RuntimeSelection, SessionPolicy
    from storage import SessionStore, StoragePolicy
    from raw_capture import storage_raw_spec
    if args.request.is_symlink() or args.request.stat().st_size > 262144:
        raise ValueError('Bounded real worker request')
    request = strict(args.request.read_bytes())
    selection = RuntimeSelection(**request['selection'])
    policy = SessionPolicy(**request['policy'])
    selection.validate(); policy.validate()
    binding_path = Path(request['binding'])
    if digest(binding_path) != request['binding_sha256']:
        raise ValueError('Deployment binding changed')
    binding = strict(binding_path.read_bytes())
    saved_session_id = request.get('saved_session_id')
    from developer_replay import validate_repeat, pin_repeat_input
    repeat_seconds=validate_repeat(selection,policy,request.get('saved_path'),saved_session_id,request.get('repeat_input_seconds'))
    if repeat_seconds is not None and pin_repeat_input(request['saved_path'],policy)!=request.get('repeat_input_sha256'):
        raise ValueError('Explicit repeated input SHA changed before worker admission')
    if saved_session_id is not None:
        if (selection.input_source != 'saved' or request.get('saved_path')
            or Path(request.get('saved_store_root', '')).absolute() != Path(request['data_root']).absolute()):
            raise ValueError('Kept replay requires only a session in this owned recording store')
    from release_authorization import authorize_session
    authorization = authorize_session(binding, selection, policy, verify_assets=True)
    publish(args.owner_directory/'SESSION_AUTHORIZATION.json', authorization)
    if request.get('raw_qualification') is True or binding.get('raw_qualification') is True:
        raise ValueError('Unqualified raw adapter requires the explicit source-only qualification harness')
    from installed_engine import InstalledSession
    if resource_snapshot()['available_ram'] < 850*1024**2:
        raise MemoryError('Initial 850 MiB available RAM admission failed')
    # All app/model/source children share the launcher-created systemd scope.
    import subprocess
    unit = request['unit']
    properties = subprocess.run(['systemctl', '--user', 'show', unit,
        '--property=ActiveState,AllowedCPUs,CPUQuotaPerSecUSec,TasksMax'],
        capture_output=True, text=True, timeout=5, check=True).stdout
    props = dict(line.split('=', 1) for line in properties.splitlines() if '=' in line)
    if (props.get('ActiveState') != 'active' or props.get('AllowedCPUs') not in ('2-3', '2,3')
        or props.get('CPUQuotaPerSecUSec') != '2s' or props.get('TasksMax') != '64'):
        raise RuntimeError('Actual shared CPU/task scope differs from requested envelope')
    publish(args.owner_directory/'ENVELOPE.json', dict(owner=identity, properties=props, policy=policy.validate(),
        allocator_environment={key:os.environ.get(key) for key in ('MALLOC_ARENA_MAX','MALLOC_MMAP_THRESHOLD_','MALLOC_TRIM_THRESHOLD_')}))
    from optional_refiner_dispatch import worker_options
    optional_options=worker_options(binding,request,selection,policy,args.owner_directory,identity,authorization)
    storage_policy = StoragePolicy(**request.get('storage_policy', {}))
    spec = dict(duration_seconds=policy.maximum_session_seconds, sample_rate=16000,
                metadata_split='text3_sqlite1_v1',
                mode='processed', selection=selection.validate(),
                metadata_reserve_bytes=16*1024**2+policy.maximum_session_seconds*256*1024,
                source_policy=policy.validate(), deployment_sha256=request['binding_sha256'])
    if repeat_seconds is not None:
        spec['developer_replay']=dict(seconds=repeat_seconds,input_sha256=request['repeat_input_sha256'],
            continuous_models=True,quality_evaluated=False)
    raw = storage_raw_spec(binding, selection.input_source)
    if raw is not None:
        spec.update(mode='raw_processed', raw=raw, raw_capability='QUALIFIED_PACKED_4X16K_PCM32')
    else:
        spec['raw_capability'] = 'UNAVAILABLE_PENDING_QUALIFICATION' if selection.input_source == 'live' else 'UNAVAILABLE_FOR_PROCESSED_REPLAY'
    file_plan = file_size_plan(request['data_root'], spec['metadata_reserve_bytes'], storage_policy)
    import resource
    _, bootstrap_hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    if file_plan['file_limit_bytes'] > bootstrap_hard:
        raise OSError('Validated file allowance exceeds the early finite hard ceiling')
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_plan['file_limit_bytes'], file_plan['file_limit_bytes']))
    publish(args.owner_directory/'FILE_ALLOCATION.json', file_plan)
    store = SessionStore(request['data_root'], storage_policy)
    spool = store.begin(spec)
    publish(args.owner_directory/'SESSION.json', dict(session_id=spool.session_id, worker=identity))
    try:
        from runtime_ui_channel import emit_spatial
        session = InstalledSession(binding, selection, policy, spool, saved_path=request.get('saved_path'),
                                   saved_session_id=saved_session_id, saved_store_root=request.get('saved_store_root'),
                                   repeat_input_seconds=repeat_seconds,repeat_input_sha256=request.get('repeat_input_sha256'),
                                   notify=emit_spatial, optional_refiner_options=optional_options)
        session.gui_spatial_enabled=lambda:(args.owner_directory/'GUI_SPATIAL_ON').is_file()
    except BaseException as exc:
        try:
            failure = 'session initialization: ' + repr(exc)
            spool.fail(failure)
            publish(args.owner_directory/'RESULT.json', dict(result=None, failure=failure,
                session_id=spool.session_id, post_stop_choice_pending=False,
                logical_cleanup_complete=False, physical_process_closed=False))
        finally:
            store.close()
        return 1
    return run_owned_session(store, spool, session, args.owner_directory)


if __name__ == '__main__':
    raise SystemExit(main())
