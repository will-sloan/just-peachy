"""Exact10 GUI-export output guard checks. README_HISTORY_EXPORT_CHECK.md."""
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

import launch_history_export_action as action

PACKAGE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/package-preparation-3b8ec5e1d68d406ea1f126e834c16288/package')


class HistoryExportTests(unittest.TestCase):
    def test_actual10_guard_retains_pending_and_bounds_zip_pair(self):
        manifest=json.loads((PACKAGE/'PACKAGE_MANIFEST.json').read_bytes())
        pin=next(row for row in manifest['files'] if row['path']=='launch_raw_qualification_action.py')
        raw=(PACKAGE/pin['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),pin['sha256'])
        function=next(node for node in ast.parse(raw).body if isinstance(node,ast.FunctionDef) and node.name=='wrapper_source')
        helper={};exec(compile(ast.Module(body=[function],type_ignores=[]),'<frozen10-wrapper>','exec'),helper)
        settings=dict(budget=dict(maximum_output_bytes=1024**2,maximum_files=256))
        source=action.export_wrapper(helper['wrapper_source'],settings)
        node=next(node for node in ast.parse(source).body if isinstance(node,ast.FunctionDef) and node.name=='bounded_output')
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary).resolve()
            partial=out/('selected-recording.zip.part-'+'a'*32);partial.write_bytes(b'archive')
            os.link(partial,out/'selected-recording.zip')
            pending=out/'receipt.json.pending';pending.write_bytes(b'data');os.link(pending,out/'receipt.json')
            scope=dict(SETTINGS=settings,out=out,os=os,Path=Path,stat=stat,json=json)
            exec(compile(ast.Module(body=[node],type_ignores=[]),'<exact10-history-export-guard>','exec'),scope)
            self.assertEqual(scope['bounded_output'](),7+4+4)
            os.link(partial,out/'unrelated')
            with self.assertRaisesRegex(ValueError,'unrecognized_hardlink'):scope['bounded_output']()

    def test_shared_helper_is_exact10_and_driver_compiles(self):
        pin=next(row for row in json.loads((PACKAGE/'PACKAGE_MANIFEST.json').read_bytes())['files'] if row['path']=='owned_export.py')
        self.assertEqual(hashlib.sha256(action.EXPORT_HELPER.encode()).hexdigest(),pin['sha256'])
        compile(action.DRIVER,'<actual-history-export-ui-driver>','exec')
        tree=ast.parse(action.DRIVER)
        self.assertFalse(any(isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and
                             node.func.attr in ('start','begin','append_processed','append_raw') for node in ast.walk(tree)))


if __name__=='__main__':unittest.main()
