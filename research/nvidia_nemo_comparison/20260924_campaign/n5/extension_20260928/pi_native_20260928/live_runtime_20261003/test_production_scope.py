"""Focused scope completeness and current-reference checks. README_PRODUCTION_SCOPE.md."""
import json
from pathlib import Path
import tempfile
import unittest
import discover_production_backup_action as discovery
from prepare_production_scope import build_scope


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name).resolve();self.base=self.home/'JustPeachy';self.campaign=self.base/'research/nemotron-20260928'
        self.campaign.mkdir(parents=True)
        for version,number in (('27',10108),('28',10112)):
            release=self.campaign/('field-runtime-v'+version);release.mkdir()
            recording=self.campaign/('field-operator-sessions-v'+str(number));recording.mkdir()
            (recording/'kept.wav').write_bytes(b'private')
            (release/'control').mkdir();(release/'recordings/recording-01').mkdir(parents=True);(release/'backups').mkdir()
            (release/'control/RELEASE.json').write_text(json.dumps(dict(manager_root=str(release),
                recording_roots=[str(recording)],allocation=dict(recording_slots=['recording-01']))))
        # An additional historical/current root outside both release lists must
        # still be included, as must calibration and the actual selected source.
        (self.campaign/'field-operator-sessions-v10115').mkdir()
        (self.campaign/'field-operator-sessions-v10115/audio').write_bytes(b'more')
        (self.campaign/'field-runtime-v28-galleries').mkdir()
        for path in (self.base/'data',self.base/'config',self.home/'Desktop',self.home/'.config/kanshi',self.home/'.config/autostart',self.base/'install/releases/actual'):
            path.mkdir(parents=True,exist_ok=True)
        (self.base/'config/calibration.json').write_text('{}')
        (self.base/'data/settings.json').write_text('{}')
        (self.base/'install/current.json').write_text(json.dumps(dict(relative_path='releases/actual')))
        (self.base/'install/releases/actual/app.py').write_text('actual source')
        for path in (self.base/'start-prototype.sh',self.home/'.config/kanshi/config',self.home/'.config/autostart/just-peachy.desktop'):
            path.write_text('retained')
        from desktop_consolidation_action import OWNED
        for name in OWNED:(self.home/'Desktop'/name).write_text('retained')

    def get(self):
        value=discovery.discover(self.base,self.campaign,self.home)
        value['scope_locked_during_discovery']=True
        return value

    def test_all_release_recordings_newer_root_calibration_and_selected_source(self):
        value=self.get();roots={row['source'] for row in value['roots']}
        for path in ('field-operator-sessions-v10108','field-operator-sessions-v10112','field-operator-sessions-v10115','field-runtime-v28-galleries'):
            self.assertIn(str(self.campaign/path),roots)
        self.assertIn(str(self.base/'config/calibration.json'),roots)
        self.assertIn(str(self.base/'install/releases/actual'),roots)
        self.assertFalse(value['missing_known_roots'])
        spec,summary=build_scope(value,[],value['total_bytes'],180)
        self.assertEqual(len(spec['roots']),len(roots));self.assertFalse(summary['complete_backup_claimed'])

    def test_missing_known_recording_never_silently_omitted(self):
        path=self.campaign/'field-operator-sessions-v10108'
        (path/'kept.wav').unlink();path.rmdir()
        (self.campaign/'field-runtime-v27/recordings/recording-01/STARTED.json').write_text('{}')
        value=self.get();self.assertEqual(len(value['missing_known_roots']),1)
        with self.assertRaisesRegex(ValueError,'missing'):build_scope(value,[],100000,180)

    def test_actual_empty_slot_proves_uncreated_reservation_but_owner_refuses(self):
        import backup_external_common as common
        path=self.campaign/'field-operator-sessions-v10108';(path/'kept.wav').unlink();path.rmdir()
        value=self.get();self.assertEqual(value['slot_absence_proofs'][0]['state'],'UNUSED_NEVER_STARTED')
        spec,summary=build_scope(value,[],100000,180)
        self.assertEqual(len(summary['explicit_absent_unused_slots']),1)
        self.assertNotIn(str(path),[row['source'] for row in spec['roots']])
        common.validate_absent_reserved_slots(spec,str(self.home))
        (self.campaign/'field-runtime-v27/recordings/recording-01/OWNER.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'missing'):build_scope(self.get(),[],100000,180)
        with self.assertRaisesRegex(ValueError,'evidence'):common.validate_absent_reserved_slots(spec,str(self.home))

    def test_reserved_only_proof_rechecked_before_native_backup(self):
        import backup_external_common as common
        path=self.campaign/'field-operator-sessions-v10108';(path/'kept.wav').unlink();path.rmdir()
        root=self.campaign/'field-runtime-v27';receipt=discovery.small(root/'control/RELEASE.json')
        row=dict(policy_sha256=receipt['sha256'],slot='recordings/recording-01',operation=dict(
            schema='just-peachy.offline-runtime-operation.v1',root=str(path),slot='recording-01',policy_sha256=receipt['sha256']))
        (root/'recordings/recording-01/RESERVED.json').write_text(json.dumps(row))
        value=self.get();self.assertEqual(value['slot_absence_proofs'][0]['state'],'RESERVED_NEVER_STARTED')
        spec,_=build_scope(value,[],100000,180);common.validate_absent_reserved_slots(spec,str(self.home))
        path.mkdir()
        with self.assertRaisesRegex(ValueError,'now exists'):common.validate_absent_reserved_slots(spec,str(self.home))

    def test_external_weight_only_exact_current_extent_and_capacity(self):
        model=self.base/'install/releases/actual/model.onnx';model.write_bytes(b'weight')
        value=self.get();pin=dict(path=str(model),resolved_path=str(model),bytes=6,sha256='a'*64)
        spec,summary=build_scope(value,[pin],value['total_bytes']-6,180)
        self.assertEqual(spec['maximum_external_asset_bytes'],6)
        with self.assertRaises(ValueError):build_scope(value,[dict(pin,bytes=7)],100000,180)
        with self.assertRaises(ValueError):build_scope(value,[],value['total_bytes']-1,180)
        member=next(row for row in value['members'] if row['path'].endswith('settings.json'))
        with self.assertRaisesRegex(ValueError,'model weights'):
            build_scope(value,[dict(path=member['path'],resolved_path=member['path'],bytes=member['bytes'],sha256='b'*64)],100000,180)


if __name__=='__main__':unittest.main()
