"""Bounded native owner for recovered enrollment methods. See README.md."""
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


def early_owner(directory):
    if sys.platform != 'linux':
        raise RuntimeError('Enrollment helper requires the native Pi')
    os.sched_setaffinity(0, {2, 3})
    for kind, maximum in ((resource.RLIMIT_AS, 768*1024**2),
            (resource.RLIMIT_STACK, 1024**2), (resource.RLIMIT_FSIZE, 32*1024**2), (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(kind, (maximum, maximum))
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


def snapshot_gallery(root, destination, guard):
    """Independent exact restore copy before every destructive gallery mutation."""
    import shutil
    from runtime_support import digest, publish
    files, total = [], 0
    destination.mkdir()
    for name in ('backup', 'restore'):
        (destination/name).mkdir()
    for index, source in enumerate(sorted(root.rglob('*')), 1):
        if index > 1024:
            raise ValueError('Gallery backup membership exceeds 1024')
        guard()
        relative = source.relative_to(root)
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError('Gallery backup path escapes its owner')
        if source.is_dir():
            for name in ('backup', 'restore'):
                (destination/name/relative).mkdir()
            continue
        total += source.stat().st_size
        if total>16*1024**2 or source.stat().st_size>2*1024**2 or source.stat().st_nlink != 1:
            raise ValueError('Gallery backup exceeds reviewed bounds')
        for name in ('backup', 'restore'):
            copied = destination/name/relative
            shutil.copyfile(source, copied)
            with copied.open('rb') as stream:
                os.fsync(stream.fileno())
        expected = digest(source)
        if any(digest(destination/name/relative) != expected for name in ('backup', 'restore')):
            raise OSError('Gallery independent restore differs')
        files.append(dict(path=relative.as_posix(), bytes=source.stat().st_size, sha256=expected))
    publish(destination/'BACKUP_AND_RESTORE.json', dict(files=files, bytes=total,
        complete=True, scope='encoder-specific personal gallery before mutation'))


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
    started = time.monotonic()
    def guard():
        if owner_status(request['parent'])['closed']:
            raise RuntimeError('Owning GUI has closed')
        values = resource_snapshot()
        if values.get('available_ram', 0) < 192*1024**2:
            raise MemoryError('Enrollment RAM stop floor reached')
        import shutil
        if shutil.disk_usage(directory).free < 5*1024**3:
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
    store = open_store(binding, selection, request['data_root'], config, people, n2_people, compat, guard)

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
                        snapshot_gallery(store.root, directory/('gallery-before-%03d' % operation_count), guard)
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
