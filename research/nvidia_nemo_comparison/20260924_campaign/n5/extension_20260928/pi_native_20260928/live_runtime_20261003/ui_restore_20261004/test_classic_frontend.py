"""Focused controller-facade checks without Tk/audio/model imports.

See README_CLASSIC_FRONTEND.md. CPU14 and early owner precede project imports.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest


def main():
    import psutil
    me = psutil.Process()
    me.cpu_affinity([14])
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-receipt', type=Path, required=True)
    parser.add_argument('--retained-release', type=Path, help='Optional immutable local presentation mirror; never opens a window')
    args = parser.parse_args()
    with args.owner_receipt.open('x', encoding='utf-8') as stream:
        json.dump(dict(pid=me.pid, create_time=me.create_time(), affinity=[14], purpose='classic frontend facade checks'), stream)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ui_restore_20261004.classic_frontend import ClassicController, caption_row, selection_label
    from profiles import RuntimeSelection

    config = dict(defaults=dict(caption_size='Compact', theme='Dark', preview_zoom=1.0,
                               direction='off', spatial_visualization=False, display_smoothing_ms=0, numbered_unknowns=False),
                  caption_sizes_px=dict(Compact=21, Normal=25), themes=dict(Dark={}, Contrast={}),
                  display_smoothing_ms=[0, 150, 300])

    class Store:
        def __init__(self):
            self.calls = []
            self.record = dict(session_id='one', status='stopped', created=1, duration_seconds=1,
                               processed_samples=16000, spec=dict(mode='processed'))
        def history(self, **kwargs):
            self.calls.append(('history', kwargs)); return dict(items=[self.record], next_cursor=None)
        def read(self, identifier):
            if identifier != 'one': raise KeyError(identifier)
            return self.record
        def latest_captions(self, identifier, limit, after_revision):
            self.calls.append(('captions', identifier, after_revision))
            return dict(items=[dict(caption_id='utterance', start_sample=0, end_sample=16000,
                                   text='Hello', speaker='Speaker 1', provisional=False,
                                   revision=1, provenance=dict(speaker_supported=True))],
                        changed=after_revision != 1, revision_cursor=1)
        def keep(self, identifier, include_raw=False):
            self.calls.append(('keep', identifier, include_raw)); self.record['status'] = 'kept'
        def discard(self, identifier): self.calls.append(('discard', identifier))
        def delete(self, identifier, confirm=False): self.calls.append(('delete', identifier, confirm))

    class Manager:
        def __init__(self, directory):
            self.data_root = directory
            self.binding = {}
            self.store = Store()
            self.process = None
            self.latest_health = self.latest_spatial = self.latest_diagnostic = None
            self.stop_requested = None
            self.export_task = None
            self.run_dir = None
            self.last = None
            self.calls = []
        def start(self, selection, policy, path, saved_session_id=None):
            self.calls.append(('start', selection.validate(), path, saved_session_id))
            self.process = object(); self.last = None
        def stop(self): self.calls.append(('stop',)); self.stop_requested = 1
        def poll(self): return self.last
        def poll_export(self): return None
        def active_session_id(self): return 'one' if self.process is not None else None
        def show_spatial(self, value): self.calls.append(('spatial', value))
        def export_recordings(self, identifiers, path): self.calls.append(('export', identifiers, path))

    class Checks(unittest.TestCase):
        def setUp(self):
            self.directory = tempfile.TemporaryDirectory()
            self.addCleanup(self.directory.cleanup)
            self.manager = Manager(Path(self.directory.name))
            self.now = 1.
            self.controller = ClassicController(self.manager, RuntimeSelection(), config, clock=lambda: self.now)
            self.controller._policy = lambda: None

        def test_start_consent_and_source(self):
            with self.assertRaises(ValueError): self.controller.start_live()
            self.assertFalse(self.manager.calls)
            self.controller.start_live(consent=True)
            self.assertEqual(self.manager.calls[0][0], 'start')
            self.assertEqual(self.controller.snapshot()['state'], 'STARTING')
            self.manager.latest_health = dict(value=dict(source_samples=160))
            self.assertEqual(self.controller.snapshot()['state'], 'RUNNING')
            self.controller.stop()
            self.assertEqual(self.controller.snapshot()['state'], 'STOPPING')

        def test_close_waits_for_owned_worker(self):
            self.controller.start_live(consent=True)
            self.controller.close()
            self.assertNotEqual(self.controller.snapshot()['state'], 'CLOSED')
            self.manager.process = None
            self.manager.last = dict(returncode=0, result=dict(failure=None), nested_source=dict(closed=True))
            self.assertEqual(self.controller.snapshot()['state'], 'CLOSED')

        def test_failure_exposes_actual_cause(self):
            self.manager.last = dict(returncode=1, result=dict(failure='Initialization: unavailable device'),
                                     nested_source=dict(state='SOURCE_NOT_STARTED'))
            view = self.controller.snapshot()
            self.assertEqual(view['state'], 'ERROR')
            self.assertIn('unavailable device', view['error'])
            self.assertIn('never opened', view['status'])

        def test_caption_labels_do_not_invent_asr_finality(self):
            self.controller.current_id = 'one'
            view = self.controller.snapshot()
            self.assertEqual(view['rows'][0]['label'], 'Speaker 1')
            self.assertEqual(view['rows'][0]['source_end_sec'], 1)
            self.assertFalse(view['rows'][0]['final'])
            self.controller.switch(mode='caption_only')
            self.assertEqual(self.controller.snapshot()['rows'][0]['label'], 'Transcription')
            row = dict(caption_id='one', start_sample=0, end_sample=1, text='x', provenance=dict(asr_final=True))
            self.assertTrue(caption_row(row, 'open_with_names')['final'])

        def test_caption_read_is_throttled(self):
            self.controller.current_id = 'one'
            self.controller.snapshot(); self.controller.snapshot()
            self.assertEqual(len([row for row in self.manager.store.calls if row[0] == 'captions']), 1)
            self.now += .25
            self.controller.snapshot()
            self.assertEqual(len([row for row in self.manager.store.calls if row[0] == 'captions']), 2)

        def test_post_stop_choice_waits_for_worker(self):
            self.controller.current_id = 'one'; self.manager.process = object()
            with self.assertRaises(RuntimeError): self.controller.session_action('save')
            self.manager.process = None
            self.controller.session_action('save', include_raw=False)
            self.assertIn(('keep', 'one', False), self.manager.store.calls)

        def test_settings_no_autostart_or_identity_override(self):
            for value in ({'auto_start_listening': True}, {'identity_threshold': .5}, {'spatial_visualization': 1}):
                with self.assertRaises(ValueError): self.controller.settings_update(value)
            self.controller.settings_update(dict(caption_size='Normal', spatial_visualization=True))
            restored = ClassicController(self.manager, RuntimeSelection(), config)
            self.assertEqual(restored.settings['caption_size'], 'Normal')
            self.assertFalse(restored.settings['auto_start_listening'])

        def test_saved_replay_never_opens_microphone(self):
            self.controller.selection = RuntimeSelection('pyannote', 'titanet', 'saved')
            with self.assertRaises(ValueError): self.controller.start_live(consent=True)
            self.controller.session_action('replay', identifier='one')
            self.assertEqual(self.manager.calls[0][1]['input_source'], 'saved')
            self.assertEqual(self.manager.calls[0][3], 'one')
            self.assertIn('TitaNet', selection_label(self.controller.selection))

        def test_device_view_does_not_draw_anchor_associations(self):
            self.manager.process = object()
            self.manager.latest_spatial = dict(published_monotonic=self.now, spatial=dict(
                state='RUNNING', association_reference_frame='anchor', arrows=[dict(id='beam', angle_deg=90)],
                associations=[dict(label='A', angle_deg=20)], motion=dict(valid=True, yaw_deg=5)))
            view = self.controller.snapshot()
            self.assertEqual(view['spatial_view']['associations'], [])
            self.assertEqual(view['spatial_view']['arrows'][0]['angle_deg'], 90)
            self.assertEqual(view['motion']['yaw_deg'], 5)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    if args.retained_release:
        from ui_restore_20261004.classic_frontend import load_retained_ui
        from runtime_support import digest
        ui, loaded_config = load_retained_ui(dict(installed_release=str(args.retained_release),
            installed_manifest_sha256=digest(args.retained_release/'RELEASE_MANIFEST.json')))
        if ui.__name__ != 'PrototypeUI' or loaded_config['design_width'] != 480:
            raise AssertionError('Retained portrait class/config did not load')
        if 'numpy' in sys.modules or 'edge_speech_pipeline' in sys.modules:
            raise AssertionError('Presentation import loaded a numerical/engine graph')
        print('Actual retained PrototypeUI imported without a window, NumPy or speech-engine graph.')
    heavy = [name for name in ('app.controller', 'app.pipeline', 'torch', 'onnxruntime') if name in sys.modules]
    if heavy:
        raise AssertionError('Frontend facade unexpectedly loaded inference modules: '+repr(heavy))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
