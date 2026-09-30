"""Real source read/stop bridge, no startup; README_LIVE_SOURCE_BRIDGE_V1.md."""
from dataclasses import fields
import json
from pathlib import Path
from isolated_source_transport_v2 import SourceFault


class LiveSourceBridge:
    def __init__(self, source, live_gap, directory):
        self.source, self.live_gap = source, live_gap
        self.directory = Path(directory)
        self.next_sample = 0
        self.next_native = 0
        self.epoch = None
        self.stop_receipt = None
        self.closed = False

    @property
    def finished(self):
        status = self.source.status()
        return status['finished'] and status['pending_raw_blocks'] == 0

    def read(self, timeout=.002):
        try:
            block = self.source.read(timeout)
        except self.live_gap as exc:
            raise SourceFault('LIVE_SOURCE_GAP', {'source_fault': str(exc), 'status': self.source.status()}) from exc
        if block is None:
            return None
        if block.model_start_sample != self.next_sample or block.native_start_frame != self.next_native:
            raise SourceFault('LIVE_SOURCE_DISCONTINUITY')
        if self.epoch is None:
            self.epoch = block.epoch
        if block.epoch != self.epoch:
            raise SourceFault('LIVE_SOURCE_EPOCH_CHANGED')
        if str(block.audio.dtype) != 'float32' or block.audio.ndim != 1 or not 0 < len(block.audio) <= 2048:
            raise SourceFault('LIVE_SOURCE_AUDIO_SHAPE')
        metadata = {field.name: getattr(block, field.name) for field in fields(block) if field.name != 'audio'}
        payload = block.audio.astype('<f4', copy=False).tobytes()
        self.next_sample += len(block.audio)
        self.next_native += block.native_frames
        return block.model_start_sample, payload, metadata

    def stop(self):
        if self.stop_receipt is None:
            self.stop_receipt = self.source.stop()
            with (self.directory/'BRIDGE_STOP.json').open('x') as f:
                json.dump(self.stop_receipt, f, indent=2, allow_nan=False)

    def close(self):
        if self.closed:
            raise SourceFault('BRIDGE_ALREADY_CLOSED')
        self.stop()
        status = self.source.status()
        result = dict(closed=True, final_status=status, original_stop_status=self.stop_receipt['status'],
                      route_restoration=self.stop_receipt['route_restoration'], errors=self.stop_receipt['errors'],
                      bridge_model_samples=self.next_sample, bridge_native_frames=self.next_native,
                      stream_closed=not bool(self.source.stream.active),
                      lease_released=self.source.lease is None or self.source.lease.handle is None)
        with (self.directory/'BRIDGE_CLOSE.json').open('x') as f:
            json.dump(result, f, indent=2, allow_nan=False)
        self.closed = True
        if status['pending_raw_blocks'] or self.next_native != status['raw_frames'] or self.next_sample != status['converted_samples']:
            raise SourceFault('UNCONSUMED_ACCEPTED_RAW_TAIL', result)
        if not result['stream_closed'] or not result['lease_released'] or result['errors']:
            raise SourceFault('LIVE_SOURCE_CLOSE_INCOMPLETE', result)
        if any(value not in ('RESTORED','ALREADY_RESTORED') for value in result['route_restoration'].values()):
            raise SourceFault('SOURCE_RESTORATION_FAILED', result)
        return result
