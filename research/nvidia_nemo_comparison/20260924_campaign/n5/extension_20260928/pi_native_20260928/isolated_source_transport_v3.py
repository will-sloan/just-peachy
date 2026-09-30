"""Bounded Linux source transport; see README_SOURCE_QUIET_V1.md."""
import argparse
from collections import deque
import hashlib
import importlib
import json
import os
from pathlib import Path
import resource
import select
import signal
import socket
import struct
import subprocess
import sys
import time

HEADER = struct.Struct('<cQQIIQ')
MAX_AUDIO = 8192
MAX_META = 2048
MAX_MESSAGE = HEADER.size + MAX_AUDIO + MAX_META
MAX_BLOCKS = 64
MAX_BYTES = 65536


def encoded(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False).encode()


class SourceFault(RuntimeError):
    def __init__(self, code, detail=None):
        self.code, self.detail = code, detail or {}
        super().__init__(code)


def identity():
    return dict(pid=os.getpid(), boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]))


def child(fd, config_path):
    sys.modules['isolated_source_transport_v2'] = sys.modules[__name__]
    sys.modules['isolated_source_transport_v3'] = sys.modules[__name__]
    resource.setrlimit(resource.RLIMIT_AS, (256*1024**2,)*2)
    assert resource.getrlimit(resource.RLIMIT_STACK) == (1024**2,)*2
    assert sorted(os.sched_getaffinity(0)) == [2, 3]
    def interrupted(signum, frame):
        raise SourceFault("SOURCE_SIGNAL", {"signal": signum})
    signal.signal(signal.SIGALRM, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    signal.alarm(90)
    cfg = json.loads(Path(config_path).read_text())
    root = Path(config_path).parent
    with (root/'CHILD_OWNER.json').open('x') as f:
        json.dump(identity(), f)
    wire = socket.socket(fileno=fd)
    wire.setblocking(False)
    source = None
    pending = deque()
    seq = offset = pending_bytes = high_blocks = high_bytes = 0
    digest = hashlib.sha256()
    fault = None
    stopped = False
    blocked_since = None
    source_close = {}
    started = time.monotonic_ns()
    source_read_ns = encode_send_ns = 0
    terminal_sent = False
    try:
        # Factory/module are source-bound by the dispatcher, never user text.
        factory = getattr(importlib.import_module(cfg['source_module']), cfg['source_factory'])
        source = factory(cfg)
        with (root/'CHILD_READY.json').open('x') as f:
            json.dump({'ready_ns': time.monotonic_ns()}, f)
        while True:
            while select.select([wire], [], [], 0)[0]:
                packet = wire.recv(256)
                if not packet:
                    raise SourceFault('CONSUMER_CLOSED')
                command = json.loads(packet)
                if command == {'stop': True}:
                    if not stopped:
                        source.stop()
                        stopped = True
                elif set(command) == {'ack'} and pending and command['ack'] == pending[0][0]:
                    pending_bytes -= pending.popleft()[1]
                else:
                    raise SourceFault('INVALID_ACK_OR_COMMAND')
            if len(pending) >= MAX_BLOCKS or pending_bytes + MAX_MESSAGE > MAX_BYTES:
                if blocked_since is None:
                    blocked_since = time.monotonic()
                if time.monotonic() - blocked_since > cfg['backpressure_seconds']:
                    raise SourceFault('BACKPRESSURE_TIMEOUT', {'outstanding_blocks': len(pending), 'outstanding_bytes': pending_bytes})
                select.select([wire], [], [], .002)
                continue
            blocked_since = None
            before = time.monotonic_ns()
            block = source.read(.002)
            source_read_ns += time.monotonic_ns()-before
            if block is None:
                if source.finished:
                    break
                continue
            begin, audio, metadata = block
            if begin != offset:
                raise SourceFault('SOURCE_DISCONTINUITY', {'expected': offset, 'received': begin})
            if not isinstance(audio, bytes) or not audio or len(audio) % 4 or len(audio) > MAX_AUDIO:
                raise SourceFault('MALFORMED_AUDIO_BYTES')
            before = time.monotonic_ns()
            meta = encoded(metadata)
            if len(meta) > MAX_META:
                raise SourceFault('METADATA_QUOTA')
            packet = HEADER.pack(b'D', seq, offset, len(audio), len(meta), before) + audio + meta
            try:
                sent = wire.send(packet)
            except BlockingIOError:
                raise SourceFault('KERNEL_SEND_BACKPRESSURE', {'rejected_offset': offset, 'rejected_samples': len(audio)//4})
            if sent != len(packet):
                raise SourceFault('SHORT_PACKET_SEND')
            encode_send_ns += time.monotonic_ns()-before
            pending.append((seq, len(packet)))
            pending_bytes += len(packet)
            high_blocks, high_bytes = max(high_blocks, len(pending)), max(high_bytes, pending_bytes)
            digest.update(audio)
            offset += len(audio)//4
            seq += 1
    except BaseException as exc:
        fault = dict(code=exc.code, detail=exc.detail) if isinstance(exc, SourceFault) else dict(code=type(exc).__name__, detail={'message': str(exc)[:512]})
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if source is not None:
            try:
                source.stop()
                source_close = source.close()
            except BaseException as exc:
                fault = dict(code='SOURCE_CLOSE_FAILED', detail={'message': str(exc)[:512], 'prior': fault})
        result = dict(kind='terminal', fault=fault, stopped=stopped, sent_blocks=seq,
                      sent_samples=offset, audio_sha256=digest.hexdigest(), high_blocks=high_blocks,
                      high_bytes=high_bytes, source_close=source_close,
                      source_read_ns=source_read_ns, encode_send_ns=encode_send_ns,
                      elapsed_ns=time.monotonic_ns()-started, owner=identity(),
                      address_space=list(resource.getrlimit(resource.RLIMIT_AS)),
                      stack=list(resource.getrlimit(resource.RLIMIT_STACK)), affinity=sorted(os.sched_getaffinity(0)),
                      peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        data = b'T'+encoded(result)
        assert len(data) < MAX_MESSAGE
        deadline = time.monotonic()+1
        while time.monotonic() < deadline:
            try:
                terminal_sent = wire.send(data) == len(data)
                break
            except BlockingIOError:
                select.select([], [wire], [], .01)
            except (BrokenPipeError, ConnectionResetError):
                break
        terminal_acknowledged = False
        deadline = time.monotonic()+2
        while terminal_sent and time.monotonic()<deadline:
            if not select.select([wire], [], [], .01)[0]:continue
            try:packet=wire.recv(256)
            except ConnectionResetError:break
            if not packet:break
            command=json.loads(packet)
            if set(command)=={'ack'} and pending and command['ack']==pending[0][0]:
                pending_bytes-=pending.popleft()[1]
            elif command=={'stop':True}:
                pass  # source already stopped and closed; no new audio admitted
            elif command=={'terminal_ack':seq} and not pending:
                terminal_acknowledged=True
                break
            else:break
        with (root/'CHILD_RESULT.json').open('x') as f:
            json.dump(result | {'terminal_sent':terminal_sent,'terminal_acknowledged':terminal_acknowledged}, f, indent=2)
        wire.close()
    return int(fault is not None or not terminal_sent or not terminal_acknowledged)


class IsolatedSource:
    """One ordered byte stream. A terminal fault follows all queued accepted blocks."""
    def __init__(self, config_path):
        self.root = Path(config_path).parent
        parent, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        for s in (parent, peer):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
        self.socket_bytes = {n:parent.getsockopt(socket.SOL_SOCKET, opt) for n,opt in [('send',socket.SO_SNDBUF),('receive',socket.SO_RCVBUF)]}
        self.wire = parent
        self.proc = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--child-fd', str(peer.fileno()), '--config', str(config_path)], pass_fds=(peer.fileno(),), stdin=subprocess.DEVNULL)
        peer.close()
        self.seq = self.offset = 0
        self.digest = hashlib.sha256()
        self.terminal = None
        self.closed = False
        self.stop_sent = False
        self.forced_close = False

    def stop(self):
        if not self.closed and not self.stop_sent and self.terminal is None:
            self.wire.sendall(encoded({'stop': True}))
            self.stop_sent = True

    def read(self, timeout=.25):
        if self.closed:
            raise SourceFault('READ_AFTER_CLOSE')
        if self.terminal is not None:
            return None
        if not select.select([self.wire], [], [], max(0, timeout))[0]:
            return None
        try:
            packet, _, flags, _ = self.wire.recvmsg(MAX_MESSAGE)
        except ConnectionResetError as exc:
            raise SourceFault('CHILD_EOF_WITHOUT_TERMINAL', {'socket_errno': exc.errno}) from exc
        if flags & socket.MSG_TRUNC:
            raise SourceFault('TRUNCATED_PACKET')
        if not packet:
            raise SourceFault('CHILD_EOF_WITHOUT_TERMINAL')
        if packet[:1] == b'T':
            terminal = json.loads(packet[1:])
            if terminal['sent_blocks'] != self.seq or terminal['sent_samples'] != self.offset or terminal['audio_sha256'] != self.digest.hexdigest():
                raise SourceFault('TERMINAL_COVERAGE_MISMATCH')
            self.terminal = terminal
            self.wire.sendall(encoded({'terminal_ack':self.seq}))
            if terminal['fault']:
                raise SourceFault(terminal['fault']['code'], terminal['fault']['detail'])
            return None
        if len(packet) < HEADER.size:
            raise SourceFault('SHORT_HEADER')
        tag, seq, start, audio_bytes, meta_bytes, published_ns = HEADER.unpack_from(packet)
        if tag != b'D' or seq != self.seq or start != self.offset or not 0 < audio_bytes <= MAX_AUDIO or audio_bytes % 4 or meta_bytes > MAX_META or len(packet) != HEADER.size+audio_bytes+meta_bytes:
            raise SourceFault('INVALID_FRAME')
        audio = packet[HEADER.size:HEADER.size+audio_bytes]
        meta = json.loads(packet[HEADER.size+audio_bytes:])
        received_ns = time.monotonic_ns()
        self.digest.update(audio)
        self.offset += audio_bytes//4
        self.seq += 1
        # The terminal may already be queued and the child naturally closed.
        try:
            self.wire.sendall(encoded({'ack': seq}))
        except (BrokenPipeError, ConnectionResetError):
            pass
        return start, audio, meta, published_ns, received_ns

    def close(self, timeout=4):
        if self.closed:
            return
        try:
            if self.terminal is None:
                try:
                    self.stop()
                    end = time.monotonic()+timeout
                    while self.terminal is None and time.monotonic() < end:
                        self.read(.02)
                except (SourceFault, BrokenPipeError, ConnectionResetError):
                    pass
            try:
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.forced_close = True
                self.proc.terminate()
                self.proc.wait(timeout=2)
        finally:
            self.wire.close()
            self.closed = True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--child-fd', type=int, required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    raise SystemExit(child(args.child_fd, args.config))
