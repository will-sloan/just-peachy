"""Actual-reader synthetic composition and observed-heading edge cases."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from common import freeze
import review_application_labels as labels
import test_application_content as prior

CONTEXT = {}
PEOPLE = [dict(id='fixture-A', name='Alice'), dict(id='fixture-B', name='Bob')]


class LabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior.CONTEXT.update(CONTEXT); prior.ContentTests.setUpClass()
        fixture = prior.ContentTests('test_actual_readers_join_complete_synthetic_n2_cell'); fixture.setUp()
        cls.folder, cls.args = fixture.fixture()
        cls.checked = labels.review_cell(cls.folder, **cls.args)
        freeze(CONTEXT['output']/'SYNTHETIC_LABEL_REVIEW.json', cls.checked)
        cls.content = cls.checked['observed']['content']
        from common import load
        cls.people = load(cls.folder/'application/FINAL_SNAPSHOT.json')['people']

    def row(self, active='Alice', history='Alice'):
        def pane(text):
            return dict(present_in_widget=True, applied_heading_text=text,
                caption_visible=True, heading_visible=bool(text), heading_viewport=dict(
                    mapped=True, any_visible=bool(text), visible_nonspace_characters=1 if text else 0,
                    checked_characters=1 if text else 0, partially_clipped_characters=0))
        return dict(panes=dict(active=pane(active), history=pane(history)),
            verified_profile_id='fixture-A', display_profile_id='fixture-A', naming_state='confirmed',
            identity_assignment=dict(track_id=0))

    def project(self, content=None, people=None):
        value = self.content if content is None else content
        return labels.project(value, people=self.people if people is None else people,
            log=value['cell']['observations']['viewport_review']['evidence'])

    def test_actual_readers_preserve_unknown_fixture_headings_and_scope(self):
        result = self.checked; facts = result['labels']; counts = facts['counts']
        self.assertEqual(counts['first_visible']['native_spans'], 4)
        self.assertEqual(counts['first_visible']['unrecognized_or_ambiguous_heading'], 4)
        self.assertEqual(counts['first_final_visible']['sampled_spans'], 3)
        self.assertEqual(counts['first_final_visible']['missing_stage'], 1)
        for key in ('naming_accuracy_qualified', 'N4_accepted', 'evaluator_truth_loaded', 'inherited_suppressed_heading_inferred'):
            self.assertIs(result[key], False)
        self.assertEqual(result['integrated_N4_cells'], 0)

    def test_exact_heading_categories_are_distinct(self):
        for text, kind in [('Alice', 'ROSTER_NAME'), ('Unknown', 'UNKNOWN'),
            ('Unknown · voice unavailable', 'UNKNOWN'), ('••• · collecting voice', 'PENDING'),
            ('Speaker 0', 'ANONYMOUS'), ('Transcription', 'TRANSCRIPTION'), ('', 'SUPPRESSED'),
            ('Alice · assumed', 'FORCED_ROSTER_ASSUMPTION'), ('Other heading', 'UNRECOGNIZED')]:
            with self.subTest(kind=kind): self.assertEqual(labels.label_kind(text, PEOPLE)['kind'], kind)

    def test_native_known_profile_does_not_replace_displayed_unknown(self):
        result = labels.interpret_row(self.row('Unknown', 'Unknown'), PEOPLE)
        self.assertEqual(result['native_verified_profile_id'], 'fixture-A')
        self.assertEqual(result['same_pane_visible_roster_profile_ids'], [])
        self.assertTrue(all(p['kind'] == 'UNKNOWN' and p['roster_profile_id'] is None for p in result['panes'].values()))

    def test_conflicting_visible_names_remain_two_predictions(self):
        result = labels.interpret_row(self.row('Alice', 'Bob'), PEOPLE)
        self.assertEqual(result['same_pane_visible_roster_profile_ids'], ['fixture-A', 'fixture-B'])
        self.assertTrue(result['conflicting_visible_roster_names'])
        self.assertTrue(result['applied_pane_headings_differ'])
        self.assertEqual(result['recorded_name_native_profile_disagreements'], 1)
        self.assertFalse(result['single_identity_selected'])

    def test_caption_and_heading_visibility_are_not_unioned_across_panes(self):
        row = self.row(); row['panes']['active']['caption_visible'] = False
        row['panes']['history']['heading_visible'] = False
        result = labels.interpret_row(row, PEOPLE)
        self.assertFalse(result['any_same_pane_heading_and_caption_glyphs_visible'])
        self.assertEqual(result['same_pane_visible_roster_profile_ids'], [])

    def test_suppression_does_not_inherit_native_or_other_pane_name(self):
        result = labels.interpret_row(self.row('', 'Alice'), PEOPLE)
        active = result['panes']['active']
        self.assertEqual(active['kind'], 'SUPPRESSED'); self.assertIsNone(active['roster_profile_id'])
        self.assertFalse(result['inherited_suppressed_heading_inferred'])
        row = self.row('', ''); row['panes']['active']['heading_visible'] = True
        with self.assertRaisesRegex(ValueError, 'Suppressed heading'): labels.interpret_row(row, PEOPLE)

    def test_reserved_roster_name_is_ambiguous(self):
        for name in ('Unknown', 'Speaker 0', '••• · collecting voice', 'Transcription', 'Alice · assumed'):
            people = PEOPLE + [dict(id='collision', name=name)]
            result = labels.label_kind(name, people)
            self.assertEqual(result['kind'], 'AMBIGUOUS_RESERVED_ROSTER_NAME')
            self.assertIsNone(result['roster_profile_id'])

    def test_forced_assumption_is_not_verified_name(self):
        result = labels.interpret_row(self.row('Alice · assumed', 'Alice · assumed'), PEOPLE)
        self.assertTrue(result['any_forced_assumption'])
        self.assertEqual(result['same_pane_visible_roster_profile_ids'], [])
        self.assertFalse(result['identity_correctness_established'])

    def test_offscreen_applied_name_is_retained_without_visibility_credit(self):
        row = self.row()
        for p in row['panes'].values(): p.update(heading_visible=False, caption_visible=False)
        result = labels.interpret_row(row, PEOPLE)
        self.assertEqual(result['panes']['active']['roster_profile_id'], 'fixture-A')
        self.assertFalse(result['any_same_pane_heading_and_caption_glyphs_visible'])
        self.assertEqual(result['same_pane_visible_roster_profile_ids'], [])

    def test_partial_glyph_counts_do_not_prove_complete_heading(self):
        result = labels.interpret_row(self.row(), PEOPLE)
        self.assertTrue(result['any_same_pane_heading_and_caption_glyphs_visible'])
        self.assertFalse(result['panes']['active']['complete_heading_glyph_visibility_proven'])
        self.assertEqual(result['panes']['active']['heading_geometry']['visible_nonspace_characters'], 1)

    def test_heading_text_is_not_casefolded_trimmed_or_fuzzy_matched(self):
        for text in ('alice', ' Alice', 'Alice ', 'Alic', 'Alice · confirmed'):
            self.assertEqual(labels.label_kind(text, PEOPLE)['kind'], 'UNRECOGNIZED')

    def test_absent_pane_is_not_unknown_or_suppressed(self):
        row = self.row(); row['panes']['active'] = dict(present_in_widget=False, caption_visible=False, heading_visible=False)
        result = labels.interpret_row(row, PEOPLE)
        self.assertEqual(result['panes']['active']['kind'], 'ABSENT')
        self.assertIsNone(result['panes']['active']['applied_text'])

    def test_missing_observation_retains_stage_denominators(self):
        content = deepcopy(self.content); content['widget']['native_span_population'] += 1
        content['widget']['native_spans_not_observed'].append('unobserved-synthetic-span')
        result = self.project(content)
        self.assertEqual(result['counts']['first_visible']['native_spans'], 5)
        self.assertEqual(result['counts']['first_visible']['missing_stage'], 1)
        self.assertEqual(result['counts']['first_final_visible']['missing_stage'], 2)
        self.assertIsNone(result['spans']['unobserved-synthetic-span']['latest'])

    def test_changed_roster_is_refused_before_interpretation(self):
        people = deepcopy(self.people); people[0]['name'] = 'Changed display name'
        with self.assertRaisesRegex(ValueError, 'joined display roster'): self.project(people=people)

    def test_changed_recorded_heading_is_refused(self):
        original = labels.read_row
        def changed(*args):
            value = original(*args)
            value['panes']['active']['applied_heading_text'] = 'Foreign text'
            return value
        with patch.object(labels, 'read_row', changed), self.assertRaisesRegex(ValueError, 'changed between readers'):
            self.project()

    def test_state_and_membership_allocations_are_bounded(self):
        for name in ('MAX_STATES', 'MAX_MEMBERSHIPS'):
            with self.subTest(limit=name), patch.object(labels, name, 0), self.assertRaisesRegex(ValueError, 'bound|budget'):
                self.project()
