"""Changed controller/S7 boundary checks. Run commands are in README.md."""
import unittest
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import patch

from installed_engine import InstalledSession
from profiles import RuntimeSelection
from late_labels import SingleD1LateLabels


class PresentationBoundary(unittest.TestCase):
    def session(self, late=False):
        session=object.__new__(InstalledSession)
        selection=RuntimeSelection('nemotron','redimnet','saved','current_delayed',True,
            speaker_attribution='single_d1_late_labels' if late else 'retained')
        self.writes=[];self.events=[];self.notifications=[]
        session.selection=selection
        session.spool=SimpleNamespace(session_id='persistent-id',processed_samples=160000,
            store=SimpleNamespace(write_caption=lambda *a:self.writes.append(a),write_event=lambda *a:self.events.append(a)))
        session.engine=SimpleNamespace(_s7_trace=SimpleNamespace(record=lambda *a,**k:self.events.append((a,k))))
        session.attribution_writer=SimpleNamespace(write=self.events.append)
        session.rows=OrderedDict();session.first_caption=session.first_speaker=None
        session.notify=self.notifications.append
        session.late_labels=SingleD1LateLabels(selection,'actual-engine-id','persistent-id') if late else None
        return session

    def row(self):
        return dict(session_id='actual-engine-id',utterance_id='utterance-1',
            caption_key='actual-engine-id/utterance-1',text='synthetic caption',display_text='synthetic caption',
            source_start_sec=0.,source_end_sec=1.,label='Pending identity',text_revision_id='revision-1',segments=[])

    def test_pending_is_not_first_speaker(self):
        session=self.session();session._caption(self.row())
        self.assertIsNotNone(session.first_caption);self.assertIsNone(session.first_speaker)
        self.assertTrue(self.writes[-1][6])

    def test_supported_schema_without_voice_available(self):
        session=self.session();row=self.row()
        row.update(label='Speaker 1',segments=[dict(ownership_state='supported_history')])
        session._caption(row)
        self.assertIsNotNone(session.first_speaker);self.assertFalse(self.writes[-1][6])

    def test_same_id_late_revision_and_duplicate(self):
        session=self.session(late=True);row=self.row()
        row['word_spans']=[dict(id='span-1',source_start_sec=0.,source_end_sec=1.,
            first_seen_monotonic_sec=10.,speaker_history=[])]
        with patch('installed_engine.time.perf_counter',return_value=10.):session._caption(row)
        row['word_spans'][0]['speaker_history']=[dict(label='Speaker 1',track_id='track-1',
            event_id='n2-caption:actual-1',identity_version=[1,1],source_evidence_span=[0.,1.])]
        with patch('installed_engine.time.perf_counter',return_value=11.):
            session._caption(row);session._caption(row)
        self.assertEqual(len(self.writes),2)
        self.assertEqual(self.writes[0][1],self.writes[1][1])
        self.assertEqual(self.writes[0][4],self.writes[1][4])
        self.assertEqual(self.writes[-1][5],'Speaker 1')
        self.assertIsNotNone(session.first_speaker)
        self.assertEqual(len(session.rows),1)


if __name__=='__main__':unittest.main()
