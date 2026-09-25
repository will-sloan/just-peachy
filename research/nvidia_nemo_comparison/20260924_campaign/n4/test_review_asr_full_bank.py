"""Complete 1920-cell integrity fixture, no models. README_ASR_FULL_BANK.md."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common import bind, freeze, fingerprint, load
import review_asr_full_bank as reviewer
from asr_full_bank import component_key
import test_asr_full_bank as full_fixtures
import test_review_asr_components as lane_fixtures


class TestFullReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lane_fixtures.TestASRReview.setUpClass()
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)/'run';cls.root.mkdir()
        cls.jobs=full_fixtures.bank();wave=cls.root/'test-wave.bin';wave.write_bytes(b'unit test placeholder audio binding')
        for job in cls.jobs:job.update(audio_path=str(wave),audio_sha256=bind(wave)['sha256'])
        profile={'asr':{'journal_read_ms':100}}
        cls.contract=dict(jobs=cls.jobs,variants=['A0','A1','A2','A3'],total=1920,
            component_contract={'unit_test_only':True},profiles={'O0':profile,'O1':profile})
        freeze(cls.root/'ADMISSION.json',cls.contract);admission=bind(cls.root/'ADMISSION.json')
        variants=[]
        for variant in cls.contract['variants']:
            fixture=lane_fixtures.TestASRReview();fixture.setUp()
            try:
                template,_=fixture.fixture(variant);event_bytes=Path(template['events']['path']).read_bytes()
            finally:fixture.tearDown()
            cells={};directory=cls.root/variant;directory.mkdir()
            for job in cls.jobs:
                cell_dir=directory/job['job_id'];cell_dir.mkdir();events=cell_dir/'ASR_EVENTS.jsonl.gz';events.write_bytes(event_bytes)
                cell=deepcopy(template)
                cell.update(schema='n4-asr-component-cell-v1',status='COMPLETE',job=job,events=bind(events),
                    admission_sha256=admission['sha256'],profile_sha256=fingerprint(profile),
                    cache_key=component_key(cls.contract,job,variant,profile),
                    actual_neural_inference=True,cpu_affinity=[4],integrated_N4_cells=0)
                freeze(cell_dir/'RESULT.json',cell);cells[job['job_id']]=bind(cell_dir/'RESULT.json')
            index=dict(status='COMPLETE',variant=variant,completed=480,total=480,cells=cells,cpu_affinity=[4])
            freeze(directory/'RESULT.json',index);variants.append(bind(directory/'RESULT.json'))
            freeze(directory/'RESULT_INDEX.json',dict(cells=cells,completed=480,total=480))
        cls.final=dict(status='FULL_BANK_COLLECTED_REQUIRES_REVIEW',completed=1920,total=1920,
            owner={'pid':0,'create_time':-1},child=None,integrated_N4_cells=0,admission=admission,variants=variants)
        freeze(cls.root/'RESULT.json',cls.final)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_all_1920_cells_and_every_expanded_log_scanned(self):
        with patch.object(reviewer,'verify_admission',return_value=self.contract):
            result=reviewer.review(self.root,self.root.parent/'accepted')
        self.assertEqual(result['status'],'PASS_ASR_FULL_BANK_COMPONENTS_ONLY')
        self.assertEqual(result['per_variant_counts'],{v:480 for v in self.contract['variants']})
        self.assertEqual(result['totals']['source_samples'],3205*1920)
        self.assertEqual(result['integrated_N4_cells'],0)
        self.assertFalse(result['Controller_or_widget_parity_qualified'])

    def test_1919_or_smoke_terminal_cannot_pass(self):
        for key,value in [('completed',1919),('status','SMOKE_COLLECTED_REQUIRES_REVIEW')]:
            bad=deepcopy(self.final);bad[key]=value
            with patch.object(reviewer,'load',return_value=bad):
                with self.assertRaisesRegex(ValueError,'1920'):reviewer.review(self.root,self.root.parent/'rejected')

    def test_variant_missing_cell_rejected_even_if_claiming_480(self):
        def changed(path):
            doc=load(path)
            if Path(path)==self.root/'A0/RESULT.json':doc['cells'].pop(self.jobs[-1]['job_id'])
            return doc
        with patch.object(reviewer,'load',side_effect=changed),patch.object(reviewer,'verify_admission',return_value=self.contract):
            with self.assertRaisesRegex(ValueError,'index'):reviewer.review(self.root,self.root.parent/'rejected')

    def test_wrong_final_child_is_not_a_terminal_result(self):
        def changed(path):
            doc=load(path)
            if Path(path)==self.root/'RESULT.json':doc['child']={'pid':999,'create_time':1}
            return doc
        with patch.object(reviewer,'load',side_effect=changed),patch.object(reviewer,'verify_admission',return_value=self.contract):
            with self.assertRaisesRegex(ValueError,'census'):reviewer.review(self.root,self.root.parent/'rejected')


if __name__=='__main__':unittest.main()
