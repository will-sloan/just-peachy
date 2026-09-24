"""Harmless coordinator process/failure/resume tests; no models. See README.md."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import psutil

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('n2_campaign_under_test',HERE/'run_campaign.py')
campaign=importlib.util.module_from_spec(spec);spec.loader.exec_module(campaign)
REAL_SLEEP=time.sleep

# This temporary child does only file I/O, a bounded peer barrier and sleeping.
# Each invocation is owned by the real coordinator Popen/psutil path.
CHILD=r'''
import argparse,json,os,pathlib,time
import psutil
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--id',required=True)
p.add_argument('--peer');p.add_argument('--exit-code',type=int,default=0);p.add_argument('--seconds',type=float,default=.1)
a=p.parse_args();root=pathlib.Path(a.output);root.mkdir(parents=True,exist_ok=True)
with (root/'starts.txt').open('a') as f:f.write(str(os.getpid())+'\n')
(root/'ready').write_text(str(os.getpid()));overlap=False
if a.peer:
    peer=pathlib.Path(a.peer);end=time.monotonic()+10
    while not (peer/'ready').exists():
        if time.monotonic()>end:raise TimeoutError('harmless sibling fixture never started')
        time.sleep(.01)
    overlap=not (peer/'done').exists()
time.sleep(a.seconds)
if a.exit_code:raise SystemExit(a.exit_code)
process=psutil.Process()
result={'status':'COMPLETE','completed':{a.id:'harmless fixture'},'failed':{},'overlap_observed':overlap,
        'pid':os.getpid(),'affinity':process.cpu_affinity(),'priority':process.nice(),'models_loaded':False}
for name in ('RESULT.json','PROGRESS.json'):
    tmp=root/(name+'.tmp');tmp.write_text(json.dumps(result));tmp.replace(root/name)
(root/'done').write_text('completed')
'''


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='N2 harmless coordinator ')
        self.root=Path(self.temp.name);self.child=self.root/'harmless_child.py';self.child.write_text(CHILD)
        self.state=self.root/'state';self.state.mkdir()
        campaign.atomic(self.state/'campaign.json',dict(target_utc=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),
            packaging_reserve_hours=0,resource_policy=dict(minimum_free_gib={})))
        self.process=psutil.Process();self.affinity=self.process.cpu_affinity();self.priority=self.process.nice()
        self.cpus=self.affinity[:2]
        self.clock_patch=patch.object(campaign,'time',SimpleNamespace(monotonic=time.monotonic,sleep=lambda seconds:REAL_SLEEP(.02)))
        self.clock_patch.start()

    def tearDown(self):
        self.clock_patch.stop();self.process.cpu_affinity(self.affinity);self.process.nice(self.priority)
        self.temp.cleanup()

    def job(self,key,*,peer=None,exit_code=0,seconds=.1):
        output=self.root/'children'/key
        argv=[sys.executable,'-B',str(self.child),'--output',str(output),'--id',key,'--seconds',str(seconds)]
        if peer:argv+=['--peer',str(self.root/'children'/peer)]
        if exit_code:argv+=['--exit-code',str(exit_code)]
        return dict(id=key,argv=argv,cwd=str(self.root),cells=1,device='cpu',timeout_seconds=15,
            result=str(output/'RESULT.json'),progress=str(output/'PROGRESS.json'),result_kind='controller')

    def setup_run(self,lanes):
        document=dict(schema='n2-numerical-coordinator-v1',lanes=lanes)
        path=self.root/'spec.json';campaign.atomic(path,document)
        return SimpleNamespace(spec=path,output=self.root/'coordinator',state=self.state),document

    def one_job(self,**kwargs):
        job=self.job('single',**kwargs)
        args,document=self.setup_run([dict(cpu=self.cpus[0],jobs=[job])]);return args,document,job

    def test_actual_two_lanes_overlap_affinity_and_resume_without_respawn(self):
        if len(self.cpus)<2:self.skipTest('Two allowed CPUs required for a real two-lane fixture')
        left=self.job('left',peer='right');right=self.job('right',peer='left')
        args,_=self.setup_run([dict(cpu=self.cpus[0],jobs=[left]),dict(cpu=self.cpus[1],jobs=[right])])
        self.assertEqual(campaign.run(args),0)
        for cpu,job in zip(self.cpus,(left,right)):
            result=campaign.read(Path(job['result']))
            self.assertTrue(result['overlap_observed']);self.assertFalse(result['models_loaded'])
            self.assertEqual(result['affinity'],[cpu])
            if os.name=='nt':self.assertEqual(result['priority'],psutil.BELOW_NORMAL_PRIORITY_CLASS)
        self.assertEqual(campaign.run(args),0)
        resumed=campaign.read(args.output/'RESULT.json')
        self.assertEqual(resumed['cached_at_start'],2);self.assertEqual(resumed['completed'],2)
        self.assertFalse(resumed['llm_invoked'])
        for job in (left,right):self.assertEqual(len((Path(job['result']).parent/'starts.txt').read_text().splitlines()),1)

    def test_failure_stops_its_lane_and_other_lane_completes(self):
        if len(self.cpus)<2:self.skipTest('Two allowed CPUs required')
        failed=self.job('failed',exit_code=7);blocked=self.job('blocked');good=self.job('good')
        args,_=self.setup_run([dict(cpu=self.cpus[0],jobs=[failed,blocked]),dict(cpu=self.cpus[1],jobs=[good])])
        self.assertEqual(campaign.run(args),2)
        result=campaign.read(args.output/'RESULT.json');self.assertEqual(result['status'],'INCOMPLETE')
        self.assertEqual(result['jobs']['failed']['status'],'FAILED');self.assertEqual(result['jobs']['failed']['exit_code'],7)
        self.assertEqual(result['jobs']['good']['status'],'COMPLETE');self.assertEqual(result['jobs']['blocked']['status'],'PENDING')
        self.assertFalse((Path(blocked['result']).parent/'ready').exists())

    def test_changed_completed_evidence_prevents_resume(self):
        args,_,job=self.one_job();self.assertEqual(campaign.run(args),0)
        result=Path(job['result']);result.write_text(result.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'evidence changed'):campaign.run(args)

    def test_changed_spec_prevents_resume(self):
        args,document,_=self.one_job();self.assertEqual(campaign.run(args),0)
        document['lanes'][0]['jobs'][0]['cells']=2;campaign.atomic(args.spec,document)
        with self.assertRaisesRegex(ValueError,'contract changed'):campaign.run(args)

    def test_foreign_result_contract_or_job_is_not_resumed(self):
        args,_,_=self.one_job();self.assertEqual(campaign.run(args),0)
        path=args.output/'RESULT.json';original=campaign.read(path)
        modified=deepcopy(original);modified['contract_sha256']='0'*64;campaign.atomic(path,modified)
        with self.assertRaises(ValueError):campaign.run(args)
        modified=deepcopy(original);modified['jobs']['foreign']=dict(status='COMPLETE',cells=999)
        campaign.atomic(path,modified)
        with self.assertRaises(ValueError):campaign.run(args)

    def test_completion_requires_counts_status_and_zero_failures(self):
        _,_,job=self.one_job();path=Path(job['result']);path.parent.mkdir(parents=True)
        for document in (dict(status='PARTIAL',completed={'a':'x'},failed={}),dict(status='COMPLETE',completed={},failed={}),
                         dict(status='COMPLETE',completed={'a':'x'},failed={'b':'failed'})):
            campaign.atomic(path,document)
            with self.assertRaises(ValueError):campaign.completion(job)
        job['result_kind']='native'
        campaign.atomic(path,dict(status='COMPLETE',completed=1,failed=1))
        with self.assertRaises(ValueError):campaign.completion(job)
        campaign.atomic(path,dict(status='COMPLETE',completed=1,failed=0));self.assertEqual(campaign.completion(job)['cells'],1)
        job['result_kind']='gui';campaign.atomic(path,dict(status='COMPLETE',cells=[dict(status='FAILED')]))
        with self.assertRaises(ValueError):campaign.completion(job)

    def test_packaging_cutoff_prevents_any_child(self):
        args,_,job=self.one_job();state=campaign.read(self.state/'campaign.json')
        state['target_utc']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat();campaign.atomic(self.state/'campaign.json',state)
        with self.assertRaisesRegex(RuntimeError,'packaging reserve'):campaign.run(args)
        self.assertFalse((Path(job['result']).parent/'ready').exists())

    def test_reserve_failure_stops_owned_harmless_child(self):
        args,_,job=self.one_job(seconds=20)
        with patch.object(campaign,'disk_reserves',side_effect=[({},[]),({},['fixture'])]):
            with self.assertRaisesRegex(RuntimeError,'disk reserve'):campaign.run(args)
        result=campaign.read(args.output/'RESULT.json');owner=result['jobs']['single']['owner']
        self.assertNotIn(campaign.process_identity_state(owner['pid'],owner['create_time']),('ALIVE','UNVERIFIED'))
        self.assertEqual(result['jobs']['single']['status'],'INTERRUPTED')

    def test_job_timeout_stops_child_and_reports_failure(self):
        args,document,job=self.one_job(seconds=20)
        document['lanes'][0]['jobs'][0]['timeout_seconds']=.1;campaign.atomic(args.spec,document)
        self.assertEqual(campaign.run(args),2)
        result=campaign.read(args.output/'RESULT.json');row=result['jobs']['single']
        self.assertEqual(row['status'],'FAILED');self.assertTrue(row['timeout_reached'])
        self.assertNotIn(campaign.process_identity_state(row['owner']['pid'],row['owner']['create_time']),('ALIVE','UNVERIFIED'))

    def test_admission_rejects_unsafe_ids_devices_cpus_and_denominators(self):
        _,document,_=self.one_job()
        edits=[lambda d:d['lanes'][0]['jobs'][0].update(id='../escape'),
               lambda d:d['lanes'][0]['jobs'][0].update(device='unrecognized'),
               lambda d:d['lanes'][0].update(cpu=True),lambda d:d['lanes'][0].update(cpu=-1),
               lambda d:d['lanes'][0]['jobs'][0].update(cells=.5),lambda d:d['lanes'][0]['jobs'][0].update(cells=True)]
        for edit in edits:
            bad=deepcopy(document);edit(bad)
            with self.assertRaises(ValueError):campaign.admit(bad)

    def test_only_one_cuda_lane_and_distinct_cpu_lanes(self):
        _,document,job=self.one_job();other=deepcopy(job);other['id']='other'
        document['lanes'].append(dict(cpu=self.cpus[0],jobs=[other]))
        with self.assertRaises(ValueError):campaign.admit(document)
        document['lanes'][1]['cpu']=self.cpus[0]+1
        for lane in document['lanes']:lane['jobs'][0]['device']='cuda'
        with self.assertRaisesRegex(ValueError,'CUDA'):campaign.admit(document)


if __name__=='__main__':unittest.main(verbosity=2)
