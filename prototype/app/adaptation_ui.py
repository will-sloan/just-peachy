"""Touch-only candidate review and reversible promotion. See README_ADAPTATION.md."""
class AdaptationUI:
    def show_adaptation(self):
        self.page='adaptation';frame=self._page('Session references',back=self.show_advanced)
        if self.snapshot.get('backend',{}).get('composition',{}).get('n2'):
            self._paragraph_label(frame,'Session reference collection, bank matching and promotion are unavailable for this backend. Original model-compatible enrollments remain available through People.',True)
            self.button(frame,'Return to captions',self.home).pack(fill='x',padx=self.px(12),pady=self.px(6))
            return
        state=self.snapshot.get('adaptation',{});collect=state.get('collect',False);enabled=state.get('enabled',False)
        undo_signature=[(p['id'],p.get('enrichment_undo',False)) for p in self.snapshot.get('people',[])]
        self._paragraph_label(frame,'◇ Experimental · Off by default. Original enrollments stay unchanged. Start clears unsaved candidates. No automatic learning or new microphone capture.',True)
        self.button(frame,'Collect candidate references: '+('On' if collect else 'Off'),lambda:self._reference_toggle('collect',not collect),key='reference_collect',height=60).pack(fill='x',padx=self.px(12),pady=self.px(4))
        self.button(frame,'Use approved bank: '+('On' if enabled else 'Off'),lambda:self._reference_toggle('use',not enabled),key='reference_use',height=60).pack(fill='x',padx=self.px(12),pady=self.px(4))
        info=self._paragraph_label(frame,'',True)
        self.button(frame,'Review candidates',self.show_reference_candidates,key='reference_review').pack(fill='x',padx=self.px(12),pady=self.px(4))
        self.button(frame,'Freeze · music / overlap / conflict',lambda:self._reference_action('freeze'),key='reference_freeze',height=60).pack(fill='x',padx=self.px(12),pady=self.px(4))
        self.button(frame,'Discard session candidates',lambda:self.confirm('Discard candidates','Delete the pending session bank and turn matching Off? Saved personal additions are retained; use Undo below to remove those.',
            'Discard',lambda:self._reference_action('discard'),cancel=self.show_adaptation),key='reference_discard',height=60).pack(fill='x',padx=self.px(12),pady=self.px(4))
        for p in self.snapshot.get('people',[]):
            if p.get('enrichment_undo'):
                self.button(frame,'Undo latest · '+p['name'],lambda p=p:self.confirm('Undo personal addition','Stop capture and remove the latest enrichment for '+p['name']+'? Original enrollments are retained. Earlier captions are not rewritten.',
                    'Undo',lambda:self._reference_action('undo',person_id=p['id'],consent=True),cancel=self.show_adaptation),key='reference_undo_'+p['id'],height=60).pack(fill='x',padx=self.px(12),pady=self.px(4))
        def update():
            s=self.snapshot.get('adaptation',{})
            if ((s.get('collect',False),s.get('enabled',False))!=(collect,enabled)
                or [(p['id'],p.get('enrichment_undo',False)) for p in self.snapshot.get('people',[])]!=undo_signature):self.show_adaptation();return
            text=f"Usable speech: {s.get('usable_sec',0):.2f}s · confirmed {s.get('confirmed_sec',0):.2f}s\n{len(s.get('candidates',[]))}/16 session windows · {s.get('compatible_saved',0)} compatible saved references"
            if s.get('frozen'):text+='\nFROZEN: '+s['frozen']+' · new Start required'
            text+='\nBank weight at most 10%; base voice remains the gate. Off restores original scores for future decisions. Seats and words cannot certify identity.'
            info.configure(text=text)
        self._page_update=update;update()
    def _reference_action(self,action,**kw):
        if self._call('adaptation_action',action,**kw):self.show_adaptation()
    def _reference_toggle(self,action,on):
        if not on:self._reference_action(action,enabled=False);return
        message=('Only collect consenting participants. Existing speech windows supply voice features held in RAM until explicit promotion. You must identify each actual speaker; automatic names, seats and transcript text are not confirmation.' if action=='collect' else
            'Use explicitly confirmed session and promoted references with at most 10% weight? This is experimental. Original full-roster voice evidence must agree. Earlier captions stay unchanged. Off gives the original-score comparison.')
        self.confirm('Enable reference '+action,message,'I agree · Enable',lambda:self._reference_action(action,enabled=True,consent=True),cancel=self.show_adaptation)
    def show_reference_candidates(self):
        if self.snapshot.get('backend',{}).get('composition',{}).get('n2'):
            self.show_adaptation();return
        self.page='reference_candidates';frame=self._page('Review references',back=self.show_adaptation)
        candidates=self.snapshot.get('adaptation',{}).get('candidates',[])
        selected=getattr(self,'_reference_selected',set())&{c['id'] for c in candidates if c.get('confirmation')}
        self._reference_selected=selected
        self._paragraph_label(frame,'Confirm only speech you personally heard and can identify. A suggested name is not ground truth. No audio is saved here; consented session audio remains in Sessions. Select confirmed windows for one person before promotion.',True)
        signature=[(c['id'],c.get('person_id')) for c in candidates]
        if not candidates:self._paragraph_label(frame,'No candidates. Enable Collect in a voice name mode, then Start and speak separately.',True)
        for c in candidates:
            best=c['best_base'];confirmed=bool(c.get('confirmation'))
            margin=f"margin {c['base_margin']:.3f}" if c['base_margin'] is not None else 'no competitor available'
            self._paragraph_label(frame,f"{c['start_sample']/16000:.2f}–{c['end_sample']/16000:.2f}s · usable {c['usable_sec']:.2f}s\nBase suggests {best['name']}: {best['cosine']:.3f}, {margin}\n"+('User-confirmed' if confirmed else 'Pending confirmation')+' · noise/music not independently classified',True)
            self.button(frame,'Review this window',lambda c=c:self.show_reference_candidate(c['id']),key='reference_candidate_'+c['id']).pack(fill='x',padx=self.px(12),pady=self.px(3))
            if confirmed:self.button(frame,('✓ Selected' if c['id'] in selected else 'Select for promotion'),lambda i=c['id']:self._reference_select(i),key='reference_select_'+c['id']).pack(fill='x',padx=self.px(12),pady=self.px(3))
        self.button(frame,'Promote selected to personal profile',self._reference_promote,key='reference_promote',height=64).pack(fill='x',padx=self.px(12),pady=self.px(6))
        def update():
            if [(c['id'],c.get('person_id')) for c in self.snapshot.get('adaptation',{}).get('candidates',[])]!=signature:self.show_reference_candidates()
        self._page_update=update
    def _reference_select(self,identifier):
        selected=getattr(self,'_reference_selected',set())
        if identifier in selected:selected.remove(identifier)
        else:selected.add(identifier)
        self._reference_selected=selected;self.show_reference_candidates()
    def show_reference_candidate(self,identifier):
        c=next((c for c in self.snapshot.get('adaptation',{}).get('candidates',[]) if c['id']==identifier),None)
        if c is None:self.show_reference_candidates();return
        self.page='reference_candidate';frame=self._page('Confirm actual speaker',back=self.show_reference_candidates)
        q=c['quality'];d=c['domain']
        self._paragraph_label(frame,f"Source {c['start_sample']/16000:.2f}–{c['end_sample']/16000:.2f}s · usable {c['usable_sec']:.2f}s\nClean {q['clean_fraction']:.0%} · clipped {q['clipping']:.2%}\n{d['tap']} · {d['beam_stream']} · {d['enhancement_config']}\nNo inferred seat, closed-group name or revised text certifies this window. If unsure, leave it pending.",True)
        for p in self.snapshot.get('people',[]):
            self.button(frame,'It was '+p['name'],lambda p=p:self.confirm('Confirm heard speech','I personally heard '+p['name']+' alone during this window, without other speech or music. The original voice anchors must also agree. This confirms a temporary candidate; it does not save it permanently.',
                'Confirm this speaker',lambda:self._reference_confirm(identifier,p['id']),cancel=lambda:self.show_reference_candidate(identifier)),key='reference_confirm_'+p['id'],height=60).pack(fill='x',padx=self.px(12),pady=self.px(4))
    def _reference_confirm(self,identifier,person_id):
        if self._call('adaptation_action','confirm',id=identifier,person_id=person_id,consent=True):self.show_reference_candidates()
    def _reference_promote(self):
        selected=getattr(self,'_reference_selected',set());rows=[c for c in self.snapshot.get('adaptation',{}).get('candidates',[]) if c['id'] in selected]
        ids={c['person_id'] for c in rows}
        if not rows or len(ids)!=1 or None in ids:
            self.confirm('Choose one person','Select confirmed windows for a single person first. Nothing has been saved.','Return to review',self.show_reference_candidates,cancel=self.show_reference_candidates);return
        self.confirm('Promote selected references',f'Stop capture and save {len(rows)} selected windows in a separate personal environment bank? Original anchors stay unchanged. Undo is available after restart. Export includes these private voice features.',
            'Approve promotion',lambda:self._reference_action('promote',ids=[c['id'] for c in rows],person_id=next(iter(ids)),consent=True),cancel=self.show_reference_candidates)
