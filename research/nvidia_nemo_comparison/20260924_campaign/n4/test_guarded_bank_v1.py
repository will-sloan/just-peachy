"""Provenance rejection and retained dispatch-schema tests; README_GUARDED_BANK_V1.md."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import bind, freeze, load
from guarded_execution_v1 import SCHEMA, check_envelope, check_cell, classify_dispatch, validate_execution
from guarded_method_bank_v1 import collect_one


class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.pb=dict(path='plan.json',sha256='a'*64,bytes=1)
        self.q=dict(path='qualification.json',sha256='b'*64,bytes=2)
        self.code=[dict(path='qualified.py',sha256='c'*64,bytes=3)]
        self.e=dict(schema=SCHEMA,kind='method',original_plan=self.pb,code=self.code,qualification=self.q,
            allocation_bytes=1536*1024**2,maximum_seconds=14400,development_only=False,
            prediction_implementation='UNCHANGED_QUALIFIED_V3')
    def check(self):check_envelope(self.e,self.pb,'method',expected_code=self.code,qualified=self.q)
    def test_exact_envelope(self):self.check()
    def test_foreign_plan_code_kind_qualification_and_probe_are_refused(self):
        for k,v in [('original_plan',{}),('code',[]),('kind','scoring'),('qualification',None),('development_only',True),('schema','old')]:
            with self.subTest(k=k),patch.dict(self.e,{k:v}),self.assertRaises(ValueError):self.check()
    def test_unbounded_boolean_and_empty_budgets_refuse(self):
        for k,v in [('maximum_seconds',True),('maximum_seconds',14401),('maximum_seconds',0),('allocation_bytes',True),('allocation_bytes',9*1024**3)]:
            with self.subTest(k=k),patch.dict(self.e,{k:v}),self.assertRaises(ValueError):self.check()
    def test_cell_keeps_original_cache_and_explicit_new_producer(self):
        row=dict(cell_id='x',job_id='j',cache_key='cache',parents=[],contract={'mode':'anonymous_conversation'})
        cell=dict(row,plan=self.pb,execution_plan=self.q);check_cell(cell,row,self.pb,self.q)
        for k,v in [('execution_plan',{}),('plan',{}),('cache_key','changed'),('contract',{}),('reused_from',{}),('execution_source',{})]:
            with self.subTest(k=k),patch.dict(cell,{k:v}),self.assertRaises(ValueError):check_cell(cell,row,self.pb,self.q)
    def test_collect_does_not_change_predictor_inputs_or_returned_payload(self):
        row=dict(cell_id='x');job={'job_id':'j'};context={'source':'frozen'};value={'status':'COMPLETE','payload':[1,2]}
        calls=[]
        def predictor(r,j,c,o):calls.append((r,j,c,o));return deepcopy(value)
        with tempfile.TemporaryDirectory() as t:
            out=Path(t);b=collect_one(row,job,context,out,self.pb,self.q,predict=predictor)
            self.assertEqual(calls,[(row,job,context,out)])
            self.assertEqual(load(b['path']),dict(value,plan=self.pb,execution_plan=self.q))
    def test_predictor_failure_does_not_seal_a_success(self):
        with tempfile.TemporaryDirectory() as t:
            def fail(*a):raise ValueError('boundary')
            with self.assertRaisesRegex(ValueError,'boundary'):collect_one({}, {}, {},Path(t),self.pb,self.q,predict=fail)
            self.assertFalse((Path(t)/'RESULT.json').exists())


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.local=Path(self.temp.name);self.root=self.local/'n4/dispatch';self.target=self.local/'n4/run'
        self.target.mkdir(parents=True);self.root.mkdir();self.host=dict(pid=11,create_time=100.);self.driver=dict(pid=12,create_time=101.)
        freeze(self.target/'ADMISSION.json',dict(owner=self.driver))
        spec=self.local/'spec.json';freeze(spec,dict(argv=['python','--output',str(self.target)]));self.sb=bind(spec)
        freeze(self.root/'ADMISSION.json',dict(worker_spec=self.sb));self.ab=bind(self.root/'ADMISSION.json')
    def launch(self,**kwargs):freeze(self.root/'STARTED.json',dict(worker_spec=self.sb,**kwargs))
    def test_retained_old_field_is_an_alias(self):
        self.launch(supervisor_start=self.host);v=classify_dispatch(self.root/'ADMISSION.json',self.local,lookup=lambda _:None)
        self.assertEqual(v['state'],'ALIAS_NOT_SECOND_ALLOCATION');self.assertEqual(v['delegate'],bind(self.target/'ADMISSION.json'))
    def test_new_field_requires_exact_admission_and_is_an_alias(self):
        self.launch(supervisor=self.host,admission=self.ab)
        self.assertEqual(classify_dispatch(self.root/'ADMISSION.json',self.local,lookup=lambda _:None)['supervisor'],self.host)
    def test_new_field_without_admission_refuses(self):
        self.launch(supervisor=self.host)
        with self.assertRaisesRegex(ValueError,'admission/start'):classify_dispatch(self.root/'ADMISSION.json',self.local,lookup=lambda _:None)
    def test_ambiguous_owner_fields_refuse(self):
        self.launch(supervisor=self.host,supervisor_start=self.host,admission=self.ab)
        with self.assertRaisesRegex(ValueError,'Ambiguous'):classify_dispatch(self.root/'ADMISSION.json',self.local,lookup=lambda _:None)
    def test_live_host_without_driver_refuses(self):
        self.launch(supervisor=self.host,admission=self.ab)
        with self.assertRaisesRegex(ValueError,'no admitted driver'):
            classify_dispatch(self.root/'ADMISSION.json',self.local,lookup=lambda o:object() if o==self.host else None)
    def test_changed_spec_refuses(self):
        self.launch(supervisor=self.host,admission=self.ab);Path(self.sb['path']).write_text('{}')
        with self.assertRaises(ValueError):classify_dispatch(self.root/'ADMISSION.json',self.local,lookup=lambda _:None)


class RuntimeGateTests(unittest.TestCase):
    def test_live_family_producer_is_rejected_before_cell_reads(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);freeze(p/'EXECUTION_PLAN.json',{});eb=bind(p/'EXECUTION_PLAN.json')
            freeze(p/'ADMISSION.json',dict(owner={'pid':1,'create_time':1.},execution_plan=eb,code=[]))
            freeze(p/'RESULT.json',dict(admission=bind(p/'ADMISSION.json'),execution_plan=eb))
            with patch('guarded_execution_v1.code_bindings',return_value=[]),patch('guarded_execution_v1.exact_process',return_value=object()),self.assertRaisesRegex(ValueError,'remains active'):
                validate_execution(p)


if __name__=='__main__':unittest.main()
