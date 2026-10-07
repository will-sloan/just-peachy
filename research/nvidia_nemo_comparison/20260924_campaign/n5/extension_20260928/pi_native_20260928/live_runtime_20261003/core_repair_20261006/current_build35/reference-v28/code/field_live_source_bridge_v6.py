"""Operator source composition binding; README_FIELD_OPERATOR_PARENT_V1.md."""
from dataclasses import fields
import json
from pathlib import Path
from isolated_live_transport_v6 import SourceFault


class LiveSourceBridge:
    def __init__(self, source, live_gap, directory, receipt_routes):
        self.receipt_routes=receipt_routes
        self.receipt_failures=[]
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
        metadata = validate_block_metadata(metadata, self.source._mounted_beams.drain(block.callback_perf_counter_ns/1e9))
        payload = block.audio.astype('<f4', copy=False).tobytes()
        self.next_sample += len(block.audio)
        self.next_native += block.native_frames
        return block.model_start_sample, payload, metadata

    def stop(self):
        if self.stop_receipt is None:
            self.stop_receipt=self.source.stop()
            from field_source_receipt_routes_v1 import ReceiptFailure
            try:self.receipt_routes.source('BRIDGE_STOP.json',self.stop_receipt)
            except ReceiptFailure as exc:self.receipt_failures.append(exc.receipt)

    def close(self):
        if self.closed:raise SourceFault('BRIDGE_ALREADY_CLOSED')
        self.stop()
        status=self.source.status()
        raw_receipt=None
        if hasattr(self.source,'raw_capture_finish'):
            raw_receipt=self.source.raw_capture_finish()
        result=dict(closed=True,final_status=status,original_stop_status=self.stop_receipt['status'],
                    route_restoration=self.stop_receipt['route_restoration'],errors=self.stop_receipt['errors'],
                    bridge_model_samples=self.next_sample,bridge_native_frames=self.next_native,
                    stream_closed=bool(getattr(self.source.stream,'closed',False)),
                    lease_released=self.source.lease is None or self.source.lease.handle is None)
        from field_source_receipt_routes_v1 import ReceiptFailure
        try:self.receipt_routes.source('BRIDGE_CLOSE.json',result)
        except ReceiptFailure as exc:self.receipt_failures.append(exc.receipt)
        self.closed=True
        result['receipt_failures']=list(self.receipt_failures)
        code=None
        if status['pending_raw_blocks'] or self.next_native!=status['raw_frames'] or self.next_sample!=status['converted_samples']:code='UNCONSUMED_ACCEPTED_RAW_TAIL'
        elif not result['stream_closed'] or not result['lease_released'] or result['errors']:code='LIVE_SOURCE_CLOSE_INCOMPLETE'
        elif any(v not in ('RESTORED','ALREADY_RESTORED') for v in result['route_restoration'].values()):code='SOURCE_RESTORATION_FAILED'
        elif self.receipt_failures:code='SOURCE_RECEIPT_NOT_PUBLISHED'
        result['logical_success']=code is None;result['failure_code']=code
        self.receipt_routes.closure(result)
        if code:raise SourceFault(code,result)
        return result

"""Bounded XVF telemetry transport for the mounted IMU; see README.md.

No hardware access, model loading, filesystem writes, or position integration.
The microphone process owns the existing serialized XVF diagnostic getters.
"""
from collections import deque
from copy import deepcopy
import json
import math
import threading


FIELD_COUNTS = {'AEC_AZIMUTH_VALUES': 4, 'AEC_SPENERGY_VALUES': 4,
                'AUDIO_MGR_SELECTED_AZIMUTHS': 2}
MOUNT = dict(sensor_to_device=[[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
             array_zero_axis_device=[1, 0, 0], axes_verified=True,
             sensor_position_from_array_m=[-.045, -.16, -.015],
             offset_verified=True)
SCHEMA = 'just-peachy.xvf-telemetry.v1'
PACKET_BYTES = 1024  # Leaves space inside the existing 2048-byte block metadata.


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def sample(command, values, started, completed):
    if (command not in FIELD_COUNTS or type(values) not in (list, tuple)
            or len(values) != FIELD_COUNTS[command]
            or any(v is not None and not finite(v) for v in values)
            or not finite(started) or not finite(completed)
            or not 0 <= started <= completed):
        raise ValueError('Malformed beam telemetry sample')
    return [command, list(values), float(started), float(completed)]


class BeamQueue:
    """Transfer the existing getter callbacks without calling USB from audio code.

    Overflow explicitly advances a generation; it never masquerades as complete
    delivery. Completed samples are attached only to a later audio callback.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = deque()
        self.last = -math.inf
        self.sequence = 0
        self.generation = 0
        self.dropped = 0

    def receive(self, command, values, started, completed):
        row = sample(command, values, started, completed)
        with self.lock:
            if completed < self.last:
                raise ValueError('Beam receipt clock moved backwards')
            self.last = completed
            if len(self.pending) >= 64:
                self.dropped += len(self.pending)
                self.pending.clear()
                self.generation += 1
            self.sequence += 1
            self.pending.append([self.sequence, *row])

    def drain(self, callback):
        if not finite(callback) or callback < 0:
            raise ValueError('Actual audio callback clock required')
        with self.lock:
            result = dict(schema=SCHEMA, generation=self.generation,
                          dropped=self.dropped, samples=[])
            while self.pending and self.pending[0][-1] <= callback and len(result['samples']) < 12:
                candidate = self.pending[0]
                proposed = {**result, 'samples': result['samples'] + [candidate]}
                if len(encoded(proposed)) > PACKET_BYTES:
                    break
                result['samples'].append(self.pending.popleft())
            return result


class BeamReceiver:
    """Validate a whole packet before handing any sample to the live provider."""
    def __init__(self, provider):
        self.provider = provider
        self.sequence = 0
        self.generation = 0
        self.dropped = 0
        self.last = -math.inf

    def accept(self, packet, callback):
        if (type(packet) is not dict
                or set(packet) != {'schema', 'generation', 'dropped', 'samples'}
                or packet['schema'] != SCHEMA or len(encoded(packet)) > PACKET_BYTES
                or not finite(callback) or callback < 0):
            raise ValueError('Exact bounded beam packet required')
        generation, dropped = packet['generation'], packet['dropped']
        if (type(generation) is not int or type(dropped) is not int
                or generation < self.generation or dropped < self.dropped
                or type(packet['samples']) is not list
                or len(packet['samples']) > 12):
            raise ValueError('Beam generation/count drift')
        if generation == self.generation and dropped != self.dropped:
            raise ValueError('Undeclared beam loss')
        if generation > self.generation and dropped <= self.dropped:
            raise ValueError('Generation change requires a declared overflow')
        sequence, last, rows = self.sequence + dropped - self.dropped, self.last, []
        for value in packet['samples']:
            if type(value) is not list or len(value) != 5:
                raise ValueError('Exact beam sample shape')
            number, command, values, started, completed = value
            if type(number) is not int or number <= sequence:
                raise ValueError('Beam sequence replay')
            if number != sequence + 1:
                raise ValueError('Unreported beam sequence gap')
            row = sample(command, values, started, completed)
            if completed < last or completed > callback:
                raise ValueError('Future or reordered beam receipt')
            rows.append(row)
            sequence, last = number, completed
        if generation != self.generation:
            self.provider.invalidate_positions()
        for row in rows:
            self.provider.receive(*row)
        self.sequence, self.last = sequence, last
        self.generation, self.dropped = generation, dropped
        return len(rows)


def validate_block_metadata(metadata, telemetry, maximum=2048):
    """Retain the original transport cap and every original audio-clock field."""
    if type(metadata) is not dict or 'spatial_telemetry' in metadata:
        raise ValueError('Unmodified original audio metadata required')
    value = {**metadata, 'spatial_telemetry': deepcopy(telemetry)}
    if len(encoded(value)) > maximum:
        raise ValueError('Original audio metadata cap exceeded')
    return value


def saved_motion_policy(source_kind, recorded_motion=None):
    """A plain WAV has no beam/pose clock. Current live orientation is ineligible."""
    if source_kind not in ('live', 'file'):
        raise ValueError('Explicit audio source kind required')
    if source_kind == 'live':
        return dict(use_current_motion=True, direction_source='live_receipts')
    if recorded_motion is not None:
        raise ValueError('Recorded motion requires a separately verified audio/clock binding')
    return dict(use_current_motion=False, direction_source='unavailable_in_plain_wav')

