"""Empty-output and nonempty Controller regression. README_CONTROLLER_PROJECTION_V2.md."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

from common import load,verify
from controller_projection_v2 import validate_display_history,project_mode_result,forbid_inference
from application_publication import replay_d0_publication
from test_component_s7_replay import advance
from probe_controller_projection import read_replay


class TestEmptyController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        here=Path(__file__).resolve().parent
        public=load(here/'CONTROLLER_PROJECTION_CHECK_V1.json');verify(public['private_receipt'])
        cls.parent=load(public['private_receipt']['path']);verify(cls.parent['parent'])
        cls.modes=load(cls.parent['parent']['path']);verify(cls.parent['source_receipt'])
        source=Path(load(cls.parent['source_receipt']['path'])['prototype'])
        sys.path[:0]=[str(source),str(source/'vendor')]
        cls.runtimes={Path(b['path']).name:b for b in cls.parent['runtime_inputs']}
        cls.preparation=cls.parent['gallery_preparation'];verify(cls.preparation)
        cls.namespace=load(cls.preparation['path'])['encoders']['E0']['conditions']['none']['namespace']

    def empty(self,mode='anonymous_conversation'):
        return replay_d0_publication([advance('asr',None,1.25)],[advance('speaker',None,1.25)],duration=1.25,
            preparation=self.preparation,backend='baseline',mode=mode,tap='O0',namespace=self.namespace,session_id='empty-method-test')

    def project(self,result):
        with tempfile.TemporaryDirectory() as tmp,forbid_inference():
            return project_mode_result(result,tap='O0',preparation=self.preparation,n2_runtime=self.runtimes['n2_runtime.json'],
                n3_runtime=self.runtimes['n3_runtime.json'],data_root=Path(tmp)/'controller')

    def test_empty_anonymous_and_named_complete_without_phantom_caption(self):
        for mode in ('anonymous_conversation','selected_closed'):
            result=self.project(self.empty(mode))
            self.assertEqual(result['display_inputs'],0);self.assertEqual(result['history'],[])
            self.assertEqual(result['final_rows'],[]);self.assertEqual(result['controller_raw_rows'],[])
            self.assertTrue(result['empty_caption_session']);self.assertTrue(result['controller_closed'])
            self.assertFalse(any(result['model_loads'].values()));self.assertEqual(result['integrated_N4_cells'],0)

    def test_empty_cannot_hide_observations_or_unfinished_work(self):
        original=self.empty()
        for change in (lambda r:r['presentation'].update(raw_observations=1),lambda r:r['worker_counts'].update(closed=False),
                lambda r:r['policy_snapshot'].update(pending_events=1),lambda r:r.pop('publication_method_qualification')):
            result=deepcopy(original);change(result)
            with self.assertRaises(ValueError):validate_display_history(result)

    def test_empty_requires_valid_exact_session_publication_and_two_closures(self):
        original=self.empty()
        for change in (lambda r:r['publication_events'][-1]['payload'].update(session_id='foreign'),
                lambda r:r['publication_events'][-1]['payload'].update(publication_sequence=999),
                lambda r:r['publication_events'].pop(),
                lambda r:r['publication_events'][0].update(event_type='research_asr_observation')):
            result=deepcopy(original);change(result)
            with self.assertRaises(ValueError):validate_display_history(result)

    def test_nonempty_baseline_and_n2_d1_fields_match_prior_projection(self):
        for backend in ('baseline','nemotron_hybrid'):
            old=next(r for r in self.parent['checks'] if r['backend']==backend and r['mode']=='selected_closed' and r['tap']=='O0')
            mr=next(r for r in self.modes['checks'] if (r['backend'],r['mode'],r['job_id'])==(old['backend'],old['mode'],old['job_id']))
            result=self.project(read_replay(mr['output']));previous=read_replay(old['private_output'])
            self.assertEqual(result['final_rows'],previous['final_rows'])
            self.assertEqual(result['display_inputs'],previous['display_inputs'])
            self.assertFalse(result['empty_caption_session'])


if __name__=='__main__':unittest.main()
