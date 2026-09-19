import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from measurement_app.recordings import latest_recording, recycle_latest


class RecordingDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'experiments'
        self.root.mkdir()

    def recording(self, name):
        path = self.root / name
        path.mkdir()
        (path / 'request.json').write_text(json.dumps({'setup': {'room_name': name}}))
        (path / 'result.json').write_text('{}')
        (path / 'SHA256SUMS.txt').write_text('manifest fixture')
        return path

    def recycle(self, path, root):
        target = self.base / ('recycled_' + path.name)
        self.assertEqual(path.resolve().parent, self.root)
        self.assertEqual(target.resolve().parent, self.base)
        path.rename(target)

    def test_empty_and_diagnostics_are_not_delete_targets(self):
        self.assertIsNone(latest_recording(self.root))
        self.recording('AUTO_USB24_fixture')
        self.assertIsNone(latest_recording(self.root))

    def test_recycles_latest_only_and_returns_restore_location(self):
        old = self.recording('JPXVF_A')
        newest = self.recording('JPXVF_Z')
        item = latest_recording(self.root)
        result = recycle_latest(self.root, item['id'], item['token'], self.recycle)
        self.assertTrue(old.exists())
        self.assertFalse(newest.exists())
        self.assertEqual(result['disposition'], 'Windows Recycle Bin')

    def test_newer_recording_rejects_stale_click(self):
        self.recording('JPXVF_A')
        item = latest_recording(self.root)
        self.recording('JPXVF_Z')
        recycler = Mock()
        with self.assertRaises(RuntimeError): recycle_latest(self.root, item['id'], item['token'], recycler)
        recycler.assert_not_called()

    def test_changed_token_and_traversal_rejected(self):
        self.recording('JPXVF_A')
        item = latest_recording(self.root)
        recycler = Mock()
        for name, token in [(item['id'], 'old'), ('../JPXVF_A', item['token'])]:
            with self.assertRaises(RuntimeError): recycle_latest(self.root, name, token, recycler)
        recycler.assert_not_called()

    def test_double_click_cannot_delete_the_previous_recording(self):
        old = self.recording('JPXVF_A')
        self.recording('JPXVF_Z')
        item = latest_recording(self.root)
        recycle_latest(self.root, item['id'], item['token'], self.recycle)
        with self.assertRaises(RuntimeError): recycle_latest(self.root, item['id'], item['token'], self.recycle)
        self.assertTrue(old.exists())

    def test_no_success_if_recycler_leaves_folder(self):
        self.recording('JPXVF_A')
        item = latest_recording(self.root)
        with self.assertRaises(RuntimeError): recycle_latest(self.root, item['id'], item['token'], Mock())

