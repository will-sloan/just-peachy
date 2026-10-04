"""Pure restore refusal tests; no desktop access. README_DESKTOP_ACTIVATION.md."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from desktop_rollback_action import checked_restore_bytes,read_small


class RestoreTests(unittest.TestCase):
    def test_file_input_rejects_oversize_and_shared_links_before_loading(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('LIVE_QUALIFICATION_TEST_ROOT')) as directory:
            root=Path(directory);path=root/'synthetic.desktop';path.write_bytes(b'private fixture')
            self.assertEqual(read_small(path,64),b'private fixture')
            with self.assertRaises(ValueError):read_small(path,1)
            with self.assertRaises(ValueError):read_small(root,64)
            linked=root/'shared.desktop';os.link(path,linked)
            with self.assertRaises(ValueError):read_small(path,64)

    def test_exact_independent_copies_and_current_identity_are_required(self):
        previous=b'[Desktop Entry]\nName=Retained\n'
        current=b'[Desktop Entry]\nName=Candidate\n'
        desktop=Path('/synthetic/Desktop/Just Peachy.desktop')
        backup=Path('/synthetic/field-runtime-v29-desktop-backup-'+'a'*32)
        manifest='b'*64
        plan=dict(previous_sha256=hashlib.sha256(previous).hexdigest(),
            next_sha256=hashlib.sha256(current).hexdigest(),desktop=str(desktop),
            backup=str(backup),manifest_sha256=manifest,autostart=False)
        def checked(p=plan,left=previous,right=previous,now=current):
            return checked_restore_bytes(p,left,right,now,desktop=desktop,
                backup_root=backup,manifest_sha256=manifest)
        self.assertEqual(checked(),previous)
        failures=[dict(left=b'changed'),dict(right=b'changed'),dict(now=b'edited'),
            dict(p=dict(plan,desktop='/unrelated/file.desktop')),
            dict(p=dict(plan,backup='/unrelated')),
            dict(p=dict(plan,manifest_sha256='c'*64)),dict(p=dict(plan,autostart=True))]
        for change in failures:
            with self.subTest(change=change),self.assertRaises(ValueError):checked(**change)
        large=bytes(65537)
        oversize=dict(plan,previous_sha256=hashlib.sha256(large).hexdigest())
        with self.assertRaises(ValueError):checked(p=oversize,left=large,right=large)


if __name__=='__main__':unittest.main()
