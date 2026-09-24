"""Optional portrait review page, separate from captions. See README_TRANSCRIPT_REVIEW.md."""
class TranscriptReviewUI:
    def show_audio_review(self,identifier=None,row_id=None):
        if identifier is not None:
            if getattr(self,'_review_selection',None)!=(identifier,row_id):self._call('review_action','cancel')
            self._review_selection=(identifier,row_id)
        self.page='audio_review';frame=self._page('Audio transcript review',back=self.show_sessions)
        state=self.snapshot.get('audio_review',{});enabled=state.get('enabled',False)
        self._paragraph_label(frame,'◇ Experimental · Windows only. A selected recorded utterance can be decoded again without vocabulary bias. Original words, punctuation and speaker identity stay unchanged. This is not an N-best list or proof of missing words.',True)
        self.button(frame,'Audio review: '+('On' if enabled else 'Off'),lambda:self._review_call('switch',enabled=not enabled),key='audio_review_switch',height=56).pack(fill='x',padx=self.px(12),pady=self.px(3))
        self._paragraph_label(frame,'Language helper: not installed. No extra LLM or cloud. CM5 is disabled pending target qualification.',True)
        selection=getattr(self,'_review_selection',None)
        if selection:
            self.button(frame,'Review selected recorded utterance',lambda:self.confirm('Review this audio?',
                'Analyze only this stored ASR audio excerpt (up to 20 seconds), locally, using the existing recognizer? Stop live capture first. No recording, speaker-profile access or automatic editing occurs.',
                'Review locally',lambda:self._review_request(*selection),cancel=self.show_audio_review),key='audio_review_request',height=60).pack(fill='x',padx=self.px(12),pady=self.px(3))
        else:self._paragraph_label(frame,'Select Sessions → Reopen → Review this utterance. Text-only or incomplete recordings cannot be reviewed.',True)
        self.button(frame,'Cancel / keep original',lambda:self._review_call('cancel'),key='audio_review_cancel').pack(fill='x',padx=self.px(12),pady=self.px(3))
        self._paragraph_label(frame,state.get('status','OFF')+' · '+state.get('reason',''),True)
        result=state.get('result')
        if result:
            self._paragraph_label(frame,'Baseline: '+result['decision']+' · '+result['reason'],True)
            self._paragraph_label(frame,'Listening requires an explicit output choice and a Listen press. Word boundaries are approximate utterance links. Return here through Advanced or the same utterance after selecting output.',True)
            job=result['request']
            self.button(frame,'Choose listening output',self.show_session_outputs,key='audio_review_output').pack(fill='x',padx=self.px(12),pady=self.px(3))
            self.button(frame,'Listen to reviewed audio',lambda:self._session_command('play',identifier=job['conversation'],epoch=job['epoch_id'],start=job['source_start_sample'],end=job['source_end_sample'],stream='asr'),key='audio_review_listen').pack(fill='x',padx=self.px(12),pady=self.px(3))
            for candidate in result['candidates']:
                self._paragraph_label(frame,'Original ASR' if candidate['id']=='original' else 'Alternative · '+candidate['provenance'],True)
                self._paragraph_label(frame,candidate['text'] or '[uncertain / no words]')
                for change in candidate['changes']:
                    self.label(frame,'− '+(change['before'] or '[nothing]'),muted=True,size='small_font_px').pack(fill='x',padx=self.px(12))
                    label=self.label(frame,'+ '+(change['after'] or '[gap / omitted]'),bold=True,size='small_font_px')
                    label.configure(fg=self.color('accent'));label.pack(fill='x',padx=self.px(12),pady=self.px(2))
                if candidate['protected']:self._paragraph_label(frame,'Check against audio: '+'; '.join(candidate['protected']),True)
                if candidate['id']!='original':
                    self.button(frame,'Adopt as separate user correction…',lambda c=candidate,r=result:self.confirm('Confirm what you heard',
                        'I listened and checked the highlighted changes, including names, pronouns, negation, amounts and unusual words. I want this exact candidate recorded as my separate correction. The original ASR remains available, and Sessions provides Undo.',
                        'I checked the audio · Adopt',lambda:self._review_call('adopt',review_id=r['id'],candidate_id=c['id'],consent=True,protected_ack=True),cancel=self.show_audio_review),key='audio_review_adopt_'+candidate['id'],height=66).pack(fill='x',padx=self.px(12),pady=self.px(4))
        signature=(enabled,state.get('status'),state.get('generation'),(result or {}).get('id'))
        def update():
            s=self.snapshot.get('audio_review',{});r=s.get('result') or {}
            if (s.get('enabled',False),s.get('status'),s.get('generation'),r.get('id'))!=signature:self.show_audio_review()
        self._page_update=update
    def _review_call(self,action,**kw):
        if self._call('review_action',action,**kw):self.show_audio_review()
    def _review_request(self,identifier,row_id):
        self._review_call('request',identifier=identifier,row_id=row_id,consent=True)
