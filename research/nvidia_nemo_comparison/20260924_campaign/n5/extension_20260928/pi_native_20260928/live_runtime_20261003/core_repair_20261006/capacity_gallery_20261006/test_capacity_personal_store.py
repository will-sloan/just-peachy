"""Pinned pure personal capacity cases; README_GALLERY_CAPACITY_STORE.md.

All vectors, UUIDs, names, quality and archive bytes here are synthetic. Original
validator and constructor-admission AST regions run; no model graph is imported.
"""
import ast
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch
import uuid
import zipfile

import numpy as np
import application_contract as contract
import capacity_personal_store as capacity
import gallery_capacity_admission as admission
import runtime_support as support

INSTALLED = Path(os.environ['JP_CAPACITY_INSTALLED'])
BACKEND = 'a'*64


def fixture_parent(owner, module_name, relative, base=object):
    """Keep exact native gallery-admission statements; isolate model setup."""
    source = INSTALLED/relative
    tree = ast.parse(source.read_bytes())
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == owner)
    method = next(node for node in original.body if isinstance(node, ast.FunctionDef)
                  and node.name == '_admit_research_gallery')
    methods = [method]
    if owner == 'PipelineEngine':
        constructor = deepcopy(next(node for node in original.body if isinstance(node, ast.FunctionDef)
                                   and node.name == '__init__'))
        fields = {'config', '_research_profile', '_research_v3', '_research_gallery'}
        constructor.body = [node for node in constructor.body if
            (isinstance(node, ast.Assign) and len(node.targets) == 1 and
             isinstance(node.targets[0], ast.Attribute) and node.targets[0].attr in fields)
            or (isinstance(node, ast.If) and ast.unparse(node.test) == 'research_gallery is not None')]
        if len(constructor.body) != 5:
            raise ValueError('Exact original constructor gallery-admission region changed')
        # Original type annotations only describe unused model arguments.
        for argument in constructor.args.args+constructor.args.kwonlyargs:
            argument.annotation = None
        constructor.returns = None
        methods.insert(0, constructor)
    shell = ModuleType(module_name)
    shell.__file__, shell.__package__ = str(source), module_name.rsplit('.', 1)[0]
    shell.__dict__.update(Base=base, N2Gallery=importlib.import_module('app.n2_identity').N2Gallery)
    sys.modules[module_name] = shell
    node = deepcopy(original)
    node.bases = [] if base is object else [ast.Name(id='Base', ctx=ast.Load())]
    node.body = methods
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), 'exec'), shell.__dict__)
    return getattr(shell, owner)


class CapacityPersonalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name, relative in (('app', 'app'), ('edge_speech_pipeline', 'vendor/edge_speech_pipeline')):
            if name in sys.modules:
                raise RuntimeError('Capacity checks require a fresh host process')
            shell = ModuleType(name)
            shell.__path__ = [str(INSTALLED/relative)]
            sys.modules[name] = shell
        sys.path.insert(0, str(INSTALLED))
        cls.people = importlib.import_module('app.people')
        cls.Store = capacity.capacity_store_type(cls.people, lambda: None,
                        support.DiskBudget(1, reserve_bytes=64*1024**2))
        cls.vector = np.zeros(192, np.float32)
        cls.vector[0] = 1
        cls.route = dict(tap='O0', sample_rate=16000, gain_policy='fixture_unity',
                         preprocessing=cls.people.PREPROCESSING, waveform_domain='dry_test_fixture')
        raw = json.loads((INSTALLED/'RELEASE_MANIFEST.json').read_bytes())
        cls.manifest = {row['path']: row for row in raw['files']}
        cls.Baseline = fixture_parent('PipelineEngine', 'edge_speech_pipeline.runtime',
                                      'vendor/edge_speech_pipeline/runtime.py')
        cls.N2 = fixture_parent('N2Engine', 'app.n2_pipeline', 'app/n2_pipeline.py', cls.Baseline)
        # Only the exact pure namespace function; never import N2 models.
        model_source = INSTALLED/'app/n2_models.py'
        function = next(node for node in ast.parse(model_source.read_bytes()).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'redim_namespace')
        model_shell = ModuleType('app.n2_models')
        model_shell.__file__ = str(model_source)
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(model_source), 'exec'), model_shell.__dict__)
        sys.modules['app.n2_models'] = model_shell

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='personal-capacity-', dir=os.environ['JP_BENCH_TEST_ROOT'])
        self.root = Path(self.temporary.name)
        self.store = self.Store(self.root/'people', BACKEND)

    def tearDown(self):
        self.temporary.cleanup()

    def quality(self, serial, padding=0):
        result = dict(can_save=True, gaps=0, elapsed_s=15., usable_s=15., target_sec=15,
            accepted_intervals=[[0., 15.]], clipping=0., consistency=1., embedding_count=1,
            source_kind='synthetic_capacity_fixture', source_sha256=f'{serial:064x}')
        if padding:
            result['source_provenance'] = dict(fixture_padding='x'*padding)
        return result

    def save(self, serial, *, person=1, padding=0):
        return self.store.save('Synthetic %d'%person, self.vector, self.quality(serial, padding),
                               self.route, person_id=str(uuid.UUID(int=person)))

    def gallery(self, count=257):
        rows = [(dict(id=str(uuid.UUID(int=index+1)), name='Synthetic %d'%index,
                      references=[], backend_sha256=BACKEND, preprocessing=self.people.PREPROCESSING), self.vector)
                for index in range(count)]
        # This isolated admission fixture bypasses record construction only; the
        # real store constructor is separately covered by the 257-person case.
        return self.people.PersonalGallery(rows, BACKEND, self.route)

    def engine(self, parent, gallery):
        bound = admission.bind_capacity_admission(parent, INSTALLED, self.manifest, lambda: None)
        class Engine(parent):
            _admit_research_gallery = bound
            config = SimpleNamespace(asset=lambda _: SimpleNamespace(sha256=BACKEND))
            resident = SimpleNamespace(embedding='E0')
        profile = SimpleNamespace(schema_version='edge-research-profile.v3',
            identity=SimpleNamespace(mode='post_association', max_gallery_profiles=256), apply=lambda value: value)
        return Engine(Engine.config, research_profile=profile, research_gallery=gallery)

    def test_01_257_people_and_21_references_actual_store(self):
        for index in range(257):
            self.save(index+1, person=index+1)
        for index in range(20):
            self.save(1000+index, person=1)
        rows = self.store.list(refresh=True)
        self.assertEqual(len(rows), 257)
        self.assertEqual(len(rows[0]['references']), 21)
        self.assertEqual(len(self.store.summaries()), 257)
        gallery = self.store.gallery(self.route)
        self.assertEqual(gallery.matrix.shape, (257, 192))
        self.assertEqual(gallery.receipt['loaded_count'], 257)
        self.assertTrue(np.array_equal(gallery.matrix[0], self.vector))

    def test_02_selected_display_257_and_unchanged_message_guards(self):
        ids = [str(uuid.UUID(int=index+1)) for index in range(257)]
        selection = SimpleNamespace(embedding='redimnet', diarizer='nemotron')
        value = contract.default(selection.embedding)
        value.update(mode='selected_closed', selected_ids=ids, display_ids=ids, strict=True)
        self.assertEqual(len(contract.validate(value, selection, people=ids)['display_ids']), 257)
        for bad in (ids+[ids[0]], ['ABC'], ['00000000000000000000000000000001']):
            with self.assertRaises(ValueError):
                contract.identifiers(bad)
        value['settings'] = {'fixture': 'x'*65536}
        with self.assertRaisesRegex(ValueError, '64 KiB'):
            contract.validate(value, selection, people=ids)

    def test_03_original_record_shape_checksum_namespace_source_guards(self):
        for bad in (np.zeros(192, np.float32), np.zeros(191, np.float32), np.full(192, np.nan, np.float32)):
            with self.assertRaises(ValueError):
                self.store.save('Synthetic', bad, self.quality(1), self.route)
        row = self.save(1)
        with self.assertRaisesRegex(ValueError, 'already been enrolled'):
            self.save(1)
        path = self.store.root/row['id']/'person.json'
        original = path.read_bytes()
        for field, bad in (('preprocessing', 'other-encoder'), ('name', 'x'*81)):
            modified = deepcopy(row); modified[field] = bad
            path.write_text(json.dumps(modified), encoding='utf-8')
            with self.assertRaises(ValueError):
                self.store.list(refresh=True)
            path.write_bytes(original)
        vector_path = path.parent/row['references'][0]['vector']
        original_vector = vector_path.read_bytes()
        with vector_path.open('wb') as stream:
            np.save(stream, self.vector.astype(np.float64), allow_pickle=False)
        with self.assertRaisesRegex(ValueError, 'float32'):
            self.store.list(refresh=True)
        vector_path.write_bytes(original_vector[:-1]+bytes([original_vector[-1]^1]))
        with self.assertRaises(ValueError):
            self.store.list(refresh=True)
        vector_path.write_bytes(original_vector)
        self.assertEqual(len(self.store.list(refresh=True)), 1)

    def test_04_streamed_archive_exceeds_16mib_and_import_256(self):
        for index in range(530):
            self.save(index+1, person=index+1, padding=31000)
        self.assertEqual(len(self.store.list(refresh=True)), 530)
        self.assertIsNone(self.store._list_cache)
        archive = self.root/'synthetic.zip'
        self.store.export(archive, consent=True)
        with zipfile.ZipFile(archive) as source:
            self.assertGreater(sum(row.file_size for row in source.infolist()), 16*1024**2)
        imported = self.Store(self.root/'imported', BACKEND)
        imported.import_archive(archive, consent=True)
        self.assertEqual(len(imported.summaries()), 530)
        self.assertIsNone(imported._list_cache)
        first = imported.root/str(uuid.UUID(int=1))/'person.json'
        before = support.digest(first)
        with self.assertRaisesRegex(ValueError, 'never overwrites'):
            imported.import_archive(archive, consent=True)
        self.assertEqual(support.digest(first), before)

    def test_05_archive_checksum_and_consent_no_overwrite(self):
        self.save(1)
        archive = self.root/'synthetic.zip'
        with self.assertRaisesRegex(ValueError, 'consent'):
            self.store.export(archive)
        self.store.export(archive, consent=True)
        before = support.digest(archive)
        with self.assertRaises(FileExistsError):
            self.store.export(archive, consent=True)
        self.assertEqual(support.digest(archive), before)
        corrupt = self.root/'corrupt.zip'
        with zipfile.ZipFile(archive) as source, zipfile.ZipFile(corrupt, 'x') as destination:
            for name in source.namelist():
                raw = source.read(name)
                if name.endswith('.npy'):
                    raw = raw[:-1]+bytes([raw[-1]^1])
                destination.writestr(name, raw)
        imported = self.Store(self.root/'imported', BACKEND)
        with self.assertRaisesRegex(ValueError, 'consent'):
            imported.import_archive(corrupt)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            imported.import_archive(corrupt, consent=True)
        self.assertEqual(imported.summaries(), [])

    def test_06_physical_and_ram_floor_reject_before_save(self):
        with patch.object(capacity, 'resource_snapshot', return_value={'available_ram': capacity.RAM_FLOOR-1}):
            with self.assertRaises(MemoryError):
                self.save(1)
        self.assertFalse(any(self.store.root.iterdir()))
        self.store._capacity_budget = SimpleNamespace(check_free=lambda *_: (_ for _ in ()).throw(OSError('fixture physical floor')))
        with self.assertRaisesRegex(OSError, 'physical floor'):
            self.save(1)
        self.assertFalse(any(self.store.root.iterdir()))

    def test_07_export_temp_checks_gallery_root_and_destination(self):
        self.save(1)
        checked = []
        self.store._capacity_budget = SimpleNamespace(check_free=lambda path, count: checked.append(Path(path)))
        export_dir = self.root/'elsewhere'; export_dir.mkdir()
        self.store.export(export_dir/'synthetic.zip', consent=True)
        self.assertIn(self.store.root, checked)
        self.assertIn(export_dir, checked)
        self.assertGreater(checked.count(self.store.root), 2)

    def test_08_pinned_baseline_constructor_admits_257(self):
        gallery = self.gallery()
        engine = self.engine(self.Baseline, gallery)
        self.assertIs(engine._research_gallery, gallery)
        self.assertFalse(engine._gallery_capacity_admission['count_quota_enforced'])
        self.assertEqual(engine._gallery_capacity_admission['historical_max_gallery_profiles'], 256)
        wrong = self.gallery(); wrong.receipt['backend_sha256'] = 'b'*64
        with self.assertRaisesRegex(ValueError, 'different backend'):
            self.engine(self.Baseline, wrong)

    def test_09_pinned_n2_constructor_admits_257_preserves_namespace(self):
        gallery = self.gallery()
        namespace = sys.modules['app.n2_models'].redim_namespace(SimpleNamespace(asset=lambda _: SimpleNamespace(sha256=BACKEND)))
        gallery.namespace = namespace
        gallery.calibration = dict(status='UNCALIBRATED_PERSONAL_DOMAIN')
        engine = self.engine(self.N2, gallery)
        self.assertIs(engine._research_gallery, gallery)
        self.assertEqual(gallery.calibration, dict(status='UNCALIBRATED_PERSONAL_DOMAIN'))
        gallery.namespace = dict(namespace, model_sha256='b'*64)
        with self.assertRaisesRegex(ValueError, 'namespace'):
            self.engine(self.N2, gallery)

    def test_10_admission_shape_count_finite_and_memory_guards(self):
        for field, value in (('dimension', 191), ('loaded_count', 256)):
            gallery = self.gallery(); gallery.receipt[field] = value
            with self.assertRaisesRegex(ValueError, 'representation'):
                self.engine(self.N2, gallery)
        gallery = self.gallery(); gallery.matrix = np.zeros((257, 192), np.float64)
        with self.assertRaisesRegex(ValueError, 'representation'):
            self.engine(self.N2, gallery)
        gallery.matrix = np.full((257, 192), np.nan, np.float32)
        with self.assertRaisesRegex(ValueError, 'finite'):
            self.engine(self.N2, gallery)
        with patch.object(admission, 'resource_snapshot', return_value={'available_ram': admission.RAM_FLOOR-1}):
            with self.assertRaises(MemoryError):
                self.engine(self.Baseline, self.gallery())

    def test_11_exact_admission_binding_and_unchanged_record_size(self):
        manifest = deepcopy(self.manifest)
        manifest['app/n2_pipeline.py']['sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'source/origin'):
            admission.bind_capacity_admission(self.N2, INSTALLED, manifest, lambda: None)
        raw = (INSTALLED/'app/n2_pipeline.py').read_bytes().replace(b'len(gallery.ids)>maximum_profiles', b'len(gallery.ids)>maximum_profiles+1')
        with self.assertRaisesRegex(ValueError, 'condition differs'):
            admission._derive(raw, 'N2Engine')
        row = self.save(1)
        row['references'][0]['source_provenance'] = {'fixture': 'x'*(128*1024)}
        path = self.store.root/row['id']/'person.json'
        path.write_text(json.dumps(row), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.list(refresh=True)
