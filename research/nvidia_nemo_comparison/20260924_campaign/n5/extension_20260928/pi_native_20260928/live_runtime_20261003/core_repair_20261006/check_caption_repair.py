"""Offline structural caption regressions; never prints private transcript words.

See README_CAPTION_REPAIR.md. No microphone, inference, network or service use.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zipfile

sys.path.append(str(Path(__file__).resolve().parent.parent))
from caption_paragraphs import paragraph_rows
from classic_frontend import ClassicController, caption_row


def span(key, start, end, text, *, parent='utterance:1', token_range=(0, 1),
         track='track:1', label='Unknown', final=True, state='supported_history', profile=None):
    return dict(id=key, caption_key=parent, utterance_id=parent, session_id='fixture',
                source_start_sec=start, source_end_sec=end, token_range=list(token_range),
                raw_asr_text=text, provisional_display_text=text,
                final_punctuated_display_text=text if final else None, final=final,
                track_id=track, label=label, profile_id=profile,
                ownership_state=state, identity_status='supported' if state == 'supported_history' else 'collecting',
                selected=False, visible=True, speaker_revision=1)


class ParagraphTests(unittest.TestCase):
    def test_real_repetition_preserved_without_source_mutation(self):
        rows = [span('a', 0, 1, 'Very,', token_range=(0, 1)),
                span('b', 1, 2, 'very good.', token_range=(1, 3))]
        original = copy.deepcopy(rows)
        rows[0]['provisional_display_text'] = rows[0]['final_punctuated_display_text'] = 'Very, '
        original = copy.deepcopy(rows)
        paragraphs = paragraph_rows(rows, 'open_with_names')
        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(paragraphs[0]['raw_asr_text'], 'Very, very good.')
        self.assertEqual(paragraphs[0]['provisional_display_text'],'Very, very good.')
        self.assertEqual(rows, original)
        self.assertEqual([part['id'] for part in paragraphs[0]['_caption_parts']], ['a', 'b'])

    def test_partial_word_revision_edits_same_anchor(self):
        partial = span('old-child', 0, .8, 'In particul', token_range=(0, 2), final=False,
                       track=None, state='pending')
        final = dict(partial, id='new-child', raw_asr_text='In particular',
                     provisional_display_text='In particular', final=True,
                     final_punctuated_display_text='In particular.')
        before = paragraph_rows([partial], 'open_with_names')[0]
        after = paragraph_rows([final], 'open_with_names')[0]
        self.assertEqual(before['id'], after['id'])
        self.assertEqual(after['provisional_display_text'], 'In particular.')
        self.assertEqual(len(after['_caption_parts']), 1)
        self.assertNotIn('old-child', [part['id'] for part in after['_caption_parts']])
        self.assertEqual(paragraph_rows([final], 'open_with_names'), paragraph_rows([final], 'open_with_names'))

    def test_supported_track_and_unattributed_presentation_are_distinct(self):
        rows = [span('a', 0, 1, 'A.', parent='one'), span('b', 1, 2, 'B.', parent='two')]
        self.assertEqual(len(paragraph_rows(rows, 'open_with_names')), 1)
        for row in rows:
            row['identity_status'] = 'unavailable'
        self.assertEqual(len(paragraph_rows(rows, 'open_with_names')), 1)
        rows[1]['track_id'] = 'track:2'
        self.assertEqual(len(paragraph_rows(rows, 'open_with_names')), 2)
        rows[1]['track_id'] = rows[0]['track_id'] = None
        result = paragraph_rows(rows, 'open_with_names')
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['paragraph_identity'],'unverified_unattributed')
        self.assertFalse(result[0]['paragraph_claims_shared_speaker'])

    def test_equal_assumed_name_is_not_physical_continuity(self):
        rows = [span('a', 0, 1, 'A.', parent='one', track=None, label='Fixture name'),
                span('b', 1, 2, 'B.', parent='two', track=None, label='Fixture name')]
        for row in rows:
            row.update(closed_group_display=True, display_profile_id='assumption')
        self.assertEqual(len(paragraph_rows(rows, 'selected_closed')), 2)

    def test_gap_track_and_label_boundaries(self):
        a = span('a', 0, 1, 'First.', parent='one')
        b = span('b', 3.5, 4, 'Second.', parent='two')
        self.assertEqual(len(paragraph_rows([a, b], 'open_with_names')), 1)
        b['source_start_sec'] = 3.5001
        self.assertEqual(len(paragraph_rows([a, b], 'open_with_names')), 2)
        b['source_start_sec'] = 1
        b['label'], b['profile_id'] = 'Fixture name', 'fixture-person'
        self.assertEqual(len(paragraph_rows([a, b], 'open_with_names')), 2)
        self.assertEqual(len(paragraph_rows([a, b], 'caption_only')), 1)

    def test_pending_tail_does_not_restart_paragraph_identity(self):
        a = span('a', 0, 1, 'One', token_range=(0, 1), track=None, final=False, state='pending')
        b = span('b', 0, 1.5, 'two', token_range=(1, 2), track=None, final=False, state='pending')
        rows = paragraph_rows([a, b], 'open_with_names')
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['final'])
        b['caption_key'] = 'different-parent'
        result = paragraph_rows([a,b],'open_with_names')
        self.assertEqual(len(result),1)
        self.assertFalse(result[0]['paragraph_claims_shared_speaker'])
        b['track_id'] = 'different-track'
        self.assertEqual(len(paragraph_rows([a,b],'open_with_names')),2)

    def test_soft_bound_uses_existing_spans_and_retains_intervals(self):
        rows = [span('a', 0, 1, 'A long existing span.', token_range=(0, 4)),
                span('b', 1, 2, 'Second.', token_range=(4, 5))]
        paragraphs = paragraph_rows(rows, 'open_with_names', max_chars=10)
        self.assertEqual(len(paragraphs), 2)
        self.assertEqual(paragraphs[0]['source_end_sec'], 1)
        self.assertEqual(paragraphs[0]['_caption_parts'][0], rows[0])

    def test_final_prefix_keeps_punctuation_while_tail_is_partial(self):
        rows = [span('a', 0, 1, 'First.', parent='one'),
                span('b', 1, 2, 'next', parent='two', final=False)]
        paragraph = paragraph_rows(rows, 'open_with_names')[0]
        self.assertFalse(paragraph['final'])
        self.assertEqual(paragraph['provisional_display_text'], 'First. next')
        self.assertIsNone(paragraph['final_punctuated_display_text'])

    def test_actual_bpe_continuation_joins_without_midword_capital(self):
        a = dict(span('a',0,20.3,'IN PARTICUL',parent='one'),
                 utterance_group_id='spoken:0',utterance_final=False,leading_text_joiner=' ')
        b = dict(span('b',20.3,21,'AR',parent='two',final=False),
                 utterance_group_id='spoken:0',utterance_final=False,leading_text_joiner='')
        result = paragraph_rows([a,b],'open_with_names')[0]
        self.assertEqual(result['raw_asr_text'],'IN PARTICULAR')
        self.assertTrue(result['_needs_group_casing'])
        self.assertIsNone(result['provisional_display_text'])
        self.assertFalse(result['final'])
        self.assertEqual([p['source_end_sec'] for p in result['_caption_parts']],[20.3,21])
        b.update(track_id='different',label='Other',profile_id='other')
        result = paragraph_rows([a,b],'open_with_names')[0]
        self.assertEqual(result['label'],'Unknown')
        self.assertIsNone(result['profile_id'])

    def test_spoken_punctuation_maps_original_pieces_without_joiner_space(self):
        a = dict(span('a',0,20.3,'In particul',parent='one'),
                 utterance_group_id='spoken:0',utterance_final=False,leading_text_joiner=' ',spoken_punctuation_ready=True)
        b = dict(span('b',20.3,25,'ar.',parent='two'),
                 utterance_group_id='spoken:0',utterance_final=True,leading_text_joiner='',spoken_punctuation_ready=True)
        result = paragraph_rows([a,b],'open_with_names')[0]
        self.assertEqual(result['final_punctuated_display_text'],'In particular.')
        self.assertFalse(result['_needs_group_casing'])
        self.assertTrue(result['final'])

    def test_coarse_span_start_never_shuffles_native_token_order(self):
        rows = [span('a',0,1.1,'One',token_range=(0,1),track=None),
                span('b',1.1,1.4,'two',token_range=(1,2),track=None),
                span('c',0,4,'three',token_range=(2,3),track=None),
                span('d',20.3,22,'Next.',parent='utterance:2',token_range=(0,1),track=None)]
        original = copy.deepcopy(rows)
        shuffled = sorted(rows,key=lambda row:row['source_start_sec'])
        result = paragraph_rows(shuffled,'open_with_names')
        self.assertEqual(result[0]['raw_asr_text'],'One two three')
        self.assertEqual([part['id'] for part in result[0]['_caption_parts']],['a','b','c'])
        self.assertEqual(rows,original)


def stored(index, *, revision=1, text=None):
    part = span('child:'+str(index), index, index+1, text or 'Fixture '+str(index)+'.', parent='parent:'+str(index))
    return dict(caption_id=part['id'], start_sample=index*16000, end_sample=(index+1)*16000,
                projection_parent=part['caption_key'],
                text=part['raw_asr_text'], speaker='Unknown', provisional=False, revision=revision,
                provenance=dict(ui_projection=part, asr_final=True))


class FakeStore:
    def __init__(self):
        self.rows = [stored(index) for index in range(100)]
        self.latest_reads = 0
        self.truncated = False

    def latest_captions(self, session_id, limit, after_revision):
        self.latest_reads += 1
        return dict(items=self.rows[-limit:], revision_cursor=1, changed=after_revision != 1)

    def caption_page(self, session_id, limit, before=None):
        end = len(self.rows) if before is None else before
        start = max(0, end-limit)
        return dict(items=self.rows[start:end], next_cursor=start if start else None)

    def caption_parents(self, session_id, parent_keys, limit):
        items = [row for row in self.rows if (row.get('projection_parent') or row['caption_id']) in parent_keys]
        return dict(items=items[:limit], truncated=self.truncated or len(items)>limit)


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = [0.]
        self.store = FakeStore()
        manager = SimpleNamespace(data_root=Path(self.temp.name), store=self.store)
        config = dict(defaults=dict(caption_size='Compact'), caption_sizes_px={'Compact': 19},
                      themes={'Dark': {}}, display_smoothing_ms=[0, 150, 300])
        self.controller = ClassicController(manager, SimpleNamespace(embedding='redimnet'), config, clock=lambda:self.now[0])
        self.controller.current_id = 'fixture'
        self.controller._read_captions()

    def test_prompt_read_poll_is_100_ms(self):
        self.now[0] = .099
        self.controller._read_captions()
        self.assertEqual(self.store.latest_reads, 1)
        self.now[0] = .101
        self.controller._read_captions()
        self.assertEqual(self.store.latest_reads, 2)

    def test_manual_window_revises_labels_without_live_rotation(self):
        self.controller.set_caption_follow(False)
        first = self.controller.rows[0]['id']
        self.store.rows[60]['provenance']['ui_projection']['label'] = 'Fixture supported name'
        self.store.rows[60]['revision'] = 2
        self.store.rows.append(stored(100))
        self.now[0] = 1
        self.controller._read_captions()
        self.assertEqual(self.controller.rows[0]['id'], first)
        self.assertEqual(self.controller.rows[0]['label'], 'Fixture supported name')
        self.assertNotIn('child:100', [row['id'] for row in self.controller.rows])
        self.controller.set_caption_follow(True)
        self.assertEqual(self.controller.rows[-1]['id'], 'child:100')

    def test_paging_bounds_memory_and_reaches_oldest_source(self):
        self.controller.set_caption_follow(False)
        self.assertTrue(self.controller.captions_older())
        self.assertEqual(len(self.controller.rows), 80)
        self.assertTrue(self.controller.captions_older())
        self.assertLessEqual(len(self.controller.rows), 80)
        self.assertEqual(self.controller.rows[0]['id'], 'child:0')
        self.assertFalse(self.controller.captions_older())

    def test_overflow_retains_reading_anchor(self):
        self.controller.set_caption_follow(False)
        before = copy.deepcopy(self.controller.rows)
        self.store.truncated = True
        self.now[0] = 1
        self.controller._read_captions()
        self.assertEqual(self.controller.rows, before)

    def test_legacy_database_parent_refresh_keeps_window(self):
        for row in self.store.rows:
            row['projection_parent'] = None
        self.controller.set_caption_follow(False)
        before = [row['id'] for row in self.controller.rows]
        self.now[0] = 1
        self.controller._read_captions()
        self.assertEqual([row['id'] for row in self.controller.rows], before)

    def test_older_page_keeps_existing_paragraph_anchor(self):
        self.controller.set_caption_follow(False)
        first = self.controller.rows[0]
        first_anchor = paragraph_rows(self.controller.rows, 'open_with_names')[0]['id']
        self.controller.captions_older()
        paragraphs = paragraph_rows(self.controller.rows, 'open_with_names')
        self.assertIn(first_anchor, [row['id'] for row in paragraphs])
        self.assertTrue(next(row for row in self.controller.rows if row['id'] == first['id'])['_paragraph_break'])


def audit_export(path):
    """Read a local export in memory; report structural counts without text."""
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith('/captions.jsonl')]
        if len(members) != 1:
            raise ValueError('Exactly one recording caption index is required')
        if archive.getinfo(members[0]).file_size > 8*1024*1024:
            raise ValueError('Caption index exceeds this bounded audit limit')
        rows = [json.loads(line) for line in archive.read(members[0]).decode('utf-8').splitlines() if line]
    parents = defaultdict(list)
    for row in rows:
        parents[row['provenance']['supersedes_parent']].append(row)
    def serial(row):
        return int(row['provenance']['text_revision'].rsplit(':', 1)[1])
    current = []
    coverage = 0
    for parts in parents.values():
        revision = max(serial(part) for part in parts)
        parts = [part for part in parts if serial(part) == revision]
        parts.sort(key=lambda part: part['provenance']['ui_projection']['token_range'][0])
        occupied = []
        for part in parts:
            begin, end = part['provenance']['ui_projection']['token_range']
            occupied.extend(range(begin, end))
        if len(occupied) != len(set(occupied)):
            raise AssertionError('Latest-revision source token positions overlap')
        coverage += len(occupied)
        current.extend(parts)
    current.sort(key=lambda part:(part['start_sample'],part['provenance']['supersedes_parent'],part['provenance']['ui_projection']['token_range'][0]))
    projected = [caption_row(part, 'open_with_names') for part in current]
    paragraphs = paragraph_rows(projected, 'open_with_names')
    positions = {}
    ordered_parts = [part for paragraph in paragraphs for part in paragraph['_caption_parts']]
    for part in ordered_parts:
        key = part.get('caption_key') or part['utterance_id']
        begin,end = part['token_range']
        if begin < positions.get(key,0):
            raise AssertionError('Display paragraphs shuffle native source token order')
        positions[key] = end
    indexed_words = sum(len(part['text'].split()) for part in rows)
    current_words = sum(len(part['text'].split()) for part in current)
    paragraph_words = sum(len(part['raw_asr_text'].split()) for part in paragraphs)
    if paragraph_words != current_words:
        raise AssertionError('Paragraph view changed source word instances')
    return dict(indexed_rows=len(rows), current_rows=len(current), obsolete_rows=len(rows)-len(current),
                indexed_word_instances=indexed_words, current_word_instances=current_words,
                source_token_coverage=coverage, paragraph_word_instances=paragraph_words,
                projected_paragraphs=len(paragraphs),
                short_current_rows=sum(1<=len(part['text'].split())<=3 for part in current),
                timing_kinds=sorted({part.get('timing_kind','unspecified') for part in projected}),
                supported_track_rows=sum(bool(p.get('track_id')) and p.get('ownership_state')=='supported_history' for p in projected),
                identity_unavailable_rows=sum(p.get('identity_status')=='unavailable' for p in projected),
                native_parent_token_order_verified=True,
                unattributed_presentation_paragraphs=sum(p.get('paragraph_identity')=='unverified_unattributed' for p in paragraphs),
                assurance='Structural projection only; no physical display latency, human readability or ASR accuracy measurement')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-zip', type=Path, help='Optional local selected-recording.zip; no extraction or uploads')
    parser.add_argument('--output', type=Path, help='Optional structural JSON receipt; never transcript text')
    args = parser.parse_args()
    tests = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(ParagraphTests),
                               unittest.defaultTestLoader.loadTestsFromTestCase(HistoryTests)])
    result = unittest.TextTestRunner(verbosity=1).run(tests)
    report = dict(schema='just-peachy.caption-repair-check.v1', tests_run=result.testsRun,
                  failures=len(result.failures), errors=len(result.errors), passed=result.wasSuccessful())
    if args.export_zip:
        report['export'] = audit_export(args.export_zip)
    print(json.dumps(report, sort_keys=True, indent=2))
    if args.output:
        args.output.write_text(json.dumps(report, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
