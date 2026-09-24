"""Synthetic touch session controls; no hardware/models. See README_SESSIONS.md."""
import tkinter as tk
import unittest
from prototype.app.ui import PrototypeUI,prepare_dpi_awareness
from prototype.tests.test_ui import StubController


class SessionStub(StubController):
    def __init__(self):
        super().__init__();self.data['sessions']=dict(current_id='a'*32,opened_id=None,library=[
            dict(id='a'*32,title='Synthetic test conversation',state='DRAFT',pinned=False,audio_requested=True,size_bytes=1280,issues=[])],
            usage=dict(path='C:/synthetic-data/conversations',bytes=1280,quota_bytes=2048*1024**2,free_bytes=8*1024**3),
            outputs=[],selected_output=None,caption_links=[])
    def session_action(self,action,**values):self._record('session_action',action,**values)


class SessionUITests(unittest.TestCase):
    def setUp(self):
        prepare_dpi_awareness();self.root=tk.Tk();self.c=SessionStub();self.ui=PrototypeUI(self.root,self.c);self.root.update()
    def tearDown(self):self.ui.close();self.ui.poll()
    def test_audio_creation_and_delete_need_explicit_touch_confirmation(self):
        self.ui.show_sessions();self.ui.actions['new_audio'].invoke()
        self.assertEqual(self.c.calls,[])
        self.ui.actions['confirm'].invoke()
        self.assertEqual(self.c.calls[-1],('session_action',('new',),dict(audio=True,consent=True)))
        self.ui.show_session('a'*32);self.ui.actions['session_delete'].invoke();n=len(self.c.calls)
        self.ui.actions['cancel'].invoke();self.assertEqual(len(self.c.calls),n)
        self.ui.actions['session_delete'].invoke();self.ui.actions['confirm'].invoke()
        self.assertEqual(self.c.calls[-1],('session_action',('delete',),dict(identifier='a'*32,confirmed=True)))
    def test_text_draft_and_output_browser_do_not_open_a_stream(self):
        self.ui.show_sessions();self.ui.actions['new_text'].invoke()
        self.assertEqual(self.c.calls[-1],('session_action',('new',),dict(audio=False,consent=False)))
        self.ui.show_session_outputs();self.assertEqual(len(self.c.calls),1)
        self.ui.actions['refresh_outputs'].invoke();self.assertEqual(self.c.calls[-1],('session_action',('outputs',),{}))
    def test_recording_loss_and_playback_states_are_visible(self):
        self.ui.snapshot['sessions']['archive']=dict(audio_recording=True,archive_error=None)
        self.ui._show_status();self.assertIn('SAVING EXACT AUDIO',self.ui.status_label.cget('text'))
        self.ui.snapshot['sessions']['archive'].update(audio_recording=False,archive_error='ARCHIVE_QUEUE_FULL')
        self.ui._show_status();self.assertIn('ARCHIVE_QUEUE_FULL',self.ui.error_label.cget('text'))
        self.ui.snapshot['sessions']['playback']=dict(active=True,device=dict(name='Chosen headphones'))
        self.ui._show_status();self.assertIn('microphone off',self.ui.status_label.cget('text'))
        self.ui.snapshot['sessions']['playback']['active']=False;self.ui._show_status()
        self.assertIn('finished',self.ui.status_label.cget('text'))


if __name__=='__main__':unittest.main()
