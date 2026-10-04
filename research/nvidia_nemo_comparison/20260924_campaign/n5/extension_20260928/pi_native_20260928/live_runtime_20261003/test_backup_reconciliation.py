"""Focused backup fault/isolation/protocol tests. README_PRODUCTION_BACKUP.md."""
import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import backup_reconciliation as backup
import monitor_native_job as monitor
from reconcile_production_backup import complete_backup, receiver_types, snapshot_matches


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve()
        self.source=self.root/'source';self.source.mkdir()
        (self.source/'empty').mkdir();(self.source/'first').write_bytes(b'unchanged')
        (self.source/'second').write_bytes(b'current private bytes')
        self.spec=dict(schema='just-peachy.production-backup-scope.v1',reviewed=True,
            roots=[dict(source=str(self.source),destination='retained')],external_assets=[],
            maximum_payload_bytes=1024,maximum_external_asset_bytes=0,runtime_seconds=180)
    def tearDown(self):self.temp.cleanup()

    def test_seed_hash_not_old_manifest_and_scope_isolation(self):
        census=backup.census(self.spec)
        seeds=self.root/'seeds';seeds.mkdir();(seeds/'first').write_bytes(b'unchanged')
        (seeds/'second').write_bytes(b'old private bytes')
        (seeds/'unrelated').write_bytes(b'preserve')
        plan=backup.seed_plan(census['files'],[dict(destination='retained',local=str(seeds))])
        self.assertEqual([r['action'] for r in plan],['reuse','fetch'])
        target=self.root/'payload';target.mkdir()
        for row,p in zip(census['files'],plan):
            backup.copy_seed(p['seed'] or row['source'],target/row['path'],row)
        self.assertEqual(backup.verify_payload(target,census['files'])['bytes'],census['bytes'])
        self.assertEqual((seeds/'unrelated').read_bytes(),b'preserve')
        self.assertTrue(any(row['path']=='retained/empty' for row in census['directories']))
        (target/'unlisted').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'unlisted'):backup.verify_payload(target,census['files'])

    def test_external_assets_exact_and_membership_changes_detected(self):
        model=self.source/'model';model.write_bytes(b'immutable bytes')
        self.spec['external_assets']=[dict(path=str(model),resolved_path=str(model),bytes=model.stat().st_size,
            sha256=hashlib.sha256(model.read_bytes()).hexdigest())]
        self.spec['maximum_external_asset_bytes']=model.stat().st_size
        first=backup.census(self.spec)
        self.assertNotIn('retained/model',[r['path'] for r in first['files']])
        self.assertEqual(len(first['external_assets']),1)
        (self.source/'third').write_bytes(b'new')
        self.assertNotEqual(first,backup.census(self.spec))
        model.write_bytes(b'changed bytes')
        with self.assertRaisesRegex(ValueError,'asset differs'):backup.census(self.spec)

    def test_native_exact_startup_files_without_broadening_config(self):
        for path,(size,sha) in backup.NATIVE_EXTRA_FILES.items():
            row=dict(source=path,identity=dict(bytes=size),sha256=sha)
            census=dict(files=[row],directories=[],external_assets=[])
            backup.validate_native_census(census)
            for key,value in (('sha256','a'*64),('identity',dict(bytes=size+1))):
                with self.assertRaisesRegex(ValueError,'pin differs'):
                    backup.validate_native_census(dict(census,files=[dict(row,**{key:value})]))
            with self.assertRaises(ValueError):backup.validate_native_source(path,is_file=False)
        for path in ('/home/peachyprototype/.config/autostart',
                     '/home/peachyprototype/.config/autostart/unrelated.desktop',
                     '/home/peachyprototype/JustPeachy/other.sh',
                     '/home/peachyprototype/.config/autostart/../secrets'):
            with self.assertRaises(ValueError):backup.validate_native_source(path,is_file=True)
        backup.validate_native_source('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v28-galleries',is_file=False)

    def test_scope_and_capacity_fail_closed(self):
        for name in ('../outside','/absolute','bad\\name','a/../b','bad:drive'):
            with self.subTest(name=name),self.assertRaises(ValueError):backup.relative(name)
        self.spec['roots'].append(dict(source=str(self.source/'empty'),destination='other'))
        with self.assertRaisesRegex(ValueError,'Overlapping source'):backup.census(self.spec)
        self.spec['roots'].pop();self.spec['maximum_payload_bytes']=1
        with self.assertRaisesRegex(ValueError,'reservation'):backup.census(self.spec)

    def test_directory_membership_refused_before_hashing(self):
        with patch.object(backup,'MAX_FILES',2),patch.object(backup,'digest') as hashed:
            with self.assertRaisesRegex(ValueError,'directory membership'):backup.census(self.spec)
            hashed.assert_not_called()

    def test_active_gate_never_fakes_closed_and_rejects_owner_change(self):
        Segment,_=receiver_types(monitor,backup)
        job=dict(owner=dict(pid=7,start_ticks=123,boot_id='boot'),unit='unit',invocation_id='id',control_group='group')
        status=dict(kind='STATUS',**job,observed_owner=job['owner'],snapshot_locked=True,closed=False,census_sha256='a'*64)
        self.assertTrue(snapshot_matches(status,job,'a'*64))
        row=dict(path='one',identity=dict(bytes=3),sha256=hashlib.sha256(b'abc').hexdigest())
        receiver=Segment(self.root,10,row,0,3,job=job,census_sha='a'*64)
        receiver.feed(dict(kind='OWNER',owner={'pid':8}));receiver.feed(status)
        receiver.feed(dict(kind='SEGMENT',entry=row,offset=0,count=3))
        receiver.feed(dict(kind='CHUNK',path='one',offset=0,data=base64.b64encode(b'abc').decode()))
        end=dict(kind='SEGMENT_END',path='one',offset=0,bytes=3,sha256=row['sha256'],snapshot=status)
        receiver.feed(end)
        self.assertFalse(receiver.segment_complete['snapshot']['closed'])
        self.assertEqual((self.root/'one').read_bytes(),b'abc')
        altered=dict(status,observed_owner=dict(pid=7,start_ticks=124,boot_id='boot'))
        self.assertFalse(snapshot_matches(altered,job,'a'*64))
        normal=monitor.SegmentReceiver(self.root,10,row,0,3)
        normal.feed(dict(kind='OWNER',owner={'pid':8}));normal.feed(status)
        with self.assertRaisesRegex(ValueError,'closed segment'):
            normal.feed(dict(kind='SEGMENT',entry=row,offset=0,count=3))

    def test_completion_requires_source_closure_and_matches_production_verifier(self):
        import prepare_package
        census=backup.census(self.spec);target=self.root/'payload';target.mkdir()
        for row in census['files']:backup.copy_seed(row['source'],target/row['path'],row)
        owner=dict(pid=7,start_ticks=123,boot_id='boot')
        closure=dict(owner=owner,invocation_id='id',closed=True,exact_owner_gone=True,cgroup_empty=True,
            job_exit=dict(natural_returncode=0,error=None))
        verified=dict(owner=owner,invocation_id='id',census_sha256=hashlib.sha256(backup.encoded(census)).hexdigest(),
            membership_before_after_equal=True,hashes_before_after_equal=True,external_asset_pins_equal=True,
            locks_held_during_verification=True)
        with self.assertRaisesRegex(ValueError,'closure'):
            complete_backup(backup,target,census,verified,dict(closure,closed=False))
        with self.assertRaisesRegex(ValueError,'closure'):
            complete_backup(backup,target,census,dict(verified,hashes_before_after_equal=False),closure)
        done=complete_backup(backup,target,census,verified,closure)
        manifest=backup.encoded(census['files']);raw=backup.encoded(done)
        backup.write(self.root/'MANIFEST.json',manifest);backup.write(self.root/'COMPLETE.json',raw)
        proof=dict(scope='selected-release-and-user-data',root=str(target),manifest_path=str(self.root/'MANIFEST.json'),
            completion_path=str(self.root/'COMPLETE.json'),manifest_sha256=hashlib.sha256(manifest).hexdigest(),
            completion_sha256=hashlib.sha256(raw).hexdigest())
        self.assertEqual(prepare_package.verify_full_backup(dict(full_backup=proof)),[manifest,raw])
        (target/census['files'][0]['path']).write_bytes(b'altered')
        with self.assertRaises(ValueError):prepare_package.verify_full_backup(dict(full_backup=proof))

    def test_actual_next_precheck_decoder_ignores_reference_receipts(self):
        import ast,json
        import host_operations
        source=(host_operations.B/'desktop-exit-20261003/preparation-expansion-baseline-v3/SOURCE.py.backup').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),'0aab2f169e6a00f9dd22ae0d09e0fdceaa684e1b1ccc5f55ac3c2a3f0cf16ceb')
        tree=ast.parse(source)
        node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NATIVE' for t in n.targets))
        native=ast.literal_eval(node.value)
        owner=dict(pid=7,start_ticks=123,boot_id='ab46de82-1a91-4f10-9846-098376e85f4d')
        prefix='live-runtime-tests-20261003/production-backup-01'
        directory=self.root/prefix;directory.mkdir(parents=True)
        backup.write(directory/'OWNER.json',backup.encoded(owner))
        unit=dict(owner=owner,unit='jp-v29-production-backup-01.service',invocation_id='a'*32,
            control_group='/user.slice/example',main_pid=7,deadline_monotonic=1000,
            idle_timeout_seconds=300,runtime_max_seconds=180)
        raw=backup.encoded(unit);backup.write(directory/'UNIT_OWNERSHIP.json',raw)
        job=dict(owner=owner,unit=unit['unit'],invocation_id=unit['invocation_id'],control_group=unit['control_group'],boot_id=owner['boot_id'])
        entry=dict(path='UNIT_OWNERSHIP.json',identity=dict(bytes=len(raw)),sha256=hashlib.sha256(raw).hexdigest())
        closed=dict(job,closed=True,exact_owner_gone=True,cgroup_empty=True)
        pin=host_operations.closed_unit_owner(job,raw,entry,closed)
        for name in ('SNAPSHOT_LOCKS','SNAPSHOT_READY','SOURCE_VERIFIED','SNAPSHOT_RELEASED','FINALIZE'):
            backup.write(directory/(name+'.json'),backup.encoded(dict(owner=dict(owner,pid=999))))
        patched=host_operations.bind_native_owner_references(native,{}, {prefix+'/UNIT_OWNERSHIP.json':pin})
        first=patched.index('HISTORICAL.update(');last=patched.index("units=command(",first)
        def actual_identity(value):
            self.assertEqual(set(value),{'pid','start_ticks','boot_id'})
            self.assertEqual(value,owner)
        scope=dict(Path=Path,root=self.root,HISTORICAL={},NESTED={},PRIOR=[],hashlib=hashlib,json=json,
            strict=backup.strict,sha=lambda raw:hashlib.sha256(raw).hexdigest(),identity=actual_identity,
            ticks=lambda pid:None,boot=owner['boot_id'],RID='field-runtime-v28',
            allow_live=lambda *args:(_ for _ in ()).throw(AssertionError('Unexpected live owner')))
        exec(compile(patched[first:last],'<actual-next-native-owner-precheck>','exec'),scope)
        self.assertEqual(scope['count'],2)
        self.assertEqual(scope['all_ids'],{(owner['boot_id'],7,123)})
        with self.assertRaises(ValueError):host_operations.closed_unit_owner(job,raw,entry,dict(closed,closed=False))
        with self.assertRaises(ValueError):host_operations.closed_unit_owner(job,raw,dict(entry,sha256='0'*64),closed)


if __name__=='__main__':unittest.main()
