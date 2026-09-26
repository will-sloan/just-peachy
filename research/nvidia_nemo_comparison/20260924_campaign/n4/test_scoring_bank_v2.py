"""Bounded worker and bank/report integrity tests. README_SCORING_CLOCK_V2.md."""
from copy import deepcopy
from itertools import product
import json
import os
from pathlib import Path
import sys
import time
import unittest

from common import fingerprint,load
from metric_process import MetricProcess,MetricProcessError,PROTOCOL,MAX_RESPONSE,exact_process,identity,pin
from scoring_bank_v2 import validate_plan,validate_terminal,unavailable
from scoring_report import report,pool


def truth():
    return dict(job_id='case_O0',case_id='case',tap='O0',frames=16000,reference_class='complete_nonoverlap',
        complete_reference=True,turns=[dict(identity='actor',transcript='one two',activity_ranges_samples_estimated=[[0,16000]])])


def prediction():
    return dict(job_id='case_O0',status='COMPLETE',raw_text='',segments=[],activity=None,activity_support={},formatting=[])


class FixtureProcess(MetricProcess):
    def __init__(self,mode,**kwargs):super().__init__(**kwargs);self.mode=mode
    def _command(self):
        return [sys.executable,'-B',str(Path(__file__).resolve()),'--fixture',self.mode,self.nonce]


def fixture(mode,nonce):
    p=pin();owner=identity(p)
    def emit(v):print(json.dumps(v),flush=True)
    if mode=='startup-eof':return
    hello=dict(protocol=PROTOCOL,nonce=nonce,status='READY',owner=owner,affinity=[14],models_loaded=0)
    if mode=='foreign-owner':hello['owner']=dict(pid=os.getppid(),create_time=0)
    emit(hello)
    for line in sys.stdin:
        request=json.loads(line)
        if mode=='hang':time.sleep(20)
        if mode=='eof':return
        if mode=='oversize':sys.stdout.write('x'*(MAX_RESPONSE+2)+'\n');sys.stdout.flush();return
        if mode=='stderr':sys.stderr.write('w'*100000);sys.stderr.flush()
        response=dict(protocol=PROTOCOL,owner=owner,sequence=request['sequence'],input_sha256=request['input_sha256'],
            status='SCORED',score={'fixture':True})
        if mode=='wrong-id':response['sequence']+=1
        if mode=='metric-error':response.update(status='METRIC_ERROR',error_type='ValueError')
        emit(response)


class WorkerTests(unittest.TestCase):
    def assert_closed(self,c):
        receipt=c.close();self.assertTrue(receipt['all_exact_owners_exited']);self.assertTrue(receipt['pipe_threads_closed'])
        for owner in receipt['owners']:self.assertIsNone(exact_process(owner))

    def test_real_persistent_scoring_and_empty_vs_failure(self):
        c=MetricProcess();c.start()
        try:
            a=c.score(truth(),prediction(),timeout_seconds=15);b=c.score(truth(),dict(job_id='case_O0',status='FAILED'),timeout_seconds=5)
            self.assertEqual(a['score']['primary_wer']['deletions'],2);self.assertIsNone(b['score']['primary_wer'])
            self.assertEqual(a['owner'],b['owner']);self.assertEqual(b['score']['reference_words'],2)
        finally:self.assert_closed(c)

    def test_timeout_stops_exact_child_and_launcher(self):
        c=FixtureProcess('hang');c.start();before=time.monotonic()
        with self.assertRaises(MetricProcessError) as e:c.score({}, {},timeout_seconds=.2)
        self.assertEqual(e.exception.status,'TIMEOUT');self.assertLess(time.monotonic()-before,8);self.assert_closed(c)

    def test_protocol_eof_oversize_wrong_sequence_and_error(self):
        for mode,expected in [('eof','PROTOCOL_ERROR'),('oversize','PROTOCOL_ERROR'),('wrong-id','PROTOCOL_ERROR'),('metric-error','METRIC_ERROR')]:
            with self.subTest(mode=mode):
                c=FixtureProcess(mode);c.start()
                with self.assertRaises(MetricProcessError) as e:c.score({}, {},timeout_seconds=5)
                self.assertEqual(e.exception.status,expected);self.assert_closed(c)

    def test_startup_and_foreign_owner_rejected(self):
        for mode in ('startup-eof','foreign-owner'):
            with self.subTest(mode=mode):
                c=FixtureProcess(mode)
                with self.assertRaises(MetricProcessError):c.start()
                self.assert_closed(c)

    def test_stderr_is_bounded_and_drained(self):
        c=FixtureProcess('stderr');c.start();c.score({}, {},timeout_seconds=5);self.assert_closed(c)
        self.assertEqual(c.stderr_total,100000);self.assertEqual(len(c.stderr),65536)

    def test_creation_identity_mismatch_is_not_owned(self):
        import psutil
        owner=identity(psutil.Process());owner['create_time']-=1
        self.assertIsNone(exact_process(owner))


def plan_fixture(scope='main'):
    jobs=[dict(job_id=f's{i}_{tap}',audio_path='fixture.wav',audio_sha256='0'*64,frames=16000,sample_rate_hz=16000,
        gain=1,reset_between_scenes=True,tap=tap) for i in range(240) for tap in ('O0','O1')]
    panel=jobs[:24];selected=jobs if scope=='main' else panel
    modes=['open_with_names'] if scope=='main' else ['anonymous_conversation','enrolled_names','selected_focus','selected_closed']
    rows=[]
    for job,(a,d,e),mode in product(selected,product(('A0','A1','A2','A3'),('D0','D1'),('E0','E1')),modes):
        c=dict(variant=a,diarization=d,encoder=e,mode=mode);parents=[{'fixture':'a'},{'fixture':'s'}]
        key=f'{a}_{d}_{e}_{job["job_id"]}_{mode}'
        value=dict(audio=job,contract=c,context={},parents=parents,clock='MODELED_COMPONENT_AVAILABILITY_AND_100MS_SOURCE_CURSOR')
        rows.append(dict(cell_id=key,job_id=job['job_id'],composition=f'{a}_{d}_{e}',contract=c,parents=parents,
            cache_key=fingerprint(value),integrated_N4_cells=0,physical_widget_observed=False))
    return dict(schema='n4-integrated-method-bank-plan-v1',status='PREPARED_REVIEWED_COMPONENT_JOIN_ONLY',scope=scope,
        main_mode='open_with_names',jobs=jobs,context={},rows=rows,required=len(rows)),dict(jobs=jobs),dict(jobs=panel)


class BankTests(unittest.TestCase):
    def test_exact_main_and_mode_panel_census(self):
        for scope,expected in [('main',7680),('modes-panel',1536)]:
            p,m,q=plan_fixture(scope);self.assertEqual(len(validate_plan(p,m,q)),480);self.assertEqual(p['required'],expected)

    def test_parent_hash_duplicate_and_missing_rejected(self):
        p,m,q=plan_fixture();p['rows'][0]['parents'][0]['fixture']='wrong'
        with self.assertRaises(ValueError):validate_plan(p,m,q)
        p,m,q=plan_fixture();p['rows'][0]=deepcopy(p['rows'][1])
        with self.assertRaises(ValueError):validate_plan(p,m,q)
        p,m,q=plan_fixture();p['rows'].pop()
        with self.assertRaises(ValueError):validate_plan(p,m,q)

    def test_failed_prefix_retains_whole_denominator(self):
        p,_,_=plan_fixture();r=dict(status='FAILED_PRESERVED',total=7680,completed=2,failed=1,not_tested=7677,
            failed_cell=p['rows'][2]['cell_id'],cells=[{'path':'a'},{'path':'b'}])
        validate_terminal(r,p);r['failed_cell']=p['rows'][3]['cell_id']
        with self.assertRaises(ValueError):validate_terminal(r,p)
        r['failed_cell']=p['rows'][2]['cell_id'];r['not_tested']-=1
        with self.assertRaises(ValueError):validate_terminal(r,p)

    def test_execution_complete_metric_timeout_is_distinct(self):
        a=unavailable(truth(),'COMPLETE','TIMEOUT');b=unavailable(truth(),'FAILED','EXECUTION_FAILED')
        totals=pool([dict(score=a),dict(score=b)])
        self.assertEqual(totals['unscored_metric_reference_words'],2)
        self.assertEqual(totals['unscored_execution_reference_words'],2)
        self.assertIsNone(totals['primary_nonoverlap_WER'])

    def test_count_weighted_and_paired_missing_denominators(self):
        rows=[];strata={}
        for i in range(9):
            case=f's{i}';strata[case]=dict(case_id=case,dependency_cluster=f'd{i}',room=f'r{i%3}',actor_cluster=f'a{i}',family_id='f')
            for tap,words in [('O0',2),('O1',20)]:
                for c,errors in [('A0_D0_E0',2),('A1_D1_E1',1)]:
                    s=unavailable(dict(truth(),job_id=f'{case}_{tap}'),'COMPLETE','TIMEOUT')
                    s['reference_words']=words
                    if not (i==0 and c=='A1_D1_E1'):
                        s.update(metric_status='SCORED',primary_wer=dict(errors=errors,words=words,substitutions=errors,deletions=0,insertions=0))
                    rows.append(dict(composition=c,mode='open_with_names',job_id=f'{case}_{tap}',case_id=case,tap=tap,score=s))
        result=report(rows,strata,scope='fixture');paired=next(r for r in result['paired'] if r['metric']=='primary_wer')
        self.assertEqual(paired['required_pairs'],18);self.assertEqual(paired['result']['pairs'],16)
        self.assertEqual(paired['excluded_reference_words'],22);self.assertEqual(paired['result']['clusters'],8)
        self.assertAlmostEqual(paired['result']['candidate']['rate'],16/176)
        self.assertEqual(paired['result']['bootstrap_status'],'DESCRIPTIVE')
        with self.assertRaises(ValueError):report(rows+[rows[0]],strata,scope='duplicate')


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--fixture':fixture(sys.argv[2],sys.argv[3])
    else:pin();unittest.main()
