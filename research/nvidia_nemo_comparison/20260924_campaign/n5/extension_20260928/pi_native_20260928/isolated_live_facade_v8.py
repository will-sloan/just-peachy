"""Operator source composition binding; README_FIELD_OPERATOR_V1.md."""
from collections import deque
from dataclasses import fields
import json
from pathlib import Path
import sys
import time
from isolated_live_transport_v5 import IsolatedSource,SourceFault


class IsolatedLiveFacade:
    def __init__(self, config_path, prototype):
        self.config_path=Path(config_path);self.prototype=Path(prototype)
        sys.path[:0]=[str(self.prototype),str(self.prototype/'vendor')]
        self.transport=None;self.start_metadata=None;self.closed=False;self.physical_closure=None
        self.prefetch=deque();self.delivered=0;self.native_frames=0;self.epoch=None

    def start(self):
        if self.transport is not None or self.closed:raise SourceFault('FACADE_START_STATE')
        self.transport=IsolatedSource(self.config_path)
        deadline=time.monotonic()+45
        while not (self.config_path.parent.parent/'source/SOURCE_START.json').exists():
            if time.monotonic()>deadline:raise SourceFault('SOURCE_START_TIMEOUT')
            packet=self.transport.read(.01)
            if packet is not None:
                self.prefetch.append(packet)
                assert (self.config_path.parent.parent/'source/SOURCE_START.json').exists()
                break
            if self.transport.terminal is not None:raise SourceFault('SOURCE_ENDED_BEFORE_START')
        self.start_metadata=json.loads((self.config_path.parent.parent/'source/SOURCE_START.json').read_text())
        return self.start_metadata

    def request_stop(self):
        if self.transport is None or self.closed:raise SourceFault('FACADE_STOP_STATE')
        self.transport.stop()

    def read(self, timeout=.02):
        if self.start_metadata is None or self.closed:raise SourceFault('FACADE_READ_STATE')
        item=self.prefetch.popleft() if self.prefetch else self.transport.read(timeout)
        if item is None:return None
        begin,raw,meta,published,received=item
        import numpy as np
        from app.live_audio import LiveBlock
        assert set(meta)=={f.name for f in fields(LiveBlock) if f.name!='audio'}
        if begin!=self.delivered or meta['model_start_sample']!=begin or meta['native_start_frame']!=self.native_frames:
            raise SourceFault('FACADE_SOURCE_DISCONTINUITY')
        if self.epoch is None:self.epoch=meta['epoch']
        if meta['epoch']!=self.epoch:raise SourceFault('FACADE_EPOCH_CHANGED')
        audio=np.frombuffer(raw,dtype='<f4').copy();self.delivered+=len(audio);self.native_frames+=meta['native_frames']
        return LiveBlock(audio=audio,**meta),dict(published_ns=published,received_ns=received)

    @property
    def terminal(self):return None if self.transport is None else self.transport.terminal

    def _physical_close(self):
        transport=self.transport
        owner_path=transport.root/'control/REGISTERED_OWNER.json'
        if owner_path.is_symlink() or owner_path.stat().st_size>512:
            raise SourceFault('FACADE_OWNER_RECEIPT_INVALID')
        owner=json.loads(owner_path.read_bytes())
        if set(owner)!={'pid','start_ticks','boot_id'} or type(owner['pid']) is not int or type(owner['start_ticks']) is not int:
            raise SourceFault('FACADE_OWNER_IDENTITY_INVALID')
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if owner['pid']!=transport.proc.pid or owner['boot_id']!=transport.admission['boot_id'] or boot!=owner['boot_id']:
            raise SourceFault('FACADE_OWNER_IDENTITY_CHANGED')
        terminal_owner=self.terminal.get('owner')
        if terminal_owner!=owner:raise SourceFault('FACADE_TERMINAL_OWNER_CHANGED')
        try:observed=int(Path('/proc',str(owner['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])
        except FileNotFoundError:observed=None
        watched=transport.watch_result
        reaped=(isinstance(watched,dict) and watched.get('pid')==owner['pid']
                and type(watched.get('reaped_ns')) is int and watched['reaped_ns']>0
                and transport.proc.returncode is not None
                and watched.get('returncode')==transport.proc.returncode)
        receipt=dict(owner=owner,observed_start_ticks=observed,exact_identity_dead=observed!=owner['start_ticks'],
                     wire_closed=transport.wire.fileno()==-1,transport_closed=transport.closed,
                     watcher_joined=not transport.watcher.is_alive(),watch_error=transport.watch_error,
                     child_reaped=reaped,returncode=transport.proc.returncode,watch_result=watched)
        self.physical_closure=receipt
        if not (receipt['exact_identity_dead'] and receipt['wire_closed'] and receipt['transport_closed']
                and receipt['watcher_joined'] and receipt['watch_error'] is None and reaped):
            raise SourceFault('FACADE_PHYSICAL_CLOSE_UNVERIFIED',receipt)
        return receipt

    def finalize(self):
        # Physical release and the original logical fault are independent facts.
        if self.closed or self.transport is None or self.terminal is None or self.prefetch:
            raise SourceFault('FACADE_NOT_DRAINED')
        close_error=None
        try:self.transport.close()
        except BaseException as exc:close_error=exc
        try:
            physical=self._physical_close()
        except BaseException as exc:
            # Never replace either the original source/close fault or a physical failure.
            if close_error is not None:
                raise SourceFault('FACADE_PHYSICAL_CLOSE_UNVERIFIED',dict(
                    close_error=dict(type=type(close_error).__name__,message=str(close_error)[:1024],
                                     code=getattr(close_error,'code',None)),
                    physical_error=dict(type=type(exc).__name__,message=str(exc)[:1024]),
                    physical=self.physical_closure)) from close_error
            raise
        self.closed=True
        if close_error is not None:raise close_error
        if self.transport.forced_close:raise SourceFault('FACADE_FORCED_CLOSE')
        if self.delivered!=self.terminal['sent_samples'] or self.native_frames!=self.terminal['source_close'].get('bridge_native_frames',self.native_frames):
            raise SourceFault('FACADE_FINAL_COVERAGE')
        return dict(terminal=self.terminal,delivered_samples=self.delivered,native_frames=self.native_frames,
                    child_exit=self.transport.proc.returncode,forced_close=self.transport.forced_close,
                    physical_closure=physical)
