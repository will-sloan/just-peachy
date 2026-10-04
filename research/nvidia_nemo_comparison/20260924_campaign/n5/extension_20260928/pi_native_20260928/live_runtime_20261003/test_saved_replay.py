"""Synthetic complete-session replay/isolation checks; README_SAVED_REPLAY.md."""
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import threading
import unittest

from audio_journal import DiskAudioJournal
from profiles import SessionPolicy
from saved_replay import SavedSessionSource
from storage import SessionStore, StoragePolicy, ActiveSessionError, StorageError


class ReplayTests(unittest.TestCase):
    def setUp(self):
        parent=Path(os.environ['LIVE_REPLAY_TEST_ROOT']);parent.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=SessionStore(self.root/'store',StoragePolicy(reserve_bytes=0,reserve_fraction=0,segment_samples=351))
        self.addCleanup(self.store.close)
        self.original=self.store.begin(dict(duration_seconds=1))
        self.payload=b''.join(struct.pack('<f',(index-600)/4096) for index in range(1120))
        self.original.append_processed(0,self.payload);self.original.stop(1120);self.original.keep()
        self.source_id=self.original.session_id
        self.original_metadata=self.store.read(self.source_id)
        self.spool=self.store.begin(dict(duration_seconds=1,sample_rate=16000,metadata_reserve_bytes=1024**2))
        (self.spool.directory/'work').mkdir()
        self.events=[];self.stop_event=threading.Event()
        self.journal=DiskAudioJournal(self.spool,policy=self.spool.spec,fault_receipt=self.events.append)

    def source(self, callback=None):
        source=SavedSessionSource(self.journal,self.store.root,self.source_id,
            callback or (lambda kind,value:self.events.append((kind,value))),SessionPolicy(maximum_session_seconds=1),self.stop_event)
        self.addCleanup(source.stop)
        return source

    def test_every_segment_exact_float32_with_concurrent_output_metadata(self):
        count=[]
        def observer(start,array):
            count.append(len(array))
            self.store.write_caption(self.spool.session_id,str(start),start,start+len(array),'synthetic',None,False,{})
        self.journal.observer=observer
        source=self.source();source.start();self.assertTrue(source.wait(4))
        self.assertIsNone(source.error)
        self.assertEqual(source.sent,1120)
        self.assertLessEqual(max(count),1600)
        self.assertEqual(self.spool.read_processed(0,1120),self.payload)
        self.assertEqual(source.source_sha256,hashlib.sha256(self.payload).hexdigest())
        self.assertEqual(len(source.index.read_text().splitlines()),4)
        self.assertEqual(self.store.read(self.source_id),self.original_metadata)
        self.assertEqual([v for k,v in self.events if k=='source_stopped'][0]['complete_recording'],True)

    def test_shared_read_lease_prevents_delete_and_readonly_never_mutates(self):
        source=self.source()
        reader=SessionStore(self.store.root,read_only=True)
        with reader._session_lease(self.source_id,shared=True):
            self.assertEqual(reader.read(self.source_id)['status'],'kept')
        with self.assertRaises(ActiveSessionError):self.store.delete(self.source_id,confirm=True)
        with self.assertRaises(StorageError):reader.delete(self.source_id,confirm=True)
        with self.assertRaises(StorageError):reader.begin(dict(duration_seconds=1))
        source.stop()
        self.store.delete(self.source_id,confirm=True)

    def test_changed_segment_rejected_before_its_audio_is_accepted(self):
        source=self.source()
        path=self.store._audio_path(self.source_id,'processed-00000000.f32')
        with path.open('r+b') as stream:stream.write(struct.pack('<f',.5));stream.flush();os.fsync(stream.fileno())
        source.start();self.assertTrue(source.wait(4))
        self.assertIsNotNone(source.error)
        self.assertEqual(self.spool.processed_samples,0)
        self.assertIsNotNone(self.journal.fatal_error)

    def test_stop_releases_whole_recording_without_claiming_full_replay(self):
        def callback(kind,row):
            self.events.append((kind,row))
            if kind=='source_started':self.stop_event.set()
        source=self.source(callback);source.start();self.assertTrue(source.wait(4))
        self.assertEqual(source.sent,0)
        stopped=next(row for kind,row in self.events if kind=='source_stopped')
        self.assertFalse(stopped['complete_recording'])
        with self.store._session_lease(self.source_id):pass

    def test_gap_and_unkept_recordings_fail_closed(self):
        with self.store._db() as db:
            db.execute("UPDATE segments SET start_sample=start_sample+1 WHERE session_id=? AND idx=1 AND kind='processed'",(self.source_id,))
        with self.assertRaisesRegex(StorageError,'timeline gap'):self.source()
        with self.store._session_lease(self.source_id):pass


if __name__=='__main__':unittest.main()
