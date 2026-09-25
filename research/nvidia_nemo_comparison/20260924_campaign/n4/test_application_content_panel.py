"""Saved synthetic cell and population tests; never a production panel run."""
from copy import deepcopy
from pathlib import Path

from common import freeze, load
import test_application_panel_review_v2 as prior
import review_application_content_panel as panel

CONTEXT={}


class ContentPanelTests(prior.PanelReviewTests):
    def example(self):
        checked=load(CONTEXT['synthetic_content']['path'])
        binding=next(b for b in checked['cell']['transport']['evidence'] if Path(b['path']).name=='INPUT.json')
        payload=load(binding['path']);c=payload['contract']
        row=dict(cell_id=payload['cell_id'],composition='_'.join(c[k] for k in ('variant','diarization','encoder')),
            kind='panel',repeat=0,job=deepcopy(payload['job']),contract=deepcopy(c))
        return checked,row,payload

    def test_compact_content_preserves_scope_and_input_bindings(self):
        checked,row,payload=self.example();registry={};result=panel.compact_content(checked,row,payload,registry)
        self.assertTrue(result['primary_caption_text_consistency_reviewed'])
        self.assertFalse(result['source_to_widget_latency_qualified']);self.assertFalse(result['names_independently_scored'])
        self.assertFalse(result['exact_consumed_event_attribution']);self.assertFalse(result['N4_accepted'])
        self.assertEqual(result['integrated_N4_cells'],0);self.assertNotIn('evidence',result)
        self.assertEqual(result['content_counts']['native_spans'],4)
        for b in checked['widget']['evidence']+checked['roster']['evidence']:
            self.assertEqual(registry[b['path']],b)
        freeze(CONTEXT['output']/'SYNTHETIC_COMPACT_CONTENT.json',result)

    def test_compaction_rejects_foreign_plan_row_or_incomplete_composition(self):
        checked,row,payload=self.example()
        for field in ('cell_id','job','contract'):
            changed=deepcopy(row);changed[field]='foreign'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'planned row'):
                panel.compact_content(checked,changed,payload,{})
        checked['fixed_display_roster_independently_joined']=False
        with self.assertRaisesRegex(ValueError,'Complete cell content'):panel.compact_content(checked,row,payload,{})

    def test_missing_visibility_is_preserved_and_taps_repeats_stay_separate(self):
        checked,row,payload=self.example();w=checked['widget']
        w['native_span_population']+=1;w['native_spans_not_observed'].append('synthetic-unobserved')
        w['observed_spans_never_visible']=1;w['observed_spans_without_final_visibility']=2
        w['missing_native_caption_revisions'].append('synthetic-missing-revision')
        summary=panel.compact_content(checked,row,payload,{})
        repeat=deepcopy(summary);repeat.update(cell_id='synthetic-repeat',kind='timing_repeat',repeat=1)
        other=deepcopy(summary);other.update(cell_id='synthetic-other-tap',tap='O1')
        result=panel.aggregate([summary,repeat,other]);self.assertEqual(len(result['groups']),3)
        for group in result['groups']:
            self.assertEqual(group['cells'],1);self.assertEqual(group['counts']['unobserved_native_spans'],1)
            self.assertEqual(group['counts']['never_visible_observed_spans'],1)
            self.assertEqual(group['counts']['observed_spans_without_final_visibility'],2)
            self.assertEqual(group['counts']['missing_caption_revisions'],1)
        self.assertFalse(result['source_to_widget_latency_qualified']);self.assertEqual(result['integrated_N4_cells'],0)
        freeze(CONTEXT['output']/'SYNTHETIC_GROUPED_COVERAGE.json',result)

    def test_compaction_does_not_promote_accuracy_or_latency(self):
        checked,row,payload=self.example()
        for flag in ('accuracy_qualified','source_to_widget_latency_qualified','names_independently_scored',
                     'exact_consumed_event_attribution','complete_panel_reviewed'):
            changed=deepcopy(checked);changed[flag]=True
            with self.subTest(flag=flag),self.assertRaisesRegex(ValueError,'improperly promoted'):
                panel.compact_content(changed,row,payload,{})
        checked['widget']['observed_span_population']+=1
        with self.assertRaisesRegex(ValueError,'denominator census'):panel.compact_content(checked,row,payload,{})

    def test_shared_binding_changes_cannot_be_overwritten(self):
        checked,row,payload=self.example();b=checked['widget']['source_receipt'];registry={b['path']:dict(b,sha256='0'*64)}
        with self.assertRaisesRegex(ValueError,'Shared content input changed'):panel.compact_content(checked,row,payload,registry)

    def test_grouping_rejects_repeated_cells_or_changed_rosters(self):
        checked,row,payload=self.example();one=panel.compact_content(checked,row,payload,{})
        with self.assertRaisesRegex(ValueError,'Repeated or unreviewed'):panel.aggregate([one,one])
        second=deepcopy(one);second['cell_id']='different-synthetic-cell';second['roster']['people_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Fixed roster changed'):panel.aggregate([one,second])
        second=deepcopy(one);second['cell_id']='different-synthetic-cell';second['maximum_observation_interval_seconds']=float('nan')
        with self.assertRaisesRegex(ValueError,'sampling interval'):panel.aggregate([one,second])
