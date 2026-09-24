"""Source-text fixtures for the supplied WD-40/Amir notes. No audio or GUI."""
from pathlib import Path
import hashlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'prototype'), str(ROOT / 'prototype/vendor')]
from app.text_assistance import TextAssistance, corrected_partition
from edge_speech_pipeline.research_s6d import S6DSettings
from edge_speech_pipeline.research_s7_presentation import S7PresentationState

PEOPLE = [{'id': 'fixture-amir', 'name': 'Amir'}]


class NoteExamples(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='peachy_n1_notes_')
        self.addCleanup(temporary.cleanup)
        self.assistance = TextAssistance(Path(temporary.name) / 'vocab.json')

    def enabled_rule(self):
        self.assistance.change('switch', {'enabled': True, 'automatic': True}, PEOPLE)
        self.assistance.change('add', dict(preferred='Amir', alias='emir', context='Peachy',
            kind='name', person_id='fixture-amir', approved=True, approved_auto=True), PEOPLE)

    def test_wd40_literal_is_retained_without_reconstruction(self):
        for text in ('Use WD-40 on the hinge.', 'Use double u dee forty on the hinge.'):
            result = self.assistance.analyze(text, PEOPLE)
            self.assertEqual(result['input_text'], text)
            self.assertEqual(result['input_sha256'], hashlib.sha256(text.encode()).hexdigest())
            self.assertIsNone(result['corrected_text'])

    def test_wd40_rule_is_unavailable_and_not_silently_claimed(self):
        self.assistance.change('switch', {'enabled': True, 'automatic': True}, PEOPLE)
        with self.assertRaises(ValueError):
            self.assistance.change('add', dict(preferred='WD-40', alias='double u dee forty',
                context='hinge', approved=True, approved_auto=True), PEOPLE)
        self.assertEqual(self.assistance.snapshot(PEOPLE)['entries'], [])
        result = self.assistance.analyze('Use WD-40 on the hinge.', PEOPLE)
        self.assertEqual(result['input_text'], 'Use WD-40 on the hinge.')
        self.assertIsNone(result['corrected_text'])

    def test_amir_requires_approved_context_and_avoids_ambiguity(self):
        self.enabled_rule()
        result = self.assistance.analyze('EMIR joined Peachy.', PEOPLE)
        self.assertEqual(result['input_text'], 'EMIR joined Peachy.')
        self.assertEqual(result['corrected_text'], 'Amir joined Peachy.')
        self.assertIn('not acoustic/identity confidence', result['provenance'])
        for text, people in [('Emir joined yesterday.', PEOPLE),
                             ('Emir took 2 tablets at Peachy.', PEOPLE),
                             ('Emir joined Peachy.', PEOPLE + [{'id':'fixture-emir', 'name':'Emir Noor'}])]:
            self.assertIsNone(self.assistance.analyze(text, people)['corrected_text'])

    def test_raw_caption_and_span_ids_survive_separate_text_suggestion(self):
        state = S7PresentationState(S6DSettings(), dict(session_id='note-event', mode='M2', ownership_mode='timestamped_spans_v3'))
        raw = 'EMIR joined Peachy.'
        state.consume('s6d_text_ready', dict(session_id='note-event', utterance_id='u',
            text=raw, source_start_sec=0.0, source_end_sec=1.0, event_id='asr:1',
            text_revision_id='asr:1', final=True), 1.1)
        ids = list(state.rows['u']['token_ids'])
        self.enabled_rule()
        result = self.assistance.analyze(raw, PEOPLE)
        self.assertEqual(corrected_partition(raw, result['corrected_text'], (0,1)), 'Amir ')
        self.assertEqual(state.rows['u']['text'], raw)
        self.assertEqual(state.rows['u']['token_ids'], ids)
        self.assertTrue(all(word['exact_word_start_sec'] is None for word in state.rows['u']['word_spans']))


if __name__ == '__main__':
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NoteExamples))
    print(output.getvalue())
    receipt = dict(checked_at_utc=datetime.now(timezone.utc).isoformat(), status='PASS' if result.wasSuccessful() else 'FAIL',
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        fixture_kind='SOURCE_TEXT_AND_EVENTS_ONLY', microphone_opened=False, model_inference=False,
        production_code_changed=False, wd40_normalization='DEFERRED_N3_UNSUPPORTED_BY_CURRENT_LETTERS_ONLY_RULES',
        amir='APPROVED_CONTEXTUAL_HEURISTIC_ONLY', output=output.getvalue())
    Path(__file__).with_name('NOTE_EXAMPLE_TESTS.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
