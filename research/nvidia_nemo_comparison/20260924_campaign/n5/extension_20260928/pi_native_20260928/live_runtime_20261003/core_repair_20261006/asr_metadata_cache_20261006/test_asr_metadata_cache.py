"""Synthetic cache/SQL equivalence checks; README_ASR_METADATA_CACHE.md."""
import ast
from collections import OrderedDict
from contextlib import closing, contextmanager
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from asr_metadata_cache import CACHE_BYTES, CACHE_ENTRIES, FIXED_OVERHEAD, MISS, MetadataCache
from asr_segment_runtime import SegmentLedger
from storage import StoragePolicy


REFERENCE = Path(os.environ['JP_ASR_LEDGER_REFERENCE'])
spec = importlib.util.spec_from_file_location('reference_segment_ledger', REFERENCE)
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
PROFITABILITY = {}


def metadata(parent='utterance:000001', group='spoken:000001', value=1):
    return dict(native_segment_id=parent, utterance_group_id=group,
        recognition_segment_final=False, utterance_final=False,
        endpoint_kind='none', leading_text_joiner=' ',
        nested=dict(tokens=[value, '\u00e9', -0.0]))


class Checks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Host G: total extent makes production's fractional reserve unsuitable
        # for synthetic fixtures. Preserve an actual 5 GiB reserve; the runner
        # independently admits at least 75 GiB free on G: before any imports.
        policy = StoragePolicy(reserve_bytes=5*1024**3, reserve_fraction=0.)
        self.ledger = SegmentLedger(self.root/'candidate.sqlite3', policy=policy)
        self.original = reference.SegmentLedger(self.root/'original.sqlite3', policy=policy)

    def record(self, seq=1, parent='utterance:000001', group='spoken:000001', value=1):
        row = metadata(parent, group, value)
        for ledger in (self.ledger, self.original):
            ledger.record(seq, 'synthetic words', row)
        return parent

    def equal(self, parent):
        actual, expected = self.ledger.metadata(parent), self.original.metadata(parent)
        self.assertEqual(actual, expected)
        self.assertEqual(json.dumps(actual, sort_keys=True), json.dumps(expected, sort_keys=True))
        return actual

    def test_repeated_reads_match_original_and_avoid_sql(self):
        parent = self.record()
        self.record(2, 'utterance:other', 'spoken:other')
        original_connection = self.ledger._connection
        count = dict(reads=0)
        @contextmanager
        def counted(*, write=False):
            count['reads'] += int(not write)
            with original_connection(write=write) as db:
                yield db
        with patch.object(self.ledger, '_connection', counted):
            for index in range(200):
                if index % 10 == 0:
                    # Real SQLite commits change the same file stamp. They must
                    # preserve the unchanged parent, rather than flush all hits.
                    self.record(2, 'utterance:other', 'spoken:other', value=index)
                self.equal(parent)
        self.assertEqual(count['reads'], 1)
        PROFITABILITY.update(repeated_reads=200, candidate_sql_reads=count['reads'],
            reference_sql_reads=200, unrelated_metadata_commits=20,
            exact_normalized_rows=True, throughput_measured=False)

    def test_returns_are_private_including_nested_values(self):
        parent = self.record()
        first = self.equal(parent)
        first['nested']['tokens'][0] = 999
        first['spoken_punctuation_ready'] = True
        second = self.equal(parent)
        self.assertEqual(second['nested']['tokens'][0], 1)
        self.assertFalse(second['spoken_punctuation_ready'])

    def test_parent_change_preserves_unrelated_cached_parent(self):
        first = self.record()
        second = self.record(2, 'utterance:000002', 'spoken:000002')
        self.equal(first); self.equal(second)
        self.record(value=2)
        self.assertIs(self.ledger._metadata_cache.get(first), MISS)
        self.assertIsNot(self.ledger._metadata_cache.get(second), MISS)
        self.assertEqual(self.equal(first)['nested']['tokens'][0], 2)

    def test_unrelated_durable_tables_do_not_evict_metadata(self):
        parent = self.record()
        self.equal(parent)
        for ledger in (self.ledger, self.original):
            self.assertTrue(ledger.claim_final(parent))
            ledger.save_patches([(parent, 0, 1, 'Synthetic.')], dict(synthetic=True))
        self.assertIsNot(self.ledger._metadata_cache.get(parent), MISS)
        self.equal(parent)

    def test_group_close_refreshes_latest_and_preserves_other_group(self):
        first = self.record()
        second = self.record(2, 'utterance:000002')
        other = self.record(3, 'utterance:000003', 'spoken:000003')
        for key in (first, second, other): self.equal(key)
        for ledger in (self.ledger, self.original):
            self.assertTrue(ledger.close_group('spoken:000001', 'native_pause'))
        self.assertIsNot(self.ledger._metadata_cache.get(other), MISS)
        self.assertFalse(self.equal(first)['utterance_final'])
        self.assertTrue(self.equal(second)['utterance_final'])
        self.assertEqual(self.equal(second)['utterance_boundary_kind'], 'native_pause')

    def test_punctuation_invalidates_all_retained_group_members(self):
        first = self.record(); second = self.record(2, 'utterance:000002')
        for ledger in (self.ledger, self.original): ledger.close_group('spoken:000001', 'stop')
        self.equal(first); self.equal(second)
        for ledger in (self.ledger, self.original): ledger.mark_punctuated('spoken:000001')
        self.assertIs(self.ledger._metadata_cache.get(first), MISS)
        self.assertIs(self.ledger._metadata_cache.get(second), MISS)
        self.assertTrue(self.equal(first)['spoken_punctuation_ready'])
        self.assertTrue(self.equal(second)['spoken_punctuation_ready'])

    def test_rollback_fences_cache_without_publishing_failed_state(self):
        parent = self.record(); self.equal(parent)
        connection = self.ledger._connection
        @contextmanager
        def fail(*, write=False):
            with connection(write=write) as db:
                yield db
                if write: raise sqlite3.OperationalError('synthetic precommit failure')
        with patch.object(self.ledger, '_connection', fail):
            with self.assertRaises(sqlite3.OperationalError):
                self.ledger.record(1, 'new words', metadata(value=2))
        self.assertTrue(self.ledger._metadata_cache.fenced)
        self.assertIs(self.ledger._metadata_cache.get(parent), MISS)
        self.assertEqual(self.equal(parent)['nested']['tokens'][0], 1)
        self.assertTrue(self.ledger._metadata_cache.fenced)

    def test_uncertain_postcommit_failure_forces_exact_sql(self):
        parent = self.record(); self.equal(parent)
        connection = self.ledger._connection
        @contextmanager
        def fail_after(*, write=False):
            with connection(write=write) as db:
                yield db
            if write: raise sqlite3.OperationalError('synthetic aftercommit failure')
        with patch.object(self.ledger, '_connection', fail_after):
            with self.assertRaises(sqlite3.OperationalError):
                self.ledger.record(1, 'new words', metadata(value=2))
        self.assertTrue(self.ledger._metadata_cache.fenced)
        self.assertEqual(self.ledger.metadata(parent)['nested']['tokens'][0], 2)
        self.assertTrue(self.ledger._metadata_cache.fenced)
        self.ledger.claim_final(parent)
        self.assertFalse(self.ledger._metadata_cache.fenced)
        self.assertEqual(self.ledger.metadata(parent)['nested']['tokens'][0], 2)

    def test_reader_waits_until_owned_commit_and_invalidation(self):
        parent = self.record(); self.equal(parent)
        connection = self.ledger._connection
        written, release, reader_started = threading.Event(), threading.Event(), threading.Event()
        result, errors = [], []
        @contextmanager
        def gated(*, write=False):
            with connection(write=write) as db:
                yield db
                if write:
                    written.set()
                    if not release.wait(5): raise TimeoutError('synthetic commit gate')
        def writer():
            try: self.ledger.record(1, 'new words', metadata(value=2))
            except BaseException as exc: errors.append(exc)
        def reader():
            reader_started.set()
            try: result.append(self.ledger.metadata(parent))
            except BaseException as exc: errors.append(exc)
        with patch.object(self.ledger, '_connection', gated):
            one = threading.Thread(target=writer); one.start()
            try:
                self.assertTrue(written.wait(5))
                two = threading.Thread(target=reader); two.start()
                self.assertTrue(reader_started.wait(5))
                self.assertEqual(result, [])
            finally:
                release.set(); one.join(5)
                if 'two' in locals(): two.join(5)
        self.assertFalse(one.is_alive()); self.assertFalse(two.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(result[0]['nested']['tokens'][0], 2)

    def test_unexpected_file_drift_uses_sql(self):
        parent = self.record(); self.equal(parent)
        with closing(sqlite3.connect(self.ledger.path)) as db, db:
            db.execute('UPDATE pieces SET metadata=? WHERE parent=?',
                (json.dumps(metadata(value=3)), parent))
        # Force an observable drift even on a filesystem with coarse timestamps.
        info = self.ledger.path.stat()
        os.utime(self.ledger.path, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))
        self.assertEqual(self.ledger.metadata(parent)['nested']['tokens'][0], 3)

    def test_missing_or_replaced_ledger_is_not_hidden_by_hit(self):
        parent = self.record(); self.equal(parent)
        self.ledger.path.unlink()
        with self.assertRaises(OSError): self.ledger.metadata(parent)
        replacement = SegmentLedger(self.ledger.path, policy=self.ledger.policy)
        replacement.record(1, 'replacement', metadata(value=4))
        self.assertEqual(self.ledger.metadata(parent)['nested']['tokens'][0], 4)

    def test_actual_cache_bytes_and_lru_eviction(self):
        cache = MetadataCache()
        stamp = tuple(tuple((1 << 64) - 1 for _ in range(7)) for _ in range(4))
        cache.observe(stamp)
        observed_fixed = (sys.getsizeof(cache) + sys.getsizeof(cache.__dict__)
            + sys.getsizeof(stamp) + sum(sys.getsizeof(row)
                + sum(sys.getsizeof(value) for value in row) for row in stamp))
        self.assertLessEqual(observed_fixed, FIXED_OVERHEAD)
        for index in range(40):
            self.assertTrue(cache.put(str(index), 'x' * 600_000, 'group', False))
            self.assertLessEqual(cache.resident_bytes, CACHE_BYTES)
        self.assertIs(cache.get('0'), MISS)
        self.assertIsNot(cache.get('39'), MISS)
        self.assertFalse(cache.put('giant', 'x' * CACHE_BYTES, 'group', False))
        self.assertLessEqual(cache.resident_bytes, CACHE_BYTES)
        for index in range(CACHE_ENTRIES + 1): cache.put('small:'+str(index), '{}', 'group', False)
        self.assertLessEqual(len(cache._rows), CACHE_ENTRIES)
        self.assertLessEqual(cache.resident_bytes, CACHE_BYTES)

    def test_sql_binding_coercion_and_cache_shape_fallback(self):
        parent = self.record(1, '1', 'group')
        self.equal(parent)
        self.record(1, 1, 'group', value=5)
        self.assertEqual(self.equal('1')['nested']['tokens'][0], 5)
        # Original seq-conflict SQL keeps stored parent/group; the supplied
        # replacement IDs must not leave the actual old parent cache stale.
        self.record(1, 'different-parent', 'different-group', value=6)
        self.assertEqual(self.equal('1')['nested']['tokens'][0], 6)
        self.assertIsNone(self.equal('different-parent'))
        cache = MetadataCache()
        self.assertFalse(cache.put('p'*4097, '{}', 'g', False))
        self.assertFalse(cache.put('p', b'{}', 'g', False))
        self.assertIs(cache.get(1), MISS)

    def test_optional_cache_allocation_failure_preserves_sql_row(self):
        parent = self.record()
        class NoAllocation(OrderedDict):
            def __setitem__(self, key, value): raise MemoryError('synthetic optional cache allocation')
        self.ledger._metadata_cache._rows = NoAllocation()
        self.equal(parent)
        self.assertTrue(self.ledger._metadata_cache.fenced)
        self.equal(parent)

    def test_read_fault_fences_previously_cached_parents(self):
        parent = self.record(); self.equal(parent)
        connection = self.ledger._connection
        @contextmanager
        def failed_read(*, write=False):
            if not write: raise sqlite3.OperationalError('synthetic read-open failure')
            with connection(write=write) as db:
                yield db
        with patch.object(self.ledger, '_connection', failed_read):
            with self.assertRaises(sqlite3.OperationalError):
                self.ledger.metadata('uncached-parent')
            self.assertTrue(self.ledger._metadata_cache.fenced)
            with self.assertRaises(sqlite3.OperationalError):
                self.ledger.metadata(parent)
        self.equal(parent)
        self.assertTrue(self.ledger._metadata_cache.fenced)

    def test_invalid_stored_json_retains_original_error(self):
        parent = self.record(); self.equal(parent)
        with closing(sqlite3.connect(self.ledger.path)) as db, db:
            db.execute('UPDATE pieces SET metadata=? WHERE parent=?', ('{', parent))
        info = self.ledger.path.stat()
        os.utime(self.ledger.path, ns=(info.st_atime_ns, info.st_mtime_ns + 1_000_000_000))
        with self.assertRaises(json.JSONDecodeError): self.ledger.metadata(parent)
        self.assertIs(self.ledger._metadata_cache.get(parent), MISS)

    def test_other_runtime_model_clock_and_sql_guards_unchanged(self):
        old = ast.parse(REFERENCE.read_text(encoding='utf-8'))
        new = ast.parse(Path(__file__).with_name('asr_segment_runtime.py').read_text(encoding='utf-8'))
        def named(tree):
            return {node.name: ast.dump(node, include_attributes=False) for node in tree.body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name != 'SegmentLedger'}
        self.assertEqual(named(old), named(new))
        def methods(tree):
            cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'SegmentLedger')
            return {node.name: ast.dump(node, include_attributes=False) for node in cls.body
                if isinstance(node, ast.FunctionDef)}
        before, after = methods(old), methods(new)
        for name in ('_connection', 'pieces', 'get'):
            self.assertEqual(before[name], after[name])


if __name__ == '__main__':
    unittest.main()
