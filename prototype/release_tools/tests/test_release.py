"""Bounded release safety regressions; fixtures contain no human audio/data."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import release as r


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='PROTO1 release tests with spaces ')
        self.base = Path(self.temp.name)
        self.src = self.base / 'source app'
        (self.src / 'config').mkdir(parents=True)
        (self.src / 'app').mkdir()
        (self.src / 'main.py').write_text('print("release fixture, no inference")\n', encoding='utf-8')
        (self.src / 'app' / 'core.py').write_text('SCHEMA = 1\n', encoding='utf-8')
        r.write_json(self.src / 'config' / 'assets.json', [])
        self.out = self.base / 'archives'
        self.root = self.base / 'install root'
        self.data = self.base / 'private external data'

    def tearDown(self):
        self.temp.cleanup()

    def build(self, version='v1'):
        result = r.build(self.src, self.out, version)
        return Path(result['archive'])

    def staged(self, version='v1'):
        archive = self.build(version)
        return r.stage(archive, self.root, r.digest(archive))

    def altered_zip(self, archive, name, content, replace=False):
        target = self.out / 'altered.zip'
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(target, 'w') as dst:
            for item in src.infolist():
                if replace and item.filename == name:
                    continue
                dst.writestr(item, src.read(item.filename))
            dst.writestr(name, content)
        return target

    def test_build_stage_idempotence(self):
        archive = self.build()
        self.assertEqual(r.stage(archive, self.root)['status'], 'STAGED')
        self.assertEqual(r.stage(archive, self.root)['status'], 'ALREADY_STAGED')

    def test_build_excludes_private_audio_models_evidence(self):
        for folder, name in [('people', 'private.json'), ('sessions', 'words.json'), ('models', 'model.onnx'), ('release_tools/evidence', 'private.json')]:
            p = self.src / folder / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('PRIVATE', encoding='utf-8')
        with zipfile.ZipFile(self.build()) as z:
            self.assertFalse(any(b'PRIVATE' in z.read(n) for n in z.namelist()))

    def test_versioned_archive_never_overwritten(self):
        self.build()
        with self.assertRaises(FileExistsError): self.build()

    def test_unsafe_versions(self):
        for value in ['..', '../x', '/x', 'C:x', 'x\\y', '']:
            with self.subTest(value=value), self.assertRaises(ValueError): r.validate_version(value)

    def test_unsafe_archive_members(self):
        archive = self.build()
        for name in ['../escape.py', '/absolute.py', 'C:/evil.py', 'dir\\evil.py', 'NUL.py']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                r.inspect_archive(self.altered_zip(archive, name, b'evil'))

    def test_case_collision(self):
        archive = self.build()
        with self.assertRaises(ValueError): r.inspect_archive(self.altered_zip(archive, 'MAIN.PY', b'evil'))

    def test_symlink_member(self):
        archive = self.build()
        info = zipfile.ZipInfo('link.py'); info.create_system = 3; info.external_attr = (0o120777 << 16)
        with zipfile.ZipFile(archive, 'a') as z: z.writestr(info, 'main.py')
        with self.assertRaises(ValueError): r.inspect_archive(archive)

    def test_hash_corruption(self):
        with self.assertRaises(ValueError): r.inspect_archive(self.altered_zip(self.build(), 'main.py', b'corrupt', True))

    def test_unlisted_member(self):
        with self.assertRaises(ValueError): r.inspect_archive(self.altered_zip(self.build(), 'extra.py', b'extra'))

    def test_expected_archive_hash(self):
        with self.assertRaises(ValueError): r.stage(self.build(), self.root, '0' * 64)
        self.assertFalse(self.root.exists())

    def test_activation_and_rollback_keep_private_data(self):
        self.staged(); r.activate(self.root, self.data, 'v1')
        private = self.data / 'people' / 'fixture-person.json'
        private.parent.mkdir(); private.write_bytes(b'PRIVATE PERSON fixture')
        self.staged('v2'); r.activate(self.root, self.data, 'v2')
        result = r.rollback(self.root, self.data)
        self.assertEqual(result['version'], 'v1')
        self.assertEqual(private.read_bytes(), b'PRIVATE PERSON fixture')
        self.assertFalse((self.data / 'runtime.lock').exists())

    def test_active_owner_refuses_activation(self):
        self.staged()
        r.write_json(self.data / 'runtime.lock', dict(token='application-test-owner'))
        with self.assertRaises(RuntimeError): r.activate(self.root, self.data, 'v1')
        self.assertFalse((self.root / 'current.json').exists())
        self.assertEqual(r.read_json(self.data / 'runtime.lock')['token'], 'application-test-owner')

    def test_update_exclusion_race(self):
        with r.update_boundary(self.data):
            with self.assertRaises(RuntimeError):
                with r.update_boundary(self.data): pass

    def test_incompatible_schema(self):
        self.staged(); r.write_json(self.data / 'DATA_SCHEMA.json', dict(schema_version=99))
        with self.assertRaises(ValueError): r.activate(self.root, self.data, 'v1')
        self.assertFalse((self.root / 'current.json').exists())

    def test_missing_schema_existing_people(self):
        self.staged(); (self.data / 'people').mkdir(parents=True)
        with self.assertRaises(ValueError): r.activate(self.root, self.data, 'v1')

    def test_data_under_release_refused(self):
        self.staged()
        with self.assertRaises(ValueError): r.activate(self.root, self.root / 'releases' / 'v1' / 'people', 'v1')

    def test_installed_tamper_fails_health(self):
        self.staged(); r.activate(self.root, self.data, 'v1')
        (self.root / 'releases' / 'v1' / 'main.py').write_text('tampered', encoding='utf-8')
        with self.assertRaises(ValueError): r.healthcheck(self.root, self.data)

    def test_diagnostics_excludes_people(self):
        self.staged(); r.activate(self.root, self.data, 'v1')
        r.write_json(self.data / 'people' / 'profile.json', dict(name='secret name', vector=[1, 2]))
        out = self.base / 'diagnostics.json'
        r.diagnostics(self.root, self.data, out)
        self.assertNotIn('secret name', out.read_text(encoding='utf-8'))
        self.assertFalse(r.read_json(out)['private_data_included'])

    def test_models_content_addressed_idempotent(self):
        content = b'fixture model bytes, not a model'
        sha = hashlib.sha256(content).hexdigest()
        r.write_json(self.src / 'config' / 'assets.json', [dict(component_id='fixture', sha256=sha, filename='fixture.onnx')])
        source = self.base / 'source models'
        path = source / sha / 'fixture.onnx'; path.parent.mkdir(parents=True); path.write_bytes(content)
        self.staged()
        release = self.root / 'releases' / 'v1'
        for _ in range(2): r.import_models(release, source, self.root / 'models')
        r.activate(self.root, self.data, 'v1', require_assets=True)
        self.assertEqual(len(r.healthcheck(self.root, self.data, check_models=True)['models']), 1)

    def test_missing_model_refuses_activation(self):
        r.write_json(self.src / 'config' / 'assets.json', [dict(component_id='fixture', sha256='0'*64, filename='missing.onnx')])
        self.staged()
        with self.assertRaises(ValueError): r.activate(self.root, self.data, 'v1', require_assets=True)
        self.assertFalse((self.root / 'current.json').exists())


if __name__ == '__main__': unittest.main(verbosity=2)
