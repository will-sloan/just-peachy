"""Synthetic exact-population checks, without fabricating production plans."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from common import load
import review_continuity_application as review

CONTEXT = {}


def fixture(required=2):
    candidates=([review.BASELINE]+sorted(review.COMPOSITIONS-{review.BASELINE}))[:required] if required else []
    job=dict(job_id='N4_CONTINUITY_SYNTHETIC_O0',audio_path='INERT/CONTINUITY_O0.wav',audio_sha256='0'*64,
        frames=19308429,sample_rate_hz=16000,gain=1.,reset_between_scenes=True,tap='O0')
    rows = [dict(cell_id=f'cell_{i:04d}',composition=candidates[i],job=deepcopy(job),kind='continuity',repeat=0) for i in range(required)]
    bindings = [dict(path=f'INERT/cells/{r["cell_id"]}/COLLECTED.json',sha256=f'{i:064x}',bytes=100) for i,r in enumerate(rows)]
    terminal = dict(schema=review.RUN_SCHEMA,status='COLLECTED_CONTINUITY_APPLICATION_REQUIRES_REVIEW',
        completed=required,required=required,error=None,integrated_N4_cells=0,N4_accepted=False,
        continuity_included=True,stop_restart_included=False,collected=deepcopy(bindings))
    progress = [dict(completed=i+1,total=required,cell=b,integrated_N4_cells=0) for i,b in enumerate(bindings)]
    return dict(plan=dict(schema=review.PLAN_SCHEMA,continuity=deepcopy(review.CONTINUITY_POLICY),required=required,rows=rows,candidates=candidates),terminal=terminal,collected=bindings,progress=progress,
        cell_names=[r['cell_id'] for r in rows],progress_names=[f'{i+1:04d}.json' for i in range(required)])


class PanelReviewTests(unittest.TestCase):
    def test_complete_small_and_maximum_populations(self):
        for count in (1,6):
            result = review.validate_population(**fixture(count)); self.assertEqual(result['planned_cells'],count)
            self.assertEqual(result['additional_or_missing_cells'],0)

    def test_missing_extra_and_duplicate_cell_or_progress_entries(self):
        for field in ('cell_names','progress_names'):
            for action in ('missing','extra','duplicate'):
                value=fixture()
                if action=='missing':value[field].pop()
                elif action=='extra':value[field].append('foreign')
                else:value[field][-1]=value[field][0]
                with self.subTest(field=field,action=action),self.assertRaises(ValueError):review.validate_population(**value)

    def test_partial_failed_or_promoted_terminal_is_rejected(self):
        for change in (dict(completed=39),dict(required=80),dict(status='FAILED_PACED_APPLICATION_RUN_PRESERVED'),
            dict(error='failed cell'),dict(N4_accepted=True),dict(integrated_N4_cells=40),dict(continuity_included=False),dict(stop_restart_included=True),dict(schema='old')):
            value=fixture();value['terminal'].update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'Terminal run'):review.validate_population(**value)

    def test_terminal_collected_order_and_census_are_exact(self):
        for action in ('missing','reverse','duplicate'):
            value=fixture();rows=value['terminal']['collected']
            if action=='missing':rows.pop()
            elif action=='reverse':rows.reverse()
            else:rows[-1]=rows[0]
            with self.subTest(action=action),self.assertRaisesRegex(ValueError,'collected sequence'):review.validate_population(**value)

    def test_progress_indices_totals_cells_and_flags_must_match(self):
        for change in (dict(completed=2),dict(completed=True),dict(total=39),dict(cell={}),dict(integrated_N4_cells=1)):
            value=fixture();value['progress'][0].update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'Progress receipt'):review.validate_population(**value)

    def test_invalid_planned_population_is_rejected(self):
        for count in (0,7,8,16):
            with self.subTest(count=count),self.assertRaises(ValueError):review.validate_population(**fixture(count))
        value=fixture();value['plan']['rows'][-1]=value['plan']['rows'][0]
        with self.assertRaises(ValueError):review.validate_population(**value)

    def test_compact_existing_synthetic_join_preserves_scope_and_bindings(self):
        checked=load(CONTEXT['synthetic_join']['path'])
        payload=load(next(b['path'] for b in checked['transport']['evidence'] if Path(b['path']).name=='INPUT.json'))
        row=dict(cell_id=checked['transport']['cell_id'],composition='SYNTHETIC_ONLY',kind='panel',repeat=0,
            job=payload['job'],contract=payload['contract'])
        result=review.compact_cell(checked,row,payload)
        self.assertEqual(result['evidence'],checked['joins']['evidence'])
        self.assertEqual(result['final_span_census'],checked['observations']['final_span_census'])
        self.assertFalse(result['N4_accepted']);self.assertFalse(result['native_payload_semantics_reviewed'])
        self.assertEqual(result['deployment_tier'],'UNKNOWN');self.assertEqual(result['integrated_N4_cells'],0)
        self.assertEqual(result['source_delivery']['summary'],checked['transport']['source_delivery_review']['summary'])
        self.assertFalse(result['source_delivery']['scheduling_or_append_cost_subtracted'])
        checked['N4_accepted']=True
        with self.assertRaisesRegex(ValueError,'Joined cell reader'):review.compact_cell(checked,row,{})

    def test_missing_production_run_is_refused_before_plan_reconstruction(self):
        with patch.object(review,'admit_plan') as planner,self.assertRaises(FileNotFoundError):
            review.stopped_run(CONTEXT['output']/'NO_PRODUCTION_RUN')
        planner.assert_not_called()

    def test_old_run_schema_cannot_use_v3_panel_reader(self):
        value=fixture();value['terminal']['schema']='n4-paced-application-run-v2'
        with self.assertRaisesRegex(ValueError,'Terminal run'):review.validate_population(**value)

    def test_candidate_identity_order_and_baseline_are_exact(self):
        for mutation in ('baseline','row_order','duplicate','foreign'):
            value=fixture(3);plan=value['plan']
            if mutation=='baseline':plan['candidates'].reverse()
            if mutation=='row_order':plan['rows'].reverse()
            if mutation=='duplicate':plan['candidates'][1]=plan['candidates'][0]
            if mutation=='foreign':plan['candidates'][1]=plan['rows'][1]['composition']='foreign'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):review.validate_population(**value)

    def test_full_same_sequence_no_resets_or_short_panel_substitution(self):
        for mutation in ('short','long','tap','different','kind','repeat','joins','schema','reference'):
            value=fixture();plan=value['plan'];row=plan['rows'][1]
            if mutation=='short':row['job']['frames']=16000
            if mutation=='long':row['job']['frames']=1301*16000
            if mutation=='tap':row['job']['tap']='O1'
            if mutation=='different':row['job']['audio_sha256']='1'*64
            if mutation=='kind':row['kind']='panel'
            if mutation=='repeat':row['repeat']=1
            if mutation=='joins':plan['continuity']['reset_at_internal_joins']=True
            if mutation=='schema':plan['schema']='n4-paced-panel-plan-v3'
            if mutation=='reference':row['job']['scene_cast']=['actor']
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):review.validate_population(**value)

    def test_population_pass_does_not_claim_continuity_or_restart_acceptance(self):
        result=review.validate_population(**fixture(6))
        self.assertEqual(result['source_seconds_per_candidate'],1206.7768125)
        self.assertTrue(result['initial_reset_only']);self.assertFalse(result['stop_restart_included'])
        self.assertNotIn('N4_accepted',result);self.assertNotIn('continuity_qualified',result)

    def test_compaction_rejects_changed_delivery_scope_and_row_identity(self):
        for change in ('row','samples','origin','records','acceptance'):
            checked=load(CONTEXT['synthetic_join']['path'])
            payload=load(next(b['path'] for b in checked['transport']['evidence'] if Path(b['path']).name=='INPUT.json'))
            row=dict(cell_id=payload['cell_id'],composition='SYNTHETIC_ONLY',kind='panel',repeat=0,
                job=deepcopy(payload['job']),contract=payload['contract'])
            delivery=checked['transport']['source_delivery_review']
            if change=='row':row['job']['tap']='foreign'
            if change=='samples':delivery['source_samples']+=1
            if change=='origin':delivery['source_origin_perf_counter']+=1
            if change=='records':delivery['summary']['records']+=1
            if change=='acceptance':delivery['deadline_or_continuity_accepted']=True
            with self.subTest(change=change),self.assertRaises(ValueError):review.compact_cell(checked,row,payload)
