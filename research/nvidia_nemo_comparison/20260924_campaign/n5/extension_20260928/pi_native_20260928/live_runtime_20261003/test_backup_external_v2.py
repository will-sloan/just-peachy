"""Immutable08 overlay/refusal checks; README_BACKUP_EXTERNAL_V2.md."""
import base64
import hashlib
from pathlib import Path
import unittest
import backup_external_common_v2 as common
import backup_external_protocol_v2 as protocol
import launch_backup_external_action_v2 as launch

PACKAGE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/package-preparation-e0bd8f7d7cb2429eaf260c87133ae29a/package')


class ExternalBackupTests(unittest.TestCase):
    def test_only_whole_data_and_config_are_added(self):
        base='/home/peachyprototype/JustPeachy'
        for path in (base+'/data',base+'/config'):
            common.validate_native_source(path,is_file=False)
            with self.assertRaises(ValueError):common.validate_native_source(path,is_file=True)
        for path in (base,base+'/research/nemotron-20260928',base+'/install',base+'/unrelated',base+'/data/../unrelated'):
            with self.assertRaises(ValueError):common.validate_native_source(path,is_file=False)
        self.assertEqual(common.MAX_FILES,4096)

    def test_actual_resolved_key_and_outside_assets_do_not_reduce_copy(self):
        from prepare_production_scope_v2 import build_scope
        from desktop_consolidation_action import OWNED
        base='/home/peachyprototype/JustPeachy';data=base+'/data'
        members=[dict(path='/home/peachyprototype/Desktop/'+name,bytes=1) for name in OWNED]
        members.extend([dict(path=data+'/model.onnx',bytes=10),dict(path=data+'/tokens.txt',bytes=2)])
        historical=dict(source=base+'/research/nemotron-20260928/field-operator-sessions-v6',
            new_backup_claimed=False,source_mutated=False)
        discovery=dict(schema='just-peachy.production-scope-discovery.v1',scope_locked_during_discovery=True,
            issues=[],roots=[dict(source=data,destination='data')],members=members,boot_id='fixture',
            historical_roots_preserved_outside_copy=[historical])
        def pin(path,size,resolved=None):return dict(path=path,resolved=resolved or path,bytes=size,sha256='a'*64)
        evidence=dict(schema='just-peachy.selected-native-assets.v1',actual_hashes_verified=True,boot_id='fixture',
            assets=[pin(data+'/model.onnx',10),pin(data+'/tokens.txt',2),pin(base+'/install/models/other.onnx',1000)])
        spec,summary=build_scope(discovery,evidence,100,180)
        self.assertEqual(spec['maximum_external_asset_bytes'],10)
        self.assertEqual(summary['observed_nonmodel_bytes'],len(OWNED)+2)
        self.assertEqual(spec['external_assets'][0]['resolved_path'],data+'/model.onnx')
        classified=spec['asset_evidence_classification']
        self.assertEqual(len(classified['within_scope_copied_assets']),1)
        self.assertFalse(classified['independently_verified_outside_copy'][0]['current_guard_reverified'])
        self.assertEqual(spec['historical_roots_preserved_outside_copy'],[historical])
        evidence['assets'][0]['resolved']=data+'/different.onnx'
        with self.assertRaisesRegex(ValueError,'canonical discovery'):build_scope(discovery,evidence,100,180)

    def test_external_common_pin_and_exact_rc5_scope(self):
        raw=Path(common.__file__).read_bytes()
        payload=dict(external_backup_common=dict(schema=launch.SCHEMA,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode()))
        self.assertEqual(launch.external_bytes(payload),raw)
        payload['external_backup_common']['base64']=base64.b64encode(raw+b'\n').decode()
        with self.assertRaises(ValueError):launch.external_bytes(payload)
        common.validate_native_source(common.SELECTED_RELEASE,is_file=False)
        common.validate_native_source(common.SELECTED_RELEASE+'/app.py',is_file=True)
        for path in (common.SELECTED_RELEASE+'-other/app.py','/home/peachyprototype/JustPeachy/install/releases',common.SELECTED_RELEASE+'/../other'):
            with self.assertRaises(ValueError):common.validate_native_source(path,is_file=True)

    def test_selected_source_requires_exact_current_selector(self):
        row=dict(source=common.SELECTED_RELEASE+'/app.py',identity=dict(bytes=3),sha256='a'*64)
        census=dict(files=[row],directories=[],external_assets=[])
        with self.assertRaisesRegex(ValueError,'selector'):common.validate_native_census(census)
        selector=dict(source='/home/peachyprototype/JustPeachy/install/current.json',identity=dict(bytes=common.SELECTOR_PIN[0]),sha256=common.SELECTOR_PIN[1])
        census['files'].append(selector);common.validate_native_census(census)
        selector['sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'selector'):common.validate_native_census(census)

    def test_actual08_wrapper_and_probe_boundaries_compile_without_package_changes(self):
        helper={};source=(PACKAGE/'launch_raw_qualification_action.py').read_bytes()
        exec(compile(source,'<actual08helper>','exec'),helper)
        original=helper['wrapper_source']({})
        patched=launch.wrapper_overlay(original)
        self.assertLess(patched.index("put('OWNER.json'"),patched.index("overlay=out/'backup_reconciliation.py'"))
        self.assertIn("scope.verified_inventory(package,SETTINGS['package_manifest_sha256'])",patched)
        raw=(PACKAGE/'native_backup_probe.py').read_text();derived=protocol.native_probe_overlay(raw)
        self.assertIn(b'actual',source.lower())
        self.assertIn(common.SELECTED_RELEASE.encode(),Path(common.__file__).read_bytes())
        self.assertIn(b"external_pin=admission['payload']",derived)
        with self.assertRaises(ValueError):launch.wrapper_overlay(original.replace(' sys.path.insert(0,str(package))\n',''))
        with self.assertRaises(ValueError):protocol.native_probe_overlay(raw.replace("    common=load(package/'backup_reconciliation.py',request['backup_reconciliation_sha256'])",''))
        self.assertEqual(source,(PACKAGE/'launch_raw_qualification_action.py').read_bytes())


if __name__=='__main__':unittest.main()
