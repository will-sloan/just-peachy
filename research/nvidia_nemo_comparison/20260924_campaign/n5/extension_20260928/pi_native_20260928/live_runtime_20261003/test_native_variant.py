"""Synthetic admission contracts only; see README_NATIVE_VARIANT.md."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import native_variant as subject
from nemotron_binding import bind
from profiles import RuntimeSelection, SessionPolicy, get_profile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class NativeVariantTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='variant-contract-', dir=os.environ.get('JP_BENCH_TEST_ROOT'))
        self.parent = Path(self.temporary.name).resolve()
        self.root = self.parent / 'thread2-build-test'
        self.root.mkdir()
        self.runtime = self.root / 'runtime'; self.runtime.mkdir()
        (self.root / 'build').mkdir()
        self.model = self.parent / 'D1.gguf'; self.model.write_bytes(b'fake-model-no-native')
        self.source_raw = b'fake-pinned-source-no-compilation'
        (self.root / 'session.cpp').write_bytes(self.source_raw)
        self.dependencies = {name: sha(name.encode()) for name in subject.DEPENDENCIES}
        self.patch = patch.multiple(subject, JOB_PARENT=self.parent, MODEL_PATH=self.model,
            MODEL_SHA256=sha(self.model.read_bytes()), SOURCE_SHA256=sha(self.source_raw),
            DEPENDENCIES=self.dependencies,
            WRAPPER_SHA256=self.dependencies['libnemo_speech_asr_c.so.1'])
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.rows = []
        for name, pin in self.dependencies.items():
            path = self.runtime / name; path.write_bytes(name.encode())
            self.rows.append(dict(path=str(path), sha256=pin, bytes=path.stat().st_size))
        core = b'fake-thread2-core-no-loading'; self.core_pin = sha(core)
        for directory in (self.runtime, self.root/'build'):
            (directory/'libnemo_speech_asr.so').write_bytes(core)
        self.rows.append(dict(path=str(self.runtime/'libnemo_speech_asr.so'), sha256=self.core_pin, bytes=len(core)))
        owner = dict(pid=123, start_ticks=456, boot_id='00000000-0000-0000-0000-000000000000')
        self.write('OWNER.json', owner)
        self.exit = dict(owner=owner, unit='jp-v29-thread2-build-test.service', natural_returncode=0,
                         error=None, leases_released=True)
        self.write('JOB_EXIT.json', self.exit)
        source = dict(schema='just-peachy.native-thread-source-variant.v1', source_sha256=subject.SOURCE_SHA256,
                      retained_metadata_sha256=subject.METADATA_SHA256, native_graph_threads_requested=2,
                      change='one graph-helper argument: 1 to 2', input_manifest_sha256=subject.INPUT_MANIFEST_SHA256)
        source_pin = self.write('SOURCE_VARIANT.json', source)
        self.document = dict(schema='just-peachy.n2.runtime.v1', native_device=dict(kind='cpu', gpu_index=-1),
            streaming_profile='native_cm5_chunk52', nemotron_model=str(self.model), nemotron_model_sha256=subject.MODEL_SHA256,
            nemotron_library=str(self.runtime/'libnemo_speech_asr_c.so.1'), nemotron_library_sha256=subject.WRAPPER_SHA256,
            native_runtime_files=self.rows, native_variant=dict(id='chunk52-native-threads2', configured_graph_threads=2,
                source_sha256=subject.SOURCE_SHA256, core_sha256=self.core_pin, geometry=[52,1,0,80,264,40],
                graph_cache_entries=8, native_qualified=False, numerical_comparison_required=True))
        self.build = dict(owner=owner, status='NATIVE_BUILD_COLLECTED_NOT_INFERENCE', source_sha256=subject.SOURCE_SHA256,
            source_variant_sha256=source_pin, input_manifest_sha256=subject.INPUT_MANIFEST_SHA256,
            core_sha256=self.core_pin, configured_native_graph_threads=2, retained_lru_entries=8,
            input_files_verified=2436, native_execution=False, models_loaded=False, native_runtime_files=self.rows)
        self.republish()
        self.selection = RuntimeSelection('nemotron', 'anonymous', 'saved', 'chunk52', True)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, name, value):
        raw = json.dumps(value, sort_keys=True).encode()
        (self.root/name).write_bytes(raw)
        return sha(raw)

    def republish(self):
        self.descriptor_pin = self.write('RUNTIME_VARIANT.json', self.document)
        self.build['runtime_variant_sha256'] = self.descriptor_pin
        self.write('BUILD_RESULT.json', self.build)

    def verify(self):
        return subject.verify_native_variant(self.root/'RUNTIME_VARIANT.json', self.descriptor_pin, self.selection)

    def test_verified_document_and_private_binder_gate(self):
        admission = self.verify()
        self.assertEqual(subject.verified_core_pin(admission, self.selection, admission.document()), self.core_pin)
        self.assertEqual(admission.receipt()['configured_graph_threads'], 2)
        self.assertFalse(admission.receipt()['native_qualified'])
        mutated = admission.document(); mutated['native_variant']['configured_graph_threads'] = 1
        with self.assertRaises(ValueError):
            subject.verified_core_pin(admission, self.selection, mutated)
        with self.assertRaises(ValueError):
            subject.verified_core_pin(self.document, self.selection, self.document)
        with self.assertRaises(ValueError):
            subject.verified_core_pin(replace(admission, _seal=object()), self.selection, self.document)

    def test_default_binder_still_rejects_unadmitted_core(self):
        # The normal hard-coded wrapper pin is unchanged; reject before adapter access.
        document = dict(self.document, nemotron_library_sha256='9600de4c486aa4ea8209b6f2d78ec33fb3148d74c8a4395bd23eeaf00137915f')
        with self.assertRaisesRegex(ValueError, 'Explicit pinned'):
            bind(SimpleNamespace(), self.selection, SessionPolicy(), document)
        del document['native_variant']
        with self.assertRaisesRegex(ValueError, 'Select retained'):
            bind(SimpleNamespace(), self.selection, SessionPolicy(), document)

    def test_source_library_model_and_descriptor_changes_fail_closed(self):
        for path in (self.root/'session.cpp', self.runtime/'libggml-cpu.so', self.model, self.root/'RUNTIME_VARIANT.json'):
            with self.subTest(path=path.name):
                original = path.read_bytes(); path.write_bytes(original+b'changed')
                with self.assertRaises(ValueError): self.verify()
                path.write_bytes(original)

    def test_successful_build_source_pin_and_actual_closure_required(self):
        for field, value in (('status', 'FAILED_PRESERVED'), ('source_sha256', '0'*64),
                             ('input_manifest_sha256', '0'*64), ('source_variant_sha256', None)):
            with self.subTest(field=field):
                original = self.build[field]; self.build[field] = value; self.republish()
                with self.assertRaises(ValueError): self.verify()
                self.build[field] = original
        self.republish()
        self.exit['natural_returncode'] = 1; self.write('JOB_EXIT.json', self.exit)
        with self.assertRaises(ValueError): self.verify()

    def test_paths_inventory_and_geometry_cannot_escape_variant(self):
        self.document['native_variant']['geometry'] = [55,1,0,80,264,40]; self.republish()
        with self.assertRaises(ValueError): self.verify()
        self.document['native_variant']['geometry'] = [52,1,0,80,264,40]
        self.rows[0]['path'] = str(self.parent/Path(self.rows[0]['path']).name); self.republish()
        with self.assertRaises(ValueError): self.verify()

    def test_selection_scope_and_unrelated_job_root_rejected(self):
        for selection in (replace(self.selection, nemotron_profile='candidate_3_compact'),
                          replace(self.selection, embedding='redimnet'), replace(self.selection, input_source='live'),
                          replace(self.selection, speaker_attribution='single_d1_late_labels')):
            with self.subTest(selection=selection):
                with self.assertRaises(ValueError):
                    subject.verify_native_variant(self.root/'RUNTIME_VARIANT.json', self.descriptor_pin, selection)
        with self.assertRaises(ValueError):
            subject.verify_native_variant(self.root/'other.json', self.descriptor_pin, self.selection)

    def test_integrated_option_requires_component_proof_and_is_explicit(self):
        original = self.verify()
        for source in ('live', 'saved'):
            for embedding in ('anonymous', 'redimnet', 'titanet'):
                selection = replace(self.selection, nemotron_profile='chunk52_threads2',
                                    input_source=source, embedding=embedding)
                subject.require_selection(selection)
                with self.assertRaisesRegex(ValueError, 'measured component'):
                    subject.verified_core_pin(original, selection, original.document())
                with self.assertRaisesRegex(ValueError, 'exact measured core'):
                    subject.verify_native_variant(self.root/'RUNTIME_VARIANT.json', self.descriptor_pin, selection)
        self.assertEqual(get_profile('chunk52_threads2').geometry, get_profile('chunk52').geometry)
        self.assertEqual(get_profile('chunk52_threads2').native_name, 'native_cm5_chunk52')
        with self.assertRaises(ValueError):
            replace(self.selection, nemotron_profile='chunk52_threads2', allow_experimental=False).validate()


class MeasuredComponentEvidenceTests(unittest.TestCase):
    def test_actual_read_only_component_receipt_and_no_quality_claim(self):
        result = subject.verify_component_evidence(subject.MEASURED_CORE_SHA256, subject.MEASURED_DESCRIPTOR_SHA256)
        self.assertEqual(result, subject.COMPONENT_REVIEW_SHA256)
        with self.assertRaises(ValueError):
            subject.verify_component_evidence('0'*64, subject.MEASURED_DESCRIPTOR_SHA256)

    def test_changed_component_receipt_rejected_before_admission(self):
        with tempfile.TemporaryDirectory(prefix='component-proof-', dir=os.environ.get('JP_BENCH_TEST_ROOT')) as directory:
            path = Path(directory).resolve()/'review.json'
            path.write_bytes(subject.COMPONENT_REVIEW.read_bytes()+b' ')
            with patch.object(subject, 'COMPONENT_REVIEW', path):
                with self.assertRaisesRegex(ValueError, 'pin mismatch'):
                    subject.verify_component_evidence(subject.MEASURED_CORE_SHA256, subject.MEASURED_DESCRIPTOR_SHA256)


if __name__ == '__main__':
    unittest.main()
