"""Capacity-governed gallery maintenance. See README_GALLERY_WORKER_CAPACITY.md."""
import argparse
import json
import os
from pathlib import Path
import queue
import resource
import signal
import sys
import threading
import time


def physical_file_ceiling(directory, reserve_bytes):
    """Finite absolute file length from real filesystem capacity, preserving inheritance."""
    import shutil
    usage = shutil.disk_usage(directory)
    ceiling = usage.total-reserve_bytes
    if type(reserve_bytes) is not int or reserve_bytes < 0 or ceiling <= 0:
        raise OSError('Gallery filesystem cannot preserve its physical reserve')
    _, inherited = resource.getrlimit(resource.RLIMIT_FSIZE)
    if inherited != resource.RLIM_INFINITY:
        ceiling = min(ceiling, inherited)
    if ceiling <= 0:
        raise OSError('Gallery inherited file allowance is exhausted')
    return ceiling


def early_owner(directory):
    if sys.platform != 'linux':
        raise RuntimeError('Enrollment helper requires the native Pi')
    os.sched_setaffinity(0, {2, 3})
    for kind, maximum in ((resource.RLIMIT_AS, 768*1024**2),
            (resource.RLIMIT_STACK, 1024**2), (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(kind, (maximum, maximum))
    ceiling = physical_file_ceiling(directory, 5*1024**3)
    resource.setrlimit(resource.RLIMIT_FSIZE, (min(32*1024**2, ceiling), ceiling))
    threading.stack_size(1024**2)
    sys.dont_write_bytecode = True
    owner = dict(pid=os.getpid(),
        start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    with (directory/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(owner, stream); stream.flush(); os.fsync(stream.fileno())
    signal.alarm(600)
    deadline = time.monotonic()+5
    ack = directory/'START_ACK.json'
    while not ack.exists() and time.monotonic()<deadline:
        time.sleep(.01)
    if not ack.exists() or json.loads(ack.read_bytes()) != owner:
        raise RuntimeError('Exact parent identity acknowledgement required before project imports')
    return owner


def snapshot_gallery(root, destination, guard, *, budget=None):
    """Independent exact restore copy before every destructive gallery mutation."""
    import hashlib
    import stat
    from runtime_support import digest, encoded, DiskBudget
    root, destination = Path(root).absolute(), Path(destination).absolute()
    def real(path, *, directory=False):
        for part in (path, *path.parents):
            try:
                info = part.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0)&0x400:
                raise ValueError('Real gallery backup paths required')
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise ValueError('Single-link gallery backup files required')
        if path.resolve(strict=directory) != path or directory and not path.is_dir():
            raise ValueError('Canonical gallery backup paths required')
    def identity(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    def sync_dir(path):
        if sys.platform == 'linux':
            fd = os.open(path, os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
    def members():
        # pathlib.rglob materializes each directory's entries. Retain only the
        # active directory iterators, and inspect each member before descending.
        active = []
        try:
            guard(); real(root, directory=True)
            active.append(os.scandir(root))
            while active:
                guard()
                try:
                    entry = next(active[-1])
                except StopIteration:
                    active.pop().close()
                    continue
                source = Path(entry.path)
                real(source); before = source.lstat()
                yield source, before
                if stat.S_ISDIR(before.st_mode):
                    guard(); real(source, directory=True)
                    if identity(source.lstat()) != identity(before):
                        raise ValueError('Gallery directory changed before traversal')
                    active.append(os.scandir(source))
        finally:
            for iterator in reversed(active): iterator.close()
    real(root, directory=True); real(destination.parent, directory=True); real(destination)
    if (destination == root or destination.is_relative_to(root)
        or root.is_relative_to(destination)):
        raise ValueError('Gallery backup must be outside its source tree')
    budget = budget if budget is not None else DiskBudget(1)
    budget.check_free(destination.parent, 3*65536)
    destination.mkdir(mode=0o700)
    for name in ('backup', 'restore'):
        (destination/name).mkdir(mode=0o700)
    sync_dir(destination.parent); sync_dir(destination)
    pending = destination/'BACKUP_AND_RESTORE.json.pending'
    final = destination/'BACKUP_AND_RESTORE.json'
    manifest_hash = hashlib.sha256(); count = total = 0
    with pending.open('xb') as receipt:
        def write(raw):
            guard(); budget.check_free(destination, len(raw)); budget.claim(len(raw))
            if receipt.write(raw) != len(raw): raise OSError('Short gallery receipt write')
            manifest_hash.update(raw)
        write(b'{"files":[')
        for source, before in members():
            guard(); real(source)
            relative = source.relative_to(root)
            if not source.resolve(strict=True).is_relative_to(root):
                raise ValueError('Gallery backup path escapes its owner')
            copies = [destination/name/relative for name in ('backup', 'restore')]
            if stat.S_ISDIR(before.st_mode):
                budget.check_free(destination, 2*65536)
                for copied in copies:
                    real(copied); copied.mkdir(mode=0o700); sync_dir(copied.parent)
                continue
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 2*1024**2:
                raise ValueError('Bounded ordinary gallery reference file required')
            budget.check_free(destination, 2*(before.st_size+4096))
            source_hash = hashlib.sha256()
            for copied in copies: real(copied)
            with source.open('rb') as original, copies[0].open('xb') as backup, copies[1].open('xb') as restore:
                if identity(os.fstat(original.fileno())) != identity(before):
                    raise ValueError('Gallery reference changed before backup')
                while raw := original.read(16384):
                    guard(); budget.check_free(destination, 2*len(raw))
                    for copied in (backup, restore):
                        if copied.write(raw) != len(raw): raise OSError('Short gallery backup write')
                    source_hash.update(raw); budget.claim(2*len(raw))
                for copied in (backup, restore): copied.flush(); os.fsync(copied.fileno())
                if identity(os.fstat(original.fileno())) != identity(before):
                    raise ValueError('Gallery reference changed during backup')
            expected = source_hash.hexdigest()
            if (identity(source.lstat()) != identity(before) or digest(source) != expected
                or any(digest(copied) != expected for copied in copies)):
                raise OSError('Gallery source and independent restore readback differ')
            for copied in copies: sync_dir(copied.parent)
            row = encoded(dict(path=relative.as_posix(), bytes=before.st_size, sha256=expected))
            if len(row) > 256*1024: raise ValueError('Bounded individual gallery member record required')
            write((b',' if count else b'')+row); count += 1; total += before.st_size
        write(b'],"bytes":'+str(total).encode()+b',"complete":true,"scope":'
              +encoded('encoder-specific personal gallery before mutation')+b'}\n')
        receipt.flush(); os.fsync(receipt.fileno())
    if digest(pending) != manifest_hash.hexdigest(): raise OSError('Gallery receipt independent readback differs')
    os.link(pending, final); pending.unlink(); sync_dir(destination)
    if digest(final) != manifest_hash.hexdigest(): raise OSError('Published gallery receipt differs')


def run(directory):
    owner = early_owner(directory)
    from dataclasses import replace
    from collections import OrderedDict
    from runtime_support import strict, digest, publish, owner_status, resource_snapshot
    from profiles import RuntimeSelection
    from installed_engine import load_reference, selected_descriptor
    from release_authorization import authorization
    request = strict((directory/'REQUEST.json').read_bytes())
    binding_path = Path(request['binding'])
    if digest(binding_path) != request['binding_sha256']:
        raise ValueError('Gallery binding changed')
    binding = strict(binding_path.read_bytes())
    _, approved = authorization(binding)
    if approved['limits'].get('personal_enrollment') is not True:
        raise RuntimeError('This release has not admitted the restored enrollment owner')
    selection = RuntimeSelection(**request['selection'])
    selection.validate()
    if selection.embedding == 'anonymous':
        raise ValueError('Choose ReDimNet or TitaNet before enrolling a speaker')
    from storage import StoragePolicy
    from runtime_support import DiskBudget
    import shutil
    storage_policy = StoragePolicy(**binding.get('storage_policy', {}))
    usage = shutil.disk_usage(directory)
    reserve = storage_policy.reserve(usage.total)
    file_ceiling = physical_file_ceiling(directory, reserve)
    _, inherited_hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_ceiling, inherited_hard))
    snapshot_budget = DiskBudget(1, reserve_bytes=storage_policy.reserve_bytes,
                               reserve_fraction=storage_policy.reserve_fraction)
    publish(directory/'GALLERY_FILE_ALLOCATION.json', dict(
        file_limit_bytes=file_ceiling, physical_hard_file_limit_bytes=inherited_hard,
        filesystem_total_bytes=usage.total, free_at_admission_bytes=usage.free,
        reserve_bytes=reserve, cumulative_gallery_quota_enforced=False))
    started = time.monotonic()
    def guard():
        if owner_status(request['parent'])['closed']:
            raise RuntimeError('Owning GUI has closed')
        values = resource_snapshot()
        if values.get('available_ram', 0) < 192*1024**2:
            raise MemoryError('Enrollment RAM stop floor reached')
        import shutil
        usage = shutil.disk_usage(directory)
        if usage.free < storage_policy.reserve(usage.total):
            raise OSError('Enrollment storage stop floor reached')
        if time.monotonic()-started > 510:
            raise TimeoutError('Bounded enrollment helper lifetime expired')
    initial = resource_snapshot()
    if initial.get('available_ram', 0)<850*1024**2:
        raise MemoryError('Enrollment initial RAM floor unavailable')
    base, manifest, compat = load_reference(binding)
    descriptor, document = selected_descriptor(binding, selection)
    from app import paths, people, n2_people, pipeline
    from app.controller import Controller
    from app.n2_models import N2ResidentModels
    from personal_gallery import open_store
    from app.live_audio import LiveConfig
    contract = strict((base/'config/field_contract.json').read_bytes())
    config = replace(paths.pipeline_config(directory/'work', Path(contract['models_root'])),
        asr_threads=1, speaker_threads=1, punctuation_threads=1)
    if selection.embedding == 'titanet':
        from edge_speech_pipeline import titanet_embedding
        if digest(document['titanet_manifest']) != document['titanet_manifest_sha256']:
            raise ValueError('TitaNet enrollment asset changed')
        compat.bind_titanet_memory(titanet_embedding, Path(titanet_embedding.__file__))
    store = open_store(binding, selection, request['data_root'], config, people, n2_people, compat, guard,
                       budget=snapshot_budget)

    class EnrollmentController(Controller):
        def _initialize(self, writer_delay):
            raise RuntimeError('Only recovered enrollment methods are used')
        def _stop_session(self):
            if self.engine is not None:
                raise RuntimeError('Enrollment never takes ownership of a speech session')
        def _stop_playback(self): pass
        def _review_cancel(self, reason): pass
        def _observe_output(self, stage): pass
        def _invalidate_seats(self, reason): pass
        def _live_config(self):
            value = dict(binding['live_config'], tap='O0', evidence_dir=str(directory/'device_receipts'))
            return LiveConfig(**value)

    controller = EnrollmentController.__new__(EnrollmentController)
    controller.config, controller.store = config, store
    controller.data_root, controller.models_root = directory/'work', Path(contract['models_root'])
    controller.data_root.mkdir()
    controller.models = pipeline.ResidentModels() if selection.embedding=='redimnet' else N2ResidentModels('D0','E1',document)
    controller.engine = controller.consumer = controller.archive = None
    controller.settings = dict(request['settings'], enhancement_route=getattr(selection,'enhancement_route','bypass'))
    controller.mode, controller.recipe, controller.tap = 'caption_only', 'balanced', 'O0'
    controller.selected_ids, controller.display_ids = [], []
    controller.source_kind, controller.epoch = None, 0
    controller.strict = False
    controller.lock = threading.RLock()
    controller.rows = OrderedDict()
    controller.metrics = {}
    controller.state, controller.status, controller.error = 'IDLE', 'Ready for enrollment.', None
    controller.enrollment = dict(state='IDLE', can_save=False)
    controller._enroll_audio, controller._enroll_vector = [], None
    controller._enroll_stop = threading.Event()
    controller._enroll_thread = controller._enroll_live = controller._quality_thread = None
    controller._quality_queue = controller._quality = controller._enroll_integrity = None
    controller.reference_bank = None
    commands = queue.Queue(32)
    def enqueue(action, *args, **kwargs):
        commands.put_nowait((action, args, kwargs))
    controller._enqueue = enqueue
    reader_stop = threading.Event()
    allowed = {'enrollment_prepare','enrollment_start','enrollment_stop','enrollment_save','enrollment_cancel',
        'enrollment_script_note','script_review','rename_person','delete_person','import_people','export_people','close'}
    def receive():
        import select
        pending = b''
        try:
            while not reader_stop.is_set():
                if not select.select([sys.stdin.fileno()], [], [], .25)[0]:
                    continue
                data = os.read(sys.stdin.fileno(), 4096)
                if not data:
                    enqueue('close'); return
                pending += data
                while b'\n' in pending:
                    raw, pending = pending.split(b'\n', 1)
                    if len(raw)>65535:
                        raise ValueError('Gallery command exceeds 64 KiB')
                    row = strict(raw)
                    if set(row) != {'command','args','kwargs'} or row['command'] not in allowed:
                        raise ValueError('Unknown gallery command')
                    enqueue(row['command'], *row['args'], **row['kwargs'])
                if len(pending)>65535:
                    raise ValueError('Gallery command exceeds 64 KiB')
        except BaseException as exc:
            controller.error = repr(exc)
            try: enqueue('close')
            except queue.Full: controller._enroll_stop.set()
    reader = threading.Thread(target=receive, name='gallery-command-reader', daemon=True)
    reader.start()
    operation_count = 0
    failure = None
    final_state = None
    last_command = None
    try:
        while True:
            guard()
            try: name, args, kwargs = commands.get(timeout=.25)
            except queue.Empty: name = None
            if name == 'close':
                final_state = dict(controller.enrollment)
                break
            if name:
                try:
                    if name in ('enrollment_save','rename_person','delete_person','import_people'):
                        operation_count += 1
                        snapshot_gallery(store.root, directory/('gallery-before-%03d' % operation_count), guard,
                                         budget=snapshot_budget)
                    if name == 'enrollment_prepare':
                        if args or kwargs:
                            raise ValueError('Read-only enrollment preparation has no recording inputs')
                        controller.models.enrollment_models(config)
                        guard()
                        controller.enrollment.update(state='IDLE', can_save=False,
                            models_prepared=True, embedding=selection.embedding, microphone_started=False)
                    elif name == 'enrollment_start':
                        if kwargs.pop('consent', False) is not True:
                            raise ValueError('Explicit enrollment microphone consent required')
                        person_id = kwargs.pop('person_id', None)
                        paragraph = kwargs.pop('paragraph', None)
                        if kwargs: raise ValueError('Unknown enrollment options')
                        controller._do_enrollment_start(args[0], args[1] if len(args)>1 else 30, person_id, paragraph)
                    elif name in ('rename_person','delete_person'):
                        controller._do_person_mutation('rename' if name=='rename_person' else 'delete', *args)
                    else:
                        getattr(controller, '_do_'+name)(*args, **kwargs)
                except Exception as exc:
                    controller.error = repr(exc)
                    controller.enrollment.update(state='ERROR', can_save=False, error=repr(exc))
                finally:
                    last_command = name
                    commands.task_done()
            row = dict(controller.enrollment, status=controller.status, error=controller.error,
                last_command=last_command, metrics=controller.metrics)
            raw = json.dumps(row, sort_keys=True, allow_nan=False).encode()
            if len(raw)>32000: raise ValueError('Enrollment state exceeds 32 KiB')
            sys.stdout.buffer.write(b'JP_GALLERY '+raw+b'\n'); sys.stdout.buffer.flush()
    except BaseException as exc:
        failure = repr(exc)
    finally:
        try:
            controller._do_enrollment_cancel()
        except BaseException as exc:
            failure = (failure or '')+'; '+repr(exc)
        try:
            close = getattr(controller.models, 'close', None)
            if close is not None:
                close()
            # The recovered baseline resident object has no close method.
            # Release its owning references; exact process reap remains required.
            controller.models.asr = controller.models.speakers = controller.models.enhancer = None
        except BaseException as exc:
            failure = (failure or '')+'; '+repr(exc)
        reader_stop.set()
        reader.join(2)
        if reader.is_alive():
            failure = (failure or '')+'; gallery command reader did not join'
        publish(directory/'RESULT.json', dict(owner=owner, success=failure is None,
            failure=failure, final_state=final_state, capture_quality_workers_joined=True if failure is None else False,
            command_reader_joined=not reader.is_alive(),
            physical_closure_claimed=False))
    if failure: raise RuntimeError(failure)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    run(parser.parse_args().directory)
