"""Paced complete kept-recording float32 and bound historical spatial replay. See README_SAVED_REPLAY.md."""
import hashlib
import json
import os
from pathlib import Path
import threading
import time

from storage import SessionStore, StorageError
from saved_source_metrics import SavedSourceMetrics, validate_batch_samples


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def identity(path):
    info = path.stat()
    return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
                mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns)


class SavedSessionSource:
    """Read-only source store and one shared session lease for the whole replay."""
    def __init__(self, journal, source_root, session_id, callback, policy, stop_event, *,
                 append_batch_samples=1600, clock=time.perf_counter, spatial=None):
        self.append_batch_samples = validate_batch_samples(append_batch_samples)
        self.clock = clock
        self.journal, self.callback, self.policy, self.stop_event = journal, callback, policy, stop_event
        self.spatial = spatial
        self.store = SessionStore(source_root, read_only=True)
        self.session_id = session_id
        self.lease = None
        self.thread = None
        self.done = threading.Event()
        self.sent = 0
        self.error = None
        self.index = journal.spool.directory/'work'/'saved-replay-index.jsonl'
        self.index_bytes = 0
        self.index_limit = min(8*1024**2, journal.spool.spec.get('metadata_reserve_bytes', 8*1024**2)//4)
        try:
            self.lease = self.store._session_lease(session_id, shared=True)
            self.metadata = self.store.read(session_id)
            self.frames = self.metadata['processed_samples']
            if self.metadata['status'] != 'kept' or self.metadata['spec']['sample_rate'] != 16000:
                raise ValueError('Replay requires a kept mono16k float32 recording')
            if not 0 < self.frames <= policy.maximum_samples():
                raise ValueError('Complete kept recording exceeds this explicit duration policy')
            self.metadata_sha256 = hashlib.sha256(encoded(self.metadata)).hexdigest()
            if self.spatial is not None and (self.spatial.session_id != self.session_id or
                    Path(self.spatial.store.root).resolve() != Path(self.store.root).resolve() or
                    self.spatial.frames != self.frames or
                    self.spatial.metadata_sha256 != self.metadata_sha256 or self.spatial.closed):
                raise ValueError('Recorded spatial and audio session/metadata/sample pins differ')
            self._prepare_index()
        except BaseException:
            self._release()
            raise

    def _release(self):
        if self.lease is not None:
            self.lease.close(); self.lease = None
        self.store.close()

    def _prepare_index(self):
        cursor = 0
        after = -1
        overall = hashlib.sha256()
        manifest = hashlib.sha256()
        with self.index.open('xb') as output:
            while True:
                page = self.store.processed_segment_page(self.session_id, after=after)
                if not page:
                    break
                for row in page:
                    if row['idx'] != after+1 or row['start_sample'] != cursor or row['samples'] <= 0:
                        raise StorageError('Kept recording segment timeline gap')
                    path = self.store._audio_path(self.session_id, row['data_name'])
                    before = identity(path)
                    if before['bytes'] != row['samples']*4:
                        raise StorageError('Kept recording segment extent differs')
                    digest = hashlib.sha256()
                    with path.open('rb') as source:
                        while data := source.read(65536):
                            digest.update(data); overall.update(data)
                    if identity(path) != before:
                        raise StorageError('Kept segment changed while preparing replay')
                    pin = dict(row, identity=before, sha256=digest.hexdigest())
                    raw = encoded(pin)+b'\n'
                    if len(raw) > 4096 or self.index_bytes+len(raw) > self.index_limit:
                        raise StorageError('Replay segment index exceeds its metadata allocation')
                    self.journal.spool.store._capacity(len(raw))
                    if output.write(raw) != len(raw):
                        raise OSError('Short replay index write')
                    manifest.update(raw); self.index_bytes += len(raw)
                    cursor += row['samples']; after = row['idx']
            output.flush(); os.fsync(output.fileno())
        if cursor != self.frames:
            raise StorageError('Kept recording authoritative sample count differs')
        self.source_sha256 = overall.hexdigest()
        self.index_sha256 = manifest.hexdigest()

    def start(self):
        if self.thread is not None or self.lease is None:
            raise RuntimeError('Kept recording source cannot be restarted')
        self.thread = threading.Thread(target=self._run, name='kept-recording-replay', daemon=True)
        self.thread.start()

    def _run(self):
        origin = self.clock()
        metrics = SavedSourceMetrics(origin, self.callback, self.append_batch_samples, clock=self.clock)
        overall = hashlib.sha256()
        manifest = hashlib.sha256()
        try:
            import numpy as np
            if hashlib.sha256(encoded(self.store.read(self.session_id))).hexdigest() != self.metadata_sha256:
                raise StorageError('Kept recording metadata changed before replay')
            self.callback('source_started', dict(mode='file', source_kind='kept_recording',
                source_session_id=self.session_id, source_store_id=self.store.owner['store_id'],
                source_epoch_monotonic_sec=origin, source_frames=self.frames,
                source_sha256=self.source_sha256, segment_manifest_sha256=self.index_sha256,
                physical_microphone=False, motion_applied=False, current_motion_used=False,
                recorded_spatial_replay=self.spatial is not None,
                recorded_spatial_metadata_sha256=self.spatial.metadata_sha256 if self.spatial is not None else None,
                gain=1.0, append_batch_samples=self.append_batch_samples))
            with self.index.open('rb') as index:
                while not self.stop_event.is_set():
                    line = index.readline(4097)
                    if not line:
                        break
                    if len(line)>4096 or not line.endswith(b'\n'):
                        raise StorageError('Replay index record bound')
                    manifest.update(line)
                    row = json.loads(line)
                    if row['start_sample'] != self.sent:
                        raise StorageError('Replay source cursor is non-contiguous')
                    path = self.store._audio_path(self.session_id, row['data_name'])
                    if identity(path) != row['identity']:
                        raise StorageError('Pinned kept segment changed before playback')
                    digest = hashlib.sha256()
                    remaining = row['samples']
                    with path.open('rb') as stream:
                        while remaining and not self.stop_event.is_set():
                            count = min(self.append_batch_samples, remaining)
                            raw = stream.read(count*4)
                            if len(raw) != count*4:
                                raise StorageError('Kept segment truncated during replay')
                            end = self.sent+count
                            if self.stop_event.wait(max(0., origin+end/16000-self.clock())):
                                break
                            if self.spatial is not None:
                                # Publish historical callbacks/poses/beam receipts
                                # before this exact audio becomes model-readable.
                                self.spatial.advance_samples(end)
                            metrics.append(self.journal, np.frombuffer(raw, dtype='<f4').copy(), end)
                            digest.update(raw); overall.update(raw)
                            self.sent = end; remaining -= count
                            metrics.progress()
                    if self.stop_event.is_set():
                        break
                    if digest.hexdigest() != row['sha256'] or identity(path) != row['identity']:
                        raise StorageError('Kept segment changed during playback')
            if not self.stop_event.is_set() and (self.sent != self.frames or overall.hexdigest() != self.source_sha256 or manifest.hexdigest() != self.index_sha256):
                raise StorageError('Complete replay source/hash boundary differs')
        except BaseException as error:
            self.error = repr(error)
            try:
                self.callback('fatal', dict(reason=self.error))
            except BaseException:
                pass
        finally:
            try:
                self.journal.finish(self.error)
                self.callback('source_stopped', dict(sent_samples=self.sent, source_frames=self.frames,
                    source_session_id=self.session_id, physical_microphone=False,
                    complete_recording=self.sent==self.frames and self.error is None, error=self.error,
                    recorded_spatial_replay=self.spatial is not None, current_motion_used=False,
                    saved_source_metrics=metrics.snapshot()))
            finally:
                try:
                    self._release()
                finally:
                    self.done.set()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(5)
            if self.thread.is_alive():
                raise RuntimeError('Kept recording reader remains owned')
        elif self.thread is None:
            self._release(); self.done.set()

    def wait(self, timeout=None):
        return self.done.wait(timeout)
