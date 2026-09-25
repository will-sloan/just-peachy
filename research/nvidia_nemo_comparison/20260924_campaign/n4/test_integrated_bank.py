"""Full-census join and actual boundary regressions. README_INTEGRATED_BANK.md."""
from copy import deepcopy
from itertools import product
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from common import bind,fingerprint,freeze,load,verify
from integrated_bank_plan import build_join,exact_jobs,review_sources,read_component_bank,MAIN_MODE
from integrated_bank import predict_cell,guard,run,GIB
from mode_galleries import backend_contract
from probe_controller_projection import read_replay
from probe_application_publication import semantics

HERE=Path(__file__).resolve().parent


class TestIntegratedBank(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        public=load(HERE/'APPLICATION_PUBLICATION_CHECK_V1.json');verify(public['private_receipt'])
        cls.publication=load(public['private_receipt']['path']);cls.source=public['source_receipt'];verify(cls.source)
        source=Path(load(cls.source['path'])['prototype']);sys.path[:0]=[str(source),str(source/'vendor')]
        cls.gallery_binding=public['gallery_preparation'];verify(cls.gallery_binding)
        cls.galleries=load(cls.gallery_binding['path']);cls.catalog=load(cls.galleries['catalog']['path'])
        prep=load(HERE/'PREPARATION_V2_CHECK.json');verify(prep['preparation']);out=load(prep['preparation']['path'])['outputs']
        cls.manifest=next(b for b in out if Path(b['path']).name=='AUDIO_ONLY_480.json');verify(cls.manifest)
        cls.jobs=load(cls.manifest['path'])['jobs']
        panel=next(b for b in out if Path(b['path']).name=='PACED_AUDIO_ONLY_24.json');verify(panel)
        cls.panel=load(panel['path'])['jobs']
        cls.records=[]
        for kind,variants in [('ASR',('A0','A1','A2','A3')),('D0',('E0','E1')),('D1',('E0','E1'))]:
            for variant,job in product(variants,cls.jobs):
                key=fingerprint([kind,variant,job]);binding=dict(path=f'fixture/{key}',sha256=key,bytes=1)
                cls.records.append(dict(kind=kind,variant=variant,job=deepcopy(job),result=binding,events=binding,
                    cache_key=key,namespace=None if kind=='ASR' else cls.galleries['encoders'][variant]['conditions']['open']['namespace']))
        wiring=load(HERE/'ACCEPTED_SOURCE_CATALOG_CHECK.json')
        cls.context=dict(gallery_preparation=cls.gallery_binding,runtimes={Path(b['path']).name:b for b in wiring['inputs']
            if Path(b['path']).name in ('n2_runtime.json','n3_runtime.json')})

    def join(self,records=None,scope='main',jobs=None,catalog=None,context=None,panel=None):
        return build_join(self.jobs if jobs is None else jobs,self.catalog if catalog is None else catalog,
            self.records if records is None else records,self.galleries,context or {'fixture_only':True},
            scope=scope,panel_jobs=self.panel if panel is None else panel)

    def test_full_main_and_modes_panel_exact_counts_no_execution_credit(self):
        main=self.join();panel=self.join(scope='modes-panel')
        self.assertEqual(len(main['rows']),7680);self.assertEqual(len(panel['rows']),1536)
        self.assertEqual({r['contract']['mode'] for r in main['rows']},{MAIN_MODE})
        self.assertEqual(len({r['contract']['mode'] for r in panel['rows']}),4)
        self.assertTrue(all(r['integrated_N4_cells']==0 and not r['physical_widget_observed'] for r in main['rows']))
        self.assertEqual(sum(r['D0_E1_association_qualification']=='NOMINAL_UNQUALIFIED_C_SCALE_FAILED' for r in main['rows']),1920)
        self.assertEqual(len({r['cache_key'] for r in main['rows']+panel['rows']}),9216)
        self.assertEqual([r['key'] for r in main['unavailable_catalog_entries']],['multitalker'])

    def test_missing_duplicate_foreign_and_changed_audio_parent_rejected(self):
        for rows in (self.records[:-1],self.records+[self.records[0]]):
            with self.assertRaises(ValueError):self.join(records=rows)
        rows=deepcopy(self.records);rows[0]['job']['gain']=2
        with self.assertRaisesRegex(ValueError,'altered component'):self.join(records=rows)
        rows=deepcopy(self.records);rows[0]['variant']='A9'
        with self.assertRaises(ValueError):self.join(records=rows)

    def test_encoder_namespace_and_catalog_cannot_be_substituted(self):
        rows=deepcopy(self.records);rows[-1]['namespace']={'wrong':'namespace'}
        with self.assertRaisesRegex(ValueError,'namespace'):self.join(records=rows)
        catalog=deepcopy(self.catalog);catalog['backends'].pop()
        with self.assertRaisesRegex(ValueError,'16-composition'):self.join(catalog=catalog)
        catalog=deepcopy(self.catalog);catalog['backends'].append(catalog['backends'][0])
        with self.assertRaises(ValueError):self.join(catalog=catalog)

    def test_truth_firewall_and_panel_membership(self):
        jobs=deepcopy(self.jobs);jobs[0]['reference_text']='never passed to prediction'
        with self.assertRaises(ValueError):self.join(jobs=jobs)
        panel=deepcopy(self.panel);panel[0]['audio_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'exact subset'):self.join(panel=panel)
        with self.assertRaises(ValueError):self.join(panel=self.panel[:-1])

    def test_cache_identity_changes_with_parent_and_policy(self):
        original=self.join();rows=deepcopy(self.records);rows[0]['cache_key']='changed'
        altered=self.join(records=rows);indices=[i for i,(a,b) in enumerate(zip(original['rows'],altered['rows'])) if a['cache_key']!=b['cache_key']]
        self.assertEqual(len(indices),4)
        policy=self.join(context={'fixture_only':True,'clock_policy':'different'})
        self.assertTrue(all(a['cache_key']!=b['cache_key'] for a,b in zip(original['rows'],policy['rows'])))

    def test_queue_ready_is_not_component_acceptance(self):
        for kind in ('ASR','D0','D1'):
            for status in ('RUNNING','READY_FOR_REVIEW','FULL_BANK_COLLECTED_REQUIRES_REVIEW'):
                with self.assertRaisesRegex(ValueError,'passed terminal review'):review_sources(kind,{'status':status})

    def test_review_missing_or_duplicate_rows_rejected(self):
        rows=[{'result':dict(path=str(i))} for i in range(1920)]
        r=dict(status='PASS_ASR_FULL_BANK_COMPONENTS_ONLY',component_cells=1920,admission={},final_result={},cells=rows)
        self.assertEqual(len(review_sources('ASR',r)[2]),1920)
        r['cells'][-1]=r['cells'][0]
        with self.assertRaisesRegex(ValueError,'duplicated'):review_sources('ASR',r)
        r['cells'].pop()
        with self.assertRaises(ValueError):review_sources('ASR',r)

    def test_resource_guard_stops_before_allocating_or_crossing_cutoff(self):
        future={'target_utc':'2099-01-01T00:00:00+00:00'}
        with tempfile.TemporaryDirectory() as tmp,patch('integrated_bank.shutil.disk_usage',return_value=SimpleNamespace(free=200*GIB)):
            guard(Path(tmp),GIB,future,0)
            with self.assertRaisesRegex(ValueError,'allocation'):guard(Path(tmp),GIB,future,GIB)
            with self.assertRaisesRegex(TimeoutError,'Packaging'):guard(Path(tmp),GIB,{'target_utc':'2000-01-01T00:00:00+00:00'},0)
        with patch('integrated_bank.shutil.disk_usage',return_value=SimpleNamespace(free=40*GIB)):
            with self.assertRaisesRegex(ValueError,'floor'):guard(Path('unused'),GIB,future,0)

    def test_real_reviewed_d0_960_parent_join_and_exact_owner_guard(self):
        public=load(HERE/'D0_FULL_BANK_REVIEW_V1.json');b=public['private_review']
        result=read_component_bank('D0',b,source_binding=self.source,manifest_binding=self.manifest,jobs=exact_jobs(self.jobs))
        self.assertEqual(len(result),960);self.assertEqual({r['variant'] for r in result},{'E0','E1'})
        owner=load(load(b['path'])['inputs'][0]['path'])['owner']
        with patch('psutil.Process',return_value=SimpleNamespace(create_time=lambda:owner['create_time'])):
            with self.assertRaisesRegex(ValueError,'still active'):
                read_component_bank('D0',b,source_binding=self.source,manifest_binding=self.manifest,jobs=exact_jobs(self.jobs))

    def test_actual_prediction_boundary_baseline_and_a3_d1_e1(self):
        keys={tuple(backend_contract(self.catalog,r['key'],MAIN_MODE)[k] for k in ('variant','diarization','encoder')):r['key']
            for r in self.catalog['backends'] if r['implemented']}
        for backend in ('baseline',keys[('A3','D1','E1')]):
            entry=next(r for r in self.publication['checks'] if r['backend']==backend and r['mode']==MAIN_MODE and r['tap']=='O0')
            self.check_real_prediction(entry['inputs'],backend,MAIN_MODE,entry['projection'])

    def check_real_prediction(self,inputs,backend,mode,previous=None):
        parents=[]
        for b in inputs:
            verify(b);c=load(b['path']);parents.append(dict(result=b,cache_key=c['cache_key'],events=c['events']))
        job=load(inputs[0]['path'])['job'];contract=backend_contract(self.catalog,backend,mode)
        row=dict(cell_id='development-boundary',job_id=job['job_id'],contract=contract,parents=parents,
            cache_key=fingerprint(parents),D0_E1_association_qualification='FROZEN_NOMINAL')
        with tempfile.TemporaryDirectory() as tmp:
            result=predict_cell(row,job,self.context,Path(tmp))
            self.assertEqual(result['status'],'COMPLETE_MODELED_APPLICATION_METHODS_ONLY')
            self.assertEqual(result['models_loaded'],0);self.assertTrue(result['controller_closed'])
            projected=read_replay(result['outputs']['projection'])
            if previous:
                old=read_replay(previous)
                self.assertEqual(semantics(projected['final_rows']),semantics(old['final_rows']))
                self.assertEqual([semantics(h['rows']) for h in projected['history']],[semantics(h['rows']) for h in old['history']])
            else:self.assertTrue(result['empty_hypothesis']);self.assertEqual(projected['final_rows'],[])

    def test_actual_empty_prediction_is_successful_not_failed_or_filled(self):
        public=load(HERE/'EMPTY_CONTROLLER_CHECK_V1.json');verify(public['private_receipt'])
        entry=load(public['private_receipt']['path'])['checks'][0]
        self.check_real_prediction(entry['inputs'],'baseline',entry['mode'])

    def lifecycle_fixture(self,tmp):
        root=Path(tmp)/'local';(root/'n4').mkdir(parents=True)
        freeze(root/'supervision/campaign.json',dict(target_utc='2099-01-01T00:00:00+00:00',resource_policy={'new_payload_allowance_gib':50}))
        plan=dict(context={'source_receipt':{'path':str(root/'releases/fixture/SOURCE_RECEIPT.json')},'code':[]},
            jobs=self.jobs[:3],rows=[dict(cell_id='fixture-'+str(i),job_id=j['job_id']) for i,j in enumerate(self.jobs[:3])],required=3)
        path=root/'n4/fixture-plan.json';freeze(path,plan)
        return plan,SimpleNamespace(plan=path,output=root/'n4/fixture-run',allocation_gib=1)

    def test_failed_prediction_preserved_and_remaining_denominators_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,args=self.lifecycle_fixture(tmp)
            def predictor(row,*unused):
                if row['cell_id']=='fixture-1':raise ValueError('fixture prediction failure')
                return {'fixture_only':True}
            with patch('integrated_bank.verify_plan',return_value=plan),patch('integrated_bank.guard'),\
                    patch('asr_full_bank.payload_inventory',return_value={'errors':[],'total_logical_bytes':0}),\
                    patch('integrated_bank.predict_cell',side_effect=predictor):
                with self.assertRaisesRegex(ValueError,'fixture prediction failure'):run(args)
            result=load(args.output/'RESULT.json')
            self.assertEqual((result['completed'],result['failed'],result['not_tested']),(1,1,1))
            self.assertTrue((args.output/'cells/00000/RESULT.json').exists())
            self.assertEqual(result['integrated_N4_cells'],0)

    def test_pre_cell_resource_stop_does_not_invent_a_failed_prediction(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,args=self.lifecycle_fixture(tmp)
            with patch('integrated_bank.verify_plan',return_value=plan),\
                    patch('integrated_bank.guard',side_effect=[None,ValueError('fixture budget stop')]),\
                    patch('asr_full_bank.payload_inventory',return_value={'errors':[],'total_logical_bytes':0}),\
                    patch('integrated_bank.predict_cell') as predictor:
                with self.assertRaisesRegex(ValueError,'fixture budget stop'):run(args)
                predictor.assert_not_called()
            result=load(args.output/'RESULT.json')
            self.assertEqual((result['completed'],result['failed'],result['not_tested']),(0,0,3))
            self.assertIsNone(result['failed_cell']);self.assertEqual(result['blocked_before_cell'],'fixture-0')


if __name__=='__main__':unittest.main()
