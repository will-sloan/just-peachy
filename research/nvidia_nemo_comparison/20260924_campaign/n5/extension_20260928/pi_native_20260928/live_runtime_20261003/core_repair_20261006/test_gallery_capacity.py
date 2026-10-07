"""Declared gallery metadata/copy capacity contract. See README_GALLERY_CAPACITY.md."""
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from personal_gallery import summaries, snapshot_used_gallery
from runtime_support import DiskBudget, digest


class GalleryCapacityContract(unittest.TestCase):
    def test_more_than_256_profiles_and_16_MiB_copy_use_actual_capacity(self):
        with tempfile.TemporaryDirectory(prefix='gallery-capacity-') as temporary:
            root = Path(temporary)
            source, target = root/'people', root/'used'
            source.mkdir()
            reserve, payload = 64*1024**2, 17*1024**2
            if shutil.disk_usage(root).free < reserve+payload+2*1024**2:
                self.skipTest('The declared physical free-space floor is unavailable')
            for index in range(257):
                identifier = str(uuid.UUID(int=index+1))
                person = source/identifier
                person.mkdir()
                (person/'person.json').write_text(json.dumps(dict(id=identifier,
                    name='Declared profile '+str(index), references=[])), encoding='utf-8')
                if index < 17:
                    # Copy-only fixture bytes: no speaker vectors or model input.
                    with (person/'declared-copy-fixture.bin').open('xb') as stream:
                        for _ in range(64):
                            stream.write(b'\0'*16384)
            with patch('personal_gallery.layout', return_value=(source,{},None)), \
                    patch('personal_gallery.resource_snapshot', return_value=dict(available_ram=1024**3)):
                people = summaries({},SimpleNamespace(embedding='redimnet'),root)
            self.assertEqual(len(people),257)
            budget = DiskBudget(1,reserve_bytes=reserve)
            descriptor = snapshot_used_gallery(source,target,budget,lambda:None)
            self.assertGreater(descriptor['bytes'],16*1024**2)
            self.assertEqual(descriptor['file_count'],274)
            self.assertNotIn('files',descriptor)
            membership = json.loads((target/'GALLERY_MANIFEST.json').read_bytes())
            self.assertEqual(len(membership['files']),274)
            self.assertEqual(membership['bytes'],descriptor['bytes'])
            self.assertEqual(digest(target/'GALLERY_MANIFEST.json'),descriptor['manifest_sha256'])
            for member in membership['files']:
                self.assertEqual(digest(source/member['path']),member['sha256'])
                self.assertEqual(digest(target/member['path']),member['sha256'])
            self.assertGreater(budget.accepted,budget.maximum)
            self.assertGreaterEqual(shutil.disk_usage(root).free,reserve)


if __name__ == '__main__':
    unittest.main()
