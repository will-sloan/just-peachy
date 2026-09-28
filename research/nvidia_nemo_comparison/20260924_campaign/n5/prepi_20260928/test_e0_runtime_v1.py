"""Dependency-isolation tests with inert files; see README_E0_RUNTIME.md."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import psutil
psutil.Process().cpu_affinity([14])
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
sys.path[:0] = [str(Path.cwd()), str(Path.cwd() / 'vendor')]
from app.n2_models import load_runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.native = self.root / 'inert-native-test.bin'
        self.native.write_bytes(b'inert dependency hash fixture; never load')
        self.document = dict(schema='just-peachy.n2.runtime.v1',
            native_device=dict(kind='cpu', gpu_index=-1),
            native_runtime_files=[dict(path=str(self.native), sha256=hashlib.sha256(self.native.read_bytes()).hexdigest())])
        self.write()

    def write(self):
        (self.root / 'n2_runtime.json').write_text(json.dumps(self.document), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_e0_works_without_any_titanet_fields_or_files(self):
        self.assertEqual(load_runtime(self.root, embedding='E0'), self.document)

    def test_e0_does_not_follow_retired_manifest_path(self):
        self.document.update(titanet_manifest=str(self.root/'deliberately-absent.json'), titanet_manifest_sha256='0'*64)
        self.write()
        self.assertEqual(load_runtime(self.root, embedding='E0'), self.document)

    def test_native_hash_mismatch_still_refuses_e0(self):
        self.native.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Native runtime dependency hash changed'):
            load_runtime(self.root, embedding='E0')

    def test_empty_native_dependencies_still_refuse_e0(self):
        self.document['native_runtime_files'] = []
        self.write()
        with self.assertRaisesRegex(ValueError, 'Complete native runtime dependency binding required'):
            load_runtime(self.root, embedding='E0')

    def test_legacy_default_and_e1_do_not_silently_bypass_manifest(self):
        with self.assertRaises(KeyError):
            load_runtime(self.root)
        with self.assertRaises(KeyError):
            load_runtime(self.root, embedding='E1')

    def test_unknown_embedding_refuses(self):
        with self.assertRaisesRegex(ValueError, 'Unknown embedding'):
            load_runtime(self.root, embedding='not-a-component')


if __name__ == '__main__':
    unittest.main()
