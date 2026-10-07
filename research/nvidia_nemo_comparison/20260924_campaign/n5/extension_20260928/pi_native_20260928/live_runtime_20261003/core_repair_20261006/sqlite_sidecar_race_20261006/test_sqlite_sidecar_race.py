"""Temporary SQLite/file fixtures only. See README_SQLITE_SIDECAR_RACE.md."""
from pathlib import Path
from contextlib import closing
import importlib.util
import os
import sqlite3
import stat
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

import storage_support


class FixturePolicy:
    def reserve(self, total):
        return 5 * storage_support.MIB


class SQLiteSidecarRaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='peachy-sidecar-fixture-')
        self.root = Path(self.temporary.name)
        self.policy = FixturePolicy()
        self.usage = SimpleNamespace(total=256*storage_support.MIB,
                                     free=128*storage_support.MIB)

    def tearDown(self):
        self.temporary.cleanup()

    def info(self, *, links=0, inode=11, mode=stat.S_IFREG|0o600,
             size=4096, device=7, attributes=0):
        return SimpleNamespace(st_nlink=links, st_ino=inode, st_dev=device,
                               st_mode=mode, st_size=size,
                               st_file_attributes=attributes)

    def inspect(self, snapshots, suffix='-journal'):
        path = self.root/('history.sqlite3'+suffix)
        with mock.patch.object(Path, 'lstat', side_effect=snapshots) as lookup:
            value = storage_support._sqlite_file_size(path, suffix)
        return value, lookup.call_count

    def test_missing_sidecars_and_new_database_are_normal(self):
        plan = storage_support.sqlite_file_size_plan(self.root,0,self.policy,self.usage)
        self.assertEqual(plan['existing_sidecar_bytes'],dict.fromkeys(storage_support.SIDECARS,0))
        self.assertEqual(plan['required_free_bytes'],8*storage_support.MIB)

    def test_unlinked_regular_sidecars_are_absent_after_one_recheck(self):
        for suffix in storage_support.SIDECARS[1:]:
            with self.subTest(suffix=suffix):
                self.assertEqual(self.inspect([self.info(),FileNotFoundError()],suffix),(0,2))

    def test_frozen_guard_regression_and_candidate_completed_unlink(self):
        source = Path(__file__).resolve().parent.parent/'storage_support.py'
        spec = importlib.util.spec_from_file_location('frozen_build29_storage_support',source)
        frozen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(frozen)
        journal = self.root/'history.sqlite3-journal'
        ordinary_lstat,ordinary_stat = Path.lstat,Path.stat
        def old_lookup(path,*args,**kwargs):
            return self.info() if path == journal else ordinary_lstat(path,*args,**kwargs)
        def old_final(path,*args,**kwargs):
            return self.info() if path == journal else ordinary_stat(path,*args,**kwargs)
        with mock.patch.object(Path,'lstat',old_lookup),mock.patch.object(Path,'stat',old_final):
            with self.assertRaisesRegex(ValueError,'Regular single-link SQLite files required'):
                frozen.sqlite_file_size_plan(self.root,0,self.policy,self.usage)
        snapshots = iter((self.info(),FileNotFoundError()))
        def completed_unlink(path,*args,**kwargs):
            if path != journal:
                return ordinary_lstat(path,*args,**kwargs)
            observation = next(snapshots)
            if isinstance(observation,BaseException):
                raise observation
            return observation
        with mock.patch.object(Path,'lstat',completed_unlink):
            plan = storage_support.sqlite_file_size_plan(self.root,0,self.policy,self.usage)
        self.assertEqual(plan['existing_sidecar_bytes']['-journal'],0)

    def test_valid_different_inode_replacement_is_conservatively_charged(self):
        old,new = self.info(size=8192),self.info(links=1,inode=12,size=4096)
        self.assertEqual(self.inspect([old,new]),(8192,2))
        self.assertEqual(self.inspect([old,self.info(links=1,inode=12,size=16384)]),(16384,2))

    def test_same_inode_zero_link_does_not_pass_or_retry_forever(self):
        path = self.root/'history.sqlite3-journal'
        with mock.patch.object(Path,'lstat',side_effect=[self.info(),self.info()]) as lookup:
            with self.assertRaisesRegex(ValueError,'recheck .*nlink=0') as raised:
                storage_support._sqlite_file_size(path,'-journal')
        self.assertEqual(lookup.call_count,2)
        self.assertIn(repr(str(path)),str(raised.exception))
        self.assertIn('mode=0o',str(raised.exception))

    def test_same_inode_relinked_or_unknown_inode_does_not_pass(self):
        for old,new in ((self.info(),self.info(links=1)),
                        (self.info(inode=0),self.info(links=1,inode=12)),
                        (self.info(),self.info(links=1,inode=0))):
            with self.subTest(old_inode=old.st_ino,new_inode=new.st_ino):
                with self.assertRaises(ValueError):
                    self.inspect([old,new])

    def test_main_zero_link_rejects_without_recheck(self):
        path = self.root/'history.sqlite3'
        with mock.patch.object(Path,'lstat',side_effect=[self.info(),FileNotFoundError()]) as lookup:
            with self.assertRaisesRegex(ValueError,'history.sqlite3.*nlink=0'):
                storage_support._sqlite_file_size(path,'')
        self.assertEqual(lookup.call_count,1)

    def test_first_hardlink_rejects_even_if_name_would_disappear(self):
        for suffix in storage_support.SIDECARS:
            with self.subTest(suffix=suffix):
                with mock.patch.object(Path,'lstat',side_effect=[self.info(links=2),FileNotFoundError()]) as lookup:
                    with self.assertRaisesRegex(ValueError,'nlink=2'):
                        storage_support._sqlite_file_size(self.root/('history.sqlite3'+suffix),suffix)
                self.assertEqual(lookup.call_count,1)

    def test_replacement_hardlink_symlink_reparse_and_directory_reject(self):
        anomalies = (self.info(links=2,inode=12),
                     self.info(links=1,inode=12,mode=stat.S_IFLNK|0o777),
                     self.info(links=1,inode=12,attributes=0x400),
                     self.info(links=1,inode=12,mode=stat.S_IFDIR|0o700))
        for anomaly in anomalies:
            with self.subTest(mode=anomaly.st_mode,links=anomaly.st_nlink,
                              attributes=anomaly.st_file_attributes):
                with self.assertRaisesRegex(ValueError,'recheck .*inode=12'):
                    self.inspect([self.info(),anomaly])

    def test_first_symlink_reparse_and_nonregular_reject_without_recheck(self):
        anomalies = (self.info(mode=stat.S_IFLNK|0o777),
                     self.info(attributes=0x400),self.info(mode=stat.S_IFDIR|0o700))
        for anomaly in anomalies:
            with self.subTest(mode=anomaly.st_mode,attributes=anomaly.st_file_attributes):
                with mock.patch.object(Path,'lstat',side_effect=[anomaly,FileNotFoundError()]) as lookup:
                    with self.assertRaises(ValueError):
                        storage_support._sqlite_file_size(self.root/'history.sqlite3-journal','-journal')
                self.assertEqual(lookup.call_count,1)

    def test_lookup_permission_failure_propagates(self):
        denied = PermissionError(13,'fixture denied')
        for observations in ([denied],[self.info(),denied]):
            with self.subTest(observations=len(observations)):
                with self.assertRaises(PermissionError) as raised:
                    self.inspect(observations)
                self.assertIs(raised.exception,denied)

    def test_real_hardlink_is_rejected_and_bytes_preserved(self):
        journal = self.root/'history.sqlite3-journal'
        journal.write_bytes(b'journal evidence kept')
        other = self.root/'fixture-hardlink'
        os.link(journal,other)
        self.assertEqual(journal.lstat().st_nlink,2)
        with self.assertRaisesRegex(ValueError,'history.sqlite3-journal.*nlink=2'):
            storage_support.sqlite_file_size_plan(self.root,0,self.policy,self.usage)
        self.assertEqual(journal.read_bytes(),b'journal evidence kept')
        self.assertEqual(other.read_bytes(),journal.read_bytes())

    def test_existing_database_and_journal_remain_byte_identical(self):
        main,journal = self.root/'history.sqlite3',self.root/'history.sqlite3-journal'
        main.write_bytes(b'fixture database bytes')
        journal.write_bytes(b'fixture journal retained; no recovery or deletion')
        before = (main.read_bytes(),journal.read_bytes())
        plan = storage_support.sqlite_file_size_plan(self.root,0,self.policy,self.usage)
        self.assertEqual(plan['existing_history_bytes'],len(before[0]))
        self.assertEqual(plan['existing_sidecar_bytes']['-journal'],len(before[1]))
        self.assertEqual((main.read_bytes(),journal.read_bytes()),before)

    def test_final_lookup_never_follows_links(self):
        path = self.root/'history.sqlite3-journal'
        path.write_bytes(b'fixture')
        ordinary_stat = Path.stat
        def observe(path,*,follow_symlinks=True):
            self.assertFalse(follow_symlinks,'following stat forbidden')
            return ordinary_stat(path,follow_symlinks=follow_symlinks)
        with mock.patch.object(Path,'stat',observe):
            self.assertEqual(storage_support._sqlite_file_size(path,'-journal'),7)

    def test_parent_symlink_metadata_is_rejected_with_path(self):
        original = Path.lstat
        def observe(path,*args,**kwargs):
            if path == self.root:
                return self.info(links=1,mode=stat.S_IFLNK|0o777)
            return original(path,*args,**kwargs)
        with mock.patch.object(Path,'lstat',observe):
            with self.assertRaisesRegex(ValueError,'Real SQLite file paths required') as raised:
                storage_support.sqlite_file_size_plan(self.root,0,self.policy,self.usage)
        self.assertIn(repr(str(self.root)),str(raised.exception))
        self.assertIn('nlink=1',str(raised.exception))

    def test_capacity_and_basename_guards_still_apply(self):
        with self.assertRaisesRegex(OSError,'above reserve'):
            storage_support.sqlite_file_size_plan(self.root,0,self.policy,
                SimpleNamespace(total=256*storage_support.MIB,free=6*storage_support.MIB))
        for name in ('../history.sqlite3','history.sqlite3-journal','other.txt'):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError,'basename'):
                    storage_support.sqlite_file_size_plan(self.root,0,self.policy,self.usage,database_name=name)

    def test_concurrent_real_sqlite_commits_preserve_all_updates(self):
        path = self.root/'asr_segments.sqlite3'
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode=DELETE').fetchone()[0],'delete')
            db.execute('CREATE TABLE fixture(value INTEGER NOT NULL,padding BLOB NOT NULL)')
            db.execute('INSERT INTO fixture VALUES(0,?)',(b'x'*4096,))
            db.commit()
        first_journal,release = threading.Event(),threading.Event()
        failures = []
        def writer():
            try:
                with closing(sqlite3.connect(path,timeout=2)) as db:
                    for index in range(120):
                        db.execute('BEGIN IMMEDIATE')
                        db.execute('UPDATE fixture SET value=value+1')
                        if index == 0:
                            first_journal.set()
                            if not release.wait(5):
                                raise TimeoutError('fixture first journal observer did not finish')
                        db.commit()
            except BaseException as error:
                failures.append(error)
        thread = threading.Thread(target=writer,name='fixture-sqlite-writer',daemon=True)
        thread.start()
        observations = 0
        try:
            self.assertTrue(first_journal.wait(5))
            first = storage_support.sqlite_file_size_plan(self.root,0,self.policy,self.usage,
                                                         database_name=path.name)
            self.assertGreater(first['existing_sidecar_bytes']['-journal'],0)
            release.set()
            deadline = time.monotonic()+10
            while thread.is_alive() and observations < 3000 and time.monotonic() < deadline:
                storage_support.sqlite_file_size_plan(self.root,0,self.policy,self.usage,
                                                     database_name=path.name)
                observations += 1
        finally:
            release.set()
            thread.join(10)
        self.assertFalse(thread.is_alive(),'bounded fixture writer did not close')
        self.assertFalse(failures,repr(failures))
        self.assertGreater(observations,0)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('SELECT value FROM fixture').fetchone()[0],120)
            self.assertEqual(db.execute('PRAGMA quick_check').fetchall(),[('ok',)])


if __name__ == '__main__':
    raise SystemExit('Use registered run_host_sidecar_checks.py; see maintained README')
