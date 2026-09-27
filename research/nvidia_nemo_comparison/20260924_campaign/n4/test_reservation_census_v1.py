"""Allocation discovery failure tests; README_RESERVATION_CENSUS_V1.md."""
from copy import deepcopy
from pathlib import Path
import tempfile
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from common import bind, freeze
from reservation_census_v1 import (admission_paths, classify, epoch, output_argument,
    validate_live, validate_supervision, visible_python_census)


def who(pid):
    return dict(pid=pid, create_time=1000.0+pid)


class Process:
    def __init__(self, pid, parent, argv):
        self.pid, self.parent, self.argv = pid, parent, argv
        self.info = dict(pid=pid, name='python.exe')
    def create_time(self): return 1000.0+self.pid
    def ppid(self): return self.parent
    def cmdline(self): return self.argv
    def children(self, recursive=False): return []


class Files(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.local = Path(self.temp.name); (self.local/'n4').mkdir()
    def make(self, name='run', **data):
        root = self.local/'n4'/name
        freeze(root/'ADMISSION.json', data)
        return root/'ADMISSION.json'
    def closed(self, owner): return None
    def test_nested_admission_is_not_omitted(self):
        a = self.make('run'); b = self.make('nested/run')
        self.assertEqual(admission_paths(self.local/'n4'), sorted([a,b]))
    def test_walk_permission_failure_propagates(self):
        def broken(*args, **kwargs):
            kwargs['onerror'](PermissionError('denied'))
            return []
        with patch('reservation_census_v1.os.walk', broken), self.assertRaises(PermissionError):
            admission_paths(self.local/'n4')
    def test_link_or_reparse_root_refuses_before_scan(self):
        for mode,attributes in [(stat.S_IFLNK,0),(stat.S_IFDIR,stat.FILE_ATTRIBUTE_REPARSE_POINT)]:
            info=SimpleNamespace(st_mode=mode,st_file_attributes=attributes)
            with self.subTest(mode=mode),patch('pathlib.Path.lstat',return_value=info),self.assertRaises(ValueError):
                admission_paths(self.local/'n4')
    def test_direct_live_owner_discovered(self):
        a = self.make(owner=who(1), maximum_output_bytes=100)
        r = classify(a,self.local,lookup=lambda o: object())
        self.assertEqual((r['kind'],r['state']),('DIRECT_OWNER','ACTIVE'))
    def test_reused_pid_is_closed_only_when_lookup_confirms_identity_mismatch(self):
        a = self.make(owner=who(1), maximum_output_bytes=100)
        self.assertEqual(classify(a,self.local,lookup=self.closed)['state'],'CLOSED_OWNER')
    def test_owner_access_denial_is_not_an_exit(self):
        a = self.make(owner=who(1))
        def denied(o): raise PermissionError('unverified')
        with self.assertRaises(PermissionError): classify(a,self.local,lookup=denied)
    def test_orphan_metric_child_blocks_closed_owner(self):
        a = self.make(owner=who(1)); freeze(a.parent/'RESULT.json',dict(workers=[dict(owners=[who(2)])]))
        with self.assertRaises(ValueError):
            classify(a,self.local,lookup=lambda o: object() if o['pid']==2 else None)
    def test_direct_terminal_owner_or_admission_mismatch_refuses(self):
        for name,result in [('owner',dict(owner=who(99))),('admission',dict(admission={}))]:
            a=self.make(name,owner=who(1));freeze(a.parent/'RESULT.json',result)
            with self.subTest(name=name),self.assertRaises(ValueError):classify(a,self.local,lookup=self.closed)
    def test_legacy_owner_is_read_from_bound_terminal(self):
        a = self.make(allocation_bytes=100)
        freeze(a.parent/'RESULT.json',dict(owner=who(1),admission=bind(a),child=None))
        r=classify(a,self.local,lookup=self.closed)
        self.assertEqual((r['kind'],r['state']),('TERMINAL_OWNER','CLOSED_OWNER'))
    def test_legacy_bad_join_and_live_owner_refuse(self):
        for name,ab,lookup in [('bad',{},self.closed),('live',None,lambda o: object())]:
            with self.subTest(name=name):
                a=self.make(name,allocation_bytes=100)
                freeze(a.parent/'RESULT.json',dict(owner=who(1),admission=bind(a) if ab is None else ab,child=None))
                with self.assertRaises(ValueError): classify(a,self.local,lookup=lookup)
    def test_unknown_ownerless_receipt_refuses(self):
        with self.assertRaises(ValueError): classify(self.make(),self.local,lookup=self.closed)
    def test_duplicate_missing_and_escaped_output_refuse(self):
        a=self.make()
        for argv in [[],['--output'],['--output',str(a.parent),'--output',str(a.parent)],
                     ['--output',str(self.local)],['--output',str(self.local/'n4')]]:
            with self.subTest(argv=argv), self.assertRaises(ValueError): output_argument(argv,self.local)
    def dispatch(self):
        a=self.make('target',owner=who(1),maximum_output_bytes=100)
        sb=self.local/'spec.json';freeze(sb,dict(argv=['python','x.py','--output',str(a.parent)]))
        d=self.make('dispatch',worker_spec=bind(sb));freeze(d.parent/'STARTED.json',
            dict(worker_spec=bind(sb),supervisor_start=who(2)))
        return d,a
    def test_dispatch_is_linked_alias_not_an_extra_allocation(self):
        d,a=self.dispatch();r=classify(d,self.local,lookup=self.closed)
        self.assertEqual(r['state'],'ALIAS_NOT_SECOND_ALLOCATION');self.assertEqual(r['delegate'],bind(a))
    def test_live_dispatch_without_live_target_refuses(self):
        d,a=self.dispatch()
        with self.assertRaises(ValueError):classify(d,self.local,lookup=lambda o: object() if o['pid']==2 else None)
    def historical(self, name='widget', **changes):
        launcher=self.local/'launcher.py';launcher.write_text('# immutable source')
        a=self.make(name,launcher=bind(launcher));iso=a.parent/'isolation.json'
        data=dict(schema='just-peachy.private-desktop-launch.v1',exit_code=0,timed_out=False,desktop_handle_closed=True)
        data.update(changes);freeze(iso,data);freeze(a.parent/'RESULT.json',
            dict(status='PASS_PRIVATE_TK_VIEWPORT_QUALIFICATION',admission=bind(a),isolation=bind(iso)))
        return a
    def test_historical_handle_wait_is_labelled_not_fabricated_pid(self):
        r=classify(self.historical(),self.local,lookup=self.closed)
        self.assertEqual(r['state'],'CLOSED_LEGACY_HANDLE');self.assertFalse(r['exact_pid_reconstructed'])
    def test_unclosed_or_timed_out_historical_handle_refuses(self):
        for i,change in enumerate([dict(exit_code=None),dict(exit_code=True),dict(timed_out=True),dict(desktop_handle_closed=False)]):
            with self.subTest(change=change),self.assertRaises(ValueError):
                classify(self.historical('widget'+str(i),**change),self.local,lookup=self.closed)
    def test_live_command_must_match_allocation(self):
        a=self.make(owner=who(1),maximum_output_bytes=100)
        record=classify(a,self.local,lookup=lambda o: object())
        other=self.make('other');p=Process(1,2,['python','x.py','--output',str(other.parent)])
        with self.assertRaises(ValueError): validate_live(record,self.local,lookup=lambda o:p)
    def test_live_command_source_must_be_bound(self):
        a=self.make(owner=who(1),maximum_output_bytes=100)
        record=classify(a,self.local,lookup=lambda o: object())
        p=Process(1,2,['python','x.py','--output',str(a.parent)])
        with self.assertRaises(ValueError): validate_live(record,self.local,lookup=lambda o:p)


class Supervision(unittest.TestCase):
    def setUp(self):
        self.spec=dict(argv=['venv-python','-B','scorer.py','--output','output'])
        self.worker=dict(status='RUNNING',run_id='fixed',pid=1,create_time=1001.,child_pid=2,
            child_create_time=1002.,child_launch_pending=False,heartbeat_unix=100.)
        self.active=[dict(owner=who(3))]
        self.processes={1:Process(1,0,[]),2:Process(2,1,self.spec['argv']),
                        3:Process(3,2,['base-python']+self.spec['argv'][1:])}
    def lookup(self,o):return self.processes.get(o['pid']) if o['create_time']==1000.+o['pid'] else None
    def check(self):return validate_supervision(self.worker,self.spec,self.active,lookup=self.lookup,now=101.)
    def test_exact_launcher_and_real_interpreter_join(self):self.assertEqual(self.check()['driver'],who(3))
    def test_heartbeat_updates_do_not_change_epoch(self):
        other=deepcopy(self.worker);other['heartbeat_unix']=110.
        self.assertEqual(epoch(other,self.spec),epoch(self.worker,self.spec))
    def test_epoch_detects_run_status_owner_command_and_pending_changes(self):
        for k,v in [('run_id','other'),('status','FAILED'),('create_time',999.),('child_launch_pending',True)]:
            other=dict(self.worker,**{k:v});self.assertNotEqual(epoch(other,self.spec),epoch(self.worker,self.spec))
        self.assertNotEqual(epoch(self.worker,dict(argv=[])),epoch(self.worker,self.spec))
    def test_launch_pending_and_stale_heartbeat_refuse(self):
        for k,v in [('child_launch_pending',True),('heartbeat_unix',-20.),('heartbeat_unix',102.)]:
            old=self.worker[k];self.worker[k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):self.check()
            self.worker[k]=old
    def test_pid_reuse_changed_parent_and_command_refuse(self):
        for change in ['pid','parent','command']:
            with self.subTest(change=change):
                original=deepcopy(self.worker);lp=self.processes[2];oldparent=lp.parent;oldargv=lp.argv
                if change=='pid':self.worker['create_time']=999.
                elif change=='parent':lp.parent=55
                else:lp.argv=['other']
                with self.assertRaises(ValueError):self.check()
                self.worker=original;lp.parent=oldparent;lp.argv=oldargv
    def test_missing_or_duplicate_driver_refuses(self):
        for active in [[],self.active*2]:
            with self.subTest(active=active),self.assertRaises(ValueError):
                validate_supervision(self.worker,self.spec,active,lookup=self.lookup,now=101.)
    def test_terminal_still_alive_refuses(self):
        self.worker['status']='COMPLETED'
        with self.assertRaises(ValueError):self.check()
    def test_closed_supervision_requires_both_exact_exits(self):
        self.worker['status']='COMPLETED';self.processes={}
        self.assertEqual(self.check()['state'],'CLOSED')
    def test_visible_unregistered_python_is_not_ignored(self):
        p=Process(99,0,['python',str(Path('private/n4/unknown.py').resolve())])
        with patch('psutil.process_iter',return_value=[p]),self.assertRaises(ValueError):
            visible_python_census(Path('private').resolve(),Path('stage').resolve(),[],dict(state='CLOSED'))


if __name__=='__main__':unittest.main()
