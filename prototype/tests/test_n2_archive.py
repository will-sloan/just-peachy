"""N2 window -> real archive regression without models. See app/README_N2.md."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.buffers import MemoryJournal
from app.n2_identity import N2NameMap
from app.n2_pipeline import ActivityTimeline,N2Engine
from app.sessions import SessionStore,records
from edge_speech_pipeline.contracts import PipelineEvent


class N2ArchiveTests(unittest.TestCase):
    def exercise(self,save_audio):
        with tempfile.TemporaryDirectory(prefix='n2-archive-contract-') as directory:
            root=Path(directory)
            store=SessionStore(root,dict(free_floor_mib=0))
            identifier=store.new(audio=save_audio,consent=save_audio)
            archive=store.begin(identifier,dict(pipeline_input_gain=1.,features={'synthetic_fixture':True}))
            self.addCleanup(archive.close)
            audio=np.linspace(-.2,.2,25600,dtype=np.float32)
            journal=MemoryJournal(reserve_sec=2,observer=archive.audio_block)
            journal.append(audio);journal.finish()
            engine=object.__new__(N2Engine)
            engine._n2_lock=threading.RLock();engine._n2_timeline=ActivityTimeline()
            engine._n2_last_query={};engine._n2_embedding_serial=0;engine._n2_admitted_runs=set()
            engine._n2_reported_runs=set();engine._n2_short_run_count=0
            engine._n2_short_run_sec=0.;engine._n2_reported_run_end=-1.
            engine._n2_names={};engine._n2_name_history={};engine.n2_name_map=N2NameMap()
            engine._s7_observed_clock=SimpleNamespace(relative=lambda:2.)
            engine._identity_journal=journal;engine._revise_supported_spans=lambda:None
            emitted=[];queried=[]
            def emit(kind,source,payload):
                emitted.append((kind,payload))
                archive.event(PipelineEvent(kind,source,{**payload,'publication_sequence':len(emitted)}))
            engine._emit=emit
            def embed(samples):
                queried.append(samples.copy())
                vector=np.zeros(192,np.float32);vector[0]=1.
                return vector
            models=SimpleNamespace(embed=embed,last_embed_ms=0.,namespace={'fixture':'no-model'})
            activity=np.zeros((161,8),np.float32)
            activity[10:70,0]=.9;activity[100:,1]=.9
            step=.009999999776482582
            update=SimpleNamespace(frame_start=0,frame_end=161,probabilities=activity,
                seconds_per_frame=step,audio_received_sec=1.6,is_final=True,
                emitted_audio_end_sec=161*step,available_at_monotonic=2.,received_at_monotonic=1.6,
                compute_sec=0.,track_ids=[f'fixture-slot-{i}' for i in range(8)],
                capacity_status='EIGHT_SLOTS_OVERFLOW_UNDETECTABLE')
            try:engine._accept_activity(update,models)
            finally:receipt=store.ended(identifier,archive)
            self.assertIsNone(receipt['archive_error'])
            self.assertFalse(receipt['worker_alive'])
            self.assertEqual(json.loads((archive.path/'epoch.json').read_text())['state'],'CLOSED')
            if save_audio:store.save(identifier)
            windows=list(records(archive.path/'windows.jsonl'))
            self.assertEqual(len(windows),2)
            self.assertEqual([(w['source_start_sample'],w['source_end_sample']) for w in windows],
                             [(1600,9600),(16000,24000)])
            embedding_events=[payload for kind,payload in emitted if kind=='research_embedding']
            self.assertEqual(len(embedding_events),len(queried))
            for index,(window,event,actual) in enumerate(zip(windows,embedding_events,queried)):
                first,last=window['source_start_sample'],window['source_end_sample']
                self.assertEqual(window['left_padding_samples'],0)
                self.assertEqual(window['tensor_shape'],[1,len(actual)])
                self.assertEqual(window['event_id'],event['evidence_event_id'])
                self.assertEqual(window['available_clocks']['available_source_cursor_sec'],1.6)
                self.assertEqual(event['receptive_start_sec'],first/16000)
                self.assertEqual(event['receptive_end_sec'],last/16000)
                self.assertLessEqual(last,len(audio))
                np.testing.assert_array_equal(actual.view('u4'),audio[first:last].view('u4'))
                if save_audio:
                    destination=root/f'window-{index}.npy'
                    store.export_window(identifier,archive.path.name,window['window_id'],destination)
                    np.testing.assert_array_equal(np.load(destination).view('u4'),actual.view('u4'))
            if not save_audio:self.assertFalse((archive.path/'model_input.f32le').exists())

    def test_metadata_only_archive_accepts_actual_N2_embedding_dispatch(self):
        self.exercise(False)

    def test_audio_archive_exports_the_exact_N2_query_without_padding(self):
        self.exercise(True)


if __name__=='__main__':unittest.main(verbosity=2)
