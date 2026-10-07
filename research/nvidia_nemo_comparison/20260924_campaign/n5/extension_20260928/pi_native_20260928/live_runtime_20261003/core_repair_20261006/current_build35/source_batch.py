"""Optional bounded source IPC grouping; see README_SOURCE_BATCH.md."""
import dataclasses
import json
import time

MAX_BLOCKS = 10
MAX_SAMPLES = 1600
MAX_AUDIO_BYTES = MAX_SAMPLES * 4
MAX_ROW_BYTES = 2048
MAX_METADATA_BYTES = 24 * 1024


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def batch_milliseconds(config):
    value = config.get('source_batch_ms', 0)
    if type(value) is not int or value not in (0, 100):
        raise ValueError('Source batching must explicitly select 0 or100 milliseconds')
    if value and config['live_config'].get('block_frames') != 480:
        raise ValueError('100ms source batching requires exact480-frame source callbacks')
    return value


class Batch:
    def __init__(self, start_sample):
        self.start_sample = start_sample
        self.samples = 0
        self.rows = []
        self.audio = bytearray()
        self.started = time.monotonic()

    def add(self, block, beam):
        count = len(block.audio)
        if (block.model_start_sample != self.start_sample+self.samples or
                not 0 < count <= 160 or self.samples+count > MAX_SAMPLES or
                len(self.rows) >= MAX_BLOCKS):
            raise ValueError('Bounded source batch sample sequence/extent differs')
        fields = {field.name: getattr(block, field.name) for field in dataclasses.fields(block)
                  if field.name != 'audio'}
        row = dict(metadata=fields, spatial_telemetry=beam, samples=count)
        if len(encoded(row)) > MAX_ROW_BYTES:
            raise ValueError('Original block/beam metadata exceeds batch row bound')
        if not self.rows:
            self.started = time.monotonic()
        raw = block.audio.astype('<f4', copy=False).tobytes()
        if len(raw) != count*4:
            raise ValueError('Batch requires mono float32 audio')
        self.audio.extend(raw)
        self.rows.append(row)
        self.samples += count

    @property
    def full(self):
        return len(self.rows) == MAX_BLOCKS or self.samples == MAX_SAMPLES

    def message(self, sequence, status):
        row = dict(kind='AUDIO_BATCH', sequence=sequence, start_sample=self.start_sample,
                   samples=self.samples, blocks=self.rows, status=status, source_batch_ms=100)
        validate_message(row, self.audio, self.start_sample)
        return row


def validate_message(message, audio, accepted_samples):
    if (message.get('kind') != 'AUDIO_BATCH' or message.get('source_batch_ms') != 100 or
            message.get('start_sample') != accepted_samples or
            type(message.get('samples')) is not int or not 0 < message['samples'] <= MAX_SAMPLES or
            len(audio) != message['samples']*4 or len(audio) > MAX_AUDIO_BYTES or
            type(message.get('blocks')) is not list or not 1 <= len(message['blocks']) <= MAX_BLOCKS or
            len(encoded(message)) > MAX_METADATA_BYTES):
        raise ValueError('Bounded source batch header/extent differs')
    cursor = accepted_samples
    for row in message['blocks']:
        if (type(row) is not dict or set(row) != {'metadata', 'spatial_telemetry', 'samples'} or
                type(row['samples']) is not int or not 0 < row['samples'] <= 160 or
                type(row['metadata']) is not dict or row['metadata'].get('model_start_sample') != cursor or
                len(encoded(row)) > MAX_ROW_BYTES):
            raise ValueError('Original source batch block extent differs')
        cursor += row['samples']
    if cursor != accepted_samples+message['samples']:
        raise ValueError('Source batch blocks do not cover its exact audio prefix')
    return cursor


def deliver(batch, sequence, source, raw_sink, send, receive):
    """Commit grouped raw first, then the matching processed prefix, one ACK each."""
    end = batch.start_sample+batch.samples
    if raw_sink is not None:
        # <=1600*16 bytes, below the converter's64KiB auto-flush threshold.
        # No per-block flush is permitted in this optional path.
        source._converter.flush()
        if raw_sink.accepted_samples != end:
            raise ValueError('Grouped raw durable extent differs before processed send')
    send(1, batch.message(sequence, source.status()), batch.audio)
    command, extra = receive(0, 5)
    stopping = False
    if not extra and command.get('kind') == 'STOP':
        stopping = True
        command, extra = receive(0, 5)
    if (extra or command.get('kind') != 'ACK_AUDIO' or command.get('sequence') != sequence or
            command.get('accepted_samples') != end):
        raise ValueError('Exact durable source-batch acknowledgement missing')
    return end, stopping or command.get('stop') is True or bool(raw_sink and raw_sink.stop_requested)


def capture(source, telemetry, maximum_samples, raw_sink, send, receive, control_ready, progress):
    """Read one finite group at a time; explicit Stop flushes every read sample."""
    batch = Batch(progress['sent'])
    stopping = False
    while not stopping and progress['sent'] < maximum_samples:
        if control_ready():
            command, extra = receive(0, 1)
            if extra or command.get('kind') != 'STOP':
                raise ValueError('Unexpected batched source control command')
            stopping = True
        if not stopping:
            block = source.read(.01 if batch.rows else .1)
            if block is not None:
                if block.model_start_sample+len(block.audio) > maximum_samples:
                    raise ValueError('Batched source exceeded its allocated capture prefix')
                batch.add(block, telemetry.drain(block.callback_perf_counter_ns/1e9))
        end = batch.start_sample+batch.samples
        if batch.rows and (stopping or batch.full or end == maximum_samples or
                           time.monotonic()-batch.started >= .1):
            sent, acknowledged_stop = deliver(batch, progress['sequence'], source, raw_sink, send, receive)
            progress.update(sent=sent, sequence=progress['sequence']+1)
            stopping = stopping or acknowledged_stop
            batch = Batch(sent)
    return stopping
