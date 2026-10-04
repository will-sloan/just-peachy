"""Selected export driver host contract; no native run. README_NATIVE_EXPORT.md."""
import hashlib
import ast
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

from launch_recording_export_action import DRIVER,export_wrapper
from storage import SessionStore,StoragePolicy
from verify_recording_offload import verify


class ExportTests(unittest.TestCase):
    def test_atomic_export_link_is_counted_once_and_unrelated_links_refused(self):
        # This external action must work against the exact frozen07 wrapper,
        # independently of later mutable helper changes.
        package=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/package-preparation-c7a15f5f050e428fa6ccec6498a9d780/package')
        manifest=json.loads((package/'PACKAGE_MANIFEST.json').read_bytes())
        pin=next(row for row in manifest['files'] if row['path']=='launch_raw_qualification_action.py')
        raw=(package/pin['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),pin['sha256'])
        function=next(node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='wrapper_source')
        frozen={};exec(compile(ast.Module(body=[function],type_ignores=[]),'<exact-frozen07-wrapper>','exec'),frozen)
        wrapper_source=frozen['wrapper_source']
        settings=dict(budget=dict(maximum_output_bytes=1024**2,maximum_files=256))
        source=export_wrapper(wrapper_source,settings)
        node=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='bounded_output')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp).resolve();partial=out/('selected-recording.zip.part-'+'a'*32)
            partial.write_bytes(b'archive');os.link(partial,out/'selected-recording.zip')
            scope=dict(SETTINGS=settings,out=out,os=os,Path=Path)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-export-output-guard>','exec'),scope)
            self.assertEqual(scope['bounded_output'](),7)
            os.link(partial,out/'unrelated')
            with self.assertRaisesRegex(ValueError,'hardlink'):scope['bounded_output']()

    def test_selected_exact_archive_and_original_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();data=root/'recordings';out=root/'output';out.mkdir();package=root/'package';package.mkdir()
            (package/'BINDING.json').write_text(json.dumps(dict(storage_policy=dict(reserve_bytes=0,reserve_fraction=0))))
            store=SessionStore(data,StoragePolicy(reserve_bytes=0,reserve_fraction=0))
            ids=[]
            for index in range(2):
                spool=store.begin(dict(sample_rate=16000,duration_seconds=.01))
                spool.append_processed(0,struct.pack('<f',index/4)*64);spool.stop(64);spool.keep();ids.append(spool.session_id)
            before=[store.read(value) for value in ids];store.close()
            fake=types.SimpleNamespace(RLIMIT_AS=1,setrlimit=lambda *args:None)
            with patch.dict(sys.modules,resource=fake),patch.object(sys,'argv',
                ['export_driver.py',str(out),str(package),ids[1],str(data)]):
                exec(compile(DRIVER,'<reviewed-export-driver-host-fixture>','exec'),dict(__name__='__main__'))
            receipt=json.loads((out/'EXPORT.json').read_bytes());archive=out/'selected-recording.zip'
            self.assertEqual(receipt['session_id'],ids[1]);self.assertTrue(receipt['original_session_preserved'])
            with zipfile.ZipFile(archive) as zipped:self.assertEqual({name.split('/')[0] for name in zipped.namelist()},{ids[1]})
            result=verify(archive,receipt['zip_sha256'],receipt['zip_bytes'],1024**2)
            self.assertEqual(result['status'],'VERIFIED_COMPLETE_COPY')
            store=SessionStore(data,StoragePolicy(reserve_bytes=0,reserve_fraction=0))
            self.assertEqual([store.read(value) for value in ids],before);store.close()
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),receipt['zip_sha256'])


if __name__=='__main__':unittest.main()
