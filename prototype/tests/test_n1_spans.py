"""Source EVENT regressions; no hardware, models or visible UI. See README_N1.md."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vendor'))
from edge_speech_pipeline.research_s6d import S6DSettings
from edge_speech_pipeline.research_s7_presentation import S7PresentationState


class SpanTests(unittest.TestCase):
    def setUp(self):
        self.state = S7PresentationState(S6DSettings(), dict(session_id='event-fixture',mode='M2',ownership_mode='timestamped_spans_v3'))

    def words(self,i,text,key='u',start=0,end=None):
        return self.state.consume('s6d_text_ready',dict(session_id='event-fixture',utterance_id=key,
            event_id=f'asr:{i}',text_revision_id=f'asr:{i}',text=text,source_start_sec=start,
            source_end_sec=float(i) if end is None else end,available_at_sec=i+.1,final=False),i+.1)

    def name(self,i,person,start,end,key='u',target_start=0,target_end=None,revision=None,targets=None):
        p=dict(session_id='event-fixture',utterance_id=key,event_id=f'id:{i}',identity_version=i,
            latest_label_time=i+.2,source_start_sec=start,source_end_sec=end,
            target_source_start_sec=target_start,target_source_end_sec=end if target_end is None else target_end,
            target_text_revision_id=f'asr:{i if revision is None else revision}',
            latest_label=person,latest_known_name=person,latest_known_profile_id=person,
            latest_naming_state='confirmed',replacement_tracker_id=1 if person=='A' else 2,
            evidence_ids=[f'evidence:{i}'])
        if targets is not None:p['target_span_ids']=targets
        return self.state.consume('transcript_label_revision',p,i+.3)

    def owners(self,key='u'):
        return [o['known_profile_id'] if o else None for o in self.state.rows[key]['_token_owners']]

    def test_aba_one_growing_caption_does_not_relabel_prefix(self):
        for i,p in enumerate('ABA',1):
            self.words(i,' '.join(f'word{j}' for j in range(1,i+1)))
            self.name(i,p,i-1,i)
        self.assertEqual(self.owners(),list('ABA'))
        self.assertEqual([w['committed_label'] for w in self.state.rows['u']['word_spans']],list('ABA'))
        self.assertTrue(all(w['exact_word_start_sec'] is None for w in self.state.rows['u']['word_spans']))

    def test_late_explicit_correction_keeps_ids_first_label_and_other_span(self):
        self.words(1,'first');self.name(1,'A',0,1)
        self.words(2,'first second');self.name(2,'B',1,2)
        row=self.state.rows['u'];ids=row['token_ids'][:];segments=[s['segment_id'] for s in row['segments']]
        self.name(3,'B',0,1,target_end=2,revision=2,targets=[ids[0]])
        self.assertEqual(self.owners(),['B','B'])
        self.assertEqual(row['token_ids'],ids)
        self.assertEqual(row['segments'][0]['segment_id'],segments[0])
        self.assertEqual(row['word_spans'][0]['committed_label'],'A')
        self.assertEqual([h['label'] for h in row['word_spans'][0]['speaker_history']],['A','B'])
        self.assertEqual(row['word_spans'][0]['first_shown_label'],'Pending identity')

    def test_short_interruption_and_simultaneous_utterances_remain_independent(self):
        self.words(1,'a',end=1);self.name(1,'A',0,1)
        self.words(2,'a b',end=1.05);self.name(2,'B',1,1.05)
        self.words(3,'a b c',end=2);self.name(3,'A',1.05,2)
        self.words(4,'overlap',key='v',start=.9,end=1.1)
        self.name(4,'B',.9,1.1,key='v',target_start=.9)
        self.assertEqual(self.owners(),list('ABA'));self.assertEqual(self.owners('v'),['B'])

    def test_same_time_revision_does_not_invent_phonetic_span(self):
        self.words(1,'one');self.name(1,'A',0,1)
        self.words(2,'one two',end=1)
        self.name(2,'B',0,1)
        self.assertEqual(self.owners(),['A',None])
        self.assertEqual(self.state.rows['u']['word_spans'][1]['source_start_sec'],1)

    def test_rewrite_retires_changed_suffix_without_resurrecting_owners(self):
        self.words(1,'one two');self.name(1,'A',0,1)
        before=self.state.rows['u']['token_ids'][:]
        self.words(2,'one changed')
        self.assertEqual(self.owners(),['A',None])
        self.assertEqual(self.state.rows['u']['token_ids'][0],before[0])
        self.assertNotEqual(self.state.rows['u']['token_ids'][1],before[1])
        self.assertEqual(self.state.rows['u']['retired_spans_delta'][0]['id'],before[1])
        self.assertEqual(self.state.rows['u']['retired_spans_delta'][0]['committed_label'],'A')

    def test_large_paragraph_exact_partition(self):
        text=' '.join(f'token{i}' for i in range(2000))
        self.words(1,text);self.name(1,'A',0,1)
        self.words(2,text+' interruption');self.name(2,'B',1,2)
        row=self.state.rows['u']
        self.assertEqual(''.join(s['raw_text'] for s in row['segments']),row['text'])
        self.assertEqual(len(set(row['token_ids'])),2001)
        self.assertEqual(self.owners()[-2:],['A','B'])

    def test_explicit_correction_rejects_missing_revision_and_foreign_ids(self):
        self.words(1,'first');self.name(1,'A',0,1)
        self.assertIsNone(self.name(2,'B',0,1,revision=1,targets=['foreign']))
        self.assertEqual(self.owners(),['A'])

    def test_missing_identity_serial_is_rejected(self):
        self.words(1,'first')
        row=self.state.rows['u']
        result=self.state._identity(row,dict(source_start_sec=0,source_end_sec=1,
            target_source_start_sec=0,target_source_end_sec=1,latest_label_time=1.2,
            latest_label='A',latest_naming_state='confirmed',latest_known_profile_id='A'))
        self.assertIsNone(result);self.assertEqual(self.owners(),[None])


if __name__=='__main__':unittest.main()
