"""Nonrotating native text/trace binding. README_FIELD_LIVE_LAYOUT_V1.md."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time
from copy import deepcopy
from field_live_layout_v2 import specification, finite_json


TEXT_SLOTS = {
    Path(v['path']).name: v for k, v in specification()['artifacts'].items()
    if k in ('labelled_transcript', 'readable_transcript', 'latest_transcript', 'native_clock_trace')}


class NativeTextFailure(RuntimeError):
    pass


class NativeTextOwner:
    """One native session directory, one sink per exact file, no retry or rotation.

    Counts are independent per file, so concurrent trace/transcript writers
    cannot consume another file's reservation. Existing sources stay immutable.
    This does not bind the event journal or three native finalization controls.
    """
    def __init__(self, session_parent, outputs, request_stop):
        self.parent = Path(session_parent).resolve()
        self.outputs, self.request_stop = outputs, request_stop
        self.directory = None
        self.sinks = {}
        self.lock = threading.Lock()

    def open(self, path):
        path = Path(path)
        with self.lock:
            if path.name not in TEXT_SLOTS or path.parent.parent.resolve() != self.parent:
                raise ValueError('Unmapped native text path')
            if path.parent.is_symlink() or not path.parent.is_dir():
                raise ValueError('Real native session directory required')
            directory = path.parent.resolve()
            if self.directory not in (None, directory) or path.name in self.sinks:
                raise NativeTextFailure('One session and one publication per native file')
            self.directory = directory
            # Reserve the slot before open; an open failure cannot be retried.
            self.sinks[path.name] = None
            try:
                sink = FixedText(path, self)
                self.sinks[path.name] = sink
                return sink
            except BaseException as exc:
                self.fail(exc)
                raise

    def fail(self, error, raw=None):
        return self.outputs.fail('native', error, self.request_stop, raw)

    def snapshot(self):
        return {name: None if sink is None else sink.snapshot() for name, sink in self.sinks.items()}


class FixedText:
    def __init__(self, path, owner):
        self.path, self.owner = Path(path), owner
        self.limits = deepcopy(TEXT_SLOTS[self.path.name])
        self.bytes = self.writes = 0
        self.closed = False
        self.failure = None
        self.flush_failed = False
        self.lock = threading.RLock()
        if shutil.disk_usage(self.path.parent).free < 5*1024**3:
            raise NativeTextFailure('Pi free floor')
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            self.handle = os.fdopen(fd, 'wb', buffering=0)
        except BaseException:
            os.close(fd)
            raise

    def write(self, text):
        with self.lock:
            if self.closed or self.failure is not None:
                raise NativeTextFailure('Native text is closed or failed')
            raw = None
            try:
                if type(text) is not str:
                    raise TypeError('Native text requires str')
                raw = text.encode('utf-8')
                if len(raw) > self.limits['maximum_write_bytes'] or self.bytes+len(raw) > self.limits['maximum_bytes']:
                    raise NativeTextFailure('Native text byte ceiling; earlier bytes preserved')
                if self.path.suffix == '.jsonl':
                    if not raw.endswith(b'\n'):
                        raise ValueError('Complete native JSON line required')
                    for line in raw.splitlines():
                        finite_json(line)
                if shutil.disk_usage(self.path.parent).free < 5*1024**3+len(raw):
                    raise NativeTextFailure('Pi free floor')
                view = memoryview(raw)
                while view:
                    n = self.handle.write(view)
                    if not n:
                        raise OSError('Native text short write')
                    self.bytes += n
                    view = view[n:]
                self.writes += 1
                return len(text)
            except BaseException as exc:
                self.failure = type(exc).__name__+': '+str(exc)[:512]
                # Mandatory nonblocking source Stop precedes all diagnostics.
                self.owner.fail(exc, raw)
                raise

    def flush(self):
        with self.lock:
            if not self.closed:
                if self.flush_failed:
                    raise NativeTextFailure(self.failure)
                try:
                    self.handle.flush()
                    os.fsync(self.handle.fileno())
                except BaseException as exc:
                    self.flush_failed = True
                    self.failure = self.failure or repr(exc)[:512]
                    self.owner.fail(exc)
                    raise

    def fileno(self):
        return self.handle.fileno()

    def close(self):
        with self.lock:
            if not self.closed:
                try:
                    self.flush()
                finally:
                    self.handle.close()
                    self.closed = True
            if self.failure is not None:
                raise NativeTextFailure(self.failure)

    def snapshot(self):
        return dict(bytes=self.bytes, writes=self.writes, maximum_bytes=self.limits['maximum_bytes'],
                    closed=self.closed, failure=self.failure)

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()


def bind(pipeline, trace_module, owner, pins):
    """Install into a fresh process after all actual module digests match.

    No model/source constructor is invoked. Native execution is still required.
    The final revised transcript and native controls need separate bindings.
    """
    if set(pins) != {'pipeline', 'trace'}:
        raise ValueError('Exact native binding pins')
    for name, module in (('pipeline', pipeline), ('trace', trace_module)):
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != pins[name]:
            raise ValueError('Native module changed: '+name)
    BaseTrace = trace_module.TraceWriter
    old = pipeline.PrototypeEngine._open_journal_text
    if getattr(old, '_bounded_live_text', False):
        raise ValueError('Native text already bound')

    def open_text(self, path):
        if Path(path).name == 'events.jsonl':
            return old(self, path)
        if Path(path).name not in ('labelled_transcript.jsonl', 'transcript.md'):
            raise ValueError('Unexpected native journal text')
        writer = pipeline.AsyncText(path, capacity=128, delay_once=0, sink_factory=owner.open)
        self.text_writers.append(writer)
        return writer
    open_text._bounded_live_text = True

    class BoundedTrace(BaseTrace):
        def __init__(self, path, session_id, capacity=16384):
            if Path(path).name != 's7_clocks.jsonl':
                raise ValueError('Unexpected native clock trace')
            super().__init__(path, session_id, min(capacity, 512))

        def _run(self):
            sink = None
            try:
                sink = owner.open(self.path)
            except BaseException as exc:
                self.error = repr(exc)
            last_flush = time.perf_counter()
            try:
                while True:
                    row = self.queue.get()
                    try:
                        if row is None:
                            break
                        if self.error is None:
                            sink.write(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n')
                            self.completed += 1
                            if time.perf_counter()-last_flush >= 1:
                                sink.flush()
                                last_flush = time.perf_counter()
                    except BaseException as exc:
                        self.error = self.error or repr(exc)
                        owner.fail(exc)
                    finally:
                        self.queue.task_done()
            finally:
                if sink is not None:
                    try:
                        sink.close()
                    except BaseException as exc:
                        self.error = self.error or repr(exc)
                        owner.fail(exc)
    pipeline.PrototypeEngine._open_journal_text = open_text
    trace_module.TraceWriter = BoundedTrace
    return dict(original_open_text=old, original_trace=BaseTrace,
                latest_transcript_bound=False, native_controls_bound=False,
                runtime_tested=False)
