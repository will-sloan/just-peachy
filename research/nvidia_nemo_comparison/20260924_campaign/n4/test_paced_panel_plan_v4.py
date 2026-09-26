"""V3 review joins, reuse boundaries and panel truth firewall; metadata fixtures only."""
from copy import deepcopy
from pathlib import Path
import unittest

from common import bind, fingerprint, freeze
from metric_process import identity, pin
import panel_scoring_admission_v3 as scores
import paced_panel_plan_v3 as previous
import paced_panel_plan_v4 as subject
from test_paced_panel_plan import selection
import test_paced_panel_plan_v3 as old_tests

OUTPUT=None


def ref(name):
    return dict(path=str(OUTPUT/name),sha256='0'*64,bytes=1)


def chain(scope='main'):
    required={'main':7680,'modes-panel':1536}[scope]
    binding=ref('review/RESULT.json'); qb=ref('SCORING_HISTORY_CHECK_V3.json')
    q=dict(status=scores.QUALIFICATION_STATUS,review_code=[ref('reviewer.py')],scoring_code=[ref('scorer.py')])
    review=dict(status='PASS_REVIEWED_MODELED_SCORING_ONLY',all_metric_inputs_and_report_totals_verified=True,
        N4_accepted=False,integrated_N4_cells=0,admission=ref('review/ADMISSION.json'),scoring_result=ref('scores/RESULT.json'),
        plan=ref('PLAN.json'),method_review=ref('METHOD_REVIEW.json'),report=ref('scores/REPORT.json'),
        reviewed=required,required=required,scope=scope)
    a=dict(qualification=qb,code=q['review_code'],result=review['scoring_result'],scoring_admission=ref('scores/ADMISSION.json'))
    scored=dict(status='SCORED_MODELED_BANK_REQUIRES_REVIEW',stop_reason=None,required=required,prediction_completed=required,
        scores=[ref(f'scores/cells/{i:05d}.json') for i in range(required)],prediction_failed=0,prediction_not_tested=0,
        metrics_unavailable_for_complete_predictions=0,integrated_N4_cells=0,report=review['report'],admission=a['scoring_admission'])
    sa=dict(qualification=qb,code=q['scoring_code'],plan=review['plan'],review=review['method_review'])
    plan=dict(required=required,scope=scope)
    return binding,review,a,scored,sa,plan,qb,q


def contexts():
    base={k:ref(k+'.json') for k in ('source_receipt','catalog','gallery_preparation','manifest','panel')}
    base.update(reviews={'ASR':ref('ASR.json'),'D0':ref('D0.json'),'D1':ref('D1.json')},
        runtimes={'n2_runtime.json':ref('n2_runtime.json'),'n3_runtime.json':ref('n3_runtime.json')},
        code=[ref('method.py')],qualification=[ref('METHOD_CHECK.json')])
    jobs=[{'metadata_fixture':True}]
    main=dict(scope='main',required=7680,context=deepcopy(base),jobs=jobs)
    modes=dict(scope='modes-panel',required=1536,context=deepcopy(base),jobs=deepcopy(jobs))
    main['context']['reuse_review']=ref('REUSE.json')
    return main,modes


class ScoreAdmissionTests(unittest.TestCase):
    def test_complete_both_populations_join_without_execution_credit(self):
        for scope in ('main','modes-panel'):scores.validate_chain(*chain(scope))

    def test_partial_or_accepted_headers_rejected(self):
        for key,value in (('status','PARTIAL_MODELED_BANK_SCORING'),('all_metric_inputs_and_report_totals_verified',False),
            ('N4_accepted',True),('integrated_N4_cells',1),('integrated_N4_cells',False)):
            v=chain();v[1][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):scores.validate_chain(*v)

    def test_both_implementations_and_qualification_must_match(self):
        for index,field in ((2,'qualification'),(4,'qualification'),(2,'code'),(4,'code')):
            v=chain();v[index][field]=ref('foreign') if field=='qualification' else []
            with self.subTest(index=index,field=field),self.assertRaises(ValueError):scores.validate_chain(*v)
        v=chain();v[7]['status']='PASS_SCORING_REVIEW_DEVELOPMENT_ONLY'
        with self.assertRaises(ValueError):scores.validate_chain(*v)

    def test_missing_failed_untested_or_duplicate_scores_rejected(self):
        for field in ('prediction_failed','prediction_not_tested','metrics_unavailable_for_complete_predictions'):
            v=chain();v[3][field]=1
            with self.subTest(field=field),self.assertRaises(ValueError):scores.validate_chain(*v)
        for change in ('missing','duplicate','reordered','stop','partial'):
            v=chain();r=v[3]
            if change=='missing':r['scores'].pop()
            if change=='duplicate':r['scores'][-1]=r['scores'][0]
            if change=='reordered':r['scores'][0],r['scores'][1]=r['scores'][1],r['scores'][0]
            if change=='stop':r['stop_reason']='TIMEOUT'
            if change=='partial':r['status']='PARTIAL_MODELED_BANK_SCORING'
            with self.subTest(change=change),self.assertRaises(ValueError):scores.validate_chain(*v)

    def test_all_cross_receipt_joins_are_required(self):
        for index,field in ((1,'plan'),(1,'method_review'),(1,'report'),(1,'scoring_result'),
            (2,'result'),(2,'scoring_admission'),(4,'plan'),(4,'review')):
            v=chain();v[index][field]=ref('foreign.json')
            with self.subTest(index=index,field=field),self.assertRaises(ValueError):scores.validate_chain(*v)

    def test_scope_and_full_denominators_cannot_be_relabelled(self):
        for index,field,value in ((5,'required',1),(5,'required',True),(5,'scope','panel'),
            (1,'required',1),(1,'reviewed',1),(1,'scope','modes-panel')):
            v=chain();v[index][field]=value
            with self.subTest(index=index,field=field),self.assertRaises(ValueError):scores.validate_chain(*v)

    def test_foreign_receipt_and_report_paths_rejected_even_with_matching_joins(self):
        v=chain();v[1]['report']=v[3]['report']=ref('elsewhere/REPORT.json')
        with self.assertRaises(ValueError):scores.validate_chain(*v)
        v=chain();v[2]['scoring_admission']=v[3]['admission']=ref('elsewhere/ADMISSION.json')
        with self.assertRaises(ValueError):scores.validate_chain(*v)
        v=chain();v[1]['admission']=ref('elsewhere/ADMISSION.json')
        with self.assertRaises(ValueError):scores.validate_chain(*v)

    def test_only_main_reuse_metadata_may_differ(self):
        main,modes=contexts();before=deepcopy(main)
        self.assertEqual(scores.validate_contexts(main,modes),modes['context']);self.assertEqual(main,before)
        del main['context']['reuse_review'];scores.validate_contexts(main,modes)

    def test_other_context_differences_and_job_order_are_rejected(self):
        for key in contexts()[1]['context']:
            main,modes=contexts();modes['context'][key]={'changed':True}
            with self.subTest(key=key),self.assertRaises(ValueError):scores.validate_contexts(main,modes)
        main,modes=contexts();modes['jobs']=[{'different':True}]
        with self.assertRaises(ValueError):scores.validate_contexts(main,modes)

    def test_mode_reuse_and_malformed_main_provenance_are_rejected(self):
        main,modes=contexts();modes['context']['reuse_review']=main['context']['reuse_review']
        with self.assertRaises(ValueError):scores.validate_contexts(main,modes)
        main,modes=contexts();main['context']['reuse_review']={'fixture':'unbound'}
        with self.assertRaises(ValueError):scores.validate_contexts(main,modes)

    def test_partial_review_file_stops_before_method_admission(self):
        path=OUTPUT/'partial/RESULT.json';freeze(path,dict(status='PARTIAL_MODELED_BANK_SCORING'))
        with self.assertRaises(ValueError):scores.read_review(path)

    def test_exact_live_reviewer_is_rejected_before_qualification(self):
        folder=OUTPUT/'live-owner';a=folder/'ADMISSION.json';freeze(a,dict(owner=identity(pin())))
        parent=folder/'PARENT.json';freeze(parent,dict(metadata_fixture=True))
        value=dict(status='PASS_REVIEWED_MODELED_SCORING_ONLY',all_metric_inputs_and_report_totals_verified=True,
            N4_accepted=False,integrated_N4_cells=0,admission=bind(a),
            **{key:bind(parent) for key in ('scoring_result','plan','method_review','report')})
        freeze(folder/'RESULT.json',value)
        with self.assertRaisesRegex(ValueError,'reviewer remains active'):scores.read_review(folder/'RESULT.json')


def fixture():
    jobs,panel,anchors,catalog,reviews,context,*_=old_tests.fixture_context()
    context['scoring_review_policy']=deepcopy(scores.POLICY)
    return jobs,panel,anchors,catalog,reviews,context


def plan(candidates=None):
    jobs,panel,anchors,catalog,reviews,context=fixture()
    return subject.build_plan(selection(candidates or [subject.original.BASELINE,'A3_D1_E1'],reviews),
        reviews,jobs,panel,anchors,catalog,context)


class PanelV4Tests(unittest.TestCase):
    def test_population_and_application_payload_are_unchanged(self):
        p=plan();self.assertEqual(p['required'],80);self.assertEqual(p['schema'],subject.SCHEMA)
        for i,row in enumerate(p['rows']):
            out=subject.execution_payload(p,i)
            self.assertEqual(out,previous.execution_payload(dict(p,schema=previous.SCHEMA),i))
            self.assertEqual(out['job'],row['job']);self.assertFalse(out['source_execution_authorized'])
            self.assertEqual(len(out),13)
            for name in ('reviews','selection','scoring_review_policy','component_source_receipt','truth','reference'):
                self.assertNotIn(name,out)
        self.assertFalse(p['N4_accepted']);self.assertEqual(p['integrated_N4_cells'],0)

    def test_scoring_policy_participates_in_cache_identity(self):
        jobs,panel,anchors,catalog,reviews,context=fixture()
        selected=selection([subject.original.BASELINE],reviews)
        new=subject.build_plan(selected,reviews,jobs,panel,anchors,catalog,context)
        old_context=deepcopy(context);del old_context['scoring_review_policy']
        old=previous.build_plan(selected,reviews,jobs,panel,anchors,catalog,old_context)
        self.assertNotEqual(new['rows'][0]['cache_key'],old['rows'][0]['cache_key'])
        self.assertEqual(subject.execution_payload(new,0),previous.execution_payload(old,0))

    def test_old_headers_or_changed_scoring_policy_do_not_authorize_payload(self):
        for change in ('schema','relationship','policy','remove','source'):
            p=plan()
            if change=='schema':p['schema']=previous.SCHEMA
            if change=='relationship':p['scoring_relationship']='unqualified'
            if change=='policy':p['context']['scoring_review_policy']['required_main']=1
            if change=='remove':del p['context']['scoring_review_policy']
            if change=='source':p['context']['source_receipt']={'foreign':True}
            with self.subTest(change=change),self.assertRaises(ValueError):subject.execution_payload(p,0)

    def test_builder_requires_explicit_scoring_family(self):
        jobs,panel,anchors,catalog,reviews,context=fixture();del context['scoring_review_policy']
        with self.assertRaises(ValueError):subject.build_plan(selection([subject.original.BASELINE],reviews),
            reviews,jobs,panel,anchors,catalog,context)

    def test_baseline_and_candidate_ceiling_are_preserved(self):
        p=plan([subject.original.BASELINE,*sorted(subject.original.COMPOSITIONS-{subject.original.BASELINE})[:5]])
        self.assertEqual(p['required'],240);self.assertEqual(p['candidates'][0],subject.original.BASELINE)
        with self.assertRaises(ValueError):plan(sorted(subject.original.COMPOSITIONS))

    def test_candidate_settings_or_jobs_cannot_change_after_build(self):
        for field in ('job','contract','repeat'):
            p=plan()
            if field=='job':p['rows'][0]['job']['frames']+=1
            if field=='contract':p['rows'][0]['contract']['mode']='selected_closed'
            if field=='repeat':p['rows'][0]['repeat']=99
            with self.subTest(field=field),self.assertRaises(ValueError):subject.execution_payload(p,0)

    def test_partial_scores_cannot_reach_production_reconstruction(self):
        path=OUTPUT/'partial-v4/RESULT.json';freeze(path,dict(status='PARTIAL_MODELED_BANK_SCORING'))
        with self.assertRaises(ValueError):subject.reconstruct({},dict(main=bind(path),**{'modes-panel':bind(path)}),{},[])
