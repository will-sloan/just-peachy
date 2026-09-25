"""Temporary-only storage recovery/integrity tests; README_EVIDENCE_STORE.md."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import psutil

from common import bind, freeze, load
from evidence_reader import ControllerEvidence
from evidence_store import EvidenceStore, GIB, REQUIRED_CHECKS, initialize


class EvidenceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.reserves = {'C:/': 50*GIB, 'G:/': 75*GIB} if os.name == 'nt' else {str(self.base): 0}
        self.root = initialize(self.base/'new-run', max_bytes=128*2**20,
            cell_reserve_bytes=16*2**20, minimum_free=self.reserves)
        self.store = EvidenceStore(self.root)

    def fixture(self, store, job='fixture_O0'):
        attempt = store.reserve(job, 'a'*64)
        snapshot = attempt/'FINAL_SNAPSHOT.json'
        events = attempt/'RUNTIME_EVENTS.jsonl'
        freeze(snapshot, dict(rows=[dict(raw_asr_text='one two', track_id='track-1')]))
        events.write_text(json.dumps(dict(event_type='fixture', time=0.125))+'\n', encoding='utf-8')
        binary = attempt/'journal.pcm'
        binary.write_bytes(bytes(range(256))*16)
        result = dict(status='COMPLETE', checks=dict.fromkeys(REQUIRED_CHECKS, True),
            attempt=str(attempt), job_id=job, cache_key='a'*64,
            evidence=[bind(snapshot), bind(events), bind(binary)])
        path = attempt/'RESULT.json'
        freeze(path, result)
        freeze(attempt.parent/'CHECKPOINT.json', dict(status='COMPLETE', cache_key='a'*64, result=bind(path)))
        return path, result

    def test_roundtrip_binary_json_and_index_with_next_cell(self):
        with self.store.writer() as store:
            path, result = self.fixture(store)
            original = {row['path']: Path(row['path']).read_bytes() for row in result['evidence']}
            result_binding = bind(path)
            checkpoint_binding = bind(path.parent.parent/'CHECKPOINT.json')
            process = psutil.Process()
            allocation = process.cpu_affinity(), process.nice()
            receipt = store.compact(path)
            self.assertEqual((process.cpu_affinity(), process.nice()), allocation)
            self.assertEqual(bind(path), result_binding)
            self.assertEqual(bind(path.parent.parent/'CHECKPOINT.json'), checkpoint_binding)
            self.assertTrue(all(not Path(p).exists() for p in original))
            index = load(self.root/'ARCHIVE_INDEX.json')['archives'][result_binding['sha256']]
            self.assertEqual(index['archive'], receipt['archive'])
            with ControllerEvidence(result, index['archive']) as reader:
                self.assertEqual(original, {p: reader.read_bytes(p) for p in original})
            self.assertEqual(store.compact(path), receipt)  # idempotent completed resume
            self.assertTrue(store.reserve('second_O1', 'b'*64).is_dir())

    def test_interrupted_removal_reverifies_archive_and_resumes(self):
        with self.store.writer() as store:
            path, result = self.fixture(store)
            remove = store._remove_verified
            count = 0
            def interrupted(row):
                nonlocal count
                count += 1
                if count == 2:
                    raise OSError('simulated interruption')
                remove(row)
            with patch.object(store, '_remove_verified', side_effect=interrupted):
                with self.assertRaisesRegex(OSError, 'interruption'):
                    store.compact(path)
            self.assertFalse(Path(result['evidence'][0]['path']).exists())
            self.assertTrue(Path(result['evidence'][1]['path']).exists())
            self.assertTrue((self.root/'ARCHIVE_INDEX.json').exists())
        # A new process-equivalent owner can recover from the durable intent.
        with EvidenceStore(self.root).writer() as resumed:
            self.assertEqual(resumed.compact(path)['status'], 'ARCHIVED_COPIES_RELEASED')

    def test_corrupt_archive_after_interruption_preserves_remaining_copies(self):
        with self.store.writer() as store:
            path, result = self.fixture(store)
            with patch.object(store, '_remove_verified', side_effect=OSError('stop')):
                with self.assertRaises(OSError):
                    store.compact(path)
            archive = Path(load(path.parent.parent/'STORE_INTENT.json')['archive']['path'])
            with archive.open('ab') as stream:
                stream.write(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'binding changed'):
                store.compact(path)
            self.assertTrue(all(Path(row['path']).exists() for row in result['evidence']))

    def test_changed_source_before_archive_preserves_all_files(self):
        with self.store.writer() as store:
            path, result = self.fixture(store)
            Path(result['evidence'][0]['path']).write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Binding changed'):
                store.compact(path)
            self.assertTrue(all(Path(row['path']).exists() for row in result['evidence']))
            self.assertFalse((self.root/'ARCHIVE_INDEX.json').exists())

    def test_unbound_or_missing_files_are_not_silently_discarded(self):
        with self.store.writer() as store:
            path, result = self.fixture(store)
            extra = path.parent/'unbound.bin'
            extra.write_bytes(b'extra')
            with self.assertRaisesRegex(ValueError, 'Unbound'):
                store.compact(path)
            extra.unlink()  # only this temporary fixture, never campaign evidence
            Path(result['evidence'][0]['path']).unlink()
            with self.assertRaisesRegex(ValueError, 'Missing evidence'):
                store.compact(path)
            self.assertTrue(Path(result['evidence'][1]['path']).exists())

    def test_cannot_adopt_historical_directory_or_outside_result(self):
        with self.assertRaises(FileExistsError):
            initialize(self.root, max_bytes=128*2**20, cell_reserve_bytes=16*2**20,
                       minimum_free=self.reserves)
        outside = self.base/'historical'/'attempt'/'RESULT.json'
        freeze(outside, dict(status='COMPLETE'))
        with self.store.writer() as store:
            with self.assertRaisesRegex(ValueError, 'escapes'):
                store.compact(outside)
        self.assertEqual(load(outside), dict(status='COMPLETE'))

    def test_single_writer_and_no_second_unresolved_cell(self):
        with self.assertRaisesRegex(RuntimeError, 'writer lock'):
            self.store.reserve('fixture', 'a'*64)
        with self.store.writer() as store:
            other = EvidenceStore(self.root)
            with self.assertRaises(BlockingIOError):
                with other.writer():
                    self.fail('duplicate writer')
            store.reserve('fixture', 'a'*64)
            with self.assertRaisesRegex(RuntimeError, 'Prior attempt'):
                store.reserve('another', 'b'*64)

    def test_disk_or_store_budget_exhaustion_stops_before_reservation(self):
        with self.store.writer() as store:
            with self.assertRaisesRegex(RuntimeError, 'allocation exhausted'):
                store.guard(129*2**20)
            fake = type('Usage', (), dict(free=0))()
            with patch('evidence_store.shutil.disk_usage', return_value=fake):
                with self.assertRaisesRegex(RuntimeError, 'Disk reserve'):
                    store.reserve('fixture', 'a'*64)
            self.assertFalse((self.root/'cells').exists())

    def test_failed_or_unclosed_result_preserves_attempt(self):
        with self.store.writer() as store:
            path, result = self.fixture(store)
            result['checks']['workers_closed'] = False
            path.write_text(json.dumps(result), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'closed-worker'):
                store.compact(path)
            self.assertTrue(all(Path(row['path']).exists() for row in result['evidence']))

    def test_closed_failed_attempt_retained_and_counts_against_budget(self):
        with self.store.writer() as store:
            path, result = self.fixture(store)
            result['status'] = 'FAILED'
            result['checks']['all_samples'] = False
            path.write_text(json.dumps(result), encoding='utf-8')
            checkpoint = path.parent.parent/'CHECKPOINT.json'
            checkpoint.write_text(json.dumps(dict(status='FAILED', cache_key='a'*64,
                result=bind(path))), encoding='utf-8')
            receipt = store.retain_failed(path)
            self.assertEqual(receipt['released_bytes'], 0)
            self.assertGreaterEqual(store.guard(), receipt['retained_bytes'])
            self.assertTrue(all(Path(row['path']).exists() for row in result['evidence']))
            self.assertTrue(store.reserve('next_O1', 'b'*64).is_dir())
            self.assertFalse((self.root/'ARCHIVE_INDEX.json').exists())

    def test_unbound_binary_after_intent_blocks_further_removal(self):
        with self.store.writer() as store:
            path, result = self.fixture(store)
            with patch.object(store, '_remove_verified', side_effect=OSError('stop')):
                with self.assertRaises(OSError):
                    store.compact(path)
            (path.parent/'late.bin').write_bytes(b'unexpected producer output')
            with self.assertRaisesRegex(ValueError, 'Unbound'):
                store.compact(path)
            self.assertTrue(all(Path(row['path']).exists() for row in result['evidence']))

    def test_hard_links_and_traversal_are_refused(self):
        with self.store.writer() as store:
            with self.assertRaisesRegex(ValueError, 'Invalid job'):
                store.reserve('../escape', 'a'*64)
            path, result = self.fixture(store)
            target = Path(result['evidence'][0]['path'])
            alias = self.base/'other-link.json'
            os.link(target, alias)
            with self.assertRaisesRegex(ValueError, 'Hard-linked'):
                store.compact(path)
            self.assertTrue(target.exists())
            self.assertTrue(alias.exists())


if __name__ == '__main__':
    unittest.main()
