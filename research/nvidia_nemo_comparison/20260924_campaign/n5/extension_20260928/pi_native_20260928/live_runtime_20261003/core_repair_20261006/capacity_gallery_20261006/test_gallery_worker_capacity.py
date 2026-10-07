"""Pure host gallery snapshot cases; README_GALLERY_WORKER_CAPACITY.md."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
PACKAGE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/caption-package31-f6383c985d4d41e6b065ff9487dd19ad/package')
PIN = '4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767'
manifest_raw = (PACKAGE/'PACKAGE_MANIFEST.json').read_bytes()
if hashlib.sha256(manifest_raw).hexdigest() != PIN:
    raise ValueError('Exact frozen31 pure runtime-support fixture source required')
manifest = json.loads(manifest_raw)
row = next(row for row in manifest['files'] if row['path'] == 'runtime_support.py')
support_path = PACKAGE/row['path']
raw = support_path.read_bytes()
if (len(raw), hashlib.sha256(raw).hexdigest()) != (row['bytes'], row['sha256']):
    raise ValueError('Frozen31 runtime-support source differs')
if 'runtime_support' not in sys.modules:
    spec = importlib.util.spec_from_file_location('runtime_support', support_path)
    support = importlib.util.module_from_spec(spec)
    sys.modules['runtime_support'] = support
    spec.loader.exec_module(support)
else:
    support = sys.modules['runtime_support']
    if Path(support.__file__).resolve() != support_path.resolve():
        raise ValueError('Unexpected runtime-support fixture origin')

tree = ast.parse((HERE/'gallery_worker.py').read_bytes())
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
         and node.name in ('snapshot_gallery', 'physical_file_ceiling')]
if len(nodes) != 2:
    raise ValueError('Exactly two pure gallery worker helpers required')
resource_stub = SimpleNamespace(RLIMIT_FSIZE=1, RLIM_INFINITY=-1,
                               getrlimit=lambda _: (32*1024**2, -1))
scope = dict(Path=Path, os=os, sys=sys, resource=resource_stub)
exec(compile(ast.Module(body=nodes, type_ignores=[]), '<pure-gallery-worker-fixture>', 'exec'), scope)
snapshot_gallery = scope['snapshot_gallery']
physical_file_ceiling = scope['physical_file_ceiling']


class GalleryWorkerCapacityTests(unittest.TestCase):
    def setUp(self):
        owned = os.environ.get('JP_BENCH_TEST_ROOT')
        self.temp = tempfile.TemporaryDirectory(prefix='gallery-worker-', dir=owned)
        self.directory = Path(self.temp.name).resolve()
        self.source = self.directory/'people'
        self.source.mkdir()
        self.destination = self.directory/'snapshot'
        self.budget = support.DiskBudget(1, reserve_bytes=64*1024**2)

    def tearDown(self):
        self.temp.cleanup()

    def test_snapshot_exceeds_both_old_count_and_aggregate_limits(self):
        for index in range(1025):
            (self.source/('record-%04d.json' % index)).write_bytes(b'{"fixture":true}\n')
        block = b'x'*(2*1024**2)
        for index in range(8):
            (self.source/('reference-%02d.bin' % index)).write_bytes(block)
        (self.source/'reference-08.bin').write_bytes(block[:1024**2])
        snapshot_gallery(self.source, self.destination, lambda: None, budget=self.budget)
        receipt = json.loads((self.destination/'BACKUP_AND_RESTORE.json').read_bytes())
        self.assertEqual(set(receipt), {'files', 'bytes', 'complete', 'scope'})
        self.assertTrue(receipt['complete'])
        self.assertGreater(len(receipt['files']), 1024)
        self.assertGreater(receipt['bytes'], 16*1024**2)
        self.assertGreater(self.budget.accepted, self.budget.maximum)
        for row in receipt['files']:
            for base in (self.source, self.destination/'backup', self.destination/'restore'):
                path = base/row['path']
                self.assertEqual(path.stat().st_size, row['bytes'])
                self.assertEqual(support.digest(path), row['sha256'])

    def test_rejects_hardlinked_source_file(self):
        original = self.source/'person.json'
        original.write_bytes(b'fixture')
        os.link(original, self.source/'alias.json')
        with self.assertRaisesRegex(ValueError, 'Single-link'):
            snapshot_gallery(self.source, self.destination, lambda: None, budget=self.budget)
        self.assertEqual(original.read_bytes(), b'fixture')
        self.assertFalse((self.destination/'BACKUP_AND_RESTORE.json').exists())

    def test_walk_copies_each_member_before_reading_the_next_entry(self):
        (self.source/'person.json').write_bytes(b'fixture')
        (self.source/'nested').mkdir()
        (self.source/'nested'/'reference.bin').write_bytes(b'reference')
        scandir = os.scandir
        closed = []
        fixture = self
        class IncrementalIterator:
            def __init__(self, path):
                self.iterator = scandir(path)
                self.previous = None
            def __next__(self):
                if self.previous is not None:
                    relative = Path(self.previous.path).relative_to(fixture.source)
                    fixture.assertTrue((fixture.destination/'backup'/relative).exists())
                    fixture.assertTrue((fixture.destination/'restore'/relative).exists())
                self.previous = next(self.iterator)
                return self.previous
            def close(self):
                self.iterator.close(); closed.append(True)
        with patch.object(os, 'scandir', IncrementalIterator), \
             patch.object(Path, 'rglob', side_effect=AssertionError('Materialized walk forbidden')):
            snapshot_gallery(self.source, self.destination, lambda: None, budget=self.budget)
        self.assertEqual(len(closed), 2)
        self.assertTrue(json.loads((self.destination/'BACKUP_AND_RESTORE.json').read_bytes())['complete'])

    def test_rejects_snapshot_inside_source(self):
        with self.assertRaisesRegex(ValueError, 'outside its source tree'):
            snapshot_gallery(self.source, self.source/'snapshot', lambda: None, budget=self.budget)
        self.assertFalse((self.source/'snapshot').exists())

    def test_rejects_reparse_observation_without_following_it(self):
        original = Path.lstat
        def marked(path):
            info = original(path)
            if path == self.source:
                return SimpleNamespace(st_mode=info.st_mode, st_nlink=info.st_nlink,
                                       st_file_attributes=0x400)
            return info
        with patch.object(Path, 'lstat', marked):
            with self.assertRaisesRegex(ValueError, 'Real gallery backup paths'):
                snapshot_gallery(self.source, self.destination, lambda: None, budget=self.budget)
        self.assertFalse(self.destination.exists())

    def test_physical_pressure_rejects_before_creating_backup(self):
        budget = support.DiskBudget(1, reserve_bytes=shutil.disk_usage(self.directory).free+1)
        with self.assertRaisesRegex(OSError, 'Storage floor'):
            snapshot_gallery(self.source, self.destination, lambda: None, budget=budget)
        self.assertFalse(self.destination.exists())

    def test_corrupt_independent_restore_blocks_complete_receipt(self):
        (self.source/'person.json').write_bytes(b'fixture')
        digest = support.digest
        corrupted = []
        def corrupt_once(path):
            path = Path(path)
            if 'restore' in path.parts and not corrupted:
                path.write_bytes(b'corrupt')
                corrupted.append(path)
            return digest(path)
        with patch.object(support, 'digest', corrupt_once):
            with self.assertRaisesRegex(OSError, 'independent restore readback'):
                snapshot_gallery(self.source, self.destination, lambda: None, budget=self.budget)
        self.assertEqual((self.source/'person.json').read_bytes(), b'fixture')
        self.assertFalse((self.destination/'BACKUP_AND_RESTORE.json').exists())

    def test_individual_reference_bound_remains(self):
        (self.source/'oversized.bin').write_bytes(b'x'*(2*1024**2+1))
        with self.assertRaisesRegex(ValueError, 'Bounded ordinary'):
            snapshot_gallery(self.source, self.destination, lambda: None, budget=self.budget)

    def test_finite_file_ceiling_uses_capacity_and_preserves_inheritance(self):
        usage = SimpleNamespace(total=512*1024**2, free=200*1024**2)
        with patch.object(shutil, 'disk_usage', lambda _: usage):
            self.assertEqual(physical_file_ceiling(self.directory, 64*1024**2), 448*1024**2)
            with patch.object(resource_stub, 'getrlimit', lambda _: (32*1024**2, 192*1024**2)):
                self.assertEqual(physical_file_ceiling(self.directory, 64*1024**2), 192*1024**2)
            with self.assertRaises(OSError):
                physical_file_ceiling(self.directory, 512*1024**2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
