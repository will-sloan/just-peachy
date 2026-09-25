"""Recorded timing arithmetic and real-reader synthetic composition checks."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from common import fingerprint, freeze, load
import review_application_timing as timing
import test_application_content as prior

CONTEXT = {}


class TimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prior.CONTEXT.update(CONTEXT)
        prior.ContentTests.setUpClass()
        fixture = prior.ContentTests('test_actual_readers_join_complete_synthetic_n2_cell')
        fixture.setUp(); cls.folder, cls.args = fixture.fixture()
        cls.checked = timing.review_cell(cls.folder, **cls.args)
        freeze(CONTEXT['output']/'SYNTHETIC_TIMING_REVIEW.json', cls.checked)
        cls.content = cls.checked['content']
        closure = load(cls.folder/'application/ENGINE_CLOSURE.json')
        cls.native = timing.review_captions(Path(closure['session']), job=cls.args['payload']['job'],
            expected_envelope=cls.content['cell']['transport']['native_envelope_review'])

    def example(self):
        return deepcopy(self.native), deepcopy(self.content['widget'])

    def project(self, native, widget):
        return timing.project(native, widget, origin=100.,
            log=self.content['cell']['observations']['viewport_review']['evidence'])

    def numeric_fixture(self):
        entry = dict(kind='lexical_word', source_window_seconds=[1., 3.],
            first_publication=dict(sequence=1, monotonic_sec=110.),
            first_final_publication=dict(sequence=2, monotonic_sec=111.))
        state = dict(observed_monotonic_sec=120., publication_monotonic_range=[112., 116.],
            compatible_publications=2, ambiguous_native_publication=True, exact_consumed_event_attribution=False,
            caption_visible=True, retired=False, row_id='fixture-row', row_ref={'fixture': True},
            candidate_bindings_sha256='0'*64)
        row = dict(row_id='fixture-row', caption_visible=True, final=True)
        return state, row, entry

    def test_actual_readers_join_synthetic_cell_without_promoting_latency(self):
        result = self.checked; facts = result['timing']
        self.assertEqual(facts['counts']['lexical_word'], dict(native=4, observed=4, unobserved=0,
            without_row_visible_observation=0, without_final_row_visible_observation=1))
        self.assertEqual(facts['counts']['empty_caption']['native'], 0)
        self.assertEqual(result['integrated_N4_cells'], 0)
        for key in ('source_to_widget_latency_qualified', 'individual_word_glyph_visibility_proven',
            'exact_consumed_event_attribution', 'complete_panel_reviewed', 'N4_accepted', 'continuous_exposure_measured'):
            self.assertIs(result[key], False)
        self.assertTrue(all(v['stages']['first_row_visible']['elapsed_since_first_native_span_publication_seconds'] > 0
            for v in facts['spans'].values()))

    def test_hand_calculated_recorded_elapsed_and_uncertainty_intervals(self):
        state, row, entry = self.numeric_fixture()
        result = timing.sampled_state(state, row, entry, 100., 'first_final_visible')
        self.assertEqual(result['elapsed_since_first_native_span_publication_seconds'], 10.)
        self.assertEqual(result['elapsed_since_first_native_final_publication_seconds'], 9.)
        self.assertEqual(result['elapsed_from_compatible_native_publications_range_seconds'], [4., 8.])
        self.assertEqual(result['source_window_relative_interval_seconds'], [17., 19.])
        self.assertTrue(result['ambiguous_native_publication'])
        self.assertFalse(result['exact_consumed_event_attribution'])
        self.assertIsNone(result['continuous_exposure_seconds'])

    def test_signed_source_window_interval_is_not_clamped(self):
        state, row, entry = self.numeric_fixture(); entry['source_window_seconds'] = [18., 25.]
        result = timing.sampled_state(state, row, entry, 100., 'first_visible')
        self.assertEqual(result['source_window_relative_interval_seconds'], [-5., 2.])
        self.assertFalse(result['individual_word_glyph_visibility_proven'])

    def test_unobserved_and_never_visible_spans_keep_separate_denominators(self):
        native, widget = self.example(); ids = list(widget['spans'])
        widget['spans'] = {ids[0]: widget['spans'][ids[0]]}
        widget['spans'][ids[0]].update(first_visible=None, first_final_visible=None)
        widget.update(observed_span_population=1, native_spans_not_observed=sorted(set(ids)-{ids[0]}),
            observed_spans_never_visible=1, observed_spans_without_final_visibility=1)
        result = self.project(native, widget)
        self.assertEqual(result['counts']['lexical_word'], dict(native=4, observed=1, unobserved=3,
            without_row_visible_observation=4, without_final_row_visible_observation=4))
        self.assertIsNone(result['spans'][ids[0]]['stages']['first_row_visible'])
        self.assertIsNotNone(result['spans'][ids[0]]['stages']['latest_row_observation'])
        self.assertTrue(all(value is None for value in result['spans'][ids[1]]['stages'].values()))

    def test_empty_caption_virtual_id_is_not_a_word(self):
        native, widget = self.example(); d = deepcopy(native['displays'][-1]); part = deepcopy(d['segments'][0])
        sid = 'fixture-empty/segment:0000'; part.update(segment_id=sid, span_ids=[], raw_text='')
        d.update(segments=[part], publication_sequence=100, publication_monotonic_sec=150.)
        native['displays'].append(d); widget['native_caption_review_sha256'] = fingerprint(native)
        widget['native_span_population'] += 1; widget['native_spans_not_observed'] = [sid]
        result = self.project(native, widget)
        self.assertEqual(result['counts']['lexical_word']['native'], 4)
        self.assertEqual(result['counts']['empty_caption'], dict(native=1, observed=0, unobserved=1,
            without_row_visible_observation=1, without_final_row_visible_observation=1))
        self.assertIsNone(result['spans'][sid]['source_window_seconds'])

    def test_changed_native_review_is_refused(self):
        native, widget = self.example(); native['displays'][0]['publication_monotonic_sec'] += .1
        with self.assertRaisesRegex(ValueError, 'changed between timing'): self.project(native, widget)

    def test_missing_visibility_cannot_be_removed_from_denominator(self):
        native, widget = self.example(); widget['observed_span_population'] -= 1
        with self.assertRaisesRegex(ValueError, 'denominator differs'): self.project(native, widget)

    def test_nonfinite_or_future_native_clock_is_refused(self):
        state, row, entry = self.numeric_fixture()
        for clocks in ([112., float('nan')], [112., 121.]):
            with self.subTest(clocks=clocks), self.assertRaisesRegex(ValueError, 'clock order'):
                state['publication_monotonic_range'] = clocks
                timing.sampled_state(state, row, entry, 100., 'first_visible')

    def test_final_visibility_requires_native_final_and_final_row(self):
        state, row, entry = self.numeric_fixture(); row['final'] = False
        with self.assertRaisesRegex(ValueError, 'Final observation'):
            timing.sampled_state(state, row, entry, 100., 'first_final_visible')

    def test_invisible_latest_is_kept_but_cannot_be_first_visible(self):
        state, row, entry = self.numeric_fixture()
        state.update(caption_visible=False, retired=True); row.update(caption_visible=False, removed_from_controller=True)
        result = timing.sampled_state(state, row, entry, 100., 'latest')
        self.assertTrue(result['retired']); self.assertFalse(result['row_has_visible_caption_glyphs'])
        with self.assertRaisesRegex(ValueError, 'Visible stage'):
            timing.sampled_state(state, row, entry, 100., 'first_visible')

    def test_changed_row_membership_is_refused(self):
        native, widget = self.example(); original = timing.read_row
        def changed(*args):
            value = original(*args); value['span_ids'] = ['foreign-fixture-span']; return value
        with patch.object(timing, 'read_row', changed), self.assertRaisesRegex(ValueError, 'no longer contains'):
            self.project(native, widget)

    def test_budget_and_exact_alignment_authority_are_enforced(self):
        native, widget = self.example()
        with patch.object(timing, 'MAX_MEMBERSHIPS', 1), self.assertRaisesRegex(ValueError, 'timing bound'):
            self.project(native, widget)
        native['stable_word_spans'][0]['exact_word_start_sec'] = .1
        widget['native_caption_review_sha256'] = fingerprint(native)
        with self.assertRaisesRegex(ValueError, 'timing authority'): self.project(native, widget)

    def test_composition_refuses_native_change_after_content_reader(self):
        original = timing.review_captions
        def changed(*args, **kwargs):
            value = original(*args, **kwargs); value['displays'][0]['controller_update_monotonic_sec'] += .1; return value
        with patch.object(timing, 'review_captions', changed), self.assertRaisesRegex(ValueError, 'changed between timing'):
            timing.review_cell(self.folder, **self.args)
