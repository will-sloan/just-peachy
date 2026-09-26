"""Versioned context and child firewall regression fixtures."""
from copy import deepcopy
from pathlib import Path
import unittest

from common import bind,freeze,load
import paced_panel_plan as original
import paced_panel_plan_v3 as revised
from test_paced_panel_plan import fixtures,selection

CONTEXT={}
OUTPUT=None


def fixture_context():
    jobs,panel,regression,catalog,old,reviews=fixtures()
    source=deepcopy(CONTEXT['source'])
    scored=dict(source_receipt=source['component_source_receipt'],catalog=source['component_catalog'],
        gallery_preparation=source['component_gallery_preparation'],
        runtimes={Path(b['path']).name:b for b in source['runtimes']},
        manifest={'fixture':'manifest'},panel={'fixture':'panel'})
    common=dict(manifest=scored['manifest'],panel=scored['panel'],regression={'fixture':'regression'},
        models_root='NO_MODEL_PAYLOAD',assets=[],planner_qualification={'fixture':'pending'},code=[])
    context=revised.application_context(scored,source,CONTEXT['source_binding'],CONTEXT['app_binding'],common)
    return jobs,panel,regression,catalog,reviews,context,scored,source,common


class JournalPanelPlanTests(unittest.TestCase):
    def test_paired_census_and_child_allowlist_use_derivative_only(self):
        jobs,panel,regression,catalog,reviews,context,*_=fixture_context()
        plan=revised.build_plan(selection([original.BASELINE,'A3_D1_E1'],reviews),reviews,jobs,panel,regression,catalog,context)
        self.assertEqual(plan['schema'],revised.SCHEMA);self.assertEqual(plan['required'],80)
        self.assertEqual(plan['panel_cases_per_candidate'],24);self.assertEqual(plan['additional_repeats_per_candidate'],16)
        payload=revised.execution_payload(plan,0)
        self.assertEqual(payload['source_receipt'],context['source_receipt'])
        self.assertEqual(payload['gallery_preparation'],context['gallery_preparation'])
        self.assertNotIn('component_source_receipt',payload);self.assertNotIn('application_source_context',payload)
        self.assertNotIn('reviews',payload);self.assertFalse(payload['source_execution_authorized'])
        payload['job']['frames']=1;self.assertNotEqual(plan['rows'][0]['job']['frames'],1)
        self.assertEqual(plan['integrated_N4_cells'],0);self.assertFalse(plan['continuity_included'])

    def test_scored_parent_runtime_and_panel_mismatch_are_rejected(self):
        *_,scored,source,common=fixture_context()
        for field in ('source_receipt','catalog','gallery_preparation','runtimes','manifest','panel'):
            bad=deepcopy(scored);bad[field]={'different':True}
            with self.subTest(field=field),self.assertRaises(ValueError):
                revised.application_context(bad,source,CONTEXT['source_binding'],CONTEXT['app_binding'],common)
        bad=deepcopy(common);bad['evaluator_truth']='MUST_NOT_COPY'
        with self.assertRaises(ValueError):revised.application_context(scored,source,CONTEXT['source_binding'],CONTEXT['app_binding'],bad)

    def test_old_schema_and_changed_source_context_cannot_reuse_new_payload(self):
        jobs,panel,regression,catalog,reviews,context,*_=fixture_context()
        old=original.build_plan(selection([original.BASELINE],reviews),reviews,jobs,panel,regression,catalog,context)
        with self.assertRaises(ValueError):revised.execution_payload(old,0)
        for change in ('source_receipt','gallery_preparation','component_source_receipt','application_source_context'):
            plan=revised.build_plan(selection([original.BASELINE],reviews),reviews,jobs,panel,regression,catalog,context)
            plan['context'][change]={'foreign':True}
            with self.subTest(change=change),self.assertRaises(ValueError):revised.execution_payload(plan,0)

    def test_parent_and_derivative_have_distinct_cache_keys(self):
        jobs,panel,regression,catalog,reviews,context,*_=fixture_context()
        chosen=selection([original.BASELINE],reviews)
        new=revised.build_plan(chosen,reviews,jobs,panel,regression,catalog,context)
        parent=deepcopy(context)
        for field in ('source_receipt','catalog','gallery_preparation'):parent[field]=parent['component_'+field]
        old=original.build_plan(chosen,reviews,jobs,panel,regression,catalog,parent)
        self.assertNotEqual(new['rows'][0]['cache_key'],old['rows'][0]['cache_key'])
        self.assertEqual(new['rows'][0]['job'],old['rows'][0]['job'])
        self.assertEqual(new['rows'][0]['contract'],old['rows'][0]['contract'])

    def test_missing_derivative_lineage_never_builds_v2_plan(self):
        jobs,panel,regression,catalog,reviews,context,*_=fixture_context()
        for field in ('component_source_receipt','application_source_context','application_qualification'):
            bad=deepcopy(context);del bad[field]
            with self.subTest(field=field),self.assertRaises(ValueError):
                revised.build_plan(selection([original.BASELINE],reviews),reviews,jobs,panel,regression,catalog,bad)

    def test_partial_scoring_review_cannot_reach_production_reconstruction(self):
        path=OUTPUT/'PARTIAL_REVIEW_FIXTURE.json';freeze(path,dict(status='PARTIAL_MODELED_BANK_SCORING'))
        with self.assertRaises(ValueError):revised.reconstruct({}, {'main':bind(path),'modes-panel':bind(path)}, {}, [])

    def proof(self):
        return deepcopy(CONTEXT['proof'])

    def test_recorded_prestart_proof_is_complete_without_source_credit(self):
        proof=self.proof();revised.validate_prestart(*proof)
        self.assertEqual(len(proof[5]),16)
        self.assertFalse(proof[0]['actual_source_or_model_execution'])

    def test_counts_and_success_headers_do_not_replace_exact_prestart_population(self):
        for change in ('missing','duplicate','owner','child_error','wrong_count','source_started'):
            proof=self.proof();q,tested,a,checks,child,records,catalog,files=proof
            if change=='missing':records.pop()
            if change=='duplicate':checks['prepared_cells'][-1]=deepcopy(checks['prepared_cells'][0])
            if change=='owner':child['owner']['create_time']+=1
            if change=='child_error':child['errors']=1
            if change=='wrong_count':q['prepared_backends']=15
            if change=='source_started':tested['actual_source_or_model_execution']=True
            with self.subTest(change=change),self.assertRaises(ValueError):revised.validate_prestart(*proof)

    def test_route_and_controller_closure_must_match_every_backend(self):
        for target,field,value in ((1,'contract',{}),(1,'job',{}),(1,'runtimes',[]),
                (1,'gallery_preparation',{}),(1,'application_variant','old-cell'),
                (2,'controller_closed',False),(2,'controller_worker_exited',False),
                (2,'source_start_requested',True),(2,'errors',['failure']),
                (2,'delivery_capture',{}),(2,'status','CELL_CLOSED_REQUIRES_REVIEW')):
            proof=self.proof();proof[5][7][target][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):revised.validate_prestart(*proof)

    def test_capture_policy_origin_and_never_started_state_are_mandatory(self):
        for field,value in (('policy',{}),('source_files',[]),('installed',True),('launch_attempts',1),
                ('test_seams_used',True),('trace',{}),('errors',['failure']),('job_fingerprint','0'*64),
                ('contract_fingerprint','0'*64),('deadline_or_continuity_accepted',True),('integrated_N4_cells',1)):
            proof=self.proof();proof[5][12][3][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):revised.validate_prestart(*proof)

    def test_application_variant_changes_cache_but_preserves_truth_firewall(self):
        jobs,panel,anchors,catalog,reviews,context,*_=fixture_context()
        chosen=selection([original.BASELINE],reviews)
        new=revised.build_plan(chosen,reviews,jobs,panel,anchors,catalog,context)
        legacy=deepcopy(context);del legacy['application_policy']
        old=original.build_plan(chosen,reviews,jobs,panel,anchors,catalog,legacy)
        self.assertNotEqual(new['rows'][0]['cache_key'],old['rows'][0]['cache_key'])
        self.assertEqual(revised.execution_payload(new,0),original.execution_payload(old,0))
        self.assertNotIn('application_policy',revised.execution_payload(new,0))
        for change in ('remove','success','timing_correction','schema'):
            bad=deepcopy(new)
            if change=='remove':del bad['context']['application_policy']
            if change=='success':bad['context']['application_policy']['success_status']='CELL_CLOSED_REQUIRES_REVIEW'
            if change=='timing_correction':bad['context']['application_policy']['delivery']['timing_correction']=True
            if change=='schema':bad['schema']='n4-paced-panel-plan-v2'
            with self.subTest(change=change),self.assertRaises(ValueError):revised.execution_payload(bad,0)
