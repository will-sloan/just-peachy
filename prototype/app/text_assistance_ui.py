"""Touch vocabulary approval/review. See README_TEXT_ASSISTANCE.md."""
from .text_assistance import BIAS_UNAVAILABLE


class TextAssistanceUI:
    def _text_data(self):return self.snapshot.get('text_assistance') or {}
    def _text_button(self,frame,title,command,key=None):
        widget=self.button(frame,title,command,key=key)
        widget.pack(fill='x',padx=self.px(12),pady=self.px(4));return widget
    def _text_command(self,action,**values):return self._call('text_assistance_action',action,**values)

    def show_text_assistance(self):
        self.page='text_assistance';frame=self._page('Text assistance',back=self.show_settings);data=self._text_data()
        self._paragraph_label(frame,'Optional spelling review. Raw words remain available; a speaker label never decides what was said.',True)
        if data.get('error'):self._paragraph_label(frame,data['error'],True)
        self._text_button(frame,'Suggestions: '+('On' if data.get('enabled') else 'Off'),
                          lambda:self._text_command('switch',enabled=not data.get('enabled',False)),key='text_enabled')
        self._text_button(frame,'Approved automatic rules: '+('On' if data.get('automatic') else 'Off'),
                          lambda:self._text_command('switch',automatic=not data.get('automatic',False)),key='text_automatic')
        self._paragraph_label(frame,'Automatic rules need an exact alias + context + approval. Protected or conflicting content stays for review. ✎ marks assisted caption text; switch Off to see the original formatting.',True)
        self._text_button(frame,'Review recent final text',self.show_text_review,key='text_review')
        self._text_button(frame,'Add word / spelling preference',lambda:self._new_vocab(),key='vocab_add')
        self._text_button(frame,'Approve an enrolled name…',self.show_vocab_people,key='vocab_person')
        bias=self._text_button(frame,'Bias enrolled names · unavailable',lambda:None,key='text_bias');bias.button.configure(state='disabled')
        self._paragraph_label(frame,data.get('bias_reason',BIAS_UNAVAILABLE),True)
        for entry in data.get('entries',[]):
            description=entry['preferred']+(' ← '+entry['alias'] if entry['alias'] else '')
            if entry['context']:description+=' · context: '+entry['context']
            self._paragraph_label(frame,description)
            self._paragraph_label(frame,entry.get('inactive_reason') or ('Approved automatic rule' if entry['approved_auto'] else 'Review only'),True)
            self._text_button(frame,'Remove preference',lambda e=entry:self._text_command('delete',id=e['id']))
        revision=data.get('revision')
        self._page_update=lambda:self.show_text_assistance() if self._text_data().get('revision')!=revision else None

    def show_vocab_people(self):
        self.page='vocabulary';frame=self._page('Approve name',back=self.show_text_assistance)
        self._paragraph_label(frame,'Select a name explicitly. This permits spelling review only; it does not mean the person said their own name.',True)
        for person in self.snapshot.get('people',[]):
            self._text_button(frame,person['name']+' · '+person['id'][:8],lambda p=person:self._new_vocab(p))

    def _new_vocab(self,person=None):
        self._vocab_draft={'preferred':person['name'] if person else '', 'alias':'','context':'',
                           'kind':'name' if person else 'spelling','person_id':person['id'] if person else None,
                           'approved_auto':False}
        self._draw_vocab()

    def _draw_vocab(self):
        self.page='vocabulary';frame=self._page('Vocabulary entry',back=self.show_text_assistance);draft=self._vocab_draft
        self._paragraph_label(frame,'Approve exact spellings, not guessed speech. Amir and Emir can be different people or a title. Context limits where a mapping is offered.',True)
        for key,title in (('preferred','Preferred spelling'),('alias','Alias / heard spelling (optional)'),('context','Required context (optional for review)')):
            def edit(field=key,label=title):
                def done(value):self._vocab_draft[field]=value;self._draw_vocab()
                self.keyboard(label,draft[field],done,cancel=self._draw_vocab)
            self._text_button(frame,title+': '+(draft[key] or '—'),edit,key='vocab_'+key)
        if not draft.get('person_id'):
            self._text_button(frame,'Type: '+draft['kind'],self._cycle_vocab_kind,key='vocab_kind')
        def approve_auto():
            self._vocab_draft['approved_auto']=not draft['approved_auto'];self._draw_vocab()
        self._text_button(frame,'Automatic in this context: '+('approved' if draft['approved_auto'] else 'No'),approve_auto,key='vocab_auto')
        self._paragraph_label(frame,'Automatic is optional and needs both alias and context. Mappings keep the same word count. Rename/delete disables linked names until you approve a new entry.',True)
        def save():
            if self._text_command('add',**draft,approved=True):self.show_text_assistance()
        self._text_button(frame,'Approve entry',save,key='vocab_save')

    def _cycle_vocab_kind(self):
        kinds=('spelling','context','name');self._vocab_draft['kind']=kinds[(kinds.index(self._vocab_draft['kind'])+1)%3];self._draw_vocab()

    def show_text_review(self):
        self.page='text_review';frame=self._page('Text review',back=self.show_text_assistance)
        self._paragraph_label(frame,'Latest eight final captions. Suggestions are text heuristics, not acoustic confidence. Stop and drain before manual edits. Sessions keeps the full journal and undo history.',True)
        self._text_button(frame,'Refresh',self.show_text_review,key='text_refresh')
        self._text_button(frame,'Stop capture',lambda:self._call('stop'),key='text_stop')
        self._text_button(frame,'Sessions / correction undo',self.show_sessions,key='text_sessions')
        for row in reversed(self._text_data().get('recent',[])):
            self._paragraph_label(frame,'Raw: '+row['raw'])
            self._paragraph_label(frame,'Final formatting: '+(row.get('final') or row['raw']),True)
            aid=row.get('assistance') or {}
            if aid.get('corrected_text'):self._paragraph_label(frame,'Assisted (reversible): '+aid['corrected_text'],True)
            source=aid.get('source') or {}
            self._paragraph_label(frame,'Caption '+str(row.get('caption_key'))+' · '+str(source.get('start_sample','?'))+'–'+str(source.get('end_sample','?'))+' samples',True)
            if row.get('manual_edit'):self._paragraph_label(frame,'Manual edit: '+row['manual_edit']['corrected_text'],True)
            for suggestion in aid.get('suggestions',[]):
                self._paragraph_label(frame,suggestion['before']+' → '+suggestion['after']+' · '+suggestion['reason'],True)
            def edit(r=row):
                data=self._session_data();identifier=data.get('opened_id') or data.get('current_id')
                self.keyboard('Manual correction',r.get('final') or r['raw'],
                    lambda value:self._session_command('correct',identifier=identifier,row_id=r['caption_key'],correction=value),
                    multiline=True,cancel=self.show_text_review)
            button=self._text_button(frame,'Edit this caption (raw retained)',edit)
            if self.snapshot.get('state') not in ('STOPPED','IDLE') or self._session_data().get('archive'):button.button.configure(state='disabled')
