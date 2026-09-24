"""Touch-only optional enrollment evidence review. See README_SCRIPT_EVIDENCE.md."""
import time
from .script_evidence import MATCHED_UNAVAILABLE


def review_text(doc):
    if not doc:return 'Enable Text-aware reference selection in Advanced, then record Paragraph → Done. Ordinary enrollment remains available.'
    if doc.get('error'):return 'Optional analysis unavailable; original reference remains usable.\n'+doc['error']
    cov=doc.get('coverage',{});bank=doc.get('bank',[])
    lines=['Intended reading (not verified speech):',doc.get('script',{}).get('text',''),
           '\nIndependently decoded speech:',doc.get('transcript',{}).get('raw_asr_text',''),
           f"\nApproximate agreement: {cov.get('matched_words',0)} / {cov.get('script_words',0)} intended words.",
           f"Unknown timing: {cov.get('unknown_timing_words',0)} words. Quality-rejected/unknown audio: {cov.get('rejected_or_unknown_audio_sec',0):.1f}s.",
           f"Original retained: {doc.get('base_reference_retained_sec',0):.1f}s. Alternate: {doc.get('retained_unique_sec',0):.1f}s in {len(bank)} contexts.",
           'Original voice remains authoritative. Alternate comparison is advisory; text disagreement never removes original speech.']
    intended=doc.get('script',{}).get('text','')
    from .script_evidence import words
    script=words(intended);heard=words(doc.get('transcript',{}).get('raw_asr_text',''))
    for op in doc.get('agreement_operations',[]):
        if op['operation']=='equal':continue
        a,b=op['script_indices'];c,d=op['recognized_indices']
        lines.append(f"Uncertain {op['operation']}: intended [{' '.join(script[a:b])}] / decoded [{' '.join(heard[c:d])}]")
    lines+=['\n'+MATCHED_UNAVAILABLE,'No phoneme boundaries; token emission times are approximate. Pronunciation variants/dictionary not installed.']
    lines+=['Review note: '+n['text'] for n in doc.get('user_corrections',[])]
    return '\n'.join(lines)


class ScriptEvidenceUI:
    def _toggle_script_evidence(self):
        value=not self.snapshot.get('settings',{}).get('text_aware_references',False)
        if self._call('settings_update',{'text_aware_references':value}):
            self.snapshot.setdefault('settings',{})['text_aware_references']=value;self.show_advanced()

    def show_script_review(self,person_id=None):
        self.page='script_review';frame=self._page('Paragraph coverage',back=self.show_people if person_id else self.show_enrollment_progress)
        if person_id:self._call('script_review',person_id)
        label=self._paragraph_label(frame,'Loading evidence…',True)
        def update():
            doc=(self.snapshot.get('metrics',{}).get('stored_script_review') or {}).get('document') if person_id else self.snapshot.get('enrollment',{}).get('script_evidence')
            if person_id and self.snapshot.get('metrics',{}).get('stored_script_review',{}).get('person_id')!=person_id:doc=None
            label.configure(text=review_text(doc))
        self._page_update=update;update()
        if not person_id:
            self.button(frame,'Add correction / review note',lambda:self.keyboard('Review note', '',self._script_note,multiline=True,cancel=self.show_script_review),key='script_note',height=60).pack(fill='x',padx=self.px(12),pady=self.px(4))
            self.button(frame,'Return to reference / Save',self.show_enrollment_progress,key='script_review_back').pack(fill='x',padx=self.px(12),pady=self.px(4))

    def _script_note(self,text):
        if self._call('enrollment_script_note',text):self.show_script_review()

    def show_reference_comparison(self):
        self.page='reference_comparison';frame=self._page('Reference scores',back=self.show_advanced)
        self._paragraph_label(frame,'Original references decide names. These are raw voice cosines, not probabilities or content-matched identity scores. Toggle changes take effect at the next Start.',True)
        label=self._paragraph_label(frame,'',True)
        def update():
            record=self.snapshot.get('reference_comparison')
            if not record:label.configure(text='No current comparison. Enable Text-aware reference selection, save a supported paragraph reference, then Start a name mode.\n'+MATCHED_UNAVAILABLE);return
            age=max(0,time.perf_counter()-record['monotonic_sec'])
            lines=[f'Last voice query: {age:.1f}s ago · advisory only']
            for row in record['candidates'][:16]:
                alternate='unavailable' if row['alternate'] is None else f"{row['alternate']:.3f}"
                lines.append(f"{row['name']}: base {row['base']:.3f} / alternate {alternate}")
            label.configure(text='\n'.join(lines)+'\n'+MATCHED_UNAVAILABLE)
        self._page_update=update;update()
