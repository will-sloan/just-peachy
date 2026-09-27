"""Fail-closed handoff gates; README_SCORE_REVIEW_ADVANCE_V1.md."""
from copy import deepcopy
from pathlib import Path
import time
import unittest
from unittest.mock import patch

import advance_main_score_review_v1 as subject


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.watch=dict(run_id='exact',supervisor=dict(pid=11,create_time=1.1),
            launcher=dict(pid=12,create_time=1.2),driver=dict(pid=13,create_time=1.3))
        self.worker=dict(run_id='exact',pid=11,create_time=1.1,child_pid=12,child_create_time=1.2,
            child_launch_pending=False,status='COMPLETED',exit_code=0,heartbeat_unix=time.time())

    def test_successful_exit_of_all_three_exact_owners(self):
        seen=[]
        self.assertTrue(subject.ready(self.watch,self.worker,lambda o:seen.append(o) or None))
        self.assertEqual(seen,[self.watch[x] for x in ('supervisor','launcher','driver')])

    def test_each_still_live_owner_delays_even_after_terminal(self):
        for key in ('supervisor','launcher','driver'):
            with self.subTest(key=key):
                self.assertFalse(subject.ready(self.watch,self.worker,lambda o:object() if o==self.watch[key] else None))

    def test_active_healthy_worker_only_waits(self):
        self.worker['status']='RUNNING'
        self.assertFalse(subject.ready(self.watch,self.worker,lambda o:object()))

    def test_stale_active_heartbeat_is_not_a_completed_worker(self):
        self.worker.update(status='RUNNING',heartbeat_unix=time.time()-121)
        with self.assertRaises(ValueError):subject.ready(self.watch,self.worker,lambda o:object())

    def test_future_heartbeat_fails(self):
        self.worker.update(status='RUNNING',heartbeat_unix=time.time()+60)
        with self.assertRaises(ValueError):subject.ready(self.watch,self.worker,lambda o:object())

    def test_missing_active_supervisor_fails(self):
        self.worker['status']='RUNNING'
        with self.assertRaises(ValueError):subject.ready(self.watch,self.worker,lambda o:None)

    def test_changed_run_or_creation_identity_is_not_reused(self):
        for field,value in [('run_id','foreign'),('pid',14),('create_time',2.1),('child_pid',14),('child_create_time',2.2)]:
            with self.subTest(field=field):
                worker=dict(self.worker);worker[field]=value
                with self.assertRaises(ValueError):subject.ready(self.watch,worker,lambda o:None)

    def test_failed_exit_and_pending_launch_refuse(self):
        for changes in ({'status':'FAILED'},{'exit_code':7},{'child_launch_pending':True}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):subject.ready(self.watch,dict(self.worker,**changes),lambda o:None)

    def test_access_denial_is_not_treated_as_exit(self):
        def denied(owner):raise PermissionError('unobservable')
        with self.assertRaises(PermissionError):subject.ready(self.watch,self.worker,denied)

    def success(self):
        root=Path('G:/fixture/main-scores');ab=dict(path='admission',sha256='a'*64,bytes=1)
        plan=dict(scope='main',required=7680)
        result=dict(status='SCORED_MODELED_BANK_REQUIRES_REVIEW',required=7680,
            prediction_completed=7680,prediction_failed=0,prediction_not_tested=0,
            metrics_unavailable_for_complete_predictions=0,admission=ab,stop_reason=None,
            integrated_N4_cells=0,
            scores=[dict(path=str(root/'cells'/f'{i:05d}.json'),sha256='b'*64,bytes=1) for i in range(7680)],
            report=dict(path=str(root/'REPORT.json'),sha256='c'*64,bytes=1))
        return root,ab,plan,result

    def test_full_population_accepted_for_review_not_stage_acceptance(self):
        root,ab,plan,result=self.success();subject.validate_success(result,ab,plan,root)

    def test_missing_failed_untested_and_resource_stops_refuse(self):
        root,ab,plan,result=self.success()
        for field,value in [('prediction_completed',7679),('prediction_failed',1),('prediction_not_tested',1),
            ('metrics_unavailable_for_complete_predictions',1),('stop_reason','RESOURCE_OR_TIME_STOP'),
            ('required',1536),('status','PARTIAL_MODELED_BANK_SCORING')]:
            with self.subTest(field=field):
                changed=dict(result);changed[field]=value
                with self.assertRaises(ValueError):subject.validate_success(changed,ab,plan,root)

    def test_foreign_admission_mode_report_and_score_paths_refuse(self):
        root,ab,plan,result=self.success()
        cases=[(dict(result,admission={}),plan),(result,dict(plan,scope='modes-panel')),
            (dict(result,report=dict(path=str(root/'OTHER.json'))),plan)]
        altered=deepcopy(result);altered['scores'][0]['path']=altered['scores'][1]['path'];cases.append((altered,plan))
        for changed,p in cases:
            with self.assertRaises(ValueError):subject.validate_success(changed,ab,p,root)

    def test_qualified_terminal_validator_is_always_called(self):
        root,ab,plan,result=self.success()
        with patch.object(subject,'validate_terminal',side_effect=ValueError('qualified gate')) as check:
            with self.assertRaises(ValueError):subject.validate_success(result,ab,plan,root)
            check.assert_called_once_with(result,plan)


if __name__=='__main__':unittest.main()
