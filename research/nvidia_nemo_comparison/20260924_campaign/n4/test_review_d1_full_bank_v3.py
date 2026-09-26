"""Full paired D1 review fixture, no models. See README_D1_FULL_BANK.md."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from common import bind,freeze,fingerprint,load
from d0_bank_components import event_digest
from d1_full_bank import component_key
import review_d1_full_bank_v3 as reviewer
import test_d1_lane_components as lane
import test_asr_full_bank as full


class TestD1FullReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import soundfile as sf
        lane.TestD1ActualLoop.setUpClass()
        from app.pipeline import effective_profile
        from app.paths import pipeline_config
        from app.n2_models import redim_namespace
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)/'run';cls.root.mkdir()
        fixture=lane.TestD1ActualLoop();fixture.setup_capture()
        wave=cls.root/'fixture.wav';sf.write(wave,fixture.wave,16000,subtype='FLOAT')
        cls.jobs=full.bank()
        for job in cls.jobs:job.update(audio_path=str(wave),audio_sha256=bind(wave)['sha256'],frames=40005)
        model=cls.root/'stub-model';model.write_bytes(b'not executable; unit test placeholder')
        runtime={'embedding_namespace':{'model':'unit-test-e1','dimension':192},'nemotron_model':str(model),
            'nemotron_library_sha256':'unit-test-library'}
        freeze(cls.root/'runtime.json',runtime)
        profiles={tap:effective_profile('balanced','anonymous_conversation',tap) for tap in ['O0','O1']}
        source=Path(lane.__file__).parent # actual app modules are already loaded by the frozen-loop fixture
        cls.contract=dict(output=str(cls.root),source=str(source),models_root=str(cls.root/'unused-models'),
            total=960,jobs=cls.jobs,encoders=['E0','E1'],profiles={k:v.to_dict() for k,v in profiles.items()},
            component_contract={'unit_test_only':True,'runtime':bind(cls.root/'runtime.json')})
        freeze(cls.root/'ADMISSION.json',cls.contract);admission=bind(cls.root/'ADMISSION.json')
        encoders=[]
        for enc in ['E0','E1']:
            config=profiles['O0'].apply(pipeline_config(cls.root/'unused',cls.root/'unused-models'))
            namespace=runtime['embedding_namespace'] if enc=='E1' else redim_namespace(config)
            fixture=lane.TestD1ActualLoop();capture=fixture.setup_capture();fixture.encoder.namespace=namespace
            fixture.native.manifest=lambda:dict(model_sha256=bind(model)['sha256'],library_sha256='unit-test-library',
                native_output_sec_per_frame=.01,gpu=False,profile={'name':'low_latency'})
            summary=capture.run_capture(fixture.encoder);template=fixture.log.getvalue()
            directory=cls.root/enc;directory.mkdir();cells={}
            for job in cls.jobs:
                cell_dir=directory/job['job_id'];cell_dir.mkdir();event_path=cell_dir/'D1_EVENTS.jsonl.gz'
                data=template.replace('test-scene',job['job_id']).encode('utf-8')
                with gzip.open(event_path,'wb') as stream:stream.write(data)
                cell_summary=json.loads(json.dumps(summary).replace('test-scene',job['job_id']))
                profile=profiles[job['tap']].to_dict()
                cell=dict(schema='n4-d1-component-cell-v1',status='COMPLETE',job=job,encoder=enc,
                    admission_sha256=admission['sha256'],cache_key=component_key(cls.contract,job,enc,profile),
                    profile_sha256=fingerprint(profile),namespace=namespace,summary=cell_summary,events=bind(event_path),
                    events_expanded=event_digest(event_path),cpu_affinity=[4],actual_neural_inference=True,integrated_N4_cells=0)
                freeze(cell_dir/'RESULT.json',cell);cells[job['job_id']]=bind(cell_dir/'RESULT.json')
            freeze(directory/'RESULT.json',dict(status='COMPLETE',encoder=enc,completed=480,total=480,cells=cells,cpu_affinity=[4]))
            encoders.append(bind(directory/'RESULT.json'))
            freeze(directory/'RESULT_INDEX.json',dict(completed=480,total=480,cells=cells))
        cls.final=dict(status='FULL_BANK_COLLECTED_REQUIRES_REVIEW',completed=960,total=960,
            owner={'pid':0,'create_time':-1},child=None,admission=admission,encoders=encoders,
            predecessor_review={'unit_test_only':True})
        freeze(cls.root/'RESULT.json',cls.final)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_all_960_full_logs_and_paired_queries_pass(self):
        args=SimpleNamespace(run=self.root,output=self.root.parent/'accepted')
        with patch.object(reviewer,'verify_admission',return_value=self.contract),patch.object(reviewer,'require_predecessor',return_value=self.final['predecessor_review']):
            result=reviewer.review(args)
        self.assertEqual(result['status'],'PASS_D1_FULL_BANK_COMPONENTS_ONLY')
        self.assertEqual(result['matched_query_windows_per_encoder'],3*480)
        self.assertEqual(result['native_frames_per_encoder'],251*480)
        self.assertEqual(result['short_runs_per_encoder'],480)
        self.assertEqual(result['integrated_N4_cells'],0)

    def test_partial_final_or_missing_index_cannot_pass(self):
        for mode in ['final','index']:
            def changed(path):
                doc=load(path)
                if mode=='final' and Path(path)==self.root/'RESULT.json':doc['completed']=959
                if mode=='index' and Path(path)==self.root/'E0/RESULT_INDEX.json':doc['cells'].pop(self.jobs[-1]['job_id'])
                return doc
            with patch.object(reviewer,'load',side_effect=changed),patch.object(reviewer,'verify_admission',return_value=self.contract),patch.object(reviewer,'require_predecessor',return_value=self.final['predecessor_review']):
                with self.assertRaises(ValueError):reviewer.review(SimpleNamespace(run=self.root,output=self.root.parent/'rejected'))


if __name__=='__main__':unittest.main()
