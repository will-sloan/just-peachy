"""Model-free restart selection, identity, admission and payload regressions."""
from copy import deepcopy
from unittest.mock import patch
import unittest

from common import bind, fingerprint, freeze
from test_paced_panel_plan import selection
import test_paced_panel_plan_v3 as fixture
import restart_application_plan as subject

CONTEXT = {}
OUTPUT = None


def panel(candidates=None):
    jobs,short,anchors,catalog,reviews,context,*_ = fixture.fixture_context()
    return subject.panels.build_plan(selection(candidates or [subject.original.BASELINE,'A3_D1_E1'],reviews),
        reviews,jobs,short,anchors,catalog,context)


def plan(candidates=None):
    return subject.build_plan({'development_fixture':'panel'},panel(candidates),CONTEXT['qualification'])


def rekey_panel_row(value, row):
    row['cache_key'] = fingerprint(dict(job=row['job'],contract=row['contract'],execution=value['execution'],
        kind=row['kind'],repeat=row['repeat'],context_sha256=fingerprint(value['context'])))


class RestartPlanTests(unittest.TestCase):
    def test_two_taps_two_sessions_same_full_file(self):
        value=plan(); self.assertEqual(value['required'],4); self.assertEqual(value['required_sessions'],8)
        self.assertEqual([r['job']['tap'] for r in value['rows']],['O0','O1','O0','O1'])
        self.assertEqual(value['rows'][0]['job'],value['rows'][2]['job'])
        self.assertEqual(value['rows'][1]['job'],value['rows'][3]['job'])
        self.assertTrue(value['restart']['same_controller_ui_worker_models'])
        self.assertEqual(value['rows'][0]['stop_after_samples'],357440)
        self.assertEqual(value['rows'][0]['job']['frames'],715127)

    def test_exact_child_allowlist_has_no_evaluator_or_stop_metadata(self):
        value=plan(); payload=subject.execution_payload(value,0)
        self.assertEqual(set(payload),set(subject.panels.execution_payload(panel(),0)))
        self.assertEqual(len(payload),13); self.assertEqual(len(payload['job']),8)
        for key in ('restart','stop_after_samples','reviews','selection','evaluator_truth','context','panel','lifecycle_qualification'):
            self.assertNotIn(key,payload)
        self.assertEqual(subject.stop_after_samples(payload['job']),value['rows'][0]['stop_after_samples'])
        payload['job']['frames']=1; self.assertNotEqual(value['rows'][0]['job']['frames'],1)

    def test_all_six_candidates_preserve_baseline_and_unique_pairs(self):
        chosen=[subject.original.BASELINE]+sorted(subject.original.COMPOSITIONS-{subject.original.BASELINE})[:5]
        value=plan(chosen); self.assertEqual(value['required'],12); self.assertEqual(value['required_sessions'],24)
        self.assertEqual(len({r['cache_key'] for r in value['rows']}),12)
        self.assertEqual(len({r['cell_id'] for r in value['rows']}),12)
        for index in range(12): subject.execution_payload(value,index)
        with self.assertRaises(ValueError): plan(chosen+['A3_D1_E1'])

    def test_baseline_and_exclusion_census_are_required(self):
        for mutation in ('no-baseline','reverse','duplicate','exclusions'):
            value=panel()
            if mutation=='no-baseline': value['selection']['selected'].pop(0)
            if mutation=='reverse': value['selection']['selected'].reverse()
            if mutation=='duplicate': value['selection']['selected'].append(value['selection']['selected'][0])
            if mutation=='exclusions': value['selection']['excluded'].pop()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): subject.build_plan({},value,{})

    def test_short_panel_cannot_be_relabelled(self):
        with self.assertRaises(ValueError): subject.execution_payload(panel(),0)
        with self.assertRaises(ValueError): subject.panels.execution_payload(plan(),0)
        value=panel(); value['schema']='n4-paced-panel-plan-v2'
        with self.assertRaises(ValueError): subject.build_plan({},value,{})

    def test_fixed_anchor_duration_gain_and_reference_firewall(self):
        value=plan()['rows'][0]['job']
        for field,replacement in (('frames',31999),('frames',1920001),('job_id','N2_S45_08_07_O0'),
                ('tap','O1'),('gain',2),('reset_between_scenes',False),('speaker','hidden truth')):
            job=deepcopy(value); job[field]=replacement
            with self.subTest(field=field),self.assertRaises(ValueError): subject.stop_after_samples(job)
        for frames in (32000,32001,715127,1920000):
            job=dict(value,frames=frames); threshold=subject.stop_after_samples(job)
            self.assertEqual(threshold%320,0); self.assertLess(threshold,frames-640)

    def test_source_panel_duplicates_missing_anchors_and_contracts_rejected(self):
        for mutation in ('missing','duplicate','route','contract','absent-anchor'):
            value=panel()
            if mutation=='missing': value['rows'].pop()
            if mutation=='duplicate': value['rows'][-1]=deepcopy(value['rows'][0])
            if mutation=='route': value['rows'][0]['composition']='A2_D0_E0'
            if mutation=='contract':
                value['rows'][0]['contract']['backend_key']='foreign'; rekey_panel_row(value,value['rows'][0])
            if mutation=='absent-anchor':
                row=next(r for r in value['rows'] if r['job']['job_id']==subject.JOBS[0] and r['kind']=='panel')
                row['job']=dict(row['job'],job_id='N2_S45_03_04_O0'); rekey_panel_row(value,row)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): subject.build_plan({},value,{})

    def test_same_audio_identity_across_candidates_and_repeats(self):
        for field,replacement in (('audio_sha256','1'*64),('frames',715447),('audio_path','X:/foreign.wav')):
            value=panel(); row=next(r for r in value['rows'] if r['job']['job_id']==subject.JOBS[0])
            row['job'][field]=replacement; rekey_panel_row(value,row)
            with self.subTest(field=field),self.assertRaises(ValueError): subject.build_plan({},value,{})

    def test_policy_context_and_lineage_mutations_invalidate_payload(self):
        for field in ('panel','lifecycle_qualification','restart','context'):
            value=plan()
            if field=='context': value[field]['models_root']='foreign'
            elif field=='restart': value[field]['sessions_per_pair']=1
            else: value[field]={'different':True}
            with self.subTest(field=field),self.assertRaises(ValueError): subject.execution_payload(value,0)

    def test_recomputed_key_cannot_hide_wrong_row_identity_or_threshold(self):
        for field,replacement in (('cell_id','other'),('composition','A3_D1_E1'),('kind','continuity'),
                ('repeat',1),('stop_after_samples',320),('collection_credit',1)):
            value=plan(); row=value['rows'][0]; row[field]=replacement; row['cache_key']=fingerprint(subject.row_key(value,row))
            with self.subTest(field=field),self.assertRaises(ValueError): subject.execution_payload(value,0)

    def test_no_execution_or_acceptance_from_preparation(self):
        for field in ('source_execution_authorized','actual_restart_qualified','N4_accepted','integrated_N4_cells'):
            value=plan(); value[field]=1 if field=='integrated_N4_cells' else True
            with self.subTest(field=field),self.assertRaises(ValueError): subject.execution_payload(value,0)

    def test_population_indices_and_hidden_fields_fail_closed(self):
        for mutation in ('rows','required','sessions','candidate','extra'):
            value=plan()
            if mutation=='rows': value['rows'].pop()
            if mutation=='required': value['required']-=1
            if mutation=='sessions': value['required_sessions']-=1
            if mutation=='candidate': value['candidates'].reverse()
            if mutation=='extra': value['rows'][0]['truth']='hidden'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): subject.execution_payload(value,0)
        for index in (True,-1,4,1.5):
            with self.subTest(index=index),self.assertRaises(ValueError): subject.execution_payload(plan(),index)

    def test_production_reconstruction_refuses_partial_upstream(self):
        target=OUTPUT/'partial'; target.mkdir()
        freeze(target/'PLAN.json',panel()); freeze(target/'ADMISSION.json',dict(owner={'pid':1,'create_time':0},code=[]))
        freeze(target/'RESULT.json',dict(status='PARTIAL',admission=bind(target/'ADMISSION.json')))
        with self.assertRaises(ValueError): subject.reconstruct(target/'PLAN.json')

    def test_live_lifecycle_probe_cannot_qualify_plan(self):
        with patch.object(subject,'exact_process',return_value=object()),self.assertRaises(ValueError):
            subject.lifecycle_qualification()

    def test_lifecycle_qualification_matches_preserved_receipt(self):
        binding,value=subject.lifecycle_qualification()
        self.assertEqual(binding,CONTEXT['qualification']); self.assertEqual(len(value['code']),102)

    def test_actual_fixed_saved_anchors_match_duration_policy(self):
        self.assertEqual(tuple(j['job_id'] for j in CONTEXT['actual_jobs']),subject.JOBS)
        for job in CONTEXT['actual_jobs']:
            threshold=subject.stop_after_samples(job)
            self.assertLess(threshold,job['frames']); self.assertGreater(threshold,0)
