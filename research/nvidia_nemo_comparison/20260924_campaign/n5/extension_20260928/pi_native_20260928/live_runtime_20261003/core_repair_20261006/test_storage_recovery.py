"""Isolated recovery/projection contract tests. README_STORAGE_RECOVERY.md.

No model, audio device, SSH, production database, or physical-full-disk test.
"""
import array
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
# Unchanged profiles/runtime_support are dependencies of launcher, not native work.
sys.path.insert(1,str(HERE.parent))
import storage
import storage_support


class StorageRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='peachy-storage-contract-')
        self.root = Path(self.temporary.name)/'recordings'
        self.policy = storage.StoragePolicy(reserve_bytes=5*1024**2,reserve_fraction=0,segment_samples=4)
        self.store = storage.SessionStore(self.root,self.policy)

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def recording(self, *, kept=False):
        spool = self.store.begin(dict(duration_seconds=10,metadata_reserve_bytes=4*1024**2,
                                      metadata_split='text1_sqlite1_v2',terminal_metadata_reserve_bytes=256*1024))
        spool.append_processed(0,array.array('f',[0.0,0.1,0.2,0.0]).tobytes())
        self.store.write_caption(spool.session_id,'parent',0,4,'synthetic content',provisional=False)
        self.store.write_event(spool.session_id,'synthetic',dict(value='private fixture content'))
        artifact = spool.directory/'work'/'producer'/'fixture.json'
        artifact.parent.mkdir(parents=True)
        artifact.write_text('{"fixture":true}',encoding='utf-8')
        self.store.register_artifact(spool.session_id,'work/producer/fixture.json')
        spool.stop()
        if kept:
            self.store.keep(spool.session_id)
        return spool.session_id

    def assert_removed(self, identifier):
        self.assertFalse((self.root/'sessions'/identifier).exists())
        self.assertFalse(self.store.deletion_pending(identifier))
        with self.store._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sessions WHERE id=?',(identifier,)).fetchone()[0],0)
            for table in ('segments','artifacts','captions','events','metadata_usage','terminal_events','terminal_metadata_usage','caption_projections'):
                self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table+' WHERE session_id=?',(identifier,)).fetchone()[0],0)

    def fingerprint(self, identifier):
        directory = self.root/'sessions'/identifier
        files = {path.relative_to(directory).as_posix():path.read_bytes() for path in directory.rglob('*') if path.is_file()}
        with self.store._db() as db:
            rows = {table:[dict(row) for row in db.execute('SELECT * FROM '+table+' WHERE '+('id' if table=='sessions' else 'session_id')+'=?',(identifier,))]
                    for table in ('sessions','segments','captions','events','artifacts','metadata_usage')}
        return files,rows

    def test_discard_removes_content_is_retry_safe_and_preserves_kept(self):
        kept = self.recording(kept=True)
        target = self.recording()
        before = self.fingerprint(kept)
        receipt = self.store.discard(target)
        self.assert_removed(target)
        self.assertEqual(receipt['status'],'discarded')
        self.assertEqual(self.store.discard(target),receipt)
        self.assertEqual(before,self.fingerprint(kept))
        with self.assertRaises(storage.StorageError):
            self.store.discard(kept)

    def test_interruption_after_audio_removal_recovers_only_explicit_intent(self):
        kept,target = self.recording(kept=True),self.recording()
        before = self.fingerprint(kept)
        original = self.store._remove_audio
        def interrupted(*args,**kwargs):
            original(*args,**kwargs)
            raise OSError('isolated interruption after media deletion')
        with mock.patch.object(self.store,'_remove_audio',side_effect=interrupted):
            with self.assertRaises(OSError):
                self.store.discard(target)
        self.assertTrue(self.store.deletion_pending(target))
        self.store = storage.SessionStore(self.root,self.policy)
        self.assert_removed(target)
        self.assertEqual(before,self.fingerprint(kept))

    def test_interrupted_database_purge_resumes_without_restoring_content(self):
        target = self.recording()
        original = self.store._purge_session_table
        def interrupted(table,identifier,**kwargs):
            original(table,identifier,**kwargs)
            if table == 'captions':
                raise OSError('isolated interruption between table batches')
        with mock.patch.object(self.store,'_purge_session_table',side_effect=interrupted):
            with self.assertRaises(OSError):
                self.store.discard(target)
        self.store = storage.SessionStore(self.root,self.policy)
        self.assert_removed(target)

    def test_interruption_after_owner_unlink_recovers_empty_owned_directory(self):
        target = self.recording()
        directory = self.root/'sessions'/target
        original = Path.rmdir
        def interrupted(path):
            if path == directory:
                raise OSError('isolated interruption before final rmdir')
            return original(path)
        with mock.patch.object(Path,'rmdir',interrupted):
            with self.assertRaises(OSError):
                self.store.discard(target)
        self.assertTrue(directory.exists())
        self.assertFalse((directory/'owner.json').exists())
        self.store = storage.SessionStore(self.root,self.policy)
        self.assert_removed(target)

    def test_completion_receipt_failure_resumes_when_session_is_already_absent(self):
        target = self.recording()
        original = storage._atomic_json
        def interrupted(path,value):
            if path.parent.name == 'deletion_receipts':
                raise OSError('isolated receipt write failure')
            return original(path,value)
        with mock.patch.object(storage,'_atomic_json',side_effect=interrupted):
            with self.assertRaises(OSError):
                self.store.discard(target)
        self.store = storage.SessionStore(self.root,self.policy)
        self.assert_removed(target)

    def test_unrelated_child_rejects_before_creating_intent_or_deleting_audio(self):
        target = self.recording()
        directory = self.root/'sessions'/target
        (directory/'unrelated.txt').write_text('must survive',encoding='utf-8')
        before = self.fingerprint(target)
        with self.assertRaises(storage.UnsafePathError):
            self.store.discard(target)
        self.assertFalse(self.store.deletion_pending(target))
        self.assertEqual(before,self.fingerprint(target))

    def test_live_or_shared_replay_lease_prevents_delete(self):
        target = self.recording()
        with self.store._session_lease(target,shared=True):
            with self.assertRaises(storage.ActiveSessionError):
                self.store.discard(target)
        self.assertEqual(self.store.read(target)['status'],'stopped')

    def test_wrong_store_intent_cannot_adopt_orphan_or_delete_retained_recording(self):
        target = self.recording(kept=True)
        before = self.fingerprint(target)
        path = self.store._deletion_path(target)
        storage._atomic_json(path,dict(schema='just-peachy.session-deletion.v1',store_id='0'*32,
                                      session_id=target,request_kind='delete',requested_unix=1,
                                      origin_status='kept',directories=[]))
        with self.assertRaises(storage.UnsafePathError):
            self.store.recover_deletions()
        path.unlink()
        self.assertEqual(before,self.fingerprint(target))

    def test_pragma_error_closes_connection_and_retains_extended_code(self):
        error = sqlite3.OperationalError('isolated disk I/O error')
        error.sqlite_errorcode = 778
        error.sqlite_errorname = 'SQLITE_IOERR_WRITE'
        connection = mock.Mock()
        connection.execute.side_effect = error
        with mock.patch.object(storage.sqlite3,'connect',return_value=connection):
            with self.assertRaises(sqlite3.OperationalError) as raised:
                with self.store._db(operation='isolated PRAGMA fault'):
                    pass
        connection.close.assert_called_once()
        self.assertIs(raised.exception,error)
        self.assertEqual(error.storage_diagnostic['chain'][0]['sqlite_errorcode'],778)
        self.assertEqual(error.storage_diagnostic['chain'][0]['sqlite_primary_errorcode'],10)

    @staticmethod
    def part(identifier,text,start=0,end=4):
        return dict(caption_id=identifier,start_sample=start,end_sample=end,text=text,speaker=None,
                    provisional=False,provenance=dict(ui_projection=dict(token_range=[0,1])))

    def test_partial_word_correction_retires_obsolete_child_and_preserves_repetitions(self):
        target = self.recording()
        self.store.replace_caption_projection(target,'parent',[self.part('parent::old','particul')],projection_revision=1)
        self.store.replace_caption_projection(target,'parent',[self.part('parent::new','particular; very, very good')],projection_revision=2)
        page = self.store.latest_captions(target)
        self.assertEqual([row['text'] for row in page['items']],['particular; very, very good'])
        self.assertEqual([row['caption_id'] for row in page['items']],['parent::new'])
        with self.store._db() as db:
            events = db.execute('SELECT COUNT(*) FROM events WHERE session_id=?',(target,)).fetchone()[0]
            charged = db.execute('SELECT used_bytes FROM metadata_usage WHERE session_id=?',(target,)).fetchone()[0]
        duplicate = self.store.replace_caption_projection(target,'parent',[self.part('parent::new','particular; very, very good')])
        self.assertFalse(duplicate['changed'])
        with self.store._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events WHERE session_id=?',(target,)).fetchone()[0],events)
            self.assertEqual(db.execute('SELECT used_bytes FROM metadata_usage WHERE session_id=?',(target,)).fetchone()[0],charged)

    def test_projection_failure_rolls_back_all_parts_and_retirement(self):
        target = self.recording()
        self.store.replace_caption_projection(target,'parent',[self.part('parent::old','stable')])
        before = self.fingerprint(target)
        original = self.store._charge_metadata
        calls = [0]
        def fault(*args,**kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise OSError('isolated second-part accounting write failure')
            return original(*args,**kwargs)
        with mock.patch.object(self.store,'_charge_metadata',side_effect=fault):
            with self.assertRaises(OSError):
                self.store.replace_caption_projection(target,'parent',[self.part('parent::a','new'),self.part('parent::b','second')])
        self.assertEqual(before,self.fingerprint(target))

    def test_historical_metadata_quota_cannot_block_speech_stop_or_terminal_facts(self):
        spool = self.store.begin(dict(duration_seconds=10,metadata_reserve_bytes=600,metadata_split='text1_sqlite1_v2'))
        identifier = spool.session_id
        with self.store._db() as db:
            db.execute('INSERT INTO metadata_usage VALUES(?,?,?)',(identifier,10000000,300))
        self.store.write_caption(identifier,'beyond-old-quota',0,0,'capacity permits this',provisional=False)
        self.store.write_terminal_event(identifier,'session_cleanup',dict(completed=['synthetic']))
        self.assertEqual(spool.stop()['status'],'stopped')
        with self.store._db() as db:
            usage = db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',(identifier,)).fetchone()
        self.assertGreater(usage['used_bytes'],10000000)
        self.assertEqual(usage['limit_bytes'],300)
        self.store.discard(identifier)
        self.assert_removed(identifier)

    def test_legacy_schema_migration_preserves_kept_content_and_old_ledger(self):
        path = HERE.parent/'stabilization_20261005'/'storage.py'
        spec = importlib.util.spec_from_file_location('legacy_peachy_storage_fixture',path)
        legacy = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = legacy
        try:
            spec.loader.exec_module(legacy)
            root = Path(self.temporary.name)/'legacy'
            old = legacy.SessionStore(root,legacy.StoragePolicy(reserve_bytes=5*1024**2,reserve_fraction=0,segment_samples=4))
            spool = old.begin(dict(duration_seconds=1))
            spool.append_processed(0,array.array('f',[0.0,0.1,0.0,0.2]).tobytes())
            old.write_caption(spool.session_id,'old-parent',0,4,'retained historical content',provisional=False)
            spool.stop()
            old.keep(spool.session_id)
            metadata = old.read(spool.session_id)
            directory = root/'sessions'/spool.session_id
            files = {child.relative_to(directory).as_posix():child.read_bytes() for child in directory.rglob('*') if child.is_file()}
            with old._db() as db:
                ledger = tuple(db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',(spool.session_id,)).fetchone())
            old.close()
            external = storage.SessionStore(root,self.policy,read_only=True)
            before_database = (root/'history.sqlite3').read_bytes()
            self.assertEqual(external.latest_captions(spool.session_id)['items'][0]['text'],'retained historical content')
            self.assertEqual(external.caption_page(spool.session_id)['items'][0]['projection_order'],0)
            self.assertIsNone(external.caption_parents(spool.session_id,['old-parent'])['items'][0]['projection_parent'])
            external.close()
            self.assertEqual((root/'history.sqlite3').read_bytes(),before_database)
            migrated = storage.SessionStore(root,self.policy)
            self.assertEqual(migrated.read(spool.session_id),metadata)
            self.assertEqual(migrated.latest_captions(spool.session_id)['items'][0]['text'],'retained historical content')
            self.assertEqual(files,{child.relative_to(directory).as_posix():child.read_bytes() for child in directory.rglob('*') if child.is_file()})
            with migrated._db() as db:
                self.assertEqual(tuple(db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',(spool.session_id,)).fetchone()),ledger)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM caption_projections').fetchone()[0],0)
            migrated.close()
        finally:
            sys.modules.pop(spec.name,None)

    def test_source_paging_frozen_parents_and_stale_projection(self):
        target = self.recording()
        for number in reversed(range(6)):
            self.store.write_caption(target,'source-%d'%number,number*10,number*10+4,'word-%d'%number,provisional=False)
        newest = self.store.caption_page(target,limit=3)
        self.assertEqual([row['caption_id'] for row in newest['items']],['source-3','source-4','source-5'])
        older = self.store.caption_page(target,limit=3,before=newest['next_cursor'])
        self.assertEqual([row['caption_id'] for row in older['items']],['source-0','source-1','source-2'])
        self.store.replace_caption_projection(target,'parent',[self.part('parent::a','supported')],projection_revision=3)
        stale = self.store.replace_caption_projection(target,'parent',[self.part('parent::old','obsolete')],projection_revision=2)
        self.assertTrue(stale['stale'])
        frozen = self.store.caption_parents(target,['parent'],limit=1)
        self.assertEqual(frozen['items'][0]['text'],'supported')
        self.assertFalse(frozen['truncated'])

    def test_coarse_and_aligned_child_clocks_keep_native_parent_token_order(self):
        target = self.recording()
        parts = [self.part('parent::a','first',11,12),self.part('parent::b','second',0,20),
                 self.part('parent::c','third',14,15),self.part('parent::d','fourth',0,20)]
        self.store.replace_caption_projection(target,'parent',parts,projection_revision=1,
                                              projection_source_start_sample=0)
        self.store.replace_caption_projection(target,'later',[
            self.part('later::a','later first',40,41),self.part('later::b','later second',30,31)],
            projection_source_start_sample=20)
        page = self.store.latest_captions(target)
        self.assertEqual([row['caption_id'] for row in page['items']],
                         ['parent::a','parent::b','parent::c','parent::d','later::a','later::b'])
        self.assertEqual([row['start_sample'] for row in page['items'][:4]],[11,0,14,0])
        self.assertEqual([row['projection_source_start'] for row in page['items']],[0,0,0,0,20,20])
        changed = [self.part('parent::a','first revised',11,12),self.part('parent::c','third revised',14,15)]
        self.store.replace_caption_projection(target,'parent',changed,projection_revision=2)
        frozen = self.store.caption_parents(target,['parent'])
        self.assertEqual([row['projection_source_start'] for row in frozen['items']],[0,0])
        latest = self.store.caption_page(target,limit=2)
        previous = self.store.caption_page(target,limit=2,before=latest['next_cursor'])
        self.assertEqual([row['caption_id'] for row in latest['items']],['later::a','later::b'])
        self.assertEqual([row['caption_id'] for row in previous['items']],['parent::a','parent::c'])

    def test_file_plan_includes_existing_db_sidecars_and_does_not_clear_journal(self):
        directory = Path(self.temporary.name)/'plan'
        directory.mkdir()
        with (directory/'history.sqlite3').open('wb') as stream:
            stream.truncate(40*1024**2)
        journal = directory/'history.sqlite3-journal'
        journal.write_bytes(b'preserved synthetic hot journal')
        before = journal.read_bytes()
        usage = types.SimpleNamespace(total=1024**3,free=512*1024**2)
        plan = storage_support.sqlite_file_size_plan(directory,1024**2,self.policy,usage)
        self.assertGreater(plan['file_limit_bytes'],32*1024**2)
        self.assertEqual(journal.read_bytes(),before)
        with self.assertRaises(OSError):
            storage_support.sqlite_file_size_plan(directory,1024**2,self.policy,types.SimpleNamespace(total=1024**3,free=1024))

    def test_file_limit_raise_is_finite_and_respects_inherited_hard_limit(self):
        fake = types.SimpleNamespace(RLIMIT_FSIZE=1,RLIM_INFINITY=-1)
        limits = [32*1024**2,128*1024**2]
        fake.getrlimit = lambda kind:tuple(limits)
        fake.setrlimit = lambda kind,value:limits.__setitem__(slice(None),list(value))
        plan = dict(file_limit_bytes=48*1024**2)
        with mock.patch.object(storage_support.sys,'platform','linux'),mock.patch.dict(sys.modules,resource=fake),mock.patch.object(storage_support,'sqlite_file_size_plan',return_value=plan):
            storage_support.ensure_sqlite_file_limit(self.root,self.policy)
            self.assertEqual(limits,[48*1024**2,128*1024**2])
            with mock.patch.object(storage_support,'sqlite_file_size_plan',return_value=dict(file_limit_bytes=256*1024**2)):
                with self.assertRaises(OSError):
                    storage_support.ensure_sqlite_file_limit(self.root,self.policy)

    def test_shared_file_plan_supports_only_safe_owned_database_basenames(self):
        directory = Path(self.temporary.name)/'ledger-plan'
        directory.mkdir()
        (directory/'asr_segments.sqlite3').write_bytes(b'synthetic numeric ledger extent')
        journal = directory/'asr_segments.sqlite3-journal'
        journal.write_bytes(b'preserved ledger journal')
        usage = types.SimpleNamespace(total=1024**3,free=512*1024**2)
        plan = storage_support.sqlite_file_size_plan(directory,4*1024**2,self.policy,usage,database_name='asr_segments.sqlite3')
        self.assertEqual(plan['existing_history_bytes'],(directory/'asr_segments.sqlite3').stat().st_size)
        self.assertEqual(plan['database_name'],'asr_segments.sqlite3')
        self.assertEqual(journal.read_bytes(),b'preserved ledger journal')
        for name in ('../history.sqlite3','folder/history.sqlite3','C:history.sqlite3','history.sqlite3-journal','.sqlite3','x'*100+'.sqlite3'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                storage_support.sqlite_file_size_plan(directory,0,self.policy,usage,database_name=name)

    def test_observed_database_above_old_gui_file_limit_is_admitted(self):
        directory = Path(self.temporary.name)/'observed-numeric-plan'
        directory.mkdir()
        observed_database_bytes = 35_889_152
        observed_journal_bytes = 41_552
        with (directory/'history.sqlite3').open('wb') as stream:
            stream.truncate(observed_database_bytes)
        journal = directory/'history.sqlite3-journal'
        journal.write_bytes(b'j'*observed_journal_bytes)
        usage = types.SimpleNamespace(total=64*1024**3,free=14_272_741_376)
        plan = storage_support.sqlite_file_size_plan(directory,0,self.policy,usage)
        self.assertGreater(observed_database_bytes,33_554_432)
        self.assertEqual(plan['existing_history_bytes'],observed_database_bytes)
        self.assertEqual(plan['existing_sidecar_bytes']['-journal'],observed_journal_bytes)
        self.assertGreaterEqual(plan['file_limit_bytes'],observed_database_bytes+8*1024**2)
        self.assertEqual(plan['file_limit_bytes'],observed_database_bytes+usage.free-self.policy.reserve(usage.total))
        self.assertLessEqual(plan['file_limit_bytes'],plan['physical_file_ceiling_bytes'])
        self.assertEqual(journal.read_bytes(),b'j'*observed_journal_bytes)

    def test_manager_initialization_recovery_remains_capture_disabled(self):
        import launcher
        args = types.SimpleNamespace(binding='synthetic-binding',data_root=self.root,unit='synthetic',unit_ownership=None,headless=False)
        failure = sqlite3.OperationalError('isolated startup I/O error')
        with mock.patch.object(launcher,'Manager',side_effect=failure),mock.patch.object(launcher,'startup_recovery_dialog',return_value=None) as dialog:
            self.assertIsNone(launcher.initialize_manager(args))
            self.assertIs(dialog.call_args.args[0],failure)

    def test_manager_database_close_failure_still_releases_launcher_handle(self):
        import launcher
        manager = launcher.Manager.__new__(launcher.Manager)
        manager._readiness_cancel = threading.Event()
        manager._readiness_thread = None
        manager.poll = mock.Mock()
        manager.poll_export = mock.Mock()
        manager.export_task = manager.process = None
        failure = sqlite3.OperationalError('isolated store close failure')
        manager.store = types.SimpleNamespace(close=mock.Mock(side_effect=failure),_spool=None)
        handle = (Path(self.temporary.name)/'synthetic-launcher.lock').open('wb')
        manager.lease = types.SimpleNamespace(close=mock.Mock(),file=handle)
        with self.assertRaises(sqlite3.OperationalError) as raised:
            manager.close()
        self.assertIs(raised.exception,failure)
        manager.lease.close.assert_called_once()
        self.assertTrue(handle.closed)

    def test_append_failure_cleanup_cannot_replace_primary_error(self):
        spool = self.store.begin(dict(duration_seconds=1))
        primary = OSError('isolated original audio write failure')
        with mock.patch.object(self.store,'_capacity',side_effect=primary),mock.patch.object(spool,'fail',side_effect=sqlite3.OperationalError('isolated secondary diagnostic failure')):
            with self.assertRaises(OSError) as raised:
                spool.append_processed(0,array.array('f',[0.0]).tobytes())
        self.assertIs(raised.exception,primary)
        self.assertTrue(any('secondary diagnostic failure' in note for note in primary.__notes__))
        spool.fail('synthetic fixture closure')

    def test_failure_publication_error_survives_secondary_lease_release_error(self):
        spool = self.store.begin(dict(duration_seconds=1))
        primary = sqlite3.OperationalError('isolated failure publication I/O error')
        with mock.patch.object(self.store,'_db',side_effect=primary),mock.patch.object(spool,'_release',side_effect=OSError('isolated secondary lease error')):
            with self.assertRaises(sqlite3.OperationalError) as raised:
                spool.fail('synthetic publication failure')
        self.assertIs(raised.exception,primary)
        self.assertTrue(any('secondary lease error' in note for note in primary.__notes__))
        spool.fail('synthetic fixture closure')


if __name__ == '__main__':
    unittest.main(verbosity=2)
