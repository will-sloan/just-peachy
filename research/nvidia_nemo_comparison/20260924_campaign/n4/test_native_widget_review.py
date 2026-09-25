"""Synthetic cross-journal joins; no widget or model launch. See its README."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, freeze
from viewport_ledger_v2 import ViewportLedger
import review_native_widget as widget
import test_native_caption_review as native_fixture

CONTEXT = {}


class NativeWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixture.SOURCE = CONTEXT['source']
        native_fixture.NativeCaptionTests.setUpClass()

    def setUp(self):
        self.folder = CONTEXT['output']/self._testMethodName; self.folder.mkdir()
        native_fixture.OUTPUT = self.folder
        self.native = native_fixture.NativeCaptionTests('test_actual_span_state_rewrite_identity_zero_and_formatting')
        self.native.setUp(); self.native.scenario()

    def observations(self, *, at_offset=.03, visible=True, origin=100.):
        snapshots = []
        # These expected strings are independent explicit fixture values, not
        # generated with the production join's formatter or signature code.
        expected = [['One old'], ['One new words'], ['One ', 'new words'], ['One ', 'new words.']]
        for p, texts in zip(self.native.display_rows(), expected):
            rows = []
            for part, text in zip(p['segments'], texts):
                known = part.get('known_profile_id') if part.get('naming_state') == 'confirmed' else None
                geometry = dict(mapped=True, any_visible=visible, visible_nonspace_characters=1 if visible else 0,
                    checked_characters=1, partially_clipped_characters=0)
                pane = dict(present_in_widget=True, applied_caption_text=text, applied_heading_text='Recorded heading',
                    caption_visible=visible, heading_visible=visible, caption_viewport=deepcopy(geometry), heading_viewport=deepcopy(geometry))
                rows.append(dict(row_id=part['segment_id'], caption_key=p['caption_key'],
                    span_ids=part['span_ids'] or [part['segment_id']], raw_asr_text=part['raw_text'], final=p['final'],
                    source_start_sec=part['source_start_sec'], source_end_sec=part['source_end_sec'],
                    timing_kind=part['timing_kind'], speaker_revision=part.get('speaker_revision'),
                    verified_profile_id=known, display_profile_id=known, naming_state=part.get('naming_state'),
                    identity_assignment=part.get('prototype_assignment'), strictly_filtered=False,
                    caption_visible=visible, heading_visible=visible, panes=dict(active=deepcopy(pane), history=deepcopy(pane))))
            at = p['publication_monotonic_sec']+at_offset
            snapshots.append(dict(schema='n4-tk-viewport-observation-v1', observed_monotonic_sec=at,
                source_origin_monotonic_sec=origin, source_elapsed_sec=at-origin, source_clock='ACTUAL_SOURCE_MONOTONIC',
                source_relative_times_available=True, physical_scanout_measured=False, source_to_widget_latency_qualified=False,
                rows=rows, character_checks=len(rows)*4, scope='Synthetic protocol and geometry facts; no actual widget execution'))
        return snapshots

    def review(self, observations=None, **overrides):
        session, envelope = self.native.write()
        ledger = ViewportLedger(self.folder/'viewport')
        for observed in observations if observations is not None else self.observations(): ledger.add(observed)
        ledger.close()
        kwargs = dict(job=self.native.job, expected_envelope=envelope,
            viewport_summary=bind(ledger.directory/'SUMMARY.json'), source_receipt=CONTEXT['source_receipt'],
            people=[], mode='open_with_names')
        kwargs.update(overrides)
        return widget.review(session, **kwargs)

    def test_complete_primary_text_and_first_final_latest_states(self):
        observations = self.observations()
        # Token replacement in a reused row does not itself remove that row.
        # Record an explicit empty viewport to exercise real row retirement.
        removed = deepcopy(observations[-1]); removed['rows'] = []; removed['character_checks'] = 0
        removed['observed_monotonic_sec'] += .1
        removed['source_elapsed_sec'] = removed['observed_monotonic_sec']-removed['source_origin_monotonic_sec']
        observations.append(removed)
        result = self.review(observations)
        self.assertEqual(result['native_span_population'], 4)
        self.assertEqual(result['observed_span_population'], 4)
        self.assertEqual(result['native_spans_not_observed'], [])
        self.assertTrue(result['primary_caption_text_consistency_reviewed'])
        self.assertFalse(result['application_owner_reviewed']); self.assertFalse(result['source_to_widget_latency_qualified'])
        self.assertTrue(any(s['retired'] for s in result['states'].values()))
        self.assertEqual(result['integrated_N4_cells'], 0)
        freeze(self.folder/'SYNTHETIC_WIDGET_JOIN.json', result)

    def test_wrong_raw_word_is_rejected_even_with_valid_viewport_ledger(self):
        observations = self.observations(); observations[-1]['rows'][0]['raw_asr_text'] = 'fabricated '
        with self.assertRaisesRegex(ValueError, 'no matching native'): self.review(observations)

    def test_wrong_applied_caption_is_not_hidden_by_correct_raw_words(self):
        observations = self.observations()
        observations[-1]['rows'][1]['panes']['active']['applied_caption_text'] = 'invented caption'
        with self.assertRaisesRegex(ValueError, 'compatible preceding'): self.review(observations)

    def test_native_publication_must_precede_widget_observation(self):
        observations = self.observations(); first = observations[0]
        first['observed_monotonic_sec'] = 101.6; first['source_elapsed_sec'] = 1.6
        # Use subtraction to preserve the collector's exact elapsed equation.
        first['source_elapsed_sec'] = first['observed_monotonic_sec']-first['source_origin_monotonic_sec']
        with self.assertRaisesRegex(ValueError, 'compatible preceding'): self.review(observations)

    def test_native_and_viewport_source_origins_must_agree(self):
        with self.assertRaisesRegex(ValueError, 'source origins differ'): self.review(self.observations(origin=90.))

    def test_unobserved_and_never_visible_spans_keep_denominators(self):
        result = self.review(self.observations(visible=False)[:1])
        self.assertEqual(result['native_span_population'], 4); self.assertEqual(result['observed_span_population'], 2)
        self.assertEqual(len(result['native_spans_not_observed']), 2)
        self.assertEqual(result['observed_spans_never_visible'], 2)
        self.assertEqual(result['observed_spans_without_final_visibility'], 2)

    def test_identical_native_states_keep_multiple_possible_predecessors(self):
        original = deepcopy(next(e['payload'] for e in self.native.events if e['event_type'] == 'transcript_label_revision'))
        original.update(event_id='policy:00000002', latest_label_time=3., available_at_sec=3.)
        self.native.emit('transcript_label_revision', original)
        observations = self.observations()[-1:]
        observations[0]['observed_monotonic_sec'] = self.native.tick+.03
        observations[0]['source_elapsed_sec'] = observations[0]['observed_monotonic_sec']-100.
        result = self.review(observations)
        self.assertGreater(result['ambiguous_state_joins'], 0)
        self.assertTrue(any(s['compatible_publications'] > 1 for s in result['states'].values()))
        self.assertFalse(result['exact_consumed_event_attribution'])

    def test_recorded_heading_does_not_certify_a_person(self):
        observations = self.observations()
        for sample in observations:
            for row in sample['rows']:
                for pane in row['panes'].values(): pane['applied_heading_text'] = 'Fixture person · assumed'
        result = self.review(observations)
        self.assertFalse(result['naming_accuracy_qualified'])
        self.assertTrue(any('Fixture person · assumed' in s['recorded_headings'].values() for s in result['states'].values()))

    def test_partial_formatter_respects_names_and_split_lexical_fallback(self):
        case, _ = widget.casing(CONTEXT['source_receipt'])
        parent = deepcopy(self.native.display_rows()[-1]); part = parent['segments'][1]
        parent['display_text'] = 'Changed lexical content'
        self.assertEqual(widget.expected_caption(parent, part, [], case), 'new words')
        parent = dict(text='alice uses api', final=False, segments=[dict()], display_text='alice uses api')
        self.assertEqual(widget.expected_caption(parent, dict(raw_text='alice uses api'), [dict(id='fixture',name='ALICE')], case), 'ALICE uses API')

    def test_primary_mode_and_roster_contract_are_explicit(self):
        with self.assertRaisesRegex(ValueError, 'primary open mode'): self.review(mode='selected_closed')

    def test_index_allocation_is_bounded(self):
        with patch.object(widget, 'MAX_ENTRIES', 1), self.assertRaisesRegex(ValueError, 'index budget'): self.review()

    def test_changed_viewport_after_independent_review_is_rejected(self):
        original = widget.build_index
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            with (self.folder/'viewport/OBSERVATIONS.jsonl').open('ab') as stream: stream.write(b'{}\n')
            return result
        with patch.object(widget, 'build_index', mutate), self.assertRaisesRegex(ValueError, 'Binding changed'):
            self.review()
