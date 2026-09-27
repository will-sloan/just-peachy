"""Model-free derivative regressions; see README_D1_ANONYMOUS_V1.md."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(os.environ['JP_D1_ANONYMOUS_SOURCE']).resolve()
sys.path[:0] = [str(ROOT), str(ROOT/'vendor')]
import numpy as np
from app.n2_pipeline import N2Engine, ActivityTimeline
from prepare_d1_anonymous_v1 import patch_engine


class AnonymousTests(unittest.TestCase):
    def test_model_acquisition_keeps_named_baseline_and_research_paths(self):
        for diarizer, mode, observer, caption_only, expected in [
            ('D1','anonymous_conversation',None,False,True),
            ('D1','open_with_names',None,False,False),
            ('D1','selected_closed',None,False,False),
            ('D0','anonymous_conversation',None,False,False),
            ('D1','anonymous_conversation',object(),False,False),
            ('D1','caption_only',None,True,True),
        ]:
            with self.subTest(diarizer=diarizer,mode=mode,observer=bool(observer)):
                e=object.__new__(N2Engine)
                e.n2_diarization=diarizer; e.mode=mode; e.n2_observer_factory=observer
                e._telemetry={}; e.config=object()
                e.resident=SimpleNamespace(acquire=Mock(return_value=(None,'ASR stream')))
                self.assertEqual(e._prepare_native_models(caption_only),(None,'ASR stream'))
                e.resident.acquire.assert_called_once_with(e.config,expected)

    def test_no_embeddings_preserves_all_slots_overlap_short_turns_and_captions(self):
        e=object.__new__(N2Engine)
        e.n2_diarization='D1'; e.mode='anonymous_conversation'; e.n2_observer_factory=None
        e._n2_lock=threading.RLock();e._n2_timeline=ActivityTimeline()
        e._n2_last_query={};e._n2_embedding_serial=0;e._n2_admitted_runs=set()
        e._n2_reported_runs=set();e._n2_short_run_count=0;e._n2_short_run_sec=0.;e._n2_reported_run_end=-1.
        e._n2_names={};e._n2_name_history={};e._n2_span_signatures={};e._n2_revision=0;e._n2_associations={}
        e._session_dir=Path('synthetic-session')
        e._s7_observed_clock=SimpleNamespace(relative=lambda:3.)
        e._identity_journal=SimpleNamespace(read=Mock(side_effect=AssertionError('No identity audio reread')))
        rows=[dict(utterance_id='u',text_revision_id='r',source_start_sec=0.,source_end_sec=1.6,
                   raw_text='kept words',word_spans=[dict(id='single',source_start_sec=0.,source_end_sec=.6),
                   dict(id='overlap',source_start_sec=.6,source_end_sec=.8),
                   dict(id='short',source_start_sec=.8,source_end_sec=1.)])]
        original=deepcopy(rows);e._s6d_presentation=SimpleNamespace(snapshot_rows=lambda:rows)
        events=[];e._emit=lambda typ,end,payload:events.append((typ,payload))
        frames=np.zeros((160,8),np.float32);frames[:60,0]=.9;frames[60:80,:2]=.9
        frames[80:100,1]=.9
        for slot in range(2,8):frames[100+(slot-2)*10:110+(slot-2)*10,slot]=.9
        update=SimpleNamespace(frame_start=0,frame_end=160,probabilities=frames,seconds_per_frame=.01,
              audio_received_sec=1.6,available_at_monotonic=102.,received_at_monotonic=100.,
              compute_sec=.01,is_final=True,emitted_audio_end_sec=1.6,
              track_ids=[f'track-{i}' for i in range(8)],capacity_status='AVAILABLE')
        e._accept_activity(update,None)
        self.assertEqual(e._n2_embedding_serial,0)
        e._identity_journal.read.assert_not_called()
        self.assertEqual(e._n2_timeline.seen_slots,set(range(8)))
        self.assertTrue(e._n2_timeline.associate(.6,.8)['overlap'])
        labels={p['target_span_ids'][0]:p['latest_label'] for t,p in events if t=='transcript_label_revision'}
        self.assertEqual(labels,dict(single='Speaker 1',overlap='Unknown',short='Speaker 2'))
        self.assertEqual(rows,original)
        self.assertFalse(any(t in ('research_embedding','speaker_decision') for t,p in events))
        coverage=[p for t,p in events if t=='n2_exclusive_run_coverage']
        self.assertTrue(coverage)
        self.assertTrue(all(p['unavailable_reason']=='EMBEDDING_DISABLED_ANONYMOUS_MODE' for p in coverage))

    def test_patch_refuses_reapplication(self):
        with self.assertRaises(ValueError):patch_engine((ROOT/'app/n2_pipeline.py').read_bytes())

    def test_patch_refuses_unrecognized_source(self):
        with self.assertRaises(ValueError):patch_engine(b'pass\n')


if __name__=='__main__':unittest.main()
