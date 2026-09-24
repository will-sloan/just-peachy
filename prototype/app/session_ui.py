"""Touch-only developer session pages. See README_SESSIONS.md."""
from pathlib import Path
import time


class SessionUI:
    def _session_data(self):return self.snapshot.get('sessions') or {}

    def _session_command(self,action,**values):
        return self._call('session_action',action,**values)

    def show_sessions(self):
        self.page='sessions';frame=self._page('Sessions',back=self.show_settings)
        data=self._session_data();usage=data.get('usage',{})
        self._paragraph_label(frame,'Developer archive · local and unencrypted. New preserves the previous draft; Save pins it against automatic cleanup. Delete conversations never deletes enrolled people.',True)
        self.button(frame,'New transcript · text only',lambda:self._new_conversation(False),key='new_text').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'New transcript + exact audio…',lambda:self._new_conversation(True),key='new_audio').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Stop capture / listening',lambda:self._call('stop'),key='session_stop').pack(fill='x',padx=self.px(12),pady=self.px(3))
        if data.get('current_id'):
            self.button(frame,'Save current conversation',lambda:self._session_command('save'),key='save_session').pack(fill='x',padx=self.px(12),pady=self.px(3))
            self.button(frame,'Mark problem · add a short note',lambda:self._session_note(data['current_id']),key='session_note').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Listening output · choose explicitly',self.show_session_outputs,key='session_outputs').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self._paragraph_label(frame,f"Archive {usage.get('bytes',0)/1024**2:.1f} / {usage.get('quota_bytes',0)/1024**2:.0f} MiB · free {usage.get('free_bytes',0)/1024**3:.1f} GiB\n"+
            'Up to 10 unpinned drafts; saved/pinned data is retained. Limits stop archival with a visible warning, while live captions can continue. Float32 mono16k ≈220 MiB/hour; PCM16 ≈110 MiB/hour.',True)
        self._paragraph_label(frame,usage.get('path','Archive path pending'),True)
        rows=data.get('library',[])
        if not rows:self._paragraph_label(frame,'No conversations yet. Start also creates a text-only draft.')
        for row in rows:
            name=row['title'][:42]+'\n'+('Saved · pinned' if row['pinned'] else 'Draft')+f" · {row['size_bytes']/1024**2:.1f} MiB"
            if row.get('issues'):name+=' · PARTIAL'
            self.button(frame,name,lambda r=row:self.show_session(r['id']),height=60).pack(fill='x',padx=self.px(12),pady=self.px(3))
        signature=repr(rows)
        def update():
            if repr(self._session_data().get('library',[]))!=signature:self.show_sessions()
        self._page_update=update

    def _new_conversation(self,audio):
        def create():
            if self._session_command('new',audio=audio,consent=audio):self.home()
        if audio:self.confirm('Store conversation audio?',
            'Get consent from everyone present. Save the exact post-XVF mono float32 model input, including noise and omissions. This is sensitive, unencrypted local audio, not raw microphones or all beams. Previous drafts are retained. Capture begins only after Start.',
            'Participants consent · Create audio draft',create,cancel=self.show_sessions)
        else:create()

    def _session_note(self,identifier):
        self.keyboard('Problem note','',lambda text:self._session_command('note',identifier=identifier,note=text),multiline=True,cancel=self.show_sessions)

    def show_session(self,identifier):
        self.page='session_detail';frame=self._page('Conversation',back=self.show_sessions)
        data=self._session_data();row=next((r for r in data.get('library',[]) if r['id']==identifier),{})
        self._paragraph_label(frame,row.get('title',identifier))
        for issue in row.get('issues',[]):self._paragraph_label(frame,'Partial / unavailable evidence: '+str(issue.get('error')))
        def opened():
            if self._session_command('open',identifier=identifier):self.show_session(identifier)
        self.button(frame,'Reopen · load transcript and audio links',opened,key='session_open').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'View loaded captions',self.home,key='session_captions').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Rename',lambda:self.keyboard('Conversation name',row.get('title',''),lambda text:self._session_command('rename',identifier=identifier,title=text),cancel=lambda:self.show_session(identifier)),key='session_rename').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Save / pin',lambda:self._session_command('save',identifier=identifier),key='session_pin').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Add note',lambda:self._session_note(identifier)).pack(fill='x',padx=self.px(12),pady=self.px(3))
        for audio,title in ((False,'Export text and user annotations…'),(True,'Export full evidence + exact audio…')):
            self.button(frame,title,lambda a=audio:self._session_export(identifier,a)).pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Delete conversation…',lambda:self.confirm('Delete conversation?',
            'Delete this conversation and its recordings/notes, including saved/pinned data? Enrolled people and voice references remain.',
            'Delete this conversation',lambda:self._delete_session(identifier),cancel=lambda:self.show_session(identifier)),key='session_delete').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self._paragraph_label(frame,'Listening stops and releases capture first. Choose an output explicitly; default speakers are never changed. Start stops playback before opening a microphone.',True)
        self.button(frame,'Choose listening output',self.show_session_outputs).pack(fill='x',padx=self.px(12),pady=self.px(3))
        if data.get('opened_id')==identifier:
            self._paragraph_label(frame,'Listening stream (enhanced may be unavailable in older/bypass epochs):',True)
            for value,label in (('input','Original input'),('asr','Actual ASR input'),('identity','Actual identity input'),('enhanced','Enhanced / fallback output')):
                self.button(frame,('✓ ' if getattr(self,'_listening_stream','input')==value else '')+label,
                    lambda v=value:self._choose_listening_stream(v,identifier),height=50).pack(fill='x',padx=self.px(12),pady=self.px(2))
            for item in data.get('caption_links',[]):
                self._paragraph_label(frame,item['text'])
                self._paragraph_label(frame,f"{item['start']/16000:.2f}–{item['end']/16000:.2f}s · coarse utterance; not word alignment",True)
                self.button(frame,'Review this utterance…',lambda r=item:self.show_audio_review(identifier,r['id']),key='review_'+item['id']).pack(fill='x',padx=self.px(12),pady=self.px(3))
                end=min(item['end'],item['start']+60*16000)
                self.button(frame,'Listen to this interval'+(' · first 60s' if end<item['end'] else ''),
                    lambda r=item,e=end:self._session_command('play',identifier=identifier,epoch=r['epoch'],start=r['start'],end=e,stream=getattr(self,'_listening_stream','input'))).pack(fill='x',padx=self.px(12),pady=self.px(3))
                self.button(frame,'User correction · separate from raw',lambda r=item:self.keyboard('User correction',r['text'],
                    lambda text:self._session_command('correct',identifier=identifier,row_id=r['id'],correction=text),multiline=True,
                    cancel=lambda:self.show_session(identifier))).pack(fill='x',padx=self.px(12),pady=self.px(3))
        annotations=data.get('annotations') or {}
        if annotations.get('identifier')==identifier:
            for note in annotations.get('notes',[]):self._paragraph_label(frame,'User note: '+note['note'],True)
            undone={e.get('reverts') for e in annotations.get('corrections',[])}
            for edit in annotations.get('corrections',[]):
                self._paragraph_label(frame,('Undo recorded' if edit.get('reverts') else 'User correction (raw retained): '+edit['corrected_text']),True)
                if not edit.get('reverts') and edit['id'] not in undone:
                    self.button(frame,'Undo this correction',lambda e=edit:self._session_command('undo_correction',identifier=identifier,edit_id=e['id'])).pack(fill='x',padx=self.px(12),pady=self.px(3))
        signature=(repr(data.get('library')),data.get('opened_id'),repr(data.get('caption_links')),repr(data.get('annotations')))
        def update():
            d=self._session_data()
            if (repr(d.get('library')),d.get('opened_id'),repr(d.get('caption_links')),repr(d.get('annotations')))!=signature:self.show_session(identifier)
        self._page_update=update

    def _choose_listening_stream(self,value,identifier):
        self._listening_stream=value;self.show_session(identifier)

    def _delete_session(self,identifier):
        if self._session_command('delete',identifier=identifier,confirmed=True):self.show_sessions()

    def _session_export(self,identifier,audio):
        base=Path(self._session_data().get('usage',{}).get('path',str(Path.home()))).parent/'conversation_exports'
        destination=base/(identifier+'_'+str(time.time_ns())+('_full.zip' if audio else '_text.zip'))
        def choose():self.keyboard('Export ZIP path',str(destination),lambda path:self._session_command('export',identifier=identifier,path=path,audio=audio,consent=True),cancel=lambda:self.show_session(identifier))
        self.confirm('Export sensitive data?',
            ('Full evidence includes exact audio, names, roster UUIDs and identity events. Save/pin first. ' if audio else 'Text and notes can contain spoken names and private information. ')+
            'The ZIP is unencrypted. Choose a local destination; this application does not upload it.',
            'I consent · Choose export path',choose,cancel=lambda:self.show_session(identifier))

    def show_session_outputs(self):
        self.page='session_outputs';frame=self._page('Listening output',back=self.show_sessions)
        self._paragraph_label(frame,'Explicit choice only. No output is selected automatically; recognition/enrollment stays off during playback.',True)
        self.button(frame,'Refresh output devices',lambda:self._session_command('outputs'),key='refresh_outputs').pack(fill='x',padx=self.px(12),pady=self.px(3))
        data=self._session_data();chosen=data.get('selected_output')
        for device in data.get('outputs',[]):
            selected=chosen==device
            self.button(frame,('✓ ' if selected else '')+device['name']+'\n'+device['hostapi'],
                lambda d=device:self._session_command('output',index=d['index']),accent=selected,height=72).pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Stop listening',lambda:self._session_command('stop_playback')).pack(fill='x',padx=self.px(12),pady=self.px(3))
        signature=repr((data.get('outputs'),chosen))
        def update():
            d=self._session_data()
            if repr((d.get('outputs'),d.get('selected_output')))!=signature:self.show_session_outputs()
        self._page_update=update
