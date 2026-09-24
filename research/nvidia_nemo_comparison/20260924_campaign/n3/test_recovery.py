"""Model-free regressions for recovery and export metadata; see README_REUSE.md."""
import json
from pathlib import Path
import tempfile
import unittest

from export_a1 import configure_encoder_export
from reuse_results import bound, check_prototype_changes, evidence_files, load, reuse, sha


class ExportPortsTests(unittest.TestCase):
    def encoder(self):
        class Encoder:
            @property
            def disabled_deployment_input_names(self):
                return set()
            @property
            def input_names(self):
                return [name for name in ['audio_signal', 'length', 'cache_last_channel',
                    'cache_last_time', 'cache_last_channel_len', 'bypass_pre_encode']
                    if name not in self.disabled_deployment_input_names]
            def forward_for_export(self, audio_signal, length, cache_last_channel=None,
                                   cache_last_time=None, cache_last_channel_len=None):
                return audio_signal, length, cache_last_channel, cache_last_time, cache_last_channel_len
        return Encoder()

    def test_export_mapping_keeps_audio_and_every_recurrent_cache(self):
        encoder = self.encoder()
        original = type(encoder)
        inputs = ['audio', 'lengths', 'channel', 'time', 'cache_lengths']
        configure_encoder_export(encoder)
        # The pinned checker consumes the argument list backwards. An extra
        # trailing optional port previously shifted it and discarded audio.
        remaining = list(inputs)
        feed = {name: remaining.pop() for name in reversed(encoder.input_names)}
        self.assertEqual(feed['audio_signal'], 'audio')
        self.assertEqual(feed['cache_last_channel_len'], 'cache_lengths')
        self.assertEqual(list(encoder.forward_for_export(*inputs)), inputs)
        self.assertIn('bypass_pre_encode', original().input_names)

    def test_unknown_signature_refuses_workaround(self):
        encoder = self.encoder()
        encoder.forward_for_export = lambda x: x
        with self.assertRaisesRegex(ValueError, 'signature'):
            configure_encoder_export(encoder)


class ReuseTests(unittest.TestCase):
    def test_other_inference_source_change_blocks_reuse(self):
        with self.assertRaisesRegex(ValueError, 'Unreviewed prototype'):
            check_prototype_changes({'vendor/edge_speech_pipeline/models.py': 'old'},
                                    {'vendor/edge_speech_pipeline/models.py': 'new'})

    def test_native_only_change_is_explicitly_reported(self):
        name = 'vendor/edge_speech_pipeline/n3_asr_native.py'
        self.assertEqual(check_prototype_changes({name: 'old'}, {name: 'new'}), [name])

    def test_failed_results_are_never_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'RESULT.json').write_text(json.dumps(dict(status='FAILED')))
            with self.assertRaisesRegex(ValueError, 'complete error-free'):
                evidence_files(folder)

    def test_copy_preserves_original_receipt_and_labels_no_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            origin = folder / 'RESULT.json'
            origin.write_text(json.dumps(dict(status='COMPLETE', completed=1, total=1)))
            digest = sha(origin)
            row = dict(copies=[bound(origin)], references=[], destination=str(folder / 'copy'),
                       original_result=bound(origin), original_job=dict(id='fixture'))
            reuse(dict(jobs={'fixture': row}), 'fixture')
            self.assertEqual(sha(folder / 'copy/RESULT.json'), digest)
            self.assertEqual(sha(origin), digest)
            self.assertFalse(load(folder / 'copy/REUSE_RECEIPT.json')['new_inference'])
            with self.assertRaisesRegex(ValueError, 'Preserve existing'):
                reuse(dict(jobs={'fixture': row}), 'fixture')

    def test_changed_event_refuses_before_any_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            event = folder / 'events.jsonl'
            event.write_text('original')
            row = dict(copies=[], references=[bound(event)], destination=str(folder / 'copy'))
            event.write_text('modified')
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                reuse(dict(jobs={'fixture': row}), 'fixture')
            self.assertFalse((folder / 'copy').exists())


if __name__ == '__main__':
    unittest.main()
