"""Prepared, isolated processed XVF source; see README_INSTALLED_SOURCE.md.

Only standard-library imports occur before the child owner/ACK boundary.
No source or model is opened by importing this module.
"""
from __future__ import annotations

import dataclasses
import ast
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import threading
import time


BASE_MANIFEST = '274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'
PACKET_BYTES = 262144
BLOCK_BYTES = 16384
RAW_BYTES = 65536
STDERR_BYTES = 65536
_HEADER = struct.Struct('!II')


def _mapping(value):
    return dataclasses.asdict(value) if dataclasses.is_dataclass(value) else dict(value)


def _identity(pid=None):
    pid = os.getpid() if pid is None else pid
    return dict(pid=pid,
        start_ticks=int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def _same_owner(owner):
    try:
        return _identity(owner['pid']) == owner
    except (FileNotFoundError, ProcessLookupError):
        return False


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _send(fd, metadata, audio=b'', timeout=5):
    header = _encoded(metadata)
    audio_limit = RAW_BYTES if metadata.get('kind') == 'RAW' else BLOCK_BYTES
    if len(header) > PACKET_BYTES or len(audio) > audio_limit or len(header) + len(audio) > PACKET_BYTES:
        raise ValueError('Source IPC packet exceeds its declared bound')
    # Scatter the header/audio without making another full audio packet copy.
    parts = (_HEADER.pack(len(header), len(audio)), header, audio)
    deadline = time.monotonic() + timeout
    for part in parts:
        view = memoryview(part)
        offset = 0
        while offset < len(view):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
                raise TimeoutError('Source IPC write deadline')
            try:
                written = os.write(fd, view[offset:offset + 16384])
            except BlockingIOError:
                continue
            if written <= 0:
                raise EOFError('Source IPC peer closed during write')
            offset += written


def _receive(fd, timeout, stderr_fd=None, stderr_consumer=None):
    deadline = time.monotonic() + timeout
    packet_started = False
    def exact(count):
        nonlocal packet_started, deadline, stderr_fd
        value = bytearray()
        while len(value) < count:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if packet_started:
                    raise RuntimeError('Incomplete source IPC frame exceeded its deadline')
                raise TimeoutError('Source IPC read deadline')
            inputs = [fd] + ([stderr_fd] if stderr_fd is not None else [])
            ready = select.select(inputs, [], [], remaining)[0]
            if not ready:
                if packet_started:
                    raise RuntimeError('Incomplete source IPC frame exceeded its deadline')
                raise TimeoutError('Source IPC read deadline')
            if stderr_fd is not None and stderr_fd in ready:
                diagnostic = os.read(stderr_fd, 4096)
                if diagnostic and stderr_consumer is not None:
                    stderr_consumer(diagnostic)
                elif not diagnostic:
                    stderr_fd = None
            if fd not in ready:
                continue
            try:
                chunk = os.read(fd, count - len(value))
            except BlockingIOError:
                continue
            if not chunk:
                raise EOFError('Source IPC closed before a complete packet')
            if not packet_started:
                packet_started = True
                deadline = max(deadline, time.monotonic() + 5)
            value.extend(chunk)
        return bytes(value)
    header_count, audio_count = _HEADER.unpack(exact(_HEADER.size))
    if not 0 < header_count <= PACKET_BYTES or audio_count > RAW_BYTES or header_count + audio_count > PACKET_BYTES:
        raise ValueError('Malformed source IPC length')
    metadata = json.loads(exact(header_count))
    if type(metadata) is not dict:
        raise ValueError('Source IPC requires object metadata')
    if audio_count > (RAW_BYTES if metadata.get('kind') == 'RAW' else BLOCK_BYTES):
        raise ValueError('Source IPC audio kind exceeds its payload bound')
    return metadata, exact(audio_count) if audio_count else b''


def _load_mounted(config):
    if 'mounted_spatial_path' in config:
        path = Path(config['mounted_spatial_path']).resolve(strict=True)
        expected = config['mounted_spatial_sha256']
    else:
        path = Path(config['reference_code']).resolve(strict=True) / 'field_live_source_bridge_v6.py'
        references = config['reference_files']
        if isinstance(references, list):
            matches = [row for row in references if row['path'] in (path.name, 'code/' + path.name)]
            if len(matches) != 1:
                raise ValueError('Unique mounted transport capsule pin required')
            row = matches[0]
        else:
            row = references.get(path.name, references.get('code/' + path.name))
        expected = row['sha256'] if isinstance(row, dict) else row
    raw = path.read_bytes()
    if len(raw) > 131072 or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Mounted beam transport source pin changed')
    namespace = {'__name__': 'just_peachy_mounted_source_transport', '__file__': str(path)}
    if path.name == 'field_live_source_bridge_v6.py':
        # This pinned capsule embeds the reviewed mounted-spatial module at
        # module scope. Retain its exact definitions without importing its
        # unrelated broker/output implementation.
        selected = {'FIELD_COUNTS', 'SCHEMA', 'PACKET_BYTES', 'BeamQueue',
                    'BeamReceiver', 'encoded', 'finite', 'sample'}
        tree = ast.parse(raw)
        nodes = []
        found = set()
        for node in tree.body:
            names = ({node.name} if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else
                     {target.id for target in node.targets if isinstance(target, ast.Name)} if isinstance(node, ast.Assign) else set())
            if names & selected:
                nodes.append(node)
                found |= names & selected
        if found != selected or len(nodes) != len(selected):
            raise ValueError('Exact unique mounted transport definitions required')
        import collections
        import copy
        namespace.update(deque=collections.deque, deepcopy=copy.deepcopy, json=json,
                         math=math, threading=threading)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    else:
        exec(compile(raw, str(path), 'exec'), namespace)
    return namespace


def prepare_source_imports(config):
    """Verify source-only dependencies before adding the exact installed path."""
    root = Path(config['installed_release']).resolve(strict=True)
    manifest_raw = (root / 'RELEASE_MANIFEST.json').read_bytes()
    if config['installed_manifest_sha256'] != BASE_MANIFEST or hashlib.sha256(manifest_raw).hexdigest() != BASE_MANIFEST:
        raise ValueError('Source requires the exact installed v12 release manifest')
    manifest = json.loads(manifest_raw)
    pins = {row['path']: row for row in manifest['files']}
    # Verify source dependencies before import, including the late callback
    # fault-details derivative. Assets/models are neither read nor constructed.
    for name, row in pins.items():
        if name.endswith('.py'):
            path = root / name
            if not path.resolve().is_relative_to(root) or path.is_symlink():
                raise ValueError('Installed Python source escapes its pinned release')
            if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('Installed Python source pin changed: ' + name)
    sys.path[:0] = [str(root), str(root / 'vendor')]
    return root


def _load_live(config):
    root = prepare_source_imports(config)
    from app import live_audio
    if Path(live_audio.__file__).resolve() != root / 'app/live_audio.py':
        raise ValueError('Unexpected loaded live source origin')
    return live_audio


def _check_config(config, policy):
    from source_batch import batch_milliseconds
    batch_milliseconds(config)
    required = {'installed_release', 'installed_manifest_sha256', 'live_config', 'owner_directory'}
    if not required <= set(config):
        raise ValueError('Explicit installed source/mounted/owner configuration required')
    raw_requested = config.get('raw_capture') is True
    if policy.get('raw_capture') or policy.get('record_raw') or policy.get('raw'):
        raise ValueError('Raw route must use explicit spool/binding admission')
    if raw_requested:
        from raw_capture import admission
        admission(config, qualification_run=policy.get('raw_qualification') is True)
        if not config.get('raw_factory_path') or not config.get('raw_factory_sha256'):
            raise ValueError('Pinned retained raw factory is required')
    seconds = policy.get('duration_seconds')
    if type(seconds) is not int or seconds <= 0 or policy.get('sample_rate') != 16000:
        raise ValueError('Positive integer capture duration and mono16k session policy required')
    if config['installed_manifest_sha256'] != BASE_MANIFEST:
        raise ValueError('Unexpected installed source manifest')
    live = config['live_config']
    if live.get('lease_path') != str(Path.home() / 'JustPeachy/data/xvf-hardware.lock'):
        raise ValueError('The existing physical XVF lease must be retained')
    if live.get('hostapi', 'ALSA') != 'ALSA':
        raise ValueError('Native isolated source requires the explicit ALSA endpoint')
    if not live.get('endpoint_name'):
        raise ValueError('Explicit named input endpoint required')
    if live.get('evidence_dir'):
        raise ValueError('Source receipts are owned by the session store; disable unmanaged evidence_dir')
    if type(config.get('consent')) is not bool or config['consent'] is not True:
        raise ValueError('Explicit Start microphone consent must be supplied')


def _raw_terminal(source, sink, failure, integrity):
    """Separate a proven empty failed Start from a complete raw recording."""
    status = source.status()
    if (failure and status.get('started') is False and
            type(status.get('converted_samples')) is int and status['converted_samples'] == 0 and
            type(sink.accepted_samples) is int and sink.accepted_samples == 0 and
            integrity and integrity.get('route') is None):
        converter = getattr(source, '_converter', None)
        if converter is not None:
            if (converter.finished or converter.samples != 0 or converter.pending or
                    getattr(converter, 'written', 0) != 0):
                raise ValueError('Failed Start has unexpected partial raw data')
            converter.finished = True
        return dict(schema='just-peachy.raw-source-terminal.v1',
                    status='FAILED_BEFORE_CAPTURE', raw_samples=0, processed_samples=0,
                    complete_recording=False, primary_failure_preserved=True)
    # All positive and partial/nonempty paths retain the exact converter's
    # raw/model count, durable byte extent, digest and transport partition checks.
    source.raw_capture_finish()
    return None


def _child(owner_directory):
    if sys.platform != 'linux':
        raise RuntimeError('Native source child requires Linux')
    import resource
    os.sched_setaffinity(0, {3})
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
    resource.setrlimit(resource.RLIMIT_STACK, (1024**2, 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    threading.stack_size(1024 * 1024)
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    sys.dont_write_bytecode = True
    owner = _identity()
    root = Path(owner_directory)
    root.mkdir(parents=False, exist_ok=False)
    with (root / 'REGISTERED_OWNER.json').open('xb') as stream:
        stream.write(_encoded(dict(schema='just-peachy.source-owner.v1', owner=owner,
            cpu=3, address_space_bytes=256*1024**2, stack_bytes=1024**2,
            project_imports_started=False)))
        stream.flush()
        os.fsync(stream.fileno())
    os.set_blocking(0, False)
    os.set_blocking(1, False)
    _send(1, dict(kind='OWNER', owner=owner), timeout=15)
    message, audio = _receive(0, 15)
    if audio or message.get('kind') != 'ACK_OWNER' or message.get('owner') != owner:
        raise ValueError('Parent did not acknowledge the exact early owner')
    config, policy = message['config'], message['policy']
    _check_config(config, policy)
    live = _load_live(config)
    mounted = _load_mounted(config)
    telemetry = mounted['BeamQueue']()
    raw_sink = None
    if config.get('raw_capture') is True:
        from raw_capture import RawSink, derive_factory, derive_stop_base
        raw_source_type, install_packed_route, proof = derive_factory(config['raw_factory_path'], config['raw_factory_sha256'])
        source_base, stop_proof = derive_stop_base(config, live)
        proof.update(stop_proof)
        def emit_raw(start_sample, raw):
            _send(1, dict(kind='RAW', start_sample=start_sample, samples=len(raw)//16), raw)
            ack, extra = _receive(0, 5)
            if not extra and ack.get('kind') == 'STOP':
                raw_sink.stop_requested = True
                ack, extra = _receive(0, 5)
            if extra:
                raise ValueError('Raw acknowledgement cannot contain audio')
            return ack
        raw_sink = RawSink(policy['duration_seconds']*16000, emit_raw, proof,
            native_qualified=not policy.get('raw_qualification') and config['raw_qualification_evidence'].get('adapter_native_qualified') is True)
        install_packed_route(live)
        source_type = raw_source_type(source_base, live, raw_sink)
    else:
        source_type = live.XVFLiveSource
    source = source_type(live.LiveConfig(**config['live_config']), raw_sink) if raw_sink else source_type(live.LiveConfig(**config['live_config']))
    original_status=source.status
    def status_with_beams():
        value=original_status()
        diagnostic=getattr(source,'beam_diagnostics',None)
        # Snapshot reads the existing diagnostic worker's cached state. No
        # USB/I2C operation is performed by this status forwarding path.
        observed=diagnostic.snapshot() if diagnostic is not None else {}
        value['beam_diagnostics_state']=observed.get('state','UNAVAILABLE')
        return value
    source.status=status_with_beams
    source.spatial_observer = telemetry.receive
    source.spatial_fast = True
    sent = 0
    sequence = 0
    batch_progress = dict(sent=0, sequence=0)
    failure = None
    receipt = integrity = raw_terminal = None
    try:
        metadata = source.start(consent=True)
        _send(1, dict(kind='STARTED', metadata=metadata, status=source.status()), timeout=10)
        command, extra = _receive(0, 10)
        if extra or command.get('kind') not in ('ACK_START', 'STOP'):
            raise ValueError('Source Start acknowledgement missing')
        stopping = command['kind'] == 'STOP'
        if config.get('source_batch_ms', 0) == 100 and not stopping:
            from source_batch import capture
            capture(source, telemetry, policy['duration_seconds']*16000, raw_sink,
                    _send, _receive, lambda: bool(select.select([0], [], [], 0)[0]), batch_progress)
            sent, sequence = batch_progress['sent'], batch_progress['sequence']
            stopping = True
        while not stopping and sent < policy['duration_seconds'] * 16000:
            if select.select([0], [], [], 0)[0]:
                command, extra = _receive(0, 1)
                if extra or command.get('kind') != 'STOP':
                    raise ValueError('Unexpected source control command')
                break
            block = source.read(0.1)
            if block is None:
                continue
            if block.model_start_sample != sent or sent + len(block.audio) > policy['duration_seconds'] * 16000:
                raise ValueError('Physical source sample sequence/policy boundary mismatch')
            fields = {field.name: getattr(block, field.name) for field in dataclasses.fields(block) if field.name != 'audio'}
            beam = telemetry.drain(block.callback_perf_counter_ns / 1e9)
            payload = block.audio.astype('<f4', copy=False).tobytes()
            _send(1, dict(kind='AUDIO', sequence=sequence, metadata=fields,
                spatial_telemetry=beam, status=source.status()), payload)
            command, extra = _receive(0, 5)
            if not extra and command.get('kind') == 'STOP':
                stopping = True
                command, extra = _receive(0, 5)
            if extra or command.get('kind') != 'ACK_AUDIO' or command.get('sequence') != sequence:
                raise ValueError('Exact durable source-block acknowledgement missing')
            if command.get('accepted_samples') != sent + len(block.audio):
                raise ValueError('Parent acknowledgement differs from delivered audio')
            sent += len(block.audio)
            sequence += 1
            stopping = stopping or command.get('stop') is True or bool(raw_sink and raw_sink.stop_requested)
    except BaseException as error:
        if config.get('source_batch_ms', 0) == 100:
            sent, sequence = batch_progress['sent'], batch_progress['sequence']
        failure = type(error).__name__ + ': ' + str(error)
    finally:
        try:
            receipt = source.stop()
            integrity = live.summarize_live_integrity(source)
            if raw_sink is not None:
                raw_terminal = _raw_terminal(source, raw_sink, failure, integrity)
        except BaseException as error:
            failure = (failure + '; ' if failure else '') + 'Physical Stop: ' + repr(error)
        stream_closed = source.stream is None or bool(getattr(source.stream, 'closed', False))
        lease_released = source.lease is None or source.lease.handle is None
        closure = dict(kind='CLOSED', owner=owner, error=failure, sent_samples=sent,
            stream_closed=stream_closed, lease_released=lease_released,
            status=source.status(), receipt=receipt, integrity=integrity,
            physical_raw_available=raw_sink is not None, raw_capture=raw_sink.receipt if raw_sink else None,
            raw_terminal=raw_terminal,
            raw_qualification_run=policy.get('raw_qualification') is True,
            source_batch_ms=config.get('source_batch_ms', 0), processed_acknowledgements=sequence,
            processed_source='retained_v28_packed_16k_route' if raw_sink else 'installed_v12_input_only_48k_route')
        with (root / 'SOURCE_CLOSE.json').open('xb') as stream:
            stream.write(_encoded(closure))
            stream.flush()
            os.fsync(stream.fileno())
        _send(1, closure, timeout=10)
    return 0 if not failure and stream_closed and lease_released and integrity and integrity['ok'] else 1


class _RemoteStatus:
    def __init__(self, source):
        self.source = source
        self.beam_diagnostics = _RemoteBeamDiagnostics(source)

    def status(self):
        return dict(self.source._status)

    def stop(self):
        self.source.stop()
        return self.source.stop_receipt

    def wait(self, timeout=None):
        return self.source.wait(timeout)


class _RemoteBeamDiagnostics:
    def __init__(self,source):self.source=source
    def snapshot(self):
        return dict(state=self.source._status.get('beam_diagnostics_state','UNAVAILABLE'),
                    read_only_remote=True)


class _IsolatedSource:
    def __init__(self, journal, config, callback, spatial_provider, policy, spool):
        self.journal, self.callback, self.spatial_provider = journal, callback, spatial_provider
        self.config, self.policy, self.spool = _mapping(config), _mapping(policy), spool
        if hasattr(policy, 'validate'):
            policy.validate()
        if 'maximum_session_seconds' in self.policy:
            self.policy['duration_seconds'] = self.policy['maximum_session_seconds']
            self.policy['sample_rate'] = spool.spec['sample_rate']
        self.config['raw_capture'] = spool.spec.get('mode') == 'raw_processed'
        self.policy['raw_qualification'] = spool.spec.get('raw_qualification') is True
        if self.config['raw_capture']:
            self.config['raw_qualification_evidence'] = spool.spec['raw']['qualification']
            self.config['raw_qualification'] = self.policy['raw_qualification']
        self.config.setdefault('owner_directory', str(spool.directory / 'work' / 'source'))
        expected_owner_root = (spool.directory / 'work' / 'source').resolve()
        actual_owner_root = Path(self.config['owner_directory']).absolute()
        if actual_owner_root != expected_owner_root or actual_owner_root.exists() or actual_owner_root.is_symlink():
            raise ValueError('Fresh session-owned source directory required')
        if not actual_owner_root.parent.is_dir() or actual_owner_root.parent.is_symlink():
            raise ValueError('Prepared real session work directory required')
        _check_config(self.config, self.policy)
        if any(self.policy[key] != spool.spec[key] for key in ('duration_seconds', 'sample_rate')):
            raise ValueError('Source and disk spool session policy differ')
        self.stop_event = threading.Event()
        self._done = threading.Event()
        self._started = threading.Event()
        self._write_lock = threading.Lock()
        self.thread = self.process = None
        self.owner = None
        self.sent = 0
        self.raw_sent = 0
        self.raw_digest = hashlib.sha256()
        self.error = None
        self.secondary_errors = []
        self.start_metadata = self.stop_receipt = self.integrity = self.timing = None
        self.clock_metadata = None
        self._status = dict(started=False, finished=False, converted_samples=0)
        self._stderr = bytearray()
        self.live = _RemoteStatus(self)
        self._beam = _load_mounted(self.config)['BeamReceiver'](spatial_provider or _NullSpatial())

    def _record(self, kind, value):
        return self.spool.store.write_event(self.spool.session_id, kind, value)

    def _control(self, value):
        with self._write_lock:
            _send(self.process.stdin.fileno(), value, timeout=5)

    def _accept_raw(self, message, audio):
        from raw_capture import validate_block
        if not self.config.get('raw_capture'):
            raise ValueError('Unrequested raw audio packet')
        end = validate_block(message.get('start_sample'), audio, self.raw_sent,
                             self.policy['duration_seconds']*16000)
        if message.get('samples') != len(audio)//16:
            raise ValueError('Raw packet sample metadata differs from payload')
        if self.config.get('source_batch_ms', 0) == 100:
            if self.raw_sent != self.sent or not 0 < end-self.sent <= 1600:
                raise ValueError('Batched raw requires one bounded packet before matching processed audio')
        self.spool.append_raw(self.raw_sent, audio)
        self.raw_digest.update(audio)
        self.raw_sent = end
        self._control(dict(kind='ACK_RAW', accepted_samples=end, stop=self.stop_event.is_set()))

    def _accept_audio_batch(self, message, audio):
        from source_batch import validate_message
        from app.live_audio import LiveBlock
        from app.live_timing import CaptureTimeline
        import numpy as np
        if self.config.get('source_batch_ms', 0) != 100:
            raise ValueError('Unrequested source batch')
        end = validate_message(message, audio, self.sent)
        if self.config.get('raw_capture') and self.raw_sent != end:
            raise ValueError('Matching grouped raw must be durable before processed audio')
        array = np.frombuffer(audio, dtype='<f4')
        offset = 0
        receipts = []
        for row in message['blocks']:
            count = row['samples']
            block = LiveBlock(audio=array[offset:offset+count], **row['metadata'])
            if self.timing is None:
                self.timing = CaptureTimeline(self.start_metadata, block)
                self.clock_metadata = self.timing.metadata()
                self.callback('source_started', {'mode':'live', 'source_epoch_monotonic_sec':self.timing.origin,
                    'route':self.start_metadata['route'], 'endpoint':self.start_metadata['endpoint'],
                    'capture_metadata':self.start_metadata, **self.clock_metadata})
            self.timing.accept(block, time.perf_counter_ns())
            if (block.model_start_sample+count)/16000 > time.perf_counter()-self.timing.origin:
                raise ValueError('Batched support is ahead of its fixed capture timeline')
            self._beam.accept(row['spatial_telemetry'], block.callback_perf_counter_ns/1e9)
            if self.spatial_provider is not None:
                self.spatial_provider.advance_audio(block)
            receipts.append(dict(start_sample=block.model_start_sample, samples=count,
                metadata=row['metadata'], spatial_telemetry=row['spatial_telemetry'],
                audio_sha256=hashlib.sha256(memoryview(audio)[offset*4:(offset+count)*4]).hexdigest()))
            offset += count
        # Every original clock/beam observation is accepted before one exact
        # contiguous journal commit. One bounded event avoids10 SQLite fsyncs.
        self.journal.append(array)
        self.sent = end
        self._status = message['status']
        self._record('source_batch', dict(start_sample=message['start_sample'], samples=message['samples'],
            source_batch_ms=100, sequence=message['sequence'], blocks=receipts))
        terminal = self.stop_event.is_set() or bool(self.journal.fatal_error)
        self._control(dict(kind='ACK_AUDIO', sequence=message['sequence'], accepted_samples=end, stop=terminal))
        return terminal

    def _diagnostic(self, raw):
        if len(self._stderr) + len(raw) > STDERR_BYTES:
            raise ValueError('Source stderr reservation exhausted')
        self._stderr.extend(raw)

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Create a fresh isolated source for each Start')
        self.thread = threading.Thread(target=self._run, name='processed-source-parent', daemon=True)
        self.thread.start()
        if not self._started.wait(180):
            self.stop_event.set()
            raise TimeoutError('Native source Start deadline')
        if self.error:
            raise RuntimeError(self.error)

    def _run(self):
        closure = None
        try:
            self.process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                '--child', self.config['owner_directory']], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0, close_fds=True)
            for handle in (self.process.stdin, self.process.stdout, self.process.stderr):
                os.set_blocking(handle.fileno(), False)
            owner, extra = _receive(self.process.stdout.fileno(), 20,
                self.process.stderr.fileno(), self._diagnostic)
            if extra or owner.get('kind') != 'OWNER' or owner['owner']['pid'] != self.process.pid or not _same_owner(owner['owner']):
                raise ValueError('Actual source process early identity did not verify')
            self.owner = owner['owner']
            self._record('source_owner', owner)
            self._control(dict(kind='ACK_OWNER', owner=self.owner, config=self.config, policy=self.policy))
            from app.live_audio import LiveBlock
            from app.live_timing import CaptureTimeline
            import numpy as np
            next_sequence = 0
            stop_sent = False
            deadline = time.monotonic() + 180
            while True:
                if self.stop_event.is_set() and not stop_sent:
                    self._control(dict(kind='STOP'))
                    stop_sent = True
                    deadline = time.monotonic() + 120
                if time.monotonic() > deadline:
                    raise TimeoutError('Source/physical-close deadline')
                try:
                    message, audio = _receive(self.process.stdout.fileno(), min(0.5, max(.01, deadline-time.monotonic())),
                        self.process.stderr.fileno(), self._diagnostic)
                except TimeoutError:
                    continue
                kind = message.get('kind')
                if kind == 'STARTED':
                    self.start_metadata = message['metadata']
                    self._status = message['status']
                    self._record('source_started_physical', message)
                    self._control(dict(kind='STOP' if stop_sent else 'ACK_START'))
                    self._started.set()
                    deadline = time.monotonic() + self.policy['duration_seconds'] + 120
                elif kind == 'RAW':
                    self._accept_raw(message, audio)
                elif kind == 'AUDIO_BATCH':
                    if message.get('sequence') != next_sequence:
                        raise ValueError('Source batch IPC sequence changed')
                    terminal = self._accept_audio_batch(message, audio)
                    if terminal:
                        stop_sent = True
                        deadline = time.monotonic()+120
                    next_sequence += 1
                elif kind == 'AUDIO':
                    if self.config.get('source_batch_ms', 0) == 100:
                        raise ValueError('Batched source cannot bypass grouped processed acknowledgement')
                    if message['sequence'] != next_sequence or len(audio) % 4 or not audio:
                        raise ValueError('Source audio IPC sequence/shape changed')
                    block = LiveBlock(audio=np.frombuffer(audio, dtype='<f4').copy(), **message['metadata'])
                    if block.model_start_sample != self.sent:
                        raise ValueError('Source audio absolute sample cursor changed')
                    if self.timing is None:
                        self.timing = CaptureTimeline(self.start_metadata, block)
                        self.clock_metadata = self.timing.metadata()
                        self.callback('source_started', {'mode':'live', 'source_epoch_monotonic_sec':self.timing.origin,
                            'route':self.start_metadata['route'], 'endpoint':self.start_metadata['endpoint'],
                            'capture_metadata':self.start_metadata, **self.clock_metadata})
                    self.timing.accept(block, time.perf_counter_ns())
                    if (self.sent + len(block.audio))/16000 > time.perf_counter() - self.timing.origin:
                        raise ValueError('Source support is ahead of its fixed capture timeline')
                    self._beam.accept(message['spatial_telemetry'], block.callback_perf_counter_ns/1e9)
                    if self.spatial_provider is not None:
                        self.spatial_provider.advance_audio(block)
                    self.journal.append(block.audio)
                    self.sent += len(block.audio)
                    self._status = message['status']
                    self._record('source_block', dict(start_sample=block.model_start_sample, samples=len(block.audio),
                        metadata=message['metadata'], spatial_telemetry=message['spatial_telemetry'],
                        audio_sha256=hashlib.sha256(audio).hexdigest()))
                    terminal = self.stop_event.is_set() or bool(self.journal.fatal_error)
                    self._control(dict(kind='ACK_AUDIO', sequence=next_sequence, accepted_samples=self.sent, stop=terminal))
                    if terminal:
                        stop_sent = True
                        deadline = time.monotonic() + 120
                    next_sequence += 1
                elif kind == 'CLOSED':
                    if audio or message['owner'] != self.owner:
                        raise ValueError('Source closure identity changed')
                    closure = message
                    self.stop_receipt = message['receipt']
                    self.integrity = message['integrity']
                    self._status = message['status']
                    if message['sent_samples'] != self.sent or not message['stream_closed'] or not message['lease_released']:
                        raise RuntimeError('Physical source closure/accepted-prefix check failed')
                    if message['error'] or not self.integrity or not self.integrity['ok']:
                        raise RuntimeError(message['error'] or 'Installed source integrity failed')
                    if self.config.get('raw_capture'):
                        raw = message.get('raw_capture') or {}
                        readback = self.spool.raw_receipt()
                        if self.raw_sent != self.sent or raw.get('samples') != self.raw_sent or raw.get('sha256') != self.raw_digest.hexdigest() or readback['sha256'] != raw.get('sha256'):
                            raise RuntimeError('Raw/processed clock or independent spool readback differs')
                        self._record('raw_capture_verified', dict(source=raw, spool=readback,
                            qualification_run=self.policy.get('raw_qualification') is True))
                    break
                else:
                    raise ValueError('Unknown source IPC message')
            code = self.process.wait(timeout=10)
            if code or _same_owner(self.owner):
                raise RuntimeError('Source process did not exit cleanly with its exact owner gone')
        except BaseException as error:
            self.error = type(error).__name__ + ': ' + str(error)
        finally:
            self._started.set()
            forced = False
            if self.process is not None and self.process.poll() is None:
                try:
                    self._control(dict(kind='STOP'))
                    recovery_deadline = time.monotonic() + 120
                    while self.process.poll() is None and time.monotonic() < recovery_deadline:
                        try:
                            message, ignored_audio = _receive(self.process.stdout.fileno(), .5,
                                self.process.stderr.fileno(), self._diagnostic)
                        except TimeoutError:
                            continue
                        except EOFError:
                            break
                        if message.get('kind') == 'CLOSED':
                            closure = message
                            self.stop_receipt = message.get('receipt')
                            self.integrity = message.get('integrity')
                            break
                    self.process.wait(timeout=max(.1, recovery_deadline-time.monotonic()))
                except BaseException:
                    forced = True
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=10)
                    self.error = self.error or 'Source required forced reaping; physical closure is unqualified'
            if self.process is not None:
                for handle in (self.process.stdin, self.process.stdout, self.process.stderr):
                    if handle is not None:
                        handle.close()
            summary = dict(owner=self.owner, sent_samples=self.sent, error=self.error,
                raw_samples=self.raw_sent,
                closure=closure, forced_reap=forced,
                exact_owner_gone=bool(self.owner and not _same_owner(self.owner)),
                child_exit_code=self.process.returncode if self.process is not None else None,
                stderr=bytes(self._stderr).decode('utf-8', 'replace'))
            try:
                self._record('source_closed', summary)
                self.callback('source_stopped', dict(integrity=self.integrity,
                    converted_samples_delivered=self.sent, physical_closure=summary))
                if self.error:
                    self.callback('fatal', dict(reason=self.error))
            except BaseException as error:
                self.error = self.error or 'Source closure publication failed: ' + repr(error)
            finally:
                self.journal.finish(self.error)
                self._done.set()

    def stop(self):
        self.stop_event.set()
        if self.thread is None:
            self.journal.finish()
            self._done.set()
            return
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(145)
            if self.thread.is_alive():
                raise RuntimeError('Source owner thread remains; physical closure is incomplete')
        if self.error:
            raise RuntimeError(self.error)

    def wait(self, timeout=None):
        return self._done.wait(timeout)


class _NullSpatial:
    def receive(self, *args):
        pass

    def invalidate_positions(self):
        pass


def create_source(journal, config, callback, spatial_provider, policy, spool):
    """Create without capture; start() alone launches the explicit source owner."""
    if sys.platform != 'linux':
        raise RuntimeError('Installed isolated XVF source is prepared for Linux only')
    prepare_source_imports(config)
    if spool.spec.get('raw_qualification') is True:
        # The source-only harness does not need the model pipeline base class.
        # LiveBlock/CaptureTimeline are loaded later by the source controller.
        return _IsolatedSource(journal, config, callback, spatial_provider, policy, spool)
    from app.pipeline import LivePipelineSource
    class PreparedSource(_IsolatedSource, LivePipelineSource):
        pass
    return PreparedSource(journal, config, callback, spatial_provider, policy, spool)


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--child':
        raise SystemExit('This source is started by create_source, not a standalone capture CLI')
    raise SystemExit(_child(sys.argv[2]))
