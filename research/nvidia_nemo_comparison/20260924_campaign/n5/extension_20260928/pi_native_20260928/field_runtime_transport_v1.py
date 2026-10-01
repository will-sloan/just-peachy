"""Bounded manager protocol transport; README_FIELD_RUNTIME_EXPORT_V1.md."""
import json
import struct
import subprocess
import threading
import time

from field_runtime_auxiliary_v1 import strict_json
from field_runtime_policy_v3 import validate as validate_policy
from field_local_manager_owners_v1 import identity, key


class TransportFailure(RuntimeError):
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


def frame(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if not 1 <= len(raw) <= 262144:
        raise ValueError('Bounded metadata frame')
    return struct.pack('!I', len(raw)) + raw


class Channel:
    """One stdout reader; all stdin publications use a bounded writer thread."""
    def __init__(self, proc, check, deadline, state):
        self.proc, self.check, self.deadline, self.state = proc, check, deadline, state
        self.wire_bytes = 0
        self.writer = None

    def read(self, count):
        if type(count) is not int or not 1 <= count <= 16384:
            raise ValueError('Explicit 16KiB read ceiling')
        self.check()
        raw = self.proc.stdout.read(count)
        self.wire_bytes += len(raw)
        # Full reserved tree plus original 2MiB control/code bound; this is a
        # transport ceiling, never an additional filesystem allocation.
        if self.wire_bytes > self.state['wire_maximum_bytes']:
            raise ValueError('Manager wire ceiling')
        self.check()
        return raw

    def exact(self, count):
        if type(count) is not int or not 0 <= count <= 262144:
            raise ValueError('Exact bounded frame size')
        out = bytearray()
        while len(out) < count:
            raw = self.read(min(16384, count-len(out)))
            if not raw:
                raise EOFError('Truncated manager frame')
            out.extend(raw)
        return bytes(out)

    def json(self):
        size = struct.unpack('!I', self.exact(4))[0]
        if not 1 <= size <= 262144:
            raise ValueError('Manager metadata ceiling')
        return strict_json(self.exact(size))

    def send(self, raw):
        if type(raw) is not bytes or not 1 <= len(raw) <= 262148:
            raise ValueError('Bounded framed input')
        if self.writer is not None and self.writer.is_alive():
            raise RuntimeError('Concurrent protocol writer')
        def write():
            try:
                view = memoryview(raw)
                while view:
                    self.check()
                    n = self.proc.stdin.write(view[:16384])
                    if type(n) is not int or not 1 <= n <= min(len(view), 16384):
                        raise OSError('Invalid protocol write count')
                    view = view[n:]
                self.proc.stdin.flush()
            except BaseException as exc:
                self.state['writer_error'] = type(exc).__name__ + ': ' + str(exc)[:512]
        self.writer = threading.Thread(target=write, daemon=True)
        self.writer.start()
        while self.writer.is_alive():
            self.writer.join(.02)
            self.check()
        self.check()

    def send_json(self, value):
        self.send(frame(value))


def run(command, payload, *, policy, persist_early, consume, verify_closed, stop_owned,
        guard, timeout=105):
    """One process attempt. The caller owns admission, source pins and storage.

    persist_early must durably publish the actual early identity before return.
    consume(channel, owner, close) may invoke close inside the mirror receiver.
    close requires EOF, natural exit, joined I/O and independent exact closure.
    No retry, destination cleanup, BACKUP publication or admission occurs here.
    """
    if type(command) is not list or not command or any(type(x) is not str for x in command):
        raise ValueError('Exact argv')
    if type(payload) is not bytes or not 1 <= len(payload) <= 262144:
        raise ValueError('Original bootstrap input ceiling')
    if type(timeout) not in (int, float) or not 0 < timeout <= 105:
        raise ValueError('Finite bounded phase')
    for callback in (persist_early, consume, verify_closed, stop_owned, guard):
        if not callable(callback):
            raise ValueError('Required protocol guard')
    validate_policy(policy)
    allocation = policy['allocation']
    wire_maximum = allocation['metadata_maximum_bytes'] + allocation['recordings']*allocation['local_backup_per_recording'] + 2097152
    guard()
    threading.stack_size(1048576)
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, bufsize=0)
    state = dict(wire_maximum_bytes=wire_maximum, stderr=bytearray(), reader_error=None, writer_error=None,
                 fault=None, stopped=False, killed=False, owner=None,
                 early_persisted=False, hello_matched=False, closure_verified=False)
    finished = threading.Event()
    failure = threading.Event()
    stop_lock = threading.Lock()
    deadline = time.monotonic() + timeout

    def check():
        if failure.is_set():
            raise RuntimeError(state['fault'] or 'Transport failed')
        if state['reader_error'] or state['writer_error']:
            raise RuntimeError(state['reader_error'] or state['writer_error'])
        if time.monotonic() >= deadline:
            raise TimeoutError('Manager transport deadline')
        guard()

    def stop():
        with stop_lock:
            if state['stopped']:
                return
            state['stopped'] = True
            try:
                # Callback must itself be bounded and stop only its admitted unit.
                stop_owned()
            except BaseException as exc:
                state['stop_error'] = type(exc).__name__ + ': ' + str(exc)[:512]
            finally:
                if proc.poll() is None:
                    state['killed'] = True
                    proc.kill()

    def drain():
        try:
            while True:
                raw = proc.stderr.read(4096)
                if not raw:
                    return
                room = 65536-len(state['stderr'])
                state['stderr'].extend(raw[:room])
                if len(raw) > room:
                    raise ValueError('Manager stderr ceiling')
        except BaseException as exc:
            state['reader_error'] = type(exc).__name__ + ': ' + str(exc)[:512]

    def watch():
        while not finished.wait(.02):
            try:
                check()
            except BaseException as exc:
                state['fault'] = type(exc).__name__ + ': ' + str(exc)[:512]
                failure.set()
                stop()
                return

    reader = threading.Thread(target=drain, daemon=True)
    watcher = threading.Thread(target=watch, daemon=True)
    channel = Channel(proc, check, deadline, state)
    reader.start()
    watcher.start()

    def close():
        if state['closure_verified']:
            raise RuntimeError('One closure publication only')
        if channel.read(1):
            raise ValueError('Unexpected trailing stdout')
        proc.wait(timeout=max(.001, deadline-time.monotonic()))
        reader.join(max(.001, deadline-time.monotonic()))
        check()
        if proc.returncode != 0 or reader.is_alive() or state['stopped'] or state['killed']:
            raise RuntimeError('Natural clean exit required')
        if channel.writer is not None and channel.writer.is_alive():
            raise RuntimeError('Input writer still active')
        proof = verify_closed(state['owner'])
        if proof is not True:
            raise RuntimeError('Independent exact closure required')
        check()
        state['closure_verified'] = True

    error = None
    value = None
    try:
        early = channel.json()
        if type(early) is not dict or set(early) != {'early_owner'}:
            raise ValueError('Exact early owner envelope')
        owner = dict(identity(early['early_owner']))
        state['owner'] = owner
        if persist_early(dict(owner)) is not True:
            raise RuntimeError('Durable early owner receipt required')
        state['early_persisted'] = True
        channel.send(struct.pack('!I', len(payload)) + payload)
        hello = channel.json()
        if (type(hello) is not dict or set(hello) != {'type', 'owner'}
                or hello['type'] != 'HELLO' or key(hello['owner']) != key(owner)):
            raise ValueError('HELLO must match persisted early identity')
        state['hello_matched'] = True
        value = consume(channel, dict(owner), close)
        if not state['closure_verified']:
            raise RuntimeError('Consumer returned before exact closure')
        check()
    except BaseException as exc:
        error = type(exc).__name__ + ': ' + str(exc)[:512]
        state['fault'] = state['fault'] or error
        failure.set()
        stop()
    finally:
        finished.set()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            state['killed'] = True
            proc.kill()
            proc.wait(timeout=5)
        for thread in (reader, watcher, channel.writer):
            if thread is not None:
                thread.join(3)
        joined = all(t is None or not t.is_alive() for t in (reader, watcher, channel.writer))
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if not pipe.closed:
                pipe.close()
    receipt = dict(state, stderr=bytes(state['stderr']), returncode=proc.returncode,
                   io_joined=joined, process_reaped=proc.poll() is not None,
                   wire_bytes=channel.wire_bytes)
    if error or not joined or state['reader_error'] or state['writer_error']:
        raise TransportFailure(error or 'Late I/O closure failure', receipt)
    return value, receipt
