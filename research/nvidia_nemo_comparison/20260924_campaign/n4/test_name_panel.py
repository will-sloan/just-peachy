"""Saved synthetic composition, population and weighted-count regressions."""
from copy import deepcopy
import json
from pathlib import Path

from common import freeze,load
from score_observed_names import summarize
import review_name_panel as panel
import test_application_panel_review_v2 as prior

CONTEXT={}


class NamePanelTests(prior.PanelReviewTests):
    @classmethod
    def setUpClass(cls):
        cls.checked=load(CONTEXT['synthetic_observed']['path']);cls.score=load(CONTEXT['synthetic_score']['path'])
        cls.references=CONTEXT['references'];cls.payload=load(CONTEXT['payload']['path']);c=cls.payload['contract']
        cls.row=dict(cell_id=cls.payload['cell_id'],composition='_'.join(c[k] for k in ('variant','diarization','encoder')),
            kind='panel',repeat=0,job=deepcopy(cls.payload['job']),contract=deepcopy(c))
        cls.registry={};cls.example=panel.compact(cls.checked,cls.score,cls.references,cls.row,cls.payload,cls.registry)

    def setUp(self): CONTEXT['checkpoint']()

    def test_saved_compaction_preserves_inputs_population_and_scope(self):
        s=self.example
        self.assertEqual((s['native_lexical_spans'],s['empty_caption_spans_excluded']),(4,0))
        self.assertTrue(s['conditional_name_diagnostics_scored']);self.assertFalse(s['naming_accuracy_qualified'])
        self.assertEqual(s['integrated_N4_cells'],0);self.assertFalse(s['N4_accepted'])
        for b in self.references['evidence']+self.checked['evidence']:
            self.assertEqual(self.registry[b['path']],b)
        freeze(CONTEXT['output']/'SYNTHETIC_COMPACT_NAME_SCORE.json',s)

    def test_all_scenarios_stages_and_panes_roundtrip_without_lost_counts(self):
        for si,scenario in enumerate(panel.SCENARIOS):
            for ti,stage in enumerate(panel.STAGES):
                for pi,pane in enumerate(panel.PANES):
                    self.assertEqual(panel.unpack(self.example['name_count_vectors'][si][ti][pi]),self.score['scenarios'][scenario][stage][pane])
        group=panel.aggregate([self.example])['groups'][0]
        self.assertEqual(group['scenarios']['observed']['first_final_visible']['active']['missing_stage'],1)

    def count_fixture(self,correct,wrong,cell_id):
        # Explicit arithmetic fixture, not a modified production receipt.
        rows=[dict(reference_category='AVAILABLE_PROFILE_REFERENCE',reference_support='SINGLE_INTERSECTING_ESTIMATED_IDENTITY',
            heading_kind='ROSTER_NAME',joint_visible=True,outcome=outcome) for outcome in
            ['ESTIMATED_SUPPORT_CORRECT_AVAILABLE_NAME']*correct+['ESTIMATED_SUPPORT_WRONG_AVAILABLE_NAME']*wrong]
        s=deepcopy(self.example);n=correct+wrong;s.update(cell_id=cell_id,native_lexical_spans=n,empty_caption_spans_excluded=0)
        s['content_counts']['native_spans']=n;s['pane_conflicts']=[[0,0] for _ in panel.STAGES]
        s['revision_counts']=[[0,n,0],[0,n,0]];v=panel.pack(summarize(rows))
        s['name_count_vectors']=[[[deepcopy(v) for _ in panel.PANES] for _ in panel.STAGES] for _ in panel.SCENARIOS]
        return s

    def test_group_rates_sum_counts_instead_of_averaging_cell_rates(self):
        small=self.count_fixture(4,0,'small');large=self.count_fixture(0,8,'large')
        r=panel.aggregate([small,large]);c=r['groups'][0]['scenarios']['observed']['first_visible']['active']
        self.assertEqual((c['single_available_reference_spans'],c['outcome_counts']['ESTIMATED_SUPPORT_CORRECT_AVAILABLE_NAME']),(12,4))
        self.assertEqual(c['rates']['estimated_correct_name_per_single_available_reference_span'],1/3)
        self.assertNotEqual(c['rates']['estimated_correct_name_per_single_available_reference_span'],.5)
        self.assertTrue(r['rates_from_summed_counts']);self.assertFalse(r['per_cell_rates_averaged'])
        freeze(CONTEXT['output']/'WEIGHTED_COUNT_FIXTURE.json',r)

    def test_tap_repeat_and_reference_class_groups_remain_separate(self):
        rows=[deepcopy(self.example) for _ in range(4)]
        for i,r in enumerate(rows):r['cell_id']=f'development-{i}'
        rows[1]['tap']='O1';rows[2]['kind']='timing_repeat';rows[3]['reference_class']='incomplete_ambient_reference'
        report=panel.aggregate(rows);self.assertEqual(len(report['groups']),4)
        self.assertTrue(all(g['cells']==1 for g in report['groups']))

    def test_foreign_row_binding_or_promoted_score_rejected(self):
        row=deepcopy(self.row);row['job']['audio_sha256']='0'*64
        with self.assertRaises(ValueError):panel.compact(self.checked,self.score,self.references,row,self.payload,{})
        for change in (dict(observed_review_sha256='0'*64),dict(naming_accuracy_qualified=True),dict(native_spans=5)):
            score=deepcopy(self.score);score.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):panel.compact(self.checked,score,self.references,self.row,self.payload,{})

    def test_shared_reference_binding_conflict_is_not_overwritten(self):
        b=self.references['evidence'][0];registry={b['path']:dict(b,sha256='0'*64)}
        with self.assertRaisesRegex(ValueError,'Shared content input changed'):
            panel.compact(self.checked,self.score,self.references,self.row,self.payload,registry)

    def test_corrupt_axis_category_or_denominator_is_rejected(self):
        for mode in ('negative','truncated','visible','axis','scope'):
            s=deepcopy(self.example)
            if mode=='negative':s['name_count_vectors'][0][0][0][0][0]=-1
            elif mode=='truncated':s['name_count_vectors'].pop()
            elif mode=='visible':s['name_count_vectors'][0][0][0][4]+=1
            elif mode=='axis':s['name_count_axes_sha256']='0'*64
            else:s['naming_accuracy_qualified']=True
            with self.subTest(mode=mode),self.assertRaises(ValueError):panel.aggregate([s])
        c=deepcopy(self.score['scenarios']['observed']['first_visible']['active']);c['outcome_counts']['invented']=0
        with self.assertRaises(ValueError):panel.pack(c)

    def test_duplicate_cells_and_changed_fixed_roster_control_or_context_rejected(self):
        with self.assertRaises(ValueError):panel.aggregate([self.example,self.example])
        for field in ('roster','constant_control_profile_id','reference_context_sha256'):
            s=deepcopy(self.example);s['cell_id']='different';s[field]='changed'
            with self.subTest(field=field),self.assertRaises(ValueError):panel.aggregate([self.example,s])

    def test_maximum_panel_compaction_budget_with_registry_reserve(self):
        rows=[];classes=tuple(panel.EXPECTED_CLASSES)
        for i in range(240):
            s=deepcopy(self.example);s.update(cell_id=f'budget-fixture-{i:03d}',composition=f'fixture-{i%6}',
                kind=('panel','timing_repeat')[(i//6)%2],tap=('O0','O1')[(i//12)%2],reference_class=classes[(i//24)%4])
            rows.append(s)
        report=panel.aggregate(rows)
        size=lambda value:len((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
        cell_bytes=sum(size(r) for r in rows);report_bytes=size(report);registry_reserve=2*1024**2
        self.assertLess(cell_bytes+report_bytes+registry_reserve,panel.OUTPUT_LIMIT)
        freeze(CONTEXT['output']/'OUTPUT_BUDGET_FIXTURE.json',dict(cells=240,groups=len(report['groups']),
            compact_cell_bytes=cell_bytes,grouped_report_bytes=report_bytes,registry_and_admission_reserve=registry_reserve,
            hard_output_limit=panel.OUTPUT_LIMIT,production_registry_size_not_yet_observed=True))

    def test_empty_lexical_population_has_null_rates_and_no_missing_credit(self):
        s=self.count_fixture(0,0,'empty');s['empty_caption_spans_excluded']=2;s['content_counts']['native_spans']=2
        g=panel.aggregate([s])['groups'][0];self.assertEqual(g['empty_caption_spans_excluded'],2)
        for stages in g['scenarios'].values():
            for panes in stages.values():
                for counts in panes.values():
                    self.assertEqual(counts['native_lexical_spans'],0);self.assertTrue(all(v is None for v in counts['rates'].values()))
