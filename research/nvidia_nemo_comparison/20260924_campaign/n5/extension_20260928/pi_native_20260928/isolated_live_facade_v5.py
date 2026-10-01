"""Explicit Start/request-Stop/drain/finalize interface; README_FIELD_LIVE_ENTRY_V1.md."""
from collections import deque
from dataclasses import fields
import json
from pathlib import Path
import sys
import time
from isolated_live_transport_v3 import IsolatedSource,SourceFault


class IsolatedLiveFacade:
    def __init__(self, config_path, prototype):
        self.config_path=Path(config_path);self.prototype=Path(prototype)
        sys.path[:0]=[str(self.prototype),str(self.prototype/'vendor')]
        self.transport=None;self.start_metadata=None;self.closed=False
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

    def finalize(self):
        # Never discard accepted audio to make Stop appear successful.
        if self.closed or self.transport is None or self.terminal is None or self.prefetch:
            raise SourceFault('FACADE_NOT_DRAINED')
        self.transport.close()
        self.closed=True
        if self.transport.forced_close:raise SourceFault('FACADE_FORCED_CLOSE')
        if self.delivered!=self.terminal['sent_samples'] or self.native_frames!=self.terminal['source_close'].get('bridge_native_frames',self.native_frames):
            raise SourceFault('FACADE_FINAL_COVERAGE')
        return dict(terminal=self.terminal,delivered_samples=self.delivered,native_frames=self.native_frames,
                    child_exit=self.transport.proc.returncode,forced_close=self.transport.forced_close)
