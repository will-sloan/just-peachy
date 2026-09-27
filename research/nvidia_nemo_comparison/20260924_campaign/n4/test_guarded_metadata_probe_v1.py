"""In-memory manifest regression tests; README_GUARDED_METADATA_PROBE_V1.md."""
from copy import deepcopy
from pathlib import Path
import unittest

from guarded_metadata_probe_v1 import validate_manifest


class ManifestTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent
        self.entry = dict(path=str(root/'fixture_entry.py'), sha256='a'*64, bytes=42)
        self.base = dict(path=str(root/'fixture_guard.py'), sha256='b'*64, bytes=90)
        self.code = [self.base, self.entry]

    def test_complete_entry_and_resource_binding(self):
        validate_manifest(self.code, [self.base], self.entry)

    def test_original_omitted_entry_failure(self):
        with self.assertRaises(ValueError): validate_manifest([self.base], [self.base], self.entry)

    def test_resource_cannot_be_dropped(self):
        with self.assertRaises(ValueError): validate_manifest([self.entry], [self.base], self.entry)

    def test_resource_hash_cannot_be_changed(self):
        code = deepcopy(self.code); code[0]['sha256'] = 'c'*64
        with self.assertRaises(ValueError): validate_manifest(code, [self.base], self.entry)

    def test_duplicate_entry_is_rejected(self):
        with self.assertRaises(ValueError): validate_manifest(self.code+[self.entry], [self.base], self.entry)

    def test_entry_hash_must_match(self):
        entry = dict(self.entry, sha256='c'*64)
        with self.assertRaises(ValueError): validate_manifest(self.code, [self.base], entry)

    def test_invalid_source_metadata_and_census(self):
        for changed in ({'bytes':True}, {'sha256':'g'*64}, {'path':'relative.py'}, {'extra':0}):
            with self.subTest(changed=changed):
                code=deepcopy(self.code);code[0].update(changed)
                with self.assertRaises(ValueError): validate_manifest(code,[self.base],self.entry)
        with self.assertRaises(ValueError): validate_manifest(self.code*257,[self.base],self.entry)


if __name__ == '__main__': unittest.main()
