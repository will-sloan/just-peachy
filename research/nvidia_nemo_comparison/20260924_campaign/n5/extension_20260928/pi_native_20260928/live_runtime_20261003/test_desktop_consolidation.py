"""No-device exact11 archive/restore tests. README_DESKTOP_CONSOLIDATION.md."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import desktop_consolidation_action as action


class DesktopConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.desktop=self.root/'Desktop';self.desktop.mkdir()
        self.archive=self.root/'archive';self.selected=next(iter(action.OWNED))
        baseline=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/operation-post-soak-baseline-02/dispatch/RESULT.json')
        rows=json.loads(baseline.read_bytes())['desktop_startup_files'];self.originals={}
        for row in rows:
            name=Path(row['path']).name
            if name in action.OWNED:
                raw=row['text'].encode();self.originals[name]=raw
                self.assertEqual((len(raw),action.sha(raw)),action.OWNED[name])
                (self.desktop/name).write_bytes(raw)
        self.current=b'[Desktop Entry]\nName=Just Peachy\nExec=/synthetic/unified\n'
        (self.desktop/self.selected).write_bytes(self.current)
        (self.desktop/'unrelated.txt').write_bytes(b'preserve me');(self.desktop/'personal').mkdir()

    def consolidate(self):
        return action.archive_shortcuts(self.desktop,self.archive,self.selected,
            self.originals[self.selected],action.sha(self.current))

    def test_actual11pins_archive_readback_and_explicit_restore(self):
        result=self.consolidate()
        self.assertEqual(result['owned_shortcuts_remaining'],1)
        self.assertEqual(set(p.name for p in self.desktop.iterdir()),{self.selected,'unrelated.txt','personal'})
        for name,raw in self.originals.items():
            self.assertEqual((self.archive/'before'/name).read_bytes(),raw)
            self.assertEqual((self.archive/'restore'/name).read_bytes(),raw)
        self.assertEqual(len(list((self.archive/'archived').iterdir())),10)
        restored=action.restore_shortcuts(self.desktop,self.archive)
        self.assertEqual(restored['status'],'ALL11_RETAINED_SHORTCUTS_RESTORED_NOT_STARTED')
        for name,raw in self.originals.items():self.assertEqual((self.desktop/name).read_bytes(),raw)
        self.assertEqual((self.desktop/'unrelated.txt').read_bytes(),b'preserve me')
        self.assertEqual((self.archive/'unified.desktop.restore').read_bytes(),self.current)

    def test_changed_owned_file_refuses_before_archive(self):
        name=next(name for name in action.OWNED if name!=self.selected)
        (self.desktop/name).write_bytes(b'edited')
        with self.assertRaisesRegex(ValueError,'pins'):self.consolidate()
        self.assertFalse(self.archive.exists());self.assertEqual(len(list(self.desktop.iterdir())),13)

    def test_copy_failure_removes_no_desktop_files(self):
        with patch.object(action,'write',side_effect=OSError('synthetic full disk')):
            with self.assertRaises(OSError):self.consolidate()
        self.assertEqual(len(list(self.desktop.iterdir())),13)
        self.assertFalse((self.archive/'PLAN.json').exists())

    def test_restore_refuses_altered_independent_copy_and_unrelated_changes(self):
        self.consolidate();name=next(iter(self.originals))
        (self.archive/'restore'/name).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'restore'):action.restore_shortcuts(self.desktop,self.archive)
        (self.archive/'restore'/name).write_bytes(self.originals[name])
        (self.desktop/'unrelated.txt').write_bytes(b'user changed this')
        with self.assertRaisesRegex(ValueError,'membership'):action.restore_shortcuts(self.desktop,self.archive)
        self.assertEqual((self.desktop/'unrelated.txt').read_bytes(),b'user changed this')


if __name__=='__main__':unittest.main()
