"""Synthetic exact-population checks, without fabricating production plans."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from common import load
import review_application_panel_v2 as review

CONTEXT = {}


def fixture(required=40):
    rows = [dict(cell_id=f'cell_{i:04d}') for i in range(required)]
    bindings = [dict(path=f'INERT/cells/{r["cell_id"]}/COLLECTED.json',sha256=f'{i:064x}',bytes=100) for i,r in enumerate(rows)]
    terminal = dict(schema=review.RUN_SCHEMA,status='COLLECTED_PACED_APPLICATION_PANEL_REQUIRES_REVIEW',
        completed=required,required=required,error=None,integrated_N4_cells=0,N4_accepted=False,
        continuity_included=False,collected=deepcopy(bindings))
    progress = [dict(completed=i+1,total=required,cell=b,integrated_N4_cells=0) for i,b in enumerate(bindings)]
    return dict(plan=dict(required=required,rows=rows),terminal=terminal,collected=bindings,progress=progress,
        cell_names=[r['cell_id'] for r in rows],progress_names=[f'{i+1:04d}.json' for i in range(required)])


class PanelReviewTests(unittest.TestCase):
    def test_complete_small_and_maximum_populations(self):
        for count in (40,240):
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
            dict(error='failed cell'),dict(N4_accepted=True),dict(integrated_N4_cells=40),dict(continuity_included=True),dict(schema='old')):
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
        for count in (0,39,41,241,280):
            with self.subTest(count=count),self.assertRaises(ValueError):review.validate_population(**fixture(count))
        value=fixture();value['plan']['rows'][-1]=value['plan']['rows'][0]
        with self.assertRaises(ValueError):review.validate_population(**value)

    def test_compact_existing_synthetic_join_preserves_scope_and_bindings(self):
        checked=load(CONTEXT['synthetic_join']['path'])
        row=dict(cell_id=checked['transport']['cell_id'],composition='SYNTHETIC_ONLY',kind='panel',repeat=0,
            job=dict(tap='O0',job_id='fixture'))
        result=review.compact_cell(checked,row,{'fixture':'no inference input'})
        self.assertEqual(result['evidence'],checked['joins']['evidence'])
        self.assertEqual(result['final_span_census'],checked['observations']['final_span_census'])
        self.assertFalse(result['N4_accepted']);self.assertFalse(result['native_payload_semantics_reviewed'])
        self.assertEqual(result['deployment_tier'],'UNKNOWN');self.assertEqual(result['integrated_N4_cells'],0)
        checked['N4_accepted']=True
        with self.assertRaisesRegex(ValueError,'Joined cell reader'):review.compact_cell(checked,row,{})

    def test_missing_production_run_is_refused_before_plan_reconstruction(self):
        with patch.object(review,'admit_plan') as planner,self.assertRaises(FileNotFoundError):
            review.stopped_run(CONTEXT['output']/'NO_PRODUCTION_RUN')
        planner.assert_not_called()
