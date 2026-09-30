"""Bounded Linux source transport; see README_FIELD_LIVE_SOURCE_V1.md."""
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


import threading
import field_child_deadline_v1 as deadlines
from field_live_source_outputs_v1 import load,sha,OutputFailure

def child(fd,config_path,expected):
    resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2)
    assert resource.getrlimit(resource.RLIMIT_STACK)==(1024**2,)*2 and sorted(os.sched_getaffinity(0))==[2,3]
    cfg,a,outputs=load(config_path,expected,role="child")
    alarm=deadlines.ChildAlarm(cfg['deadline'],a).arm()
    wire=socket.socket(fileno=fd);wire.setblocking(False)
    source=None;pending=deque();seq=offset=pending_bytes=high_blocks=high_bytes=0
    digest=hashlib.sha256();fault=None;stopped=False;blocked_since=None;source_close={}
    started=time.monotonic_ns();source_read_ns=encode_send_ns=0;terminal_sent=False;terminal_acknowledged=False
    publication_failure=None;finalization_error=None
    try:
        # Parent records exact PID/start ticks before child work, independently
        # of whether the child's own source-group owner receipt can fit.
        if not select.select([wire],[],[],min(2,deadlines.remaining(cfg['deadline'])))[0] or wire.recv(256)!=b'REGISTERED':raise SourceFault('PARENT_IDENTITY_NOT_REGISTERED')
        outputs.source('CHILD_OWNER.json',identity())
        factory=getattr(importlib.import_module(cfg['source_module']),cfg['source_factory']);source=factory(cfg)
        outputs.request_stop=source.signal_stop
        outputs.source('CHILD_READY.json',{'ready_ns':time.monotonic_ns()})
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
        fault=dict(code=exc.code,detail=exc.detail) if isinstance(exc,SourceFault) else dict(code=type(exc).__name__,detail={'message':str(exc)[:512]})
    finally:
        # Cleanup remains inside the same absolute soft/hard budget; the parent
        # watcher remains active while this thread waits for terminal ACK.
        if source is not None:
            for operation in ['stop','close']:
                try:
                    value=getattr(source,operation)()
                    if operation=='close':source_close=value
                except BaseException as exc:fault=dict(code='SOURCE_CLOSE_FAILED',detail={'operation':operation,'message':str(exc)[:512],'prior':fault})
        try:
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
            try:outputs.source('CHILD_RESULT.json',result|dict(terminal_sent=terminal_sent,terminal_acknowledged=terminal_acknowledged))
            except OutputFailure as exc:publication_failure=exc.receipt
        except BaseException as exc:finalization_error=dict(type=type(exc).__name__,message=str(exc)[:512])
        finally:
            wire.close();alarm.close()
        closure=dict(owner=identity(),wire_closed=wire.fileno()==-1,source_created=source is not None,source_close=source_close,
                     fault=fault,publication_failure=publication_failure,finalization_error=finalization_error,
                     terminal_sent=terminal_sent,terminal_acknowledged=terminal_acknowledged,deadline=cfg['deadline'])
        closure['logical_success']=not any([fault,publication_failure,finalization_error]) and terminal_sent and terminal_acknowledged
        outputs.finish('transport_child',closure)
    return int(not closure['logical_success'])


class IsolatedSource:
    """One ordered byte stream. A terminal fault follows all queued accepted blocks."""
    def __init__(self,config_path):
        cfg,a,self.outputs=load(config_path);self.root=Path(cfg['output_root']);self.deadline=cfg['deadline'];self.admission=a
        parent,peer=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        for s in (parent,peer):
            s.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,262144);s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,262144)
        self.socket_bytes={n:parent.getsockopt(socket.SOL_SOCKET,opt) for n,opt in [('send',socket.SO_SNDBUF),('receive',socket.SO_RCVBUF)]}
        self.wire=parent;self.watch_result=None;self.watch_error=None
        try:
            self.proc=deadlines.spawn([sys.executable,'-B',str(Path(__file__).resolve()),'--child-fd',str(peer.fileno()),'--config',str(config_path),'--config-sha256',sha(config_path)],self.deadline,a,pass_fds=(peer.fileno(),),stdin=subprocess.DEVNULL)
        finally:peer.close()
        def watch():
            try:self.watch_result=deadlines.supervise(self.proc,self.deadline,a)
            except BaseException as exc:self.watch_error=type(exc).__name__+': '+str(exc)
        self.watcher=threading.Thread(target=watch,name='absolute-source-watch',daemon=False);self.watcher.start()
        self.seq=self.offset=0;self.digest=hashlib.sha256();self.terminal=None;self.closed=False;self.stop_sent=False;self.forced_close=False
        try:
            tick=int(Path('/proc',str(self.proc.pid),'stat').read_text().rsplit(')',1)[1].split()[19])
            self.outputs.groups['control'].json('REGISTERED_OWNER.json',dict(pid=self.proc.pid,start_ticks=tick,boot_id=a['boot_id']))
            self.wire.sendall(b'REGISTERED')
        except BaseException:
            self.wire.close();self.watcher.join(timeout=deadlines.remaining(self.deadline,hard=True)+2);raise

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

    def close(self,timeout=4):
        if self.closed:return
        try:
            if self.terminal is None:
                try:
                    self.stop();end=min(time.monotonic()+timeout,self.deadline['soft_ns']/1e9)
                    while self.terminal is None and time.monotonic()<end:self.read(.02)
                except (SourceFault,BrokenPipeError,ConnectionResetError):pass
            self.watcher.join(timeout=deadlines.remaining(self.deadline,hard=True)+2)
        finally:self.wire.close();self.closed=True
        if self.watcher.is_alive() or self.watch_error:raise SourceFault('CHILD_WATCHER_NOT_CLOSED',{'error':self.watch_error})
        self.forced_close=self.watch_result['terminate_sent'] or self.watch_result['kill_sent']
        receipt=self.root/'closure/transport_child.json'
        if not receipt.exists():raise SourceFault('CHILD_CLOSURE_MISSING')
        closure=json.loads(receipt.read_text())
        if self.proc.returncode!=0 or not closure['logical_success']:raise SourceFault('CHILD_OUTPUT_OR_FINALIZATION_FAILED',closure)

from field_transport_close_latch_v1 import source_class as _latch_source
IsolatedSource=_latch_source(IsolatedSource,SourceFault)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--child-fd',type=int,required=True);p.add_argument('--config',required=True);p.add_argument('--config-sha256',required=True);a=p.parse_args()
    raise SystemExit(child(a.child_fd,a.config,a.config_sha256))
