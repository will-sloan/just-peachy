"""Fresh app adapters; see README_APP_BOUNDED_ARTIFACTS_V1.md."""
import copy
import json
import os
import queue
import threading
import time
from collections import OrderedDict
from pathlib import Path
from field_artifact_limits_v1 import resolved, digest
import numpy as np
from .bounded_live_artifacts_v1 import CompactJournal, PCM16Writer, encoded

MIB = 1024**2


class CompactBinary:
    """Archive worker file interface. The index is bypassed for this format."""
    def __init__(self, path, limit=None, *, artifact_limits=None):
        limits = resolved(artifact_limits)
        limit = limits["conversation_journal_bytes"] if limit is None else limit
        if type(limit) is not int or not 1024 <= limit <= limits["conversation_journal_bytes"]: raise ValueError("Conversation journal bound exceeds contract")
        self.sink = CompactJournal(path, limit, artifact_limits=limits)
        self.failed = False

    def write(self, data):
        self.sink.append(json.loads(data))
        return len(data)

    def tell(self): return self.sink.bytes
    def fileno(self): return self.sink.file.fileno()
    def close(self):
        if not self.sink.closed:
            self.sink.close('SOURCE_FAILURE' if self.failed else 'COMPLETE')
    def metrics(self): return self.sink.metrics()


class AudioWithPCM:
    """Exact float master plus explicit quantized listening copy on archive thread."""
    def __init__(self, path, max_frames, *, artifact_limits=None):
        self.file = Path(path).open('xb', buffering=0)
        try: self.pcm = PCM16Writer(Path(path).with_name('model_input.wav'), max_frames, artifact_limits=artifact_limits)
        except BaseException:
            self.file.close()
            raise
        self.failed = False

    def write(self, data):
        samples = np.frombuffer(data, dtype='<f4')
        self.pcm.write_float32(samples, source_start_frame=self.file.tell()//4)
        view = memoryview(data)
        while view:
            n = self.file.write(view)
            if not n: raise OSError('Incomplete exact audio write')
            view = view[n:]
        return len(data)

    def tell(self): return self.file.tell()
    def fileno(self): return self.file.fileno()
    def close(self):
        try:
            if not self.pcm.closed:
                self.pcm.close('SOURCE_FAILURE' if self.failed else 'COMPLETE')
        finally: self.file.close()
    def metrics(self): return self.pcm.metrics()


class ArtifactAsyncText:
    """Bounded queued JSON events; construct, use and close sink on worker thread."""
    def __init__(self, path, capacity=512, delay_once=0, sink_factory=None, byte_limit=None, *, artifact_limits=None):
        self.artifact_limits = resolved(artifact_limits)
        byte_limit = self.artifact_limits["native_journal_bytes"] if byte_limit is None else byte_limit
        if type(byte_limit) is not int or not 1024 <= byte_limit <= self.artifact_limits["native_journal_bytes"]: raise ValueError("Native journal bound exceeds contract")
        if type(capacity) is not int or not 1 <= capacity <= 512: raise ValueError("Journal queue item bound invalid")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.queue = queue.Queue(capacity)
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.sink = None
        self.pending_bytes = self.max_pending_bytes = 0
        self.accepted = self.completed = self.max_depth = 0
        self.error = None
        self.closed = False
        self.delay_once = delay_once
        self.byte_limit = byte_limit
        self.thread = threading.Thread(target=self._run, name='bounded-event-journal', daemon=True)
        self.thread.start()
        if not self.ready.wait(5): raise TimeoutError('Event writer did not initialize')
        if self.error: raise RuntimeError(self.error)

    def write(self, text):
        if not isinstance(text, str): raise TypeError('Expected JSON text')
        size = len(text.encode('utf-8'))
        with self.lock:
            if self.closed or self.error: raise RuntimeError('Journal unavailable: '+str(self.error))
            if size > MIB or self.pending_bytes+size > 4*MIB:
                self.error = 'Journal record/queue byte bound exceeded'
                raise RuntimeError(self.error)
            try: self.queue.put_nowait((text, size))
            except queue.Full:
                self.error = 'Journal item queue exhausted'
                raise RuntimeError(self.error)
            self.pending_bytes += size
            self.max_pending_bytes = max(self.max_pending_bytes, self.pending_bytes)
            self.accepted += 1
            self.max_depth = max(self.max_depth, self.queue.qsize())
        return len(text)

    def _run(self):
        try:
            self.sink = CompactJournal(self.path, self.byte_limit, artifact_limits=self.artifact_limits)
        except Exception as exc: self.error = repr(exc)
        finally: self.ready.set()
        if self.sink is None: return
        try:
            while True:
                item = self.queue.get()
                try:
                    if item is None: break
                    text, size = item
                    if self.delay_once:
                        time.sleep(self.delay_once)
                        self.delay_once = 0
                    # Already accepted records drain even after producer exhaustion.
                    if not self.sink.closed:
                        self.sink.append(json.loads(text))
                        self.completed += 1
                except Exception as exc: self.error = repr(exc)
                finally:
                    if item is not None:
                        with self.lock: self.pending_bytes -= item[1]
                    self.queue.task_done()
        finally:
            try:
                if not self.sink.closed: self.sink.close('SOURCE_FAILURE' if self.error else 'COMPLETE')
            except Exception as exc: self.error = repr(exc)

    def flush(self):
        if self.error: raise RuntimeError(self.error)

    def close(self):
        with self.lock:
            if self.closed:
                if self.thread.is_alive(): raise RuntimeError("Event journal closure still pending")
                if self.error or self.completed != self.accepted: raise RuntimeError("Event journal failed: "+str(self.error))
                return
            self.closed = True
        self.queue.put(None, timeout=10)
        self.thread.join(10)
        if self.thread.is_alive(): raise TimeoutError('Event writer did not drain')
        if self.error or self.completed != self.accepted:
            raise RuntimeError('Event journal failed: '+str(self.error))


    def closure_receipt(self):
        return dict(close_requested=self.closed, worker_alive=self.thread.is_alive(),
            physical_sink_closed=bool(self.sink is not None and self.sink.closed and self.sink.file.closed),
            error=self.error, accepted=self.accepted, completed=self.completed,
            uncompleted=self.accepted-self.completed, pending_bytes=self.pending_bytes,
            queue_items=self.queue.qsize(), clean=bool(self.closed and not self.thread.is_alive() and
                not self.error and self.accepted==self.completed),
            sink=self.sink.metrics() if self.sink is not None else None)


def compact_records(path, allow_partial=False, *, artifact_limits=None):
    """Strict bounded decoder. Partial prefixes require explicit archive metadata."""
    path = Path(path)
    limits = resolved(artifact_limits)
    if path.stat().st_size > max(limits['native_journal_bytes'], limits['conversation_journal_bytes']): raise ValueError('Compact archive exceeds admitted bound')
    states = OrderedDict()
    seq = 0
    with path.open('rb') as stream:
        while True:
            line = stream.readline(MIB+1)
            if not line:
                if allow_partial: return
                raise ValueError('Missing terminal marker')
            if len(line) > MIB: raise ValueError('Oversized compact record')
            if not line.endswith(b'\n'):
                if allow_partial: return
                raise ValueError('Torn compact record')
            row = json.loads(line)
            if row.get('format') == 'footer':
                if row['count'] != seq or stream.read(1): raise ValueError('Invalid terminal count/trailing data')
                if row['status'] != 'COMPLETE' and not (allow_partial and row['status'] in ('BYTE_LIMIT','RECORD_LIMIT','SOURCE_FAILURE')):
                    raise ValueError('Incomplete compact archive')
                return
            if row['seq'] != seq: raise ValueError('Noncontiguous event sequence')
            if row['format'] == 'event': event = row['value']
            elif row['format'] == 'patch':
                key = tuple(row['key'])
                oldseq, old = states[key]
                if oldseq != row['base_seq'] or len(row['ops']) > 4096: raise ValueError('Invalid patch base/bound')
                payload = copy.deepcopy(old)
                for op in row['ops']:
                    action, route = op[:2]
                    if len(route) > 24: raise ValueError('Patch depth exceeded')
                    if action in ('set','del'):
                        if not route:
                            if action != 'set': raise ValueError('Invalid root deletion')
                            payload = op[2]
                        else:
                            parent = payload
                            for token in route[:-1]: parent = parent[token]
                            if action == 'set': parent[route[-1]] = op[2]
                            else: del parent[route[-1]]
                    elif action in ('append','truncate'):
                        values = payload
                        for token in route: values = values[token]
                        if not isinstance(values,list): raise ValueError('Patch target not list')
                        if action == 'append': values.extend(op[2])
                        else:
                            if not 0 <= op[2] <= len(values): raise ValueError('Invalid truncation')
                            del values[op[2]:]
                    else: raise ValueError('Unknown patch operation')
                event = dict(row['meta'], payload=payload)
            else: raise ValueError('Unknown event format')
            if len(encoded(event)) > MIB: raise ValueError('Expanded event exceeds bound')
            kind = event.get('event_type', event.get('kind'))
            if kind == 's6d_display':
                key = (kind, event['payload']['session_id'])
                states[key] = (seq, copy.deepcopy(event['payload']))
                states.move_to_end(key)
                while len(states) > 2: states.popitem(last=False)
            seq += 1
            yield event


def compact_rows(folder, identifier, epoch, limit):
    """Preserve first caption order/latest revisions and formatting revision gate."""
    metadata = json.loads((folder/'epoch.json').read_text())
    if metadata.get('state') not in ('CLOSED','PARTIAL','RECOVERED_PARTIAL'):
        raise RuntimeError('Compact archive still open')
    limits = resolved(metadata.get('artifact_limits'))
    if metadata.get('artifact_limits') is not None and digest(limits) != metadata.get('artifact_limits_sha256'): raise ValueError('Archive artifact contract hash mismatch')
    rows, formats, sizes = OrderedDict(), {}, {}
    for event in compact_records(folder/'events.jsonl', allow_partial=metadata.get('state') != 'CLOSED', artifact_limits=limits):
        kind = event.get('kind')
        if kind not in ('s6d_display','prototype_formatted_text'): continue
        value = event['payload']; key = value.get('caption_key') or str(value.get('utterance_id'))
        sizes[(kind,key)] = len(encoded(value))
        if len(sizes) > 2048 or sum(sizes.values()) > 8*MIB: raise ValueError('Reopen working set exceeds scope')
        (rows if kind == 's6d_display' else formats)[key] = copy.deepcopy(value)
    values = list(rows.items())
    if limit is not None:
        if type(limit) is not int or limit < 0: raise ValueError('Invalid row limit')
        values = values[-limit:] if limit else []
    for key, row in values:
        row['archive_epoch_id'] = epoch; row['archive_conversation_id'] = identifier
        row['source_start_sample'] = round(float(row.get('source_start_sec',0))*16000)
        row['source_end_sample'] = round(float(row.get('source_end_sec',0))*16000)
        row['audio_link_quality'] = 'coarse utterance interval; not phonetic word alignment'
        formatting = formats.get(key)
        if formatting and formatting.get('text_revision_id') == row.get('text_revision_id'):
            row['archived_provisional_display_text'] = formatting['provisional_display_text']
            row['archived_final_formatted_text'] = formatting['final_formatted_text']
            row['text_assistance'] = copy.deepcopy(formatting.get('text_assistance'))
        yield row
