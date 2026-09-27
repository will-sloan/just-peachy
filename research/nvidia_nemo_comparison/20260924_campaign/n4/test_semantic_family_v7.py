"""Cross-family calculation parity, raw evidence retention and write bounds."""
import ast
from copy import deepcopy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze, load
import semantic_family_v7 as family
import review_application_semantics_v4 as old
import review_application_semantics_v7 as semantic
import review_semantic_panel_v4 as old_panel
import review_semantic_panel_v7 as panel
import review_application_content_panel_v7 as content
import review_application_panel_v7 as evidence
import paced_panel_plan_guarded_v2 as planner

CONTEXT={}


def function_ast(module,name):
    text=Path(module.__file__).read_text(encoding='utf-8').replace('V7','V4')
    return ast.dump(next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)


class FamilyTests(unittest.TestCase):
    def setUp(self):
        self.folder=CONTEXT['output']/self._testMethodName;self.folder.mkdir()

    def test_semantic_calculations_and_reference_firewall_unchanged(self):
        for name in ('review_content','review_timing','project_labels','review_labels','join_observed',
                     'migrate_reference_inputs','load_reference_context','score_cell'):
            self.assertEqual(function_ast(old,name),function_ast(semantic,name),name)
        for name in ('compact_content','population','compact','aggregate'):
            self.assertEqual(function_ast(old_panel,name),function_ast(panel,name),name)

    def test_v7_plan_population_and_evidence_reader_wiring(self):
        for module in (panel,content):
            self.assertIs(module.execution_payload,planner.execution_payload)
            self.assertIs(module.stopped_run,evidence.stopped_run)
            self.assertIs(module.validate_population,evidence.validate_population)
            self.assertEqual(module.QUALIFICATION,family.QUALIFICATION)
        self.assertIs(content.review_cell,semantic.review_content)
        from review_application_cell_v7 import review_cell
        self.assertIs(semantic.review_evidence,review_cell)

    def test_complete_parent_closure_preserved(self):
        code=family.code_bindings();self.assertLessEqual(len(code),512)
        self.assertEqual(len(code),len({b['path'] for b in code}))
        for name in family.PARENTS:
            self.assertIn(bind(family.HERE/name),code)
            for b in load(family.HERE/name)['code']:self.assertIn(b,code)
        for module in (semantic,panel,content):self.assertEqual(module.code_bindings(),code)

    def example(self):
        checked=load(CONTEXT['content']['path']);payload=load(CONTEXT['payload']['path']);c=payload['contract']
        row=dict(cell_id=payload['cell_id'],composition='_'.join(c[k] for k in ('variant','diarization','encoder')),
            kind='panel',repeat=0,job=payload['job'],contract=c)
        return checked,row,payload

    def test_content_compaction_retains_exact_raw_delivery_binding(self):
        checked,row,payload=self.example();registry={}
        compact=content.compact_content(checked,row,payload,registry);delivery=compact['source_delivery']
        original=checked['cell']['transport']['source_delivery_review']['summary']
        self.assertNotIn('summary',delivery)
        self.assertEqual(delivery['summary_sha256'],fingerprint(original))
        envelope=delivery['envelope'];self.assertEqual(registry[envelope['path']],envelope)
        self.assertEqual(load(envelope['path'])['review']['summary'],original)
        self.assertTrue(delivery['raw_summary_preserved_in_bound_envelope'])
        self.assertFalse(delivery['scheduling_or_append_cost_subtracted'])
        self.assertFalse(delivery['deadline_or_continuity_accepted'])

    def test_old_receipt_status_cannot_be_relabelled_by_compactor(self):
        checked,row,payload=self.example()
        for status in ('PASS_V5_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY',
                       'PASS_V4_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY',
                       'PASS_V2_APPLICATION_CONTENT_AND_FIXED_ROSTER_JOINS_ONLY'):
            with self.assertRaises(ValueError):content.compact_content(dict(checked,status=status),row,payload,{})

    def test_exact_unicode_and_platform_newline_size_boundary(self):
        root=self.folder/'bytes';value={'text':'\u00e9\nsecond line\r\nlast line'}
        family.freeze_bounded(root/'first.json',value,root);size=(root/'first.json').stat().st_size
        with patch.object(family,'OUTPUT_LIMIT',2*size+65536):family.freeze_bounded(root/'second.json',value,root)
        self.assertEqual((root/'second.json').stat().st_size,size)
        with patch.object(family,'OUTPUT_LIMIT',3*size+65536-1),self.assertRaisesRegex(ValueError,'output bound'):
            family.freeze_bounded(root/'third.json',value,root)
        self.assertFalse((root/'third.json').exists());self.assertEqual(load(root/'first.json'),value)

    def test_output_escape_and_nonfinite_json_refused_before_write(self):
        root=self.folder/'bounded';root.mkdir()
        with self.assertRaises(ValueError):family.freeze_bounded(self.folder/'escape.json',{},root)
        with self.assertRaises(ValueError):family.freeze_bounded(root/'nan.json',{'value':float('nan')},root)
        self.assertFalse(list(root.iterdir()))

    def test_maximum_content_panel_fits_with_registry_and_failure_reserve(self):
        checked,row,payload=self.example();registry={};base=content.compact_content(checked,row,payload,registry)
        summaries=[]
        for i in range(240):
            v=deepcopy(base);v.update(cell_id=f'bound-{i}',composition=f'fixture-{i%6}',
                tap=('O0','O1')[(i//6)%2],kind=('panel','timing_repeat')[(i//12)%2])
            summaries.append(v)
        grouped=content.aggregate(summaries)
        size=lambda v:len((json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').replace('\n',os.linesep).encode('utf-8'))
        budget=sum(size(s) for s in summaries)+size(grouped)+2*1024**2+65536
        self.assertLessEqual(budget,family.OUTPUT_LIMIT)
        freeze(self.folder/'CONTENT_BUDGET.json',dict(cells=240,total_with_registry_and_failure_reserve=budget,
            limit=family.OUTPUT_LIMIT,production_registry_not_observed=True))
