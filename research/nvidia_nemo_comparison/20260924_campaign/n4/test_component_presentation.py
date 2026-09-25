"""Actual frozen span-state replay tests. README_COMPONENT_PRESENTATION.md."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest

from component_presentation import ComponentPresentation, CLOCK_KIND


class TestComponentPresentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('JP_N4_SOURCE',
            r'G:\Just_Peachy_N1\20260924_campaign\local\releases\n4-catalog-v3\prototype'))
        sys.path[:0] = [str(source), str(source/'vendor')]
        from edge_speech_pipeline.research_s6d import S6DSettings, build_presentation_state
        cls.settings = S6DSettings
        cls.build = staticmethod(build_presentation_state)

    def setUp(self):
        state = self.build(self.settings(max_display_rows=512), s7=dict(mode='M1',
            session_id='synthetic-protocol', ownership_mode='timestamped_spans_v3'))
        self.capture = ComponentPresentation(state)

    def observation(self, serial, text, start=0., end=1., final=False, uid='utterance:000000'):
        return dict(kind='asr', event_id=f'asr:{serial:08d}', utterance_id=uid,
            source_start_sec=start, source_end_sec=end, available_at_sec=end+.1,
            text=text, final=final, display_text=text, punctuation=None, asr_decode_ms=1.)

    def test_all_words_survive_rewrite_final_and_formatting(self):
        self.capture.text(self.observation(1, 'one old'))
        self.capture.text(self.observation(2, 'one new words', end=2., final=True))
        self.capture.formatting(dict(utterance_id='utterance:000000', input_event_id='asr:00000002',
            raw_text='one new words', punctuation={'text':'One new words.'}, modeled_available_at_sec=2.2))
        result = self.capture.snapshot()
        self.assertEqual(result['rows'][0]['text'], 'one new words')
        self.assertEqual(result['rows'][0]['display_text'], 'One new words.')
        self.assertEqual(result['rows'][0]['retired_span_count'], 1)
        self.assertEqual(result['clock_kind'], CLOCK_KIND)
        self.assertFalse(result['physical_widget_observed'])
        self.assertEqual(result['first_visible_latency'], 'UNAVAILABLE_MODELED_REPLAY')

    def test_foreign_session_is_rejected(self):
        event = self.observation(1, 'text')
        event['session_id'] = 'another-scene'
        with self.assertRaisesRegex(ValueError, 'Foreign'):
            self.capture.text(event)

    def test_consecutive_finals_with_same_source_boundary_are_preserved(self):
        self.capture.text(self.observation(1, 'first', final=True))
        self.capture.text(self.observation(2, 'second', start=1., end=1., final=True, uid='utterance:000001'))
        result = self.capture.snapshot()
        self.assertEqual([r['text'] for r in result['rows']], ['first', 'second'])
        self.assertEqual(result['rows'][1]['word_spans'][0]['source_start_sec'], 1.)
        self.assertIsNone(result['rows'][1]['word_spans'][0]['exact_word_start_sec'])

    def test_stale_identity_cannot_relabel_new_words(self):
        self.capture.text(self.observation(1, 'first'))
        self.capture.text(self.observation(2, 'first second', end=2., final=True))
        self.capture.policy(dict(event_type='transcript_label_revision', event_id='policy:00000001',
            utterance_id='utterance:000000', source_start_sec=0., source_end_sec=1.,
            target_source_start_sec=0., target_source_end_sec=1., target_text_revision_id='asr:00000001',
            available_at_sec=2.2, latest_label_time=2.2, latest_label='Speaker 8',
            replacement_tracker_id=8, latest_anonymous_label='Speaker 8'))
        result = self.capture.snapshot()
        self.assertEqual(result['rejected']['identity_wrong_target_revision'], 1)
        self.assertTrue(all(s['track_id'] is None for s in result['rows'][0]['segments']))

    def test_current_supported_identity_uses_actual_token_spans(self):
        self.capture.text(self.observation(1, 'first', final=True))
        self.capture.policy(dict(event_type='transcript_label_revision', event_id='policy:00000001',
            utterance_id='utterance:000000', source_start_sec=0., source_end_sec=1.,
            target_source_start_sec=0., target_source_end_sec=1., target_text_revision_id='asr:00000001',
            available_at_sec=1.2, latest_label_time=1.2, latest_label='Speaker 2',
            replacement_tracker_id=2, latest_anonymous_label='Speaker 2'))
        row = self.capture.snapshot()['rows'][0]
        self.assertEqual(row['segments'][0]['track_id'], 2)
        self.assertEqual(row['text'], 'first')
        self.assertIsNone(row['word_spans'][0]['exact_word_start_sec'])

    def test_formatting_requires_exact_raw_final_once(self):
        self.capture.text(self.observation(1, 'actual', final=True))
        good = dict(utterance_id='utterance:000000', input_event_id='asr:00000001',
            raw_text='actual', punctuation={'text':'Actual.'}, modeled_available_at_sec=1.2)
        for key, value in [('input_event_id', 'asr:00000009'), ('raw_text', 'other')]:
            bad = deepcopy(good); bad[key] = value
            with self.assertRaises(ValueError): self.capture.formatting(bad)
        self.capture.formatting(good)
        with self.assertRaises(ValueError): self.capture.formatting(good)

    def test_observed_clocks_and_noncausal_input_are_refused(self):
        bad = self.observation(1, 'text')
        bad['observed_text_ready_at_sec'] = 1.1
        with self.assertRaisesRegex(ValueError, 'Observed'): self.capture.text(bad)
        self.setUp()
        self.capture.text(self.observation(1, 'text', final=True))
        with self.assertRaisesRegex(ValueError, 'after final'):
            self.capture.text(self.observation(2, 'later'))
        self.setUp()
        bad = self.observation(1, 'text'); bad['available_at_sec'] = .1
        with self.assertRaisesRegex(ValueError, 'Noncausal'): self.capture.text(bad)


if __name__ == '__main__': unittest.main()
