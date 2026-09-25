"""A1 package, lifetime and final-P0 tests; see app/README_N3.md."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch
import numpy as np

sys.path[:0] = [str(Path(__file__).resolve().parents[1]),
               str(Path(__file__).resolve().parents[1] / 'vendor')]
from edge_speech_pipeline import n3_a1_adapter as adapter
from edge_speech_pipeline.n3_a1_service import OnnxRecognizer, Result
from prototype.app.n3_models import N3ResidentModels


class A1Tests(unittest.TestCase):
    def test_packaged_neural_and_stream_classes_match_reviewed_source(self):
        # Fixed normalized ASTs of the actual saved-audio parity implementation.
        expected = AST_BINDINGS
        folder = Path(adapter.__file__).parent
        for filename, classes in expected.items():
            tree = ast.parse((folder / filename).read_text(encoding='utf-8'))
            for name, digest in classes.items():
                node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
                self.assertEqual(hashlib.sha256(ast.dump(node).encode()).hexdigest(), digest)

    def owner(self):
        class Service:
            def reset_state(self): self.calls = []
            def transcribe(self, pcm):
                self.calls.append(pcm)
                return Result('before<EOU>after' if len(self.calls) == 1 else '', len(self.calls) == 1)
        owner = OnnxRecognizer.__new__(OnnxRecognizer)
        owner.service = Service(); owner.active = None; owner.serial = 0
        return owner

    def test_packaged_stream_preserves_tail_and_both_sides_of_eou(self):
        owner = self.owner(); observations = []
        for _ in range(2):
            stream = owner.stream(); stream.feed(np.array([.25], np.float32))
            rows = stream.finish_events()
            observations.append([(r['raw_text'], r['final']) for r in rows])
            self.assertEqual(stream.input_samples, 1)
            self.assertEqual(len(owner.service.calls), 17)
            self.assertEqual(np.frombuffer(owner.service.calls[0], '<i2')[0], 8192)
            self.assertEqual(stream.finish_events(), [])
            stream.close()
        self.assertEqual(observations[0], observations[1])
        self.assertEqual([text for text, final in observations[0] if final], ['before', 'after'])

    def test_p0_is_final_formatter_and_does_not_mutate_raw_stream(self):
        from edge_speech_pipeline.models import SherpaStream
        formatter = adapter.PunctuationOwner.__new__(adapter.PunctuationOwner)
        formatter._format = SherpaStream.punctuate
        formatter.punctuation = SimpleNamespace(add_punctuation_with_case=lambda text: 'Before after.')
        stream = adapter.A1Stream(SimpleNamespace(punctuation=formatter), SimpleNamespace(raw_text='before after'))
        result = stream.punctuate(stream.raw_text)
        self.assertEqual(result['text'], 'Before after.')
        self.assertEqual(stream.raw_text, 'before after')
        self.assertEqual(result['model_sha256'], '9d611f445fe4a46186080fe161be6059d87d72eb88d3a8cb00c1a06e83a6067e')
        self.assertEqual(result['status'], 'learned')

    def test_owner_close_breaks_model_cycle_even_when_stream_is_retained(self):
        owner = adapter.A1Recognizer.__new__(adapter.A1Recognizer)
        owner.recognizer = self.owner(); owner.punctuation = object(); owner.closed = False
        retained = owner.stream()
        owner.close(); owner.close()
        self.assertTrue(retained.closed)
        self.assertIsNone(retained.inner.owner.service)
        self.assertIsNone(owner.recognizer.active)
        self.assertIsNone(owner.punctuation)
        with self.assertRaisesRegex(RuntimeError, 'closed'): owner.stream()

    def test_caption_only_uses_one_a1_owner_across_independent_files(self):
        opened = []
        class Recognizer:
            def __init__(self, document, config): opened.append(self); self.closed = False
            def stream(self): return object()
            def close(self): self.closed = True
        resident = N3ResidentModels({'variant': 'A1'})
        with patch.object(adapter, 'A1Recognizer', Recognizer), \
             patch('prototype.app.n3_models.SpeakerModels', side_effect=AssertionError('Unexpected speaker load')):
            speakers, first = resident.acquire(object(), caption_only=True)
            _, second = resident.acquire(object(), caption_only=True)
            self.assertIsNone(speakers); self.assertIsNot(first, second)
            self.assertEqual((len(opened), resident.asr_loads, resident.speaker_loads), (1, 1, 0))
            resident.close()
        self.assertTrue(opened[0].closed); self.assertIsNone(resident.native_asr)

    def test_unadmitted_binding_rejected_before_loading_models(self):
        for document in ({}, {'variant': 'A2'}, {'variant': 'A1', 'right_context': 0}):
            with self.assertRaisesRegex(ValueError, 'binding differs'):
                adapter.validate_binding(document)


AST_BINDINGS = {'n3_a1_service.py': {'FeatureBuffer': '7b29b6f544536108fd97014409ab355e5673d59bc24aabb8cb9a20d14df6e823', 'OnnxService': '24908b6afebf8a8bb2d587c7bb4631ceda14f250497fbf524d3eff1e46a1683b'}, 'n3_a1_stream.py': {'ReferenceStream': 'bb3c877b6de9d84b714510f27fd4eef1b1add12e22e4de493a8e0d452ffbb244'}}

if __name__ == '__main__': unittest.main(verbosity=2)
