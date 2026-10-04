"""Changed native/embedding separation; see README_NATIVE_SELECTION.md."""
import copy
import unittest
from unittest.mock import patch

from installed_engine import native_documents
from profiles import RuntimeSelection


class NativeSelectionTests(unittest.TestCase):
    def test_titanet_gallery_remains_selected_with_native_override(self):
        old = dict(titanet_manifest='gallery-specific-manifest',
                   titanet_manifest_sha256='e'*64, embedding_namespace='titanet-v1',
                   native_runtime_files=['old-native'], nemotron_model='old-model')
        original = copy.deepcopy(old)
        native = dict(nemotron_model='same-pinned-model', nemotron_model_sha256='a'*64,
                      nemotron_library='isolated-wrapper', nemotron_library_sha256='b'*64,
                      native_runtime_files=['verified-core'], streaming_profile='native_cm5_chunk52',
                      native_device=dict(kind='cpu', gpu_index=-1))
        class Verified:
            def document(self):
                return copy.deepcopy(native)
        verified = Verified()
        selection = RuntimeSelection('nemotron', 'titanet', 'live', 'chunk52_threads2', True)
        binding = dict(native_variants=dict(chunk52_threads2=dict(path='pinned-descriptor', sha256='c'*64)))
        with patch('native_variant.verify_native_variant', return_value=verified) as verify:
            merged, sealed_document, token = native_documents(binding, selection, old)
        verify.assert_called_once_with('pinned-descriptor', 'c'*64, selection)
        self.assertIs(token, verified)
        self.assertEqual(sealed_document, native)
        self.assertEqual(old, original)
        self.assertEqual(merged['embedding_namespace'], 'titanet-v1')
        self.assertEqual(merged['titanet_manifest'], 'gallery-specific-manifest')
        self.assertEqual(merged['native_runtime_files'], ['verified-core'])
        self.assertNotIn('embedding_namespace', sealed_document)

    def test_variant_missing_or_unpinned_fails_before_verifier(self):
        selection = RuntimeSelection('nemotron', 'redimnet', 'saved', 'chunk52_threads2', True)
        with patch('native_variant.verify_native_variant') as verify:
            for binding in ({}, dict(native_variants=dict(chunk52_threads2=dict(path='unbound')))):
                with self.assertRaises(ValueError):
                    native_documents(binding, selection, {})
            verify.assert_not_called()

    def test_original_profile_never_loads_variant(self):
        selection = RuntimeSelection('nemotron', 'redimnet', 'live', 'chunk52', True)
        document = dict(native_runtime_files=['original'])
        with patch('native_variant.verify_native_variant') as verify:
            model, native, token = native_documents({}, selection, document)
            self.assertIs(model, document)
            self.assertIs(native, document)
            self.assertIsNone(token)
            verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
