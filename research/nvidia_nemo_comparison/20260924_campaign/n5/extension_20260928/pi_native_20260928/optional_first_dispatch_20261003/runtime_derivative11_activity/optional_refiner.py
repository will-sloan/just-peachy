"""Bounded optional D1 child supervisor. See README_OPTIONAL_REFINER.md."""
from __future__ import annotations

import base64
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import threading
import time

from optional_refiner_admission import validate_requested_admission as validate_admission, operational_binding_sha256
from optional_refiner_resources import CombinedResourceGuard
from optional_refiner_labels import RefinerLabelBridge
from optional_refiner_protocol import Channel, BLOCK_SAMPLES, RATE


def available_ram():
    rows=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    return int(rows['MemAvailable'].split()[0])*1024


def physical_ram():
    rows=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    return int(rows['MemTotal'].split()[0])*1024


class JournalRPC:
    """One sequential read cursor; the parent alone owns the mutable spool."""
    def __init__(self,journal,maximum_samples):
        self.journal=journal;self.maximum_samples=maximum_samples;self.cursor=0
        self.digest=hashlib.sha256()

    def read(self,request):
        if (request.get('kind')!='read' or type(request.get('start_sample')) is not int or
                request['start_sample']!=self.cursor or request.get('maximum_samples')!=BLOCK_SAMPLES):
            raise ValueError('One exact sequential optional read required')
        state=self.journal.snapshot()
        if state.get('fatal_error'):
            raise RuntimeError('Primary committed journal reported failure')
        committed=state['committed_samples']
        if type(committed) is not int or not self.cursor<=committed<=self.maximum_samples:
            raise ValueError('Committed journal watermark regressed or exceeded admission')
        count=min(BLOCK_SAMPLES,self.journal.max_read_samples,committed-self.cursor)
        raw=self.journal.spool.read_processed(self.cursor,count) if count else b''
        if type(raw) is not bytes or len(raw)!=count*4:
            raise RuntimeError('Optional read cannot preserve exact committed source prefix')
        response=dict(kind='audio',start_sample=self.cursor,committed_samples=committed,
                      finished=bool(state['finished']),audio=base64.b64encode(raw).decode())
        self.cursor+=count;self.digest.update(raw)
        return response


class OptionalD1Refiner:
    """Model work and journal RPC run off the primary caption publication path.

    All failures disable refinement, retain primary evidence and emit diagnostics.
    Caller must close this owner before declaring the session completely closed.
    No child restart is allowed: a gap would invalidate continuous D1 state.
    """
    def __init__(self,*,journal,selection,policy,binding_path,binding_sha256,
                 admission_raw,admission_sha256,expected_pins,session_id,source_id,
                 unit,output_directory,reserved_output_bytes):
        if platform.system()!='Linux' or platform.machine()!='aarch64':
            raise RuntimeError('Native optional refinement requires the CM5; host contracts are separate')
        if set(os.sched_getaffinity(0))!={2,3}:
            raise RuntimeError('Parent must already be admitted on shared CPU2/3')
        if type(reserved_output_bytes) is not int or reserved_output_bytes<4*1024**2:
            raise ValueError('Independent 4 MiB optional output/mirror reservation required')
        from runtime_support import strict
        raw_binding=Path(binding_path).read_bytes()
        if (len(raw_binding)>65536 or hashlib.sha256(raw_binding).hexdigest()!=binding_sha256 or
                expected_pins.get('operational_binding_sha256')!=operational_binding_sha256(strict(raw_binding))):
            raise ValueError('Selected operational binding differs from exact admission')
        self.admission=validate_admission(admission_raw,admission_sha256,selection,policy,expected_pins,
                                          available_ram(),physical_ram_bytes=physical_ram(),phase='pre_child')
        self.selection,self.policy,self.journal=selection,policy,journal
        self.output=Path(output_directory).absolute()
        if any(p.is_symlink() for p in (self.output,*self.output.parents)):
            raise ValueError('Fresh real optional worker directory required')
        self.output.mkdir(exist_ok=False)
        self.config=dict(kind='configure',binding=str(binding_path),binding_sha256=binding_sha256,
                         input_source=selection.input_source,policy=policy.validate(),session_id=session_id)
        self.unit=unit;self.rpc=JournalRPC(journal,policy.maximum_samples())
        self.resource_guard=CombinedResourceGuard(unit,self.output/'COMBINED_RESOURCES.jsonl',self.admission['limits'])
        self.bridge=RefinerLabelBridge(session_id,source_id,selection.revision_window_seconds)
        self.lock=threading.Lock();self.messages=deque(maxlen=32);self.activity=deque(maxlen=8)
        self.stop_event=threading.Event();self.thread=self.process=self.channel=None
        self.started=None;self.failure=None;self.child_owner=None;self.child_result=None
        self.ready=False;self.done=False;self.frames=self.received=0;self.closed_receipt=None
        self.last_resource=None;self.diagnostic_drops=0
        self.alignment_bytes=0

    def _diagnostic(self,kind,**payload):
        row=dict(kind=kind,optional_refiner=True,primary_continues=True,**payload)
        with self.lock:
            if len(self.messages)==self.messages.maxlen:self.diagnostic_drops+=1
            self.messages.append(row)

    def start(self):
        if self.thread is not None or self.stop_event.is_set():
            raise RuntimeError('Optional native supervisor is single-use')
        self.started=time.monotonic()
        self.thread=threading.Thread(target=self._run,name='optional-d1-supervisor',daemon=True)
        self.thread.start()
        return self

    def _run(self):
        parent_socket,child_socket=socket.socketpair()
        self.channel=Channel(parent_socket)
        limits=self.admission['limits']
        arguments=[sys.executable,'-B',str(Path(__file__).with_name('optional_refiner_worker.py')),
            '--fd',str(child_socket.fileno()),'--parent-pid',str(os.getpid()),'--unit',self.unit,
            '--output',str(self.output/'child'),'--deadline',str(self.policy.total_deadline_seconds),
            '--as-bytes',str(limits['child_as_bytes'])]
        environment=dict(os.environ)
        environment.pop('NEMO_SPEECH_TIMING',None) # No unlimited native phase log.
        health_at=0.;finished_at=None;awaiting_response=False
        try:
            with (self.output/'native.log').open('xb',buffering=0) as log:
                self.process=subprocess.Popen(arguments,pass_fds=(child_socket.fileno(),),
                    stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=environment,
                    close_fds=True,start_new_session=False)
                child_socket.close()
                self.channel.send(self.config)
                while not self.stop_event.is_set():
                    now=time.monotonic()
                    if now-self.started>self.policy.total_deadline_seconds:
                        raise TimeoutError('Optional complete child lifetime exceeded')
                    if not self.ready and now-self.started>self.policy.model_load_seconds:
                        raise TimeoutError('Optional model initialization deadline')
                    state=self.journal.snapshot()
                    if state.get('fatal_error'):raise RuntimeError('Primary journal failed; optional work discarded')
                    if state['finished'] and finished_at is None:finished_at=now
                    if finished_at is not None and now-finished_at>self.policy.max_drain_seconds:
                        raise TimeoutError('Optional drain deadline; primary prefix remains')
                    if state['committed_samples']-min(self.frames*160,self.received)>=limits['maximum_lag_seconds']*RATE:
                        raise TimeoutError('Optional label lag no longer fits the revision window')
                    if now>=health_at:
                        health_at=now+1.
                        if self.resource_guard.exceeded():
                            raise MemoryError('Combined physical-memory soft-stop; dropping only optional refinement')
                        if (self.output/'native.log').stat().st_size>=512*1024:
                            raise RuntimeError('Optional native log capacity reached')
                    message=self.channel.receive()
                    if message is None:
                        if self.process.poll() is not None:raise RuntimeError('Optional child exited without complete closure receipt')
                        continue
                    kind=message.get('kind')
                    if kind=='owner':
                        owner=message.get('owner',{})
                        if self.child_owner is not None or owner.get('pid')!=self.process.pid or owner.get('parent_pid')!=os.getpid():
                            raise RuntimeError('Optional child ownership mismatch')
                        self.child_owner=owner;self._diagnostic('optional_refiner_owner',owner=owner)
                    elif kind=='ready':
                        if self.child_owner is None or self.ready:raise RuntimeError('Invalid optional initialization ordering')
                        self.ready=True;self.last_resource=message.get('resources')
                        self._diagnostic('optional_refiner_ready',initialization_seconds=message['initialization_seconds'],resources=self.last_resource)
                    elif kind=='read':
                        if not self.ready or awaiting_response:raise RuntimeError('Overlapping optional audio request')
                        response=self.rpc.read(message)
                        awaiting_response=bool(response['audio']) or response['finished']
                        self.channel.send(response)
                    elif kind=='activity':
                        raw=base64.b64decode(message['masks'],validate=True)
                        final=message.get('final')
                        if (type(final) is not bool or message.get('frame_start')!=self.frames or
                                message.get('frame_end')!=self.frames+len(raw) or len(raw)>8192 or
                                message.get('received_samples')!=self.rpc.cursor or not awaiting_response):
                            raise RuntimeError('Optional native frame/source delivery mismatch')
                        self.frames+=len(raw);self.received=self.rpc.cursor
                        awaiting_response=not final and bool(response['finished']) and self.rpc.cursor==response['committed_samples']
                        self.last_resource=message.get('resources')
                        # Empty updates acknowledge consumed audio during D1 warm-up.
                        # Their checked source watermark must not occupy a label batch.
                        if raw:
                            with self.lock:
                                if len(self.activity)==self.activity.maxlen:
                                    raise RuntimeError('Optional activity consumer capacity reached')
                                self.activity.append((message['frame_start'],raw,self.received))
                    elif kind=='closed':
                        if (message.get('owner')!=self.child_owner or message.get('delivered_samples')!=self.rpc.cursor or
                                message.get('output_frames')!=self.frames or message.get('delivered_f32_sha256')!=self.rpc.digest.hexdigest() or
                                message.get('complete_eof') is not True or message.get('model_closed') is not True or message.get('failure') is not None or
                                not state['finished'] or self.rpc.cursor!=state['committed_samples'] or
                                self.frames!=(0 if self.rpc.cursor==0 else self.rpc.cursor//160+1)):
                            raise RuntimeError('Optional worker did not close with exact source/EOF/probability coverage')
                        self.child_result=message;self.done=True
                        break
                    else:raise RuntimeError('Unknown optional worker message')
                if self.stop_event.is_set() and not self.done:
                    self.failure=self.failure or 'OPTIONAL_STOPPED_BY_PARENT; primary retained'
        except BaseException as exc:
            self.failure=type(exc).__name__+': '+str(exc)[:1024]
            self._diagnostic('optional_refiner_disabled',reason=self.failure,
                             primary_audio_dropped=False,child_restarted=False)
        finally:
            child_socket.close()
            if self.channel is not None:
                self.channel.close()
            try:self._reap()
            except BaseException as exc:
                self.failure=(self.failure or '')+'; child reap incomplete: '+str(exc)[:512]
            receipt=dict(schema='just-peachy.optional-refiner-closure.v1',failure=self.failure,
                child_owner=self.child_owner,child_result=self.child_result,
                process_returncode=self.process.returncode if self.process else None,
                child_dead=self.process is None or self.process.poll() is not None,
                sent_samples=self.rpc.cursor,processed_samples=self.received,returned_frames=self.frames,complete_eof=self.done and self.failure is None,
                diagnostic_drops=self.diagnostic_drops,primary_audio_dropped=False,
                quality_qualified=False)
            self.closed_receipt=receipt
            try:
                raw=json.dumps(receipt,sort_keys=True,allow_nan=False).encode()+b'\n'
                if len(raw)>65536:raise ValueError('Closure receipt capacity')
                with (self.output/'CLOSURE.json').open('xb') as stream:
                    stream.write(raw);stream.flush();os.fsync(stream.fileno())
            except BaseException as exc:
                self._diagnostic('optional_refiner_receipt_failed',reason=str(exc)[:512])
            self._diagnostic('optional_refiner_closed',**receipt)

    def _reap(self):
        process=self.process
        if process is None:return
        if process.poll() is None:
            try:process.wait(timeout=.25 if not self.done else 2.)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:process.wait(timeout=1.)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=2.)
        if process.returncode!=0 and self.failure is None:
            self.failure='Optional child exited '+str(process.returncode)

    def poll(self,rows,*,now=None):
        """Nonblocking handoff after primary caption publication or health tick.

        Returns diagnostics and label payloads; never waits/joins/reads audio or
        calls native code. Caller emits payloads through engine._emit so the
        installed S7 exact-target validation remains authoritative.
        """
        with self.lock:
            batches=list(self.activity);self.activity.clear()
            diagnostics=list(self.messages);self.messages.clear()
        revisions=[]
        try:
            for first,masks,received in batches:self.bridge.append(first,masks,received)
            if self.failure is None:
                revisions=self.bridge.revisions(rows,watermark=self.journal.committed_samples,
                                                now=time.perf_counter() if now is None else now)
                if revisions:
                    # One small immutable proof file, referenced by hash from all
                    # affected labels; never repeat a whole alignment per token.
                    pin,raw=self.bridge.last_alignment
                    directory=self.output/'alignment'
                    directory.mkdir(exist_ok=True)
                    path=directory/(pin+'.json')
                    if not path.exists():
                        if self.alignment_bytes+len(raw)>1024**2:
                            raise RuntimeError('Optional alignment evidence capacity reached')
                        with path.open('xb') as stream:
                            stream.write(raw);stream.flush();os.fsync(stream.fileno())
                        self.alignment_bytes+=len(raw)
                if self.bridge.status!=getattr(self,'last_bridge_status',None):
                    self.last_bridge_status=self.bridge.status
                    diagnostics.append(dict(kind='optional_refiner_label_status',status=self.bridge.status,
                                            primary_continues=True))
        except BaseException as exc:
            revisions=[]
            self.failure='Optional label bridge: '+type(exc).__name__+': '+str(exc)[:512]
            self.stop_event.set()
            diagnostics.append(dict(kind='optional_refiner_disabled',reason=self.failure,
                                    primary_continues=True,primary_audio_dropped=False))
        return diagnostics,revisions

    def close(self):
        """Stop optional work, kill/reap its exact child if needed; bounded wait."""
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(4.)
        if self.thread and self.thread.is_alive():
            self._reap();self.thread.join(1.)
        result=dict(self.closed_receipt or {},supervisor_thread_closed=not self.thread or not self.thread.is_alive(),
                    child_dead=self.process is None or self.process.poll() is not None)
        if not result['child_dead'] or not result['supervisor_thread_closed']:
            result['failure']='Optional worker closure incomplete; retain ownership'
        return result


def attach_optional_refiner(engine,selection,policy,*,diagnostic,**options):
    """Attach after engine.begin; caller invokes returned .poll() and .close().

    Required options are the explicit constructor's binding/admission pins,
    session/source IDs, owning unit, private output and reserved output bytes.
    Nothing is silently enabled: missing measured admission raises before spawn.
    """
    if not callable(diagnostic) or not hasattr(engine,'_s6d_presentation') or engine._journal is None:
        raise ValueError('Begun pinned engine and diagnostic sink required')
    worker=OptionalD1Refiner(journal=engine._journal,selection=selection,policy=policy,**options)
    class Attachment:
        def poll(self,*,publish_labels=True):
            rows=engine._s6d_presentation.snapshot_rows()
            events,patches=worker.poll(rows)
            for event in events:diagnostic(event)
            if not publish_labels or engine.state in ('COMPLETED','FAILED'):
                if patches:diagnostic(dict(kind='optional_refiner_late_tail_fallback',patch_count=len(patches)))
                patches=[]
            for patch in patches:
                try:engine._emit('transcript_label_revision',patch['source_end_sec'],patch)
                except BaseException as exc:
                    worker.failure='Optional presentation rejected: '+str(exc)[:512]
                    worker.stop_event.set()
                    diagnostic(dict(kind='optional_refiner_disabled',reason=worker.failure,primary_continues=True))
                    break
            return dict(diagnostics=len(events),label_revisions=len(patches),native_ready=worker.ready,
                        failed=worker.failure is not None,complete_eof=worker.done,
                        delivered_samples=worker.received,returned_frames=worker.frames,
                        label_backlog_seconds=max(0,worker.journal.committed_samples-min(worker.frames*160,worker.received))/RATE,
                        resources=worker.last_resource,diagnostic_drops=worker.diagnostic_drops,
                        whole_unit_rss_bytes=(worker.resource_guard.last or {}).get('whole_unit_rss_bytes'),
                        whole_unit_pss_bytes=(worker.resource_guard.last or {}).get('whole_unit_pss_bytes'))
        def close(self):
            result=worker.close()
            self.poll(publish_labels=False)
            diagnostic(dict(kind='optional_refiner_final',**result))
            return result
        @property
        def supervisor(self):return worker
    worker.start()
    return Attachment()
