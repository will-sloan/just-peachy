"""CPU14-only, synthetic, isolated storage tests; see README_STORAGE.md."""
import io
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import wave
import zipfile

from storage import (ActiveSessionError, CapacityError, SessionStore,
                     StorageError, StoragePolicy, UnsafePathError)


CPU14_BOOTSTRAP = """import os
if os.name == 'nt':
 import ctypes
 k=ctypes.windll.kernel32
 k.GetCurrentProcess.restype=ctypes.c_void_p
 k.SetProcessAffinityMask.argtypes=(ctypes.c_void_p,ctypes.c_size_t)
 assert k.SetProcessAffinityMask(k.GetCurrentProcess(),16384)
else:
 os.sched_setaffinity(0,{14})
"""


def f32(*values):
    return struct.pack("<" + "f" * len(values), *values)


class StorageTests(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get("LIVE_STORAGE_TEST_ROOT")
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="storage-test-", dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        # Tiny reserve is explicit test-only policy, never the deployment default.
        self.policy = StoragePolicy(reserve_bytes=0, reserve_fraction=0,
                                    segment_samples=4, max_append_bytes=128)
        self.store = SessionStore(self.base / "store", self.policy)
        self.addCleanup(self.store.close)

    def spec(self, **updates):
        result = {"sample_rate": 16000, "duration_seconds": 0.01}
        result.update(updates)
        return result

    def raw_spec(self):
        return self.spec(mode="raw_processed", raw={"sample_rate": 16000,
            "channels": 4, "sample_width_bytes": 4, "encoding": "PCM_S32LE",
            "qualification": {"qualified": True, "evidence": "synthetic-format-only"}})

    def kept(self, values=(0.0, 0.25, -0.5, 0.9, 1.0)):
        spool = self.store.begin(self.spec())
        spool.append_processed(0, f32(*values))
        spool.stop(len(values))
        spool.keep()
        return spool.session_id

    def child(self, body, *args):
        return subprocess.run([sys.executable, "-c", CPU14_BOOTSTRAP + body, *map(str, args)],
                              cwd=Path(__file__).parent, capture_output=True, text=True, timeout=20)

    def test_many_sessions_restart_pagination_and_selected_export(self):
        ids = [self.kept((index / 32,)) for index in range(31)]
        self.assertEqual(len(set(ids)), 31)
        reopened = SessionStore(self.store.root, self.policy)
        # Startup must not enumerate session directories or load their audio.
        with mock.patch.object(Path, "iterdir", side_effect=AssertionError("startup scan")):
            SessionStore(self.store.root, self.policy)
        seen, cursor = [], None
        while True:
            page = reopened.history(limit=7, before=cursor)
            self.assertLessEqual(len(page["items"]), 7)
            seen.extend(item["session_id"] for item in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        self.assertEqual(seen, ids[::-1])
        destination = self.base / "selected.zip"
        reopened.export([ids[0], ids[30]], destination)
        with zipfile.ZipFile(destination) as archive:
            prefixes = {name.split("/")[0] for name in archive.namelist()}
            self.assertEqual(prefixes, {ids[0], ids[30]})
            self.assertEqual(archive.read(ids[30] + "/processed-00000000.f32"), f32(30 / 32))
            metadata = json.loads(archive.read(ids[30] + "/session.json"))
            self.assertEqual(metadata["processed_samples"], 1)
        with self.assertRaises(UnsafePathError):
            reopened.export([ids[0]], destination)

    def test_exact_active_old_offset_reads_and_replay(self):
        data = f32(-2.0, -1.0, -0.5, 0.0, 0.125, 0.5, 1.0, 2.0, 0.75)
        spool = self.store.begin(self.spec())
        spool.append_processed(0, data[:24])
        self.assertEqual(spool.read_processed(1, 5), data[4:24])
        spool.append_processed(6, data[24:])
        self.assertEqual(spool.read_processed(2, 6), data[8:32])
        with self.assertRaises(StorageError):
            spool.stop(8)
        receipt = spool.stop(9)
        self.assertEqual(receipt["processed_samples"], 9)
        self.assertEqual(receipt["duration_seconds"], 9 / 16000)
        with self.assertRaises(StorageError):
            spool.append_processed(9, f32(0))
        spool.keep()
        self.assertEqual(b"".join(block for _, block in self.store.iter_processed(spool.session_id, 3)), data)
        pcm = []
        for segment in self.store._segments(spool.session_id, "processed"):
            with wave.open(str(self.store._audio_path(spool.session_id, segment["replay_name"])), "rb") as wav:
                self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (1, 2, 16000))
                pcm.extend(struct.unpack("<" + "h" * wav.getnframes(), wav.readframes(wav.getnframes())))
        self.assertEqual(pcm, [-32768, -32768, -16384, 0, 4096, 16384, 32767, 32767, 24576])

    def test_qualification_and_raw_retention_choices(self):
        with self.assertRaises(ValueError):
            self.store.begin(self.spec(mode="raw_processed", raw={"channels": 4}))
        spool = self.store.begin(self.raw_spec())
        spool.append_processed(0, f32(0, 0, 0, 0, 0))
        raw = bytes(range(80))
        spool.append_raw(0, raw)
        spool.stop(5)
        metadata = spool.keep(include_raw=True)
        self.assertTrue(metadata["include_raw"])
        self.assertEqual(metadata["spec"]["raw"]["sample_rate"], 16000)
        self.assertEqual(metadata["raw_samples"], 5)
        spool.keep(include_raw=False)
        self.assertEqual(list(self.store._segments(spool.session_id, "raw")), [])
        with self.assertRaises(StorageError):
            spool.keep(include_raw=True)

    def test_raw_mismatched_duration_cannot_be_retained(self):
        spool = self.store.begin(self.raw_spec())
        spool.append_processed(0, f32(0, 0))
        spool.append_raw(0, bytes(16))
        spool.stop(2)
        with self.assertRaises(StorageError):
            spool.keep(include_raw=True)
        spool.keep(include_raw=False)

    def test_capacity_admission_runtime_exhaustion_and_allocation(self):
        self.assertEqual(StoragePolicy().reserve_bytes, 5 * 1024 ** 3)
        raw_bytes = self.policy.estimate_bytes(self.raw_spec())
        plain_bytes = self.policy.estimate_bytes(self.spec())
        self.assertGreater(raw_bytes, plain_bytes)
        usage = type("Usage", (), {"total": 10 ** 9, "free": 1024})()
        with mock.patch("storage.shutil.disk_usage", return_value=usage):
            with self.assertRaises(CapacityError):
                self.store.begin(self.spec())
        spool = self.store.begin(self.spec(duration_seconds=1 / 16000))
        spool.append_processed(0, f32(0))
        with self.assertRaises(CapacityError):
            spool.append_processed(1, f32(1))
        spool.cancel()
        spool = self.store.begin(self.spec())
        with mock.patch("storage.shutil.disk_usage", return_value=usage):
            with self.assertRaises(CapacityError):
                spool.append_processed(0, f32(0))
        self.assertEqual(self.store.read(spool.session_id)["status"], "failed")
        self.assertEqual(self.store.read(spool.session_id)["processed_samples"], 0)
        next_spool = self.store.begin(self.spec())
        next_spool.cancel()

    def test_failed_cancelled_and_discarded_have_receipts_without_slot_cost(self):
        ids = []
        for index in range(8):
            spool = self.store.begin(self.spec())
            ids.append(spool.session_id)
            spool.append_processed(0, f32(index))
            (spool.fail("synthetic failure") if index % 2 else spool.cancel())
        self.assertEqual(len(self.store.history()["items"]), 8)
        self.store.discard(ids[0])
        self.assertEqual(self.store.read(ids[0])["status"], "discarded")
        self.assertEqual(self.store.read(ids[1])["reason"], "synthetic failure")
        self.kept()

    def test_single_active_lease_across_processes_and_crash_recovery(self):
        spool = self.store.begin(self.spec())
        body = """from storage import *
import sys
s=SessionStore(sys.argv[1],StoragePolicy(reserve_bytes=0,reserve_fraction=0))
try:
 s.begin({'duration_seconds':.01})
except ActiveSessionError:
 print('blocked')
else:
 raise AssertionError('second active session admitted')
"""
        result = self.child(body, self.store.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "blocked")
        spool.cancel()
        body = """from storage import *
import struct,sys,os
s=SessionStore(sys.argv[1],StoragePolicy(reserve_bytes=0,reserve_fraction=0))
p=s.begin({'duration_seconds':.01})
p.append_processed(0,struct.pack('<ff',.25,.5))
open(sys.argv[2],'w').write(p.session_id)
os._exit(0)
"""
        id_file = self.base / "crashed-id.txt"
        result = self.child(body, self.store.root, id_file)
        self.assertEqual(result.returncode, 0, result.stderr)
        crashed = id_file.read_text()
        restarted = self.store.begin(self.spec())
        self.assertEqual(self.store.read(crashed)["status"], "failed")
        self.assertEqual(self.store.read(crashed)["processed_samples"], 2)
        self.assertIn("owner exited", self.store.read(crashed)["reason"])
        restarted.cancel()

    def test_fsync_failure_keeps_published_cursor_and_releases_lease(self):
        spool = self.store.begin(self.spec())
        spool.append_processed(0, f32(0))
        real_sync = os.fsync
        failed = False
        def one_failure(fd):
            nonlocal failed
            if not failed:
                failed = True
                raise OSError("injected fsync failure")
            return real_sync(fd)
        with mock.patch("storage.os.fsync", side_effect=one_failure):
            with self.assertRaises(OSError):
                spool.append_processed(1, f32(0.5))
        self.assertEqual(spool.processed_samples, 1)
        receipt = self.store.read(spool.session_id)
        self.assertEqual((receipt["status"], receipt["processed_samples"]), ("failed", 1))
        self.store.write_event(spool.session_id, "journal_fault", {"accepted_samples": 1})
        self.assertEqual(self.store.events(spool.session_id)["items"][0]["event_type"], "journal_fault")
        self.store.begin(self.spec()).cancel()

    def test_stop_publication_failure_retains_failed_receipt(self):
        spool = self.store.begin(self.spec())
        spool.append_processed(0, f32(0, 0))
        original = os.replace
        def fail_once(source, destination):
            if str(destination).endswith("processed-00000000.wav"):
                raise OSError("injected rename failure")
            return original(source, destination)
        with mock.patch("storage.os.replace", side_effect=fail_once):
            with self.assertRaises(OSError):
                spool.stop(2)
        self.assertEqual(self.store.read(spool.session_id)["status"], "failed")
        self.store.delete(spool.session_id, confirm=True)
        self.store.begin(self.spec()).cancel()

    def test_deliberate_delete_isolation_and_path_validation(self):
        keep_id, delete_id = self.kept(), self.kept()
        sentinel = self.store.root / "unrelated.txt"
        sentinel.write_text("preserve")
        with self.assertRaises(StorageError):
            self.store.delete(delete_id)
        child = self.store._session_dir(delete_id) / "unrelated.txt"
        child.write_text("preserve")
        with self.assertRaises(UnsafePathError):
            self.store.delete(delete_id, confirm=True)
        self.assertTrue((self.store._session_dir(delete_id) / "processed-00000000.f32").exists())
        child.unlink()
        self.store.delete(delete_id, confirm=True)
        self.assertEqual(sentinel.read_text(), "preserve")
        self.assertEqual(self.store.read(keep_id)["status"], "kept")
        for bad_id in ("../outside", "a" * 31, "C:\\outside", "/outside"):
            with self.assertRaises(UnsafePathError):
                self.store.delete(bad_id, confirm=True)
        unrelated = self.base / "not-a-store"
        unrelated.mkdir()
        (unrelated / "personal.txt").write_text("preserve")
        with self.assertRaises(UnsafePathError):
            SessionStore(unrelated, self.policy)

    def test_hardlink_cannot_escape_cleanup(self):
        session_id = self.kept()
        path = self.store._session_dir(session_id) / "processed-00000000.f32"
        path.unlink()
        external = self.base / "personal.f32"
        external.write_bytes(b"personal audio")
        os.link(external, path)
        with self.assertRaises(UnsafePathError):
            self.store.delete(session_id, confirm=True)
        self.assertEqual(external.read_bytes(), b"personal audio")

    def test_caption_history_is_paged_revised_and_exported(self):
        session_id = self.kept()
        for index in range(35):
            self.store.write_caption(session_id, "caption-" + str(index), index * 10,
                                     index * 10 + 9, "partial", "speaker-1", True,
                                     {"source": "synthetic"})
        final = self.store.write_caption(session_id, "caption-0", 0, 9, "final", "speaker-2", False,
                                        {"model": "synthetic"})
        self.assertEqual(final["revision"], 2)
        page = self.store.captions(session_id, limit=20)
        self.assertEqual(page["items"][0]["text"], "final")
        self.assertFalse(page["items"][0]["provisional"])
        self.assertEqual(len(self.store.captions(session_id, limit=20, after=page["next_cursor"])["items"]), 15)
        destination = self.base / "captions.zip"
        self.store.export([session_id], destination)
        with zipfile.ZipFile(destination) as archive:
            self.assertEqual(len(archive.read(session_id + "/captions.jsonl").splitlines()), 35)
            self.assertEqual(len(archive.read(session_id + "/events.jsonl").splitlines()), 36)

    def test_identical_caption_is_not_another_revision_or_ui_refresh(self):
        identifier=self.kept()
        first=self.store.write_caption(identifier,'stable',0,4,'unchanged','Speaker 1',False,{'source':'fixture'})
        tail=self.store.latest_captions(identifier)
        with self.store._db() as db:
            usage=db.execute('SELECT used_bytes FROM metadata_usage WHERE session_id=?',(identifier,)).fetchone()[0]
        for _ in range(40):
            self.assertEqual(self.store.write_caption(identifier,'stable',0,4,'unchanged','Speaker 1',False,{'source':'fixture'}),first)
        self.assertFalse(self.store.latest_captions(identifier,after_revision=tail['revision_cursor'])['changed'])
        self.assertEqual(len(self.store.events(identifier)['items']),1)
        with self.store._db() as db:
            self.assertEqual(db.execute('SELECT used_bytes FROM metadata_usage WHERE session_id=?',(identifier,)).fetchone()[0],usage)
        self.assertEqual(self.store.write_caption(identifier,'stable',0,4,'revised','Speaker 1',False,{'source':'fixture'})['revision'],2)

    def test_metadata_split_is_disjoint_and_absence_remains_legacy(self):
        from storage import metadata_limits
        for reserve in (0,1,5,17,960495616):
            for explicit,denominator in ((False,6),(True,4)):
                spec={'metadata_reserve_bytes':reserve}
                if explicit:spec['metadata_split']='text3_sqlite1_v1'
                limits=metadata_limits(spec,1048576)
                self.assertEqual(limits['sqlite_bytes'],1048576+reserve//denominator)
                self.assertEqual(sum(limits.values()),reserve+1048576)
        for invalid in (None,'',False,[],{},'text4_sqlite1_v1'):
            with self.assertRaises(ValueError):self.store.begin(self.spec(metadata_split=invalid))

    def test_new_metadata_split_preserves_prior_persisted_ledger(self):
        from storage import metadata_limits
        reserve=120000
        old=self.store.begin(self.spec(metadata_reserve_bytes=reserve));old.stop(0)
        self.store.write_event(old.session_id,'fixture',{'v':'legacy'})
        spec=self.spec(metadata_reserve_bytes=reserve,metadata_split='text3_sqlite1_v1')
        new=self.store.begin(spec);new.stop(0)
        self.store.write_event(new.session_id,'fixture',{'v':'new'})
        with self.store._db() as db:
            old_limit=db.execute('SELECT limit_bytes FROM metadata_usage WHERE session_id=?',(old.session_id,)).fetchone()[0]
            new_limit=db.execute('SELECT limit_bytes FROM metadata_usage WHERE session_id=?',(new.session_id,)).fetchone()[0]
            self.assertEqual(new_limit-old_limit,reserve//4-reserve//6)
            # Even a newer spec/policy cannot silently increase a persisted limit.
            db.execute('UPDATE sessions SET spec=? WHERE id=?',(json.dumps(spec),old.session_id))
        self.store.write_event(old.session_id,'fixture',{'v':'later'})
        with self.store._db() as db:
            self.assertEqual(db.execute('SELECT limit_bytes FROM metadata_usage WHERE session_id=?',(old.session_id,)).fetchone()[0],old_limit)
            db.execute('DELETE FROM metadata_usage WHERE session_id=?',(new.session_id,))
        self.store.write_event(new.session_id,'fixture',{'v':'migrated once'})
        with self.store._db() as db:
            self.assertEqual(db.execute('SELECT limit_bytes FROM metadata_usage WHERE session_id=?',(new.session_id,)).fetchone()[0],metadata_limits(spec,self.policy.metadata_allowance_bytes)['sqlite_bytes'])

    def test_metadata_allocation_persists_and_failure_is_transactional_per_session(self):
        policy=StoragePolicy(reserve_bytes=0,reserve_fraction=0,metadata_allowance_bytes=32768)
        store=SessionStore(self.base/'bounded-metadata',policy);self.addCleanup(store.close)
        spool=store.begin(self.spec());spool.stop(0);identifier=spool.session_id
        payload={'value':''.join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(80))}
        count=0
        while True:
            try:store.write_event(identifier,'fixture',payload);count+=1
            except CapacityError:break
        self.assertGreater(count,0);self.assertLess(count,6)
        reopened=SessionStore(store.root,policy);self.addCleanup(reopened.close)
        with self.assertRaises(CapacityError):reopened.write_event(identifier,'fixture',payload)
        self.assertEqual(len(reopened.events(identifier)['items']),count)
        path=spool.directory/'work'/'close.json';path.parent.mkdir();path.write_text('{"closed":true}')
        reopened.register_artifact(identifier,'work/close.json')
        later=reopened.begin(self.spec());later.stop(0)
        reopened.write_event(later.session_id,'fixture',{'value':'other session remains usable'})
        self.assertEqual(len(reopened.events(later.session_id)['items']),1)

    def test_paused_old_session_iterators_release_sqlite_for_another_writer(self):
        import sqlite3
        old=self.kept()
        # More than a cursor page prevents an old lazy cursor from completing
        # before this paused-yield lock check.
        with self.store._db() as db:
            for index in range(2,40):
                db.execute('INSERT INTO segments VALUES(?,?,?,?,?,?,?)',(old,'processed',index,index*4,4,'processed-%08d.f32'%index,None))
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(old,'work/%03d.json'%index,'fixture',1))
        for iterator in (self.store._segments(old),self.store._artifacts(old)):
            next(iterator)
            db=sqlite3.connect(self.store.db_path,timeout=0)
            try:
                with db:db.execute('UPDATE sessions SET updated=updated+1 WHERE id=?',(old,))
            finally:db.close()
            iterator.close()

    def test_export_metadata_bound_and_discard_preserve_source_and_other_sessions(self):
        original=self.kept();other=self.kept()
        before=b''.join(raw for _,raw in self.store.iter_processed(original,block_samples=4))
        replay=self.store.begin(self.spec(source_session_id=original))
        replay.append_processed(0,f32(.25));replay.stop(1)
        self.store.write_caption(replay.session_id,'c',0,1,'retained transcript')
        replay.discard()
        self.assertEqual(b''.join(raw for _,raw in self.store.iter_processed(original,block_samples=4)),before)
        self.assertEqual(self.store.read(other)['status'],'kept')
        self.assertEqual(self.store.captions(replay.session_id)['items'][0]['text'],'retained transcript')
        self.assertFalse(any(replay.directory.glob('processed-*')))
        limited=SessionStore(self.store.root,StoragePolicy(reserve_bytes=0,reserve_fraction=0,max_export_entries=5))
        destination=self.base/'too-many-entries.zip'
        with self.assertRaisesRegex(CapacityError,'smaller batch'):limited.export([original],destination)
        self.assertFalse(destination.exists())
        self.assertEqual(b''.join(raw for _,raw in self.store.iter_processed(original,block_samples=4)),before)

    def test_lossless_event_codec_exports_original_fields_and_rejects_bad_expansion(self):
        from storage import _pack_event,_unpack_event
        import zlib
        identifier=self.kept()
        original={'clocks':[dict(start_sample=i*160,end_sample=(i+1)*160,source='exact unchanged callback') for i in range(100)]}
        self.store.write_event(identifier,'source_fixture',original)
        with self.store._db() as db:
            stored=dict(db.execute('SELECT * FROM events WHERE session_id=?',(identifier,)).fetchone())
        self.assertEqual(stored['payload_encoding'],'zlib-json-v1')
        self.assertEqual(self.store.events(identifier)['items'][0]['payload'],original)
        destination=self.base/'lossless-events.zip';self.store.export([identifier],destination)
        with zipfile.ZipFile(destination) as archive:
            recovered=json.loads(archive.read(identifier+'/events.jsonl'))
            self.assertEqual(recovered['payload'],original)
            self.assertNotIn('payload_encoding',recovered)
        for change in (dict(payload=stored['payload']+b'trailing'),dict(payload_bytes=1),
                       dict(payload_sha256='0'*64),dict(payload_sha256=None),
                       dict(payload=zlib.compress(b'x'*65537),payload_bytes=65536)):
            with self.subTest(change=list(change)),self.assertRaises(StorageError):
                _unpack_event(dict(stored,**change))

    def test_corrupt_index_name_rejected_without_touching_outside(self):
        session_id = self.kept()
        outside = self.base / "outside.f32"
        outside.write_bytes(b"keep")
        with self.store._db() as db:
            db.execute("UPDATE segments SET data_name=? WHERE session_id=? AND kind='processed' AND idx=0",
                       (str(outside), session_id))
        with self.assertRaises(UnsafePathError):
            self.store.export([session_id], self.base / "bad.zip")
        with self.assertRaises(UnsafePathError):
            self.store.delete(session_id, confirm=True)
        self.assertEqual(outside.read_bytes(), b"keep")

    def test_registered_artifacts_export_cleanup_and_metadata_allocation(self):
        session_id = self.kept()
        relative = "work/native/result.json"
        artifact = self.store._session_dir(session_id) / relative
        artifact.parent.mkdir(parents=True)
        artifact.write_text('{"synthetic":true}')
        self.store.register_artifact(session_id, relative)
        self.assertEqual(self.policy.estimate_bytes(self.spec(metadata_reserve_bytes=12345)) - self.policy.estimate_bytes(self.spec()), 12345)
        destination = self.base / "native-metadata.zip"
        self.store.export([session_id], destination)
        with zipfile.ZipFile(destination) as archive:
            self.assertEqual(archive.read(session_id + "/" + relative), b'{"synthetic":true}')
        sentinel = artifact.parent / "unregistered.txt"
        sentinel.write_text("preserve")
        with self.assertRaises(UnsafePathError):
            self.store.delete(session_id, confirm=True)
        self.assertTrue(artifact.exists())
        sentinel.unlink()
        self.store.delete(session_id, confirm=True)
        self.assertFalse(artifact.exists())


if __name__ == "__main__":
    unittest.main()
