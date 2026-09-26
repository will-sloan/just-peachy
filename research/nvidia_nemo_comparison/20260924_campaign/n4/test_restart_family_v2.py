"""Cross-version restart wiring and fail-closed lineage; no application launch."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze, load, verify
import restart_family_v2 as family
import restart_application_plan as old_plan
import restart_application_plan_v2 as plan
import restart_application_runner as old_runner
import restart_application_runner_v2 as runner
import review_restart_run_v2 as review
import review_restart_content_run as old_content
import review_restart_content_run_v2 as content
import test_restart_plan_v2 as fixtures
from restart_application_child import control

CONTEXT={}


def function_ast(module,name):
    tree=ast.parse(Path(module.__file__).read_text(encoding='utf-8'))
    return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)


class FamilyTests(unittest.TestCase):
    def test_child_control_collection_cleanup_and_payload_AST_unchanged(self):
        for name in ('collect_one','check_after_exit','check_child_result','qualified_manifests','prepare','run'):
            self.assertEqual(function_ast(old_runner,name),function_ast(runner,name),name)
        for name in ('execution_payload','row_key','lifecycle_qualification','reconstruct'):
            self.assertEqual(function_ast(old_plan,name),function_ast(plan,name),name)
        for name in ('review_population','freeze_bounded','guard'):
            self.assertEqual(function_ast(old_content,name),function_ast(content,name),name)
        from paced_application_runner_v3 import supervise_child as old
        from paced_application_runner_v4 import supervise_child as new
        import paced_application_runner_v3 as old_module
        import paced_application_runner_v4 as new_module
        self.assertIs(runner.supervise_child,new)
        self.assertEqual(function_ast(old_module,'supervise_child'),function_ast(new_module,'supervise_child'))

    def test_exact_122_record_child_closure_and_gate_remain_unchanged(self):
        parent,child,exe,script=runner.qualified_manifests()
        old_parent,old_child,old_exe,old_script=old_runner.qualified_manifests()
        self.assertEqual((child,exe,script),(old_child,old_exe,old_script))
        self.assertEqual(len(child),122)
        self.assertTrue(all(b in parent for b in old_parent))
        self.assertTrue(all(b in parent for b in child))
        self.assertNotIn(bind(runner.__file__),child)
        self.assertLess(len(json.dumps(child).encode('utf-8')),256*1024)

    def test_manifest_retains_all_parent_sources_and_proofs(self):
        code=family.code_bindings();self.assertLessEqual(len(code),512)
        self.assertEqual(len(code),len({b['path'] for b in code}))
        for name in family.PARENTS:
            q=load(family.HERE/name)
            self.assertIn(bind(family.HERE/name),code)
            for b in q['code']:self.assertIn(b,code)
        for module in (plan,runner,review,content):self.assertEqual(module.code_bindings(),code)

    def test_old_panel_and_wrong_score_lineage_are_rejected(self):
        value=fixtures.panel();self.assertEqual(value['schema'],plan.panels.SCHEMA)
        for change in ('old-schema','score-policy','score-relationship'):
            other=deepcopy(value)
            if change=='old-schema':other['schema']='n4-paced-panel-plan-v3'
            elif change=='score-policy':other['context']['scoring_review_policy']={}
            else:other['scoring_relationship']='foreign'
            with self.subTest(change=change),self.assertRaises(ValueError):plan.build_plan({},other,{})

    def test_v4_plan_to_fixed_child_all_sixteen_routes_and_no_truth(self):
        count=0
        for candidate in sorted(plan.original.COMPOSITIONS):
            candidates=[plan.original.BASELINE] if candidate==plan.original.BASELINE else [plan.original.BASELINE,candidate]
            value=fixtures.plan(candidates)
            for i,row in enumerate(value['rows']):
                payload=plan.execution_payload(value,i);count+=1
                self.assertEqual(len(payload),13);self.assertEqual(len(payload['job']),8)
                self.assertEqual(control(payload)['stop_after_samples'],row['stop_after_samples'])
                self.assertNotIn('scoring_review_policy',payload)
                self.assertNotIn('reviews',payload);self.assertNotIn('selection',payload)
                self.assertFalse(payload['source_execution_authorized'])
                with self.assertRaisesRegex(ValueError,'asset bindings'):
                    control(dict(payload,assets=[]))
        self.assertEqual(count,62)
        freeze(CONTEXT['output']/'ALL_ROUTE_PAYLOAD_COUNTS.json',dict(routes=16,payloads=count,synthetic_plan_only=True))

    def test_generated_maximum_plan_has_exact_reviewed_population(self):
        candidates=[plan.original.BASELINE]+sorted(plan.original.COMPOSITIONS-{plan.original.BASELINE})[:5]
        value=fixtures.plan(candidates);rows=value['rows'];n=len(rows)
        refs=[dict(path='INERT/'+r['cell_id'],sha256=f'{i:064x}',bytes=1) for i,r in enumerate(rows)]
        terminal=dict(schema=runner.RUN_SCHEMA,status='COLLECTED_SELECTED_RESTART_PAIRS_REQUIRES_REVIEW',
            completed=n,required=n,required_sessions=2*n,error=None,collected=refs,
            actual_restart_qualified=False,independent_complete_transport_reviewed=False,integrated_N4_cells=0,N4_accepted=False)
        progress=[dict(completed=i+1,total=n,cell=b,actual_restart_qualified=False,integrated_N4_cells=0) for i,b in enumerate(refs)]
        result=review.validate_population(value,terminal,refs,progress,[r['cell_id'] for r in rows],[f'{i+1:04d}.json' for i in range(n)])
        self.assertEqual((result['planned_pairs'],result['planned_sessions']),(12,24))
        with self.assertRaises(ValueError):review.validate_population(value,dict(terminal,schema='n4-restart-application-run-v1'),refs,progress,[r['cell_id'] for r in rows],[f'{i+1:04d}.json' for i in range(n)])

    def test_unchanged_content_leaves_accept_no_production_claims(self):
        self.assertIs(content.review_cell,old_content.review_cell)
        self.assertEqual(plan.APPLICATION_POLICY,old_plan.APPLICATION_POLICY)
        self.assertEqual(runner.COLLECTED,old_runner.COLLECTED)
        self.assertEqual(runner.MAXIMUM_CHILD_SECONDS,1200)
        self.assertIs(content.stopped_run,review.stopped_run)
        self.assertIs(content.execution_payload,plan.execution_payload)
        self.assertIs(review.qualified_runner,runner.qualified_runner)

    def test_missing_production_admission_refuses_before_child_or_slot(self):
        with patch.object(runner,'PrivateApplicationProcess') as child,patch.object(runner,'ExclusiveApplicationSlot') as slot:
            with self.assertRaises((ValueError,FileNotFoundError)):runner.run(CONTEXT['output']/'NONEXISTENT_ADMISSION.json')
            child.assert_not_called();slot.assert_not_called()
