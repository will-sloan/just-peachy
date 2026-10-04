"""Actual scope transport regression and flattened prior accounting; README_BACKUP_RECONCILER_V5.md."""
import copy
import hashlib
import json
from pathlib import Path

import backup_external_common_v2 as common
import monitor_native_job as monitor
import reconcile_production_backup_external_v5 as target
import test_backup_reconciler_v4 as previous

PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


class ReconcilerV5Tests(previous.ReconcilerV4Tests):
    def setUp(self):self.old=previous.target;previous.target=target
    def tearDown(self):previous.target=self.old

    def test_actual_scope_catalog_begin_end_on_host_and_pinned_owner_binding(self):
        spec=common.strict((PRIVATE/'production-scope-06-preparation-01/SCOPE.json').read_bytes())
        original_path=common.Path
        self.assertEqual(target.validate_native_spec(common,spec),spec)
        self.assertIs(common.Path,original_path)
        job=dict(owner=dict(pid=1,start_ticks=2,boot_id='fixture'),unit='jp-v29-fixture.service',invocation_id='a'*32,control_group='/fixture')
        census=dict(schema='just-peachy.production-backup-census.v1',scope=spec,bytes=0,files=[],directories=[],external_assets=[])
        digest=hashlib.sha256(common.encoded(census)).hexdigest()
        status=dict(kind='STATUS',snapshot_locked=True,closed=False,observed_owner=job['owner'],census_sha256=digest,**job)
        _,Catalog=target.receiver_types(monitor,common);receiver=Catalog(PRIVATE,2*1024**2,job=job)
        receiver.feed(dict(kind='OWNER',owner=job['owner']));receiver.feed(status)
        receiver.feed(dict(kind='CENSUS_BEGIN',schema=census['schema'],scope=spec,bytes=0))
        receiver.feed(dict(kind='CENSUS_END',census_sha256=digest,snapshot=status))
        self.assertTrue(receiver.finished);self.assertEqual(receiver.census['scope'],spec)
        bad=dict(status,observed_owner=dict(job['owner'],start_ticks=3));receiver=Catalog(PRIVATE,2*1024**2,job=job)
        receiver.feed(dict(kind='OWNER',owner=job['owner']));receiver.feed(bad)
        with self.assertRaisesRegex(ValueError,'active snapshot'):receiver.feed(dict(kind='CENSUS_BEGIN',schema=census['schema'],scope=spec,bytes=0))

    def test_posix_validator_preserves_relative_traversal_overlap_and_alias_refusal(self):
        original=common.strict((PRIVATE/'production-scope-06-preparation-01/SCOPE.json').read_bytes())
        for invalid in ('relative/root','C:/windows/root','/home/peachyprototype/../outside'):
            spec=copy.deepcopy(original);spec['roots'][0]['source']=invalid
            with self.subTest(invalid=invalid),self.assertRaisesRegex(ValueError,'absolute source'):target.validate_native_spec(common,spec)
        spec=copy.deepcopy(original);spec['roots'][1]['source']=spec['roots'][0]['source']
        with self.assertRaisesRegex(ValueError,'Overlapping source'):target.validate_native_spec(common,spec)
        spec=copy.deepcopy(original);spec['roots'][1]['destination']=spec['roots'][0]['destination']
        with self.assertRaisesRegex(ValueError,'Overlapping restoration'):target.validate_native_spec(common,spec)

    def test_actual_two_failed_attempts_charge_physical_bytes_once_and_require_both(self):
        job=(PRIVATE/'production-backup-02-preparation-01/production-backup-02-JOB.json').read_bytes()
        paths=[PRIVATE/('production-backup-02-reconcile-'+number) for number in ('01','02')]
        output=PRIVATE/'production-backup-02-reconcile-03'
        got=target.prior_attempts_usage(common,paths,job,output)
        self.assertEqual(got['bytes'],sum(p.stat().st_size for path in paths for p in path.rglob('*') if p.is_file()))
        self.assertEqual(got['phases'],3);self.assertEqual(got['original_deadline_unix'],1791084418.9216013)
        with self.assertRaisesRegex(ValueError,'Every retained predecessor'):target.prior_attempts_usage(common,paths[1:],job,output)
        with self.assertRaisesRegex(ValueError,'Duplicate'):target.prior_attempts_usage(common,[paths[0],paths[0]],job,output)
