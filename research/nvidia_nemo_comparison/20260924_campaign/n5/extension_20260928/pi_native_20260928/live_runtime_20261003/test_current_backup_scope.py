"""Current referenced-data scope checks; see README_CURRENT_BACKUP_SCOPE.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import hashlib
import json
from pathlib import Path
import sys
import unittest
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root/('current-scope-review-'+uuid.uuid4().hex)
    output.mkdir()
    process = psutil.Process()
    (output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=process.pid,
        create_time=process.create_time(), affinity=process.cpu_affinity())))
    root = Path(__file__).parent
    rows = []
    for name in ('discover_production_backup_action_v3.py', 'test_current_backup_scope.py', 'README_CURRENT_BACKUP_SCOPE.md'):
        raw = (root/name).read_bytes()
        for folder in ('backup', 'independent-restore'):
            destination = output/folder/name
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(raw)
            assert destination.read_bytes() == raw
        if name.endswith('.py'):
            compile(raw, name, 'exec')
        rows.append(dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    (output/'SOURCE_CLOSED.json').write_text(json.dumps(dict(files=rows, independent_restore=True)))
    import discover_production_backup_action_v3 as discovery
    from test_production_scope import ScopeTests
    from prepare_production_scope import build_scope

    class CurrentScopeTests(unittest.TestCase):
        def setUp(self):
            ScopeTests.setUp(self)
            for version in (27, 28):
                profiles = self.campaign/('field-runtime-v%d-profiles'%version)
                profiles.mkdir()
                gallery = self.campaign/('field-runtime-v%d-galleries'%version)
                gallery.mkdir(exist_ok=True)
                value = dict(runtime_profile=dict(galleries={key:dict(
                    root=str(gallery/key/'people'), manifest_path=str(gallery/key/'MANIFEST.json'))
                    for key in ('E0', 'E1')}))
                (profiles/'baseline.json').write_text(json.dumps(value))
            for name in ('field-operator-sessions-v6', 'field-runtime-v2-profiles', 'field-runtime-v2-galleries'):
                (self.campaign/name).mkdir()
                (self.campaign/name/'old.txt').write_text('preserve unchanged')

        def get(self):
            value = discovery.discover(self.base, self.campaign, self.home)
            value['scope_locked_during_discovery'] = True
            return value

        def test_references_new_recordings_and_explicit_historical_inventory(self):
            value = self.get()
            roots = {row['source'] for row in value['roots']}
            for name in ('field-runtime-v27-profiles', 'field-runtime-v28-galleries',
                         'field-operator-sessions-v10108', 'field-operator-sessions-v10115'):
                self.assertIn(str(self.campaign/name), roots)
            self.assertIn(str(self.base/'data'), roots)
            self.assertIn(str(self.base/'config'), roots)
            exclusions = {row['source']:row for row in value['historical_roots_preserved_outside_copy']}
            old = self.campaign/'field-operator-sessions-v6'
            self.assertNotIn(str(old), roots)
            self.assertFalse(exclusions[str(old)]['new_backup_claimed'])
            self.assertEqual((old/'old.txt').read_text(), 'preserve unchanged')
            build_scope(value, [], value['total_bytes'], 180)

        def test_older_gallery_referenced_by_current_profile_is_included(self):
            path = self.campaign/'field-runtime-v28-profiles/baseline.json'
            value = json.loads(path.read_text())
            gallery = self.campaign/'field-runtime-v2-galleries'
            value['runtime_profile']['galleries']['E0'] = dict(root=str(gallery/'E0/people'),
                manifest_path=str(gallery/'E0/MANIFEST.json'))
            path.write_text(json.dumps(value))
            result = self.get()
            self.assertIn(str(gallery), {row['source'] for row in result['roots']})
            self.assertNotIn(str(gallery), {row['source'] for row in result['historical_roots_preserved_outside_copy']})

        def test_missing_referenced_data_cannot_become_complete(self):
            path = self.campaign/'field-runtime-v28-profiles/baseline.json'
            value = json.loads(path.read_text())
            gallery = self.campaign/'field-runtime-v999-galleries'
            value['runtime_profile']['galleries']['E1'] = dict(root=str(gallery/'E1/people'),
                manifest_path=str(gallery/'E1/MANIFEST.json'))
            path.write_text(json.dumps(value))
            result = self.get()
            self.assertIn(str(gallery), {row['path'] for row in result['missing_known_roots']})
            with self.assertRaises(ValueError):
                build_scope(result, [], 1000000, 180)

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CurrentScopeTests))
    (output/'RESULT.json').write_text(json.dumps(dict(passed=result.wasSuccessful(), checks=result.testsRun,
        native_actions=False, source_changed=False)))
    print(json.dumps(dict(output=str(output), passed=result.wasSuccessful(), checks=result.testsRun)))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
