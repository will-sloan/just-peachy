"""Pinned external dependency checks; no native calls. README_XVF_RECOVERY.md."""
import ast
import base64
import hashlib
from pathlib import Path
import unittest
import launch_xvf_recovery_action as old
import launch_xvf_recovery_action_v2 as new

Q = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


class RecoveryDependencyTests(unittest.TestCase):
    def setUp(self):
        self.raw=(Q/'raw-qualification-06-monitor-01/NATIVE_PROBE.py.backup').read_bytes()
        self.payload=dict(native_probe_base64=base64.b64encode(self.raw).decode(),
            native_probe_bytes=new.PROBE_BYTES,native_probe_sha256=new.PROBE_SHA256)

    def test_actual_07_omits_dependency_and_external_probe_loads(self):
        package=Q/'audit-preparation/package-preparation-c7a15f5f050e428fa6ccec6498a9d780/package'
        self.assertFalse((package/'native_job_probe.py').exists())
        probe=new.load_reviewed_probe(self.payload)
        self.assertTrue(callable(probe.inspect));self.assertTrue(callable(probe.identity))
        self.assertNotEqual(probe.__name__,'__main__')

    def test_reviewed_backup_and_restore_match_bounded_stdlib_source(self):
        self.assertEqual(self.raw,(Q/'raw-qualification-06-monitor-01/NATIVE_PROBE.py.restore').read_bytes())
        self.assertEqual(len(self.raw),new.PROBE_BYTES)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),new.PROBE_SHA256)
        imports=set()
        for node in ast.walk(ast.parse(self.raw)):
            if isinstance(node,ast.Import):imports.update(item.name.split('.')[0] for item in node.names)
            elif isinstance(node,ast.ImportFrom):imports.add(node.module.split('.')[0])
        self.assertLessEqual(imports,{'base64','hashlib','json','os','pathlib','re','stat','subprocess','sys','time','resource','signal'})

    def test_missing_pin_or_extent_rejected(self):
        for key in self.payload:
            changed=dict(self.payload);del changed[key]
            with self.assertRaises(ValueError):new.load_reviewed_probe(changed)
        for updates in ({'native_probe_sha256':'a'*64},{'native_probe_bytes':1},{'native_probe_base64':'x'*32769}):
            with self.assertRaises(ValueError):new.load_reviewed_probe(dict(self.payload,**updates))

    def test_modified_code_or_invalid_encoding_rejected_before_exec(self):
        for raw in (self.raw+b'\n',self.raw.replace(b'import os',b'import xx',1)):
            with self.assertRaises(ValueError):new.load_reviewed_probe(dict(self.payload,native_probe_base64=base64.b64encode(raw).decode()))
        with self.assertRaises(ValueError):new.load_reviewed_probe(dict(self.payload,native_probe_base64='!!!!'))

    def test_no_recovery_command_or_wrapper_behavior_changed(self):
        self.assertEqual(new.SEQUENCE_SOURCE,old.SEQUENCE_SOURCE)
        self.assertEqual(new.DRIVER,old.DRIVER)
        tree=ast.parse(Path(new.__file__).read_text())
        dispatch=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='dispatch')
        self.assertNotIn("load_pure",ast.unparse(dispatch))
        compile(new.SEQUENCE_SOURCE+'\n'+new.DRIVER,'<recovery-v2-driver>','exec')


if __name__=='__main__':unittest.main()
