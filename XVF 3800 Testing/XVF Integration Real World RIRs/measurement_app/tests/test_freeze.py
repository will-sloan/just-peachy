"""Completion markers are published only after successful evidence verification."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from measurement_app import core


class AtomicFreezeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='xvf_freeze_offline_')
        self.folder = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        (self.folder / '02_raw').mkdir()
        (self.folder / '00_admin').mkdir()
        self.raw = self.folder / '02_raw' / 'native.raw'
        self.raw.write_bytes(bytes(range(256)))
        (self.folder / '00_admin' / 'request.json').write_text('{"fixture":true}\n', encoding='utf-8')
        self.files = {p for p in self.folder.rglob('*') if p.is_file()}
        self.original_sha = core.sha
        self.marker = self.folder / 'SHA256SUMS.txt'

    def test_success_publishes_only_after_every_hash_and_preserves_all_evidence(self):
        expected = {p.relative_to(self.folder).as_posix(): self.original_sha(p) for p in self.files}
        checked = []
        def hash_before_publication(path):
            self.assertFalse(self.marker.exists(), 'Completion marker published before hashing finished')
            checked.append(Path(path))
            return self.original_sha(path)
        with patch.object(core, 'sha', side_effect=hash_before_publication):
            result = core.freeze(self.folder)
        self.assertTrue(self.marker.is_file())
        self.assertGreaterEqual(len(checked), len(self.files) * 2)
        actual = {}
        for line in self.marker.read_text(encoding='utf-8').splitlines():
            digest, relative = line.split('  ', 1)
            self.assertNotIn(relative, actual)
            actual[relative] = digest
            self.assertEqual(self.original_sha(self.folder / relative), digest)
        self.assertEqual(actual, expected)
        self.assertEqual(result['files'], len(expected))
        self.assertEqual(result['manifest_sha256'], self.original_sha(self.marker))
        self.assertEqual({p for p in self.folder.rglob('*') if p.is_file()}, self.files | {self.marker})

    def test_mutation_after_initial_hash_is_detected_without_completion_marker(self):
        mutated = [False]
        def change_after_hash(path):
            digest = self.original_sha(path)
            if Path(path) == self.raw and not mutated[0]:
                mutated[0] = True
                self.raw.write_bytes(b'Changed while freeze was verifying evidence')
            return digest
        with patch.object(core, 'sha', side_effect=change_after_hash):
            with self.assertRaises(RuntimeError):
                core.freeze(self.folder)
        self.assertTrue(mutated[0])
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.raw.read_bytes(), b'Changed while freeze was verifying evidence')
        self.assertTrue(all(path.is_file() for path in self.files))

    def test_evidence_hash_io_error_retains_raw_files_and_publishes_nothing(self):
        original = self.raw.read_bytes()
        def fail_on_raw(path):
            if Path(path) == self.raw:
                raise OSError('Simulated evidence-read failure')
            return self.original_sha(path)
        with patch.object(core, 'sha', side_effect=fail_on_raw):
            with self.assertRaisesRegex(OSError, 'evidence-read'):
                core.freeze(self.folder)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.raw.read_bytes(), original)
        self.assertTrue(all(path.is_file() for path in self.files))

    def test_manifest_hash_failure_also_prevents_publication(self):
        def fail_on_pending_manifest(path):
            if Path(path) not in self.files:
                raise OSError('Simulated manifest-hash failure')
            return self.original_sha(path)
        with patch.object(core, 'sha', side_effect=fail_on_pending_manifest):
            with self.assertRaisesRegex(OSError, 'manifest-hash'):
                core.freeze(self.folder)
        self.assertFalse(self.marker.exists())
        self.assertTrue(all(path.is_file() for path in self.files))

    def test_refreeze_cannot_rewrite_existing_marker_or_files(self):
        core.freeze(self.folder)
        before = {p.relative_to(self.folder).as_posix(): self.original_sha(p)
                  for p in self.folder.rglob('*') if p.is_file()}
        with self.assertRaises((RuntimeError, FileExistsError)):
            core.freeze(self.folder)
        after = {p.relative_to(self.folder).as_posix(): self.original_sha(p)
                 for p in self.folder.rglob('*') if p.is_file()}
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
