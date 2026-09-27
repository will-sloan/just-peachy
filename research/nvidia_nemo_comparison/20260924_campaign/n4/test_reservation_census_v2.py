"""Fixture provenance failures; README_RESERVATION_CENSUS_V2.md."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import bind, freeze, load
import reservation_census_v2 as subject


class FixtureProvenance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.local = Path(self.temp.name); self.stage = self.local/'stage'; self.stage.mkdir()
        self.parent = self.local/'n4/restart-plan-probe-v1'
        self.method = 'test_production_reconstruction_refuses_partial_upstream'
        self.producer = self.stage/'probe_restart_plan.py'; self.producer.write_text('# admitted producer')
        self.test = self.stage/'test_restart_plan.py'; self.test.write_text('def '+self.method+'():\n    pass\n')
        self.fixture = self.parent/'tests/partial/ADMISSION.json'
        freeze(self.fixture, dict(owner=dict(pid=1, create_time=0), code=[]))
        self.owner = dict(pid=12345, create_time=123456.0)
        self.admission = self.parent/'ADMISSION.json'
        freeze(self.admission, dict(owner=self.owner, code=[bind(self.producer), bind(self.test)]))
        self.terminal = self.parent/'RESULT.json'
        freeze(self.terminal, dict(status='PASS', admission=bind(self.admission), owner=self.owner))
        self.log = self.parent/'tests.txt'; self.log.write_text(self.method+' (module.Test) ... ok\n')
        self.entry = dict(fixture=bind(self.fixture), parent_admission=bind(self.admission),
            parent_terminal=bind(self.terminal), parent_owner=self.owner, producer=bind(self.producer),
            test_source=bind(self.test), test_method=self.method, test_log=bind(self.log),
            classification='PRESERVED_NON_EXECUTION_TEST_FIXTURE', physical_bytes_retained=True)
        self.lookup_calls = []
        self.patch = patch.object(subject, 'HERE', self.stage); self.patch.start(); self.addCleanup(self.patch.stop)
    def lookup(self, owner):
        self.lookup_calls.append(owner); return None
    def check(self, entry=None, lookup=None):
        return subject.validate_fixture(self.entry if entry is None else entry, self.local,
                                        lookup=self.lookup if lookup is None else lookup)
    def rewrite(self, path, value):
        import json
        path.write_text(json.dumps(value), encoding='utf-8')
    def update_admission(self, value):
        self.rewrite(self.admission, value); self.entry['parent_admission'] = bind(self.admission)
        terminal = load(self.terminal); terminal['admission'] = bind(self.admission)
        self.rewrite(self.terminal, terminal); self.entry['parent_terminal'] = bind(self.terminal)
    def test_sentinel_is_retained_without_synthetic_pid_lookup_or_allocation(self):
        r = self.check()
        self.assertEqual(r['state'], 'NON_EXECUTION_FIXTURE'); self.assertNotIn('owner', r)
        self.assertTrue(r['physical_bytes_retained']); self.assertEqual(self.lookup_calls, [self.owner])
        self.assertEqual(bind(self.fixture), self.entry['fixture'])
    def test_changed_fixture_is_not_excluded(self):
        self.fixture.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Binding changed'): self.check()
    def test_active_parent_and_access_denial_refuse(self):
        with self.assertRaisesRegex(ValueError, 'still active'): self.check(lookup=lambda _: object())
        def denied(_): raise PermissionError('unknown owner')
        with self.assertRaises(PermissionError): self.check(lookup=denied)
    def test_parent_pid_reuse_identity_must_still_match_receipt(self):
        e = deepcopy(self.entry); e['parent_owner']['create_time'] += 1
        with self.assertRaisesRegex(ValueError, 'identity differs'): self.check(e)
    def test_foreign_parent_and_foreign_log_refuse(self):
        other = self.local/'other'; other.mkdir()
        for key, path in [('parent_admission', self.admission), ('test_log', self.log)]:
            foreign = other/path.name; foreign.write_bytes(path.read_bytes())
            e = dict(self.entry); e[key] = bind(foreign)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Foreign'): self.check(e)
    def test_parent_terminal_join_and_owner_mismatch_refuse(self):
        original = load(self.terminal)
        for key, value in [('admission', {}), ('owner', dict(pid=54321, create_time=1234.0))]:
            terminal = dict(original, **{key: value}); self.rewrite(self.terminal, terminal)
            self.entry['parent_terminal'] = bind(self.terminal)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'join differs|owner differs'): self.check()
    def test_parent_orphan_child_refuses(self):
        terminal = load(self.terminal); terminal['child'] = dict(pid=99, create_time=100.0)
        self.rewrite(self.terminal, terminal); self.entry['parent_terminal'] = bind(self.terminal)
        with self.assertRaisesRegex(ValueError, 'child remains active'):
            self.check(lookup=lambda x: object() if x['pid'] == 99 else None)
    def test_unadmitted_source_refuses(self):
        a = load(self.admission); a['code'] = [bind(self.producer)]; self.update_admission(a)
        with self.assertRaisesRegex(ValueError, 'not admitted'): self.check()
    def test_preserved_old_source_snapshot_matches_original_admission(self):
        saved = self.parent/'source'/self.test.name; saved.parent.mkdir()
        saved.write_bytes(self.test.read_bytes()); self.test.write_text('# later derivative')
        self.entry['test_source'] = bind(saved)
        self.assertEqual(self.check()['state'], 'NON_EXECUTION_FIXTURE')
        self.assertEqual(subject.source_binding(self.test.name, load(self.admission), self.parent), bind(saved))
    def test_wrong_old_snapshot_bytes_refuse_even_when_rebound(self):
        saved = self.parent/'source'/self.test.name; saved.parent.mkdir()
        saved.write_text('def '+self.method+'():\n    return False\n')
        self.entry['test_source'] = bind(saved)
        with self.assertRaisesRegex(ValueError, 'source bytes differ'): self.check()
    def test_foreign_snapshot_path_refuses_even_with_matching_bytes(self):
        saved = self.local/self.test.name; saved.write_bytes(self.test.read_bytes())
        self.entry['test_source'] = bind(saved)
        with self.assertRaisesRegex(ValueError, 'Foreign fixture source snapshot'): self.check()
    def test_missing_method_and_missing_log_execution_refuse(self):
        self.test.write_text('def different():\n    pass\n'); self.entry['test_source'] = bind(self.test)
        a = load(self.admission); a['code'] = [bind(self.producer), bind(self.test)]; self.update_admission(a)
        with self.assertRaisesRegex(ValueError, 'method missing'): self.check()
        self.test.write_text('def '+self.method+'():\n    pass\n'); self.entry['test_source'] = bind(self.test)
        a['code'] = [bind(self.producer), bind(self.test)]; self.update_admission(a)
        self.log.write_text('different (module.Test) ... ok\n'); self.entry['test_log'] = bind(self.log)
        with self.assertRaisesRegex(ValueError, 'not recorded'): self.check()
    def test_no_blanket_tests_directory_exclusion(self):
        for relative in ['unknown/tests/partial/ADMISSION.json',
                         'restart-plan-probe-v1/data/partial/ADMISSION.json',
                         'restart-plan-probe-v1/tests/unknown/ADMISSION.json']:
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                subject.fixture_source(Path(relative))
    def test_manifest_duplicate_count_and_schema_refuse(self):
        cases = [dict(entries=[self.entry, self.entry], fixture_count=2),
                 dict(entries=[self.entry], fixture_count=2),
                 dict(entries=[self.entry], fixture_count=1, schema='other')]
        for index, changes in enumerate(cases):
            p = self.local/f'manifest-{index}.json'
            freeze(p, dict(dict(schema=subject.SCHEMA, physical_bytes_retained=True), **changes))
            with self.subTest(index=index), self.assertRaises(ValueError):
                subject.read_fixtures(bind(p), self.local, lookup=self.lookup)
    def test_retained_failed_probe_fixture_is_valid_but_not_execution(self):
        failed = self.parent/'FAILED.json'; failed.write_bytes(self.terminal.read_bytes())
        e = dict(self.entry, parent_terminal=bind(failed)); r = self.check(e)
        self.assertEqual(r['state'], 'NON_EXECUTION_FIXTURE')
    def test_scope_or_path_relabelling_refuses(self):
        for key, value in [('physical_bytes_retained', False), ('classification', 'CLOSED_OWNER'),
                           ('test_method', 'another')]:
            e = dict(self.entry, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError): self.check(e)


if __name__ == '__main__': unittest.main()
