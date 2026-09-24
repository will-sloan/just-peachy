"""Synthetic archival/failure/isolation tests. See README_SESSIONS.md."""
from pathlib import Path
from types import SimpleNamespace
import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch,Mock
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.sessions import SessionStore,EpochArchive,records
from app.buffers import MemoryJournal
from app.session_playback import SessionPlayback
from app.controller import Controller
from edge_speech_pipeline.contracts import PipelineEvent


def caption(text='RAW WORDS',key='source/utterance1'):
    return PipelineEvent('s6d_display',.02,dict(caption_key=key,utterance_id='utterance1',text=text,
        display_text=text.capitalize(),final=True,source_start_sec=0.,source_end_sec=.02,segments=[]))


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=SessionStore(self.root,dict(free_floor_mib=0));self.writers=[]
        self.addCleanup(self.close_all)
    def close_all(self):
        for a in self.writers:a.close()
    def begin(self,audio=True,**options):
        ident=self.store.new(audio=audio,consent=audio);a=self.store.begin(ident,dict(pipeline_input_gain=1.,features={'fixture':True}),**options)
        self.writers.append(a);return ident,a
    def finish(self,ident,a):return self.store.ended(ident,a)

    def test_exact_float_master_matches_shared_model_journal_without_second_gain(self):
        ident,a=self.begin();j=MemoryJournal(observer=a.audio_block)
        samples=np.array([-.9999999,.10000001,1.2345,0.,-1e-8]*64,dtype=np.float32)
        j.append(samples);a.event(caption());self.finish(ident,a)
        saved=np.fromfile(a.path/'model_input.f32le',dtype='<f4')
        np.testing.assert_array_equal(saved.view('u4'),j.read(0,320).view('u4'))
        self.assertEqual(saved.tobytes(),samples.tobytes());self.assertIsNone(a.error)
        self.assertEqual(self.store.rows(ident)[0]['source_end_sample'],320)

    def test_text_only_revision_index_raw_is_immutable_and_save_restart(self):
        ident,a=self.begin(False);one=caption('FIRST RAW');two=caption('REVISED RAW')
        a.event(one);a.event(two);self.finish(ident,a);self.store.save(ident)
        restarted=SessionStore(self.root,dict(free_floor_mib=0));row=restarted.rows(ident)[0]
        self.assertEqual(row['text'],'REVISED RAW');self.assertEqual(one.payload['text'],'FIRST RAW')
        self.assertEqual([r['payload']['text'] for r in records(a.path/'events.jsonl')],['FIRST RAW','REVISED RAW'])
        self.assertFalse((a.path/'model_input.f32le').exists());self.assertTrue(restarted.metadata(ident)['pinned'])
        with self.assertRaises(ValueError):restarted.audio_slice(ident,a.path.name,0,320)

    def test_window_export_exact_slice_plus_segmentation_padding_only(self):
        ident,a=self.begin();x=np.linspace(-.2,.2,16000,dtype=np.float32);a.audio_block(0,x)
        a.event(PipelineEvent('research_segmentation',1.,dict(receptive_start_sec=0.,receptive_end_sec=1.,left_padding_sec=9.,publication_sequence=7)))
        a.event(PipelineEvent('research_embedding',1.,dict(receptive_start_sec=.5,receptive_end_sec=1.,publication_sequence=8)))
        self.finish(ident,a);self.store.save(ident)
        path=self.root/'window.npy';self.store.export_window(ident,a.path.name,'w00000001',path)
        np.testing.assert_array_equal(np.load(path),np.pad(x,(144000,0)))
        self.store.export_window(ident,a.path.name,'w00000002',self.root/'embedding.npy')
        np.testing.assert_array_equal(np.load(self.root/'embedding.npy'),x[8000:])
        with self.assertRaises(ValueError):self.store.audio_slice(ident,a.path.name,0,16001)

    def test_saved_formatting_is_source_backed_and_survives_index_recovery(self):
        ident,a=self.begin(False);row=caption('HELLO AMIRI');row.payload['text_revision_id']='r1'
        a.event(row);a.formatted(row.payload,['Amiri']);self.finish(ident,a)
        before=self.store.rows(ident)[0]
        self.assertEqual(before['text'],'HELLO AMIRI')
        self.assertEqual(before['archived_provisional_display_text'],'Hello Amiri')
        (a.path/'captions.sqlite').unlink()
        self.assertEqual(self.store.rows(ident)[0],before)

    def test_slow_writer_exhaustion_is_visible_and_does_not_stop_model_journal(self):
        self.store.policy.update(queue_items=2,queue_bytes=3000)
        ident,a=self.begin(delay_once=.2);j=MemoryJournal(observer=a.audio_block)
        began=time.perf_counter()
        for _ in range(30):j.append(np.ones(320,np.float32)*.1234567)
        self.assertLess(time.perf_counter()-began,.15);self.assertEqual(j.committed_samples,9600)
        self.finish(ident,a);self.assertIsNotNone(a.error);self.assertIn('QUEUE',a.error)
        self.assertLessEqual(a.max_pending_bytes,3000);self.assertLess(a.written_samples,j.committed_samples)
        self.assertEqual(json.loads((a.path/'epoch.json').read_text())['state'],'PARTIAL')

    def test_full_disk_does_not_turn_recording_loss_into_live_gap(self):
        ident,a=self.begin();j=MemoryJournal(observer=a.audio_block)
        with patch.object(a,'_check_space',side_effect=OSError('fixture disk full')):
            j.append(np.ones(320,np.float32));a.queue.join();a.close()
        self.assertIn('disk full',a.error);self.assertIsNone(j.fatal_error)
        np.testing.assert_array_equal(j.read(0,320),np.ones(320,np.float32))

    def test_recovery_preserves_torn_audio_and_ignores_unfinished_event_tail(self):
        ident,a=self.begin();a.audio_block(0,np.ones(320,np.float32));a.event(caption());self.finish(ident,a)
        p=a.path/'epoch.json';m=json.loads(p.read_text());m.update(state='OPEN',closed=False);p.write_text(json.dumps(m))
        with (a.path/'events.jsonl').open('ab') as f:f.write(b'{"torn":')
        with (a.path/'model_input.f32le').open('ab') as f:f.write(b'xx')
        restarted=SessionStore(self.root,dict(free_floor_mib=0));meta=json.loads(p.read_text())
        self.assertEqual(meta['state'],'RECOVERED_PARTIAL');self.assertEqual(meta['trailing_audio_bytes'],2)
        self.assertEqual(len(restarted.rows(ident)),1)
        self.assertEqual(restarted.audio_slice(ident,a.path.name,0,320).size,320)

    def test_actual_child_process_interruption_is_recovered_as_partial(self):
        code="""import os,sys,numpy as np
from pathlib import Path
from app.sessions import SessionStore
from edge_speech_pipeline.contracts import PipelineEvent
s=SessionStore(Path(sys.argv[1]),dict(free_floor_mib=0));i=s.new(audio=True,consent=True)
a=s.begin(i,{});a.audio_block(0,np.arange(320,dtype=np.float32)/1000)
a.event(PipelineEvent('s6d_display',.02,dict(caption_key='crash/one',utterance_id='one',text='RECOVER ME',source_start_sec=0,source_end_sec=.02)))
a.queue.join()
os._exit(19)
"""
        import os
        environment=dict(os.environ,PYTHONPATH=str(ROOT)+os.pathsep+str(ROOT/'vendor'))
        run=subprocess.run([sys.executable,'-B','-c',code,str(self.root)],env=environment,capture_output=True,timeout=10)
        self.assertEqual(run.returncode,19,run.stderr.decode(errors='replace'))
        recovered=SessionStore(self.root,dict(free_floor_mib=0));m=recovered.list()[0];epoch=m['epochs'][0]
        self.assertTrue(m['issues']);self.assertEqual(recovered.rows(m['id'])[0]['text'],'RECOVER ME')
        np.testing.assert_array_equal(recovered.audio_slice(m['id'],epoch,0,320),np.arange(320,dtype=np.float32)/1000)

    def test_quota_preserves_saved_session_and_deletion_never_touches_people(self):
        people=self.root/'people';people.mkdir();(people/'voice.bin').write_bytes(b'preserve')
        ident,a=self.begin(False);a.event(caption());self.finish(ident,a);self.store.save(ident)
        self.store.policy['draft_limit']=1
        draft=self.store.new();new=self.store.new()
        self.assertFalse(self.store.folder(draft).exists());self.assertTrue(self.store.folder(ident).exists())
        with self.assertRaises(ValueError):self.store.delete(ident)
        with self.assertRaises(ValueError):self.store.delete('../people',True)
        self.store.delete(ident,True);self.assertEqual((people/'voice.bin').read_bytes(),b'preserve')

    def test_export_requires_consent_and_text_omits_audio_vectors_roster(self):
        ident,a=self.begin();a.audio_block(0,np.ones(320,np.float32));a.event(caption());self.finish(ident,a);self.store.save(ident)
        self.store.rename(ident,'Renamed');self.store.annotate(ident,'A missed word',row_id='source/utterance1')
        self.store.annotate(ident,'',row_id='source/utterance1',correction='My correction')
        with self.assertRaises(ValueError):self.store.export(ident,self.root/'deny.zip')
        out=self.root/'text.zip';self.store.export(ident,out,consent=True)
        with zipfile.ZipFile(out) as z:
            self.assertEqual(set(z.namelist()),{'transcript.jsonl','user_annotations.json','EXPORT_NOTICE.txt'})
            self.assertIn(b'RAW WORDS',z.read('transcript.jsonl'));self.assertIn(b'My correction',z.read('user_annotations.json'))
        self.assertEqual(self.store.rows(ident)[0]['text'],'RAW WORDS')
        self.store.export(ident,self.root/'full.zip',consent=True,include_audio=True)
        with zipfile.ZipFile(self.root/'full.zip') as z:self.assertTrue(any(n.endswith('model_input.f32le') for n in z.namelist()))

    def test_source_clock_and_resource_indices_join_without_acoustic_claim(self):
        ident,a=self.begin(False);origin=time.perf_counter();a.event(PipelineEvent('source_started',0,{'source_epoch_monotonic_sec':origin}))
        a.audio_block(0,np.ones(320,np.float32));a.event(caption());self.finish(ident,a)
        resource=list(records(a.path/'resources.jsonl'))
        self.assertTrue(resource);self.assertIn('cpu_total_sec',resource[0]);self.assertIn('process_rss_bytes',resource[0])
        self.assertEqual(resource[0]['archive_epoch_id'],a.path.name)
        self.assertEqual(json.loads((a.path/'epoch.json').read_text())['source_origin_monotonic_sec'],origin)


class FakeBackend:
    def __init__(self):self.calls=[];self.audio=[];self.default='UNCHANGED'
    def query_devices(self,index,kind):return {'name':'Explicit fixture headphones','hostapi':3}
    def query_hostapis(self,index):return {'name':'Fixture API'}
    def check_output_settings(self,**kw):self.calls.append(('check',kw))
    def OutputStream(self,**kw):
        self.calls.append(('output',kw));owner=self
        class Stream:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def write(self,x):owner.audio.append(x.copy());return False
        return Stream()


class PlaybackTests(unittest.TestCase):
    def test_explicit_device_only_and_samples_unmodified(self):
        backend=FakeBackend();x=np.linspace(-.5,.5,2200,dtype=np.float32)
        playback=SessionPlayback(x,dict(index=17,name='Explicit fixture headphones',hostapi='Fixture API'),backend=backend)
        playback.thread.join(2);playback.stop();self.assertIsNone(playback.error)
        np.testing.assert_array_equal(np.concatenate(backend.audio).ravel(),x)
        self.assertEqual(backend.calls[-1][1]['device'],17);self.assertEqual(backend.default,'UNCHANGED')
    def test_changed_device_is_rejected_without_fallback(self):
        with self.assertRaises(ValueError):SessionPlayback(np.ones(320,np.float32),dict(index=17,name='wrong',hostapi='Fixture API'),backend=FakeBackend())


class SessionControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        with patch.object(Controller,'_observe_output'):
            self.c=Controller(Path(self.temp.name)/'data',Path(self.temp.name)/'models-not-loaded')
        self.addCleanup(self.close)
    def close(self):
        with patch.object(Controller,'_observe_output'):
            self.c.close();self.c.commands.join();self.c.worker.join(3)
    def test_new_retains_draft_and_does_not_reload_models(self):
        c=self.c;c._do_session_action('new',{'audio':False});first=c.conversation_id
        c.rows['old']={'text':'unsaved native words'}
        c._do_session_action('new',{'audio':True,'consent':True})
        self.assertNotEqual(c.conversation_id,first);self.assertTrue(c.session_store.folder(first).exists())
        self.assertFalse(c.rows);self.assertEqual(c.models.asr_loads,0);self.assertEqual(c.models.speaker_loads,0)
        with self.assertRaises(ValueError):c._do_session_action('new',{'audio':True})
    def test_capture_fully_stops_before_playback_and_start_stops_player(self):
        c=self.c;c._do_session_action('new',{'audio':True,'consent':True});identifier=c.conversation_id
        a=c.session_store.begin(identifier,{});a.audio_block(0,np.ones(320,np.float32));c.session_store.ended(identifier,a)
        c.chosen_output=dict(index=17,name='Explicit fixture headphones',hostapi='Fixture API')
        calls=[]
        def stop():calls.append('capture released');c.engine=None
        def player(samples,device):calls.append('output opened');return SimpleNamespace(stop=lambda:calls.append('output stopped'))
        with patch.object(c,'_stop_session',side_effect=stop),patch('app.session_playback.SessionPlayback',side_effect=player):
            c._do_session_action('play',dict(identifier=identifier,epoch=a.path.name,start=0,end=320))
            c._stop_playback()
        self.assertEqual(calls,['capture released','output opened','output stopped'])
    def test_enrollment_prevents_playback(self):
        c=self.c;c.enrollment={'state':'RECORDING'}
        with self.assertRaises(ValueError):c._do_session_action('play',{})
        c.enrollment={'state':'IDLE'}


if __name__=='__main__':unittest.main()
