"""Bundle corruption and architecture refusal checks; see README.md."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from verify_bundle import verify
from audit_arm64 import elf


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/'payload').write_bytes(b'fixture')
        self.row=dict(path='payload', bytes=7, sha256=hashlib.sha256(b'fixture').hexdigest())
        self.write([self.row])

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rows):
        (self.root/'BUNDLE_MANIFEST.json').write_text(json.dumps(dict(files=rows)))

    def test_roundtrip_and_corruption(self):
        self.assertEqual(verify(self.root)['status'], 'BUNDLE_HASHES_PASS')
        (self.root/'payload').write_bytes(b'corrupt')
        with self.assertRaises(ValueError): verify(self.root)

    def test_path_escape(self):
        for path in ['../escape', '/absolute', 'C:/escape', 'dir\\payload']:
            self.write([dict(self.row, path=path)])
            with self.subTest(path=path), self.assertRaises(ValueError): verify(self.root)

    def test_duplicate(self):
        self.write([self.row,self.row])
        with self.assertRaises(ValueError): verify(self.root)

    def test_wrong_architecture_never_executes(self):
        for content in [b'MZ'+bytes(64), b'\x7fELF\x01\x01'+bytes(64), b'\x7fELF\x02\x01'+bytes(64)]:
            with self.assertRaises(ValueError): elf(content,'wrong-architecture',self.root/'scratch')
        self.assertFalse((self.root/'scratch').exists())


if __name__=='__main__': unittest.main()
