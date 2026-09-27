"""Pure provenance fixtures, not numerical/production acceptance."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import panel_scoring_admission_guarded_v1 as subject


def setUpModule():
    from metric_process import pin
    pin()


def ref(name):
    return dict(path=str(Path.cwd()/'METADATA_FIXTURE_ONLY'/name), sha256='0'*64, bytes=1)


def chain():
    pb=ref('PLAN.json'); terminal=ref('scores/RESULT.json'); eb=ref('scores/EXECUTION_PLAN.json')
    rb=ref('review/RESULT.json'); re=ref('review/EXECUTION_PLAN.json'); mb=ref('method-review/RESULT.json')
    report=ref('scores/REPORT.json'); ab=ref('scores/ADMISSION.json')
    r=dict(status='PASS_REVIEWED_MODELED_SCORING_ONLY',all_metric_inputs_and_report_totals_verified=True,
        N4_accepted=False,integrated_N4_cells=0,reviewed=1536,required=1536,scope='modes-panel',
        admission=ref('review/ADMISSION.json'),plan=pb,scoring_result=terminal,method_review=mb,
        report=report,execution_plan=re)
    score=dict(status='SCORED_MODELED_BANK_REQUIRES_REVIEW',stop_reason=None,required=1536,
        prediction_completed=1536,prediction_failed=0,prediction_not_tested=0,
        metrics_unavailable_for_complete_predictions=0,integrated_N4_cells=0,
        scores=[ref(f'scores/cells/{i:05d}.json') for i in range(1536)],admission=ab,
        report=report,evaluator=ref('scores/EVALUATOR.json'),plan=pb,execution_plan=eb)
    reviewed=dict(result=r,admission=dict(plan=pb,reviewed_terminal=terminal),terminal=rb,execution_plan=re)
    scored=dict(result=score,admission=dict(plan=pb,review=mb),terminal=terminal,execution_plan=eb)
    return rb,reviewed,scored,dict(scope='modes-panel',required=1536)


class GuardedReaderTests(unittest.TestCase):
    def test_complete_fixture_is_accepted_without_mutation(self):
        value=chain();before=deepcopy(value);subject.validate_guarded_chain(*value);self.assertEqual(value,before)

    def test_incomplete_or_invented_acceptance_rejected(self):
        for key,value in [('status','READY_FOR_REVIEW'),('all_metric_inputs_and_report_totals_verified',False),
            ('N4_accepted',True),('integrated_N4_cells',1),('integrated_N4_cells',False)]:
            args=chain();args[1]['result'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):subject.validate_guarded_chain(*args)

    def test_scoring_failure_denominators_rejected(self):
        for key,value in [('status','PARTIAL_MODELED_BANK_SCORING'),('stop_reason','TIMEOUT'),
            ('prediction_failed',1),('prediction_not_tested',1),('metrics_unavailable_for_complete_predictions',1),
            ('required',True),('prediction_completed',True),('integrated_N4_cells',False)]:
            args=chain();args[2]['result'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):subject.validate_guarded_chain(*args)

    def test_scope_and_counts_cannot_be_relabelled(self):
        for target,key,value in [('plan','required',True),('plan','required',24),('plan','scope','main'),
            ('review','required',True),('review','reviewed',True),('review','reviewed',1535),('review','scope','main')]:
            args=chain();(args[3] if target=='plan' else args[1]['result'])[key]=value
            with self.subTest(target=target,key=key),self.assertRaises(ValueError):subject.validate_guarded_chain(*args)

    def test_missing_duplicate_reordered_or_foreign_scores_rejected(self):
        for change in ('missing','duplicate','reorder','foreign'):
            args=chain();scores=args[2]['result']['scores']
            if change=='missing':scores.pop()
            elif change=='duplicate':scores[-1]=scores[0]
            elif change=='reorder':scores[0],scores[1]=scores[1],scores[0]
            else:scores[-1]=ref('elsewhere/01535.json')
            with self.subTest(change=change),self.assertRaises(ValueError):subject.validate_guarded_chain(*args)

    def test_cross_receipt_joins_required(self):
        for index,section,key in [(1,'result','plan'),(1,'result','scoring_result'),(1,'result','method_review'),
            (1,'result','report'),(1,'admission','reviewed_terminal'),(1,'admission','plan'),
            (2,'admission','plan'),(2,'admission','review'),(2,'result','plan')]:
            args=chain();args[index][section][key]=ref('foreign.json')
            with self.subTest(index=index,section=section,key=key),self.assertRaises(ValueError):subject.validate_guarded_chain(*args)

    def test_both_execution_identities_required(self):
        for index in (1,2):
            args=chain();args[index]['result']['execution_plan']=ref('foreign/EXECUTION_PLAN.json')
            with self.subTest(index=index),self.assertRaises(ValueError):subject.validate_guarded_chain(*args)

    def test_foreign_paths_fail_even_when_some_bindings_agree(self):
        for field in ('report','admission','evaluator'):
            args=chain();foreign=ref('elsewhere/'+field.upper()+'.json');args[2]['result'][field]=foreign
            if field=='report':args[1]['result']['report']=foreign
            with self.subTest(field=field),self.assertRaises(ValueError):subject.validate_guarded_chain(*args)
        args=chain();args[1]['result']['admission']=ref('elsewhere/ADMISSION.json')
        with self.assertRaises(ValueError):subject.validate_guarded_chain(*args)

    def test_cell_identity_method_execution_and_metric_required(self):
        row=dict(cell_id='cell',job_id='job',composition='A0_D0_E0',contract={'mode':'selected_closed'})
        method=ref('method/cells/00000/RESULT.json');execution=ref('scores/EXECUTION_PLAN.json')
        value=dict(cell_id='cell',job_id='job',composition='A0_D0_E0',mode='selected_closed',
            method_result=method,execution_plan=execution,score={'metric_status':'SCORED'},integrated_N4_cells=0)
        subject.validate_score_cell(value,row,method,execution)
        for key,changed in [('cell_id','x'),('job_id','x'),('composition','x'),('mode','x'),
            ('method_result',ref('foreign')),('execution_plan',ref('foreign')),
            ('score',{'metric_status':'TIMEOUT'}),('integrated_N4_cells',False),('integrated_N4_cells',1)]:
            bad=deepcopy(value);bad[key]=changed
            with self.subTest(key=key),self.assertRaises(ValueError):subject.validate_score_cell(bad,row,method,execution)

    def test_live_review_rejected_before_following_score_inputs(self):
        # Existing file only resolves the entry path; no real evidence is read.
        path=Path(__file__).resolve().parent/'GUARDED_BANK_CHECK_V1.json'
        with patch.object(Path,'resolve',return_value=path.parent/'RESULT.json'), \
             patch.object(subject,'bind',return_value=ref('review/RESULT.json')), \
             patch.object(subject.guarded,'validate_execution',side_effect=ValueError('Producer remains active')) as gate, \
             patch.object(subject,'verify') as verify:
            with self.assertRaisesRegex(ValueError,'active'):subject.read_guarded_review(path)
            gate.assert_called_once();verify.assert_not_called()

    def test_explicit_role_required_before_reading_any_evidence(self):
        with patch.object(subject,'bind') as read:
            with self.assertRaises(ValueError):subject.read_review('unused',expected_scope='automatic')
            read.assert_not_called()


if __name__=='__main__':
    from metric_process import pin
    pin();unittest.main()
