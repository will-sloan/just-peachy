"""Optional routing and existing evidence diagnostics. See README_NOISE.md."""
from .enhancement import ROUTES

class NoiseUI:
    def show_noise(self):
        self.page='noise';frame=self._page('Noise / model routing',back=self.show_advanced)
        self._paragraph_label(frame,'◇ Experimental · DPDFNet 16 kHz. Bypass is the default. Selecting a route stops the current session; press Start for a fresh epoch. No automatic microphone or playback.',True)
        current=self.snapshot.get('settings',{}).get('enhancement_route','bypass')
        for value,label in ROUTES.items():
            self.button(frame,('✓ ' if value==current else '')+label,lambda v=value:self._choose_noise(v),
                key='noise_'+value,height=56).pack(fill='x',padx=self.px(12),pady=self.px(3))
        self._paragraph_label(frame,'Enhanced identity uses a separate reference domain. Record a new consenting reference with identity enhancement selected; existing original references are preserved. The same applies to O0/O1 compatibility.',True)
        self._paragraph_label(frame,'Exact input/output listening: Sessions → new transcript + audio (consent) → Start. After Stop, reopen and choose Original, ASR, Identity or Enhanced. No raw microphone channels are denoised.',True)
        label=self._paragraph_label(frame,'',True)
        def update():
            if self.snapshot.get('settings',{}).get('enhancement_route','bypass')!=current:self.show_noise();return
            state=self.snapshot.get('noise') or {};lines=['Existing evidence coordinator (no new inference):']
            for kind,row in state.get('observations',{}).items():
                interval='' if row.get('source_start_sample') is None else f" · {row['source_start_sample']/16000:.2f}–{row['source_end_sample']/16000:.2f}s"
                lines.append(kind.replace('_',' ')+': '+row['state']+interval)
            lines+=state.get('actions',['No running observations.'])
            if state.get('fallback'):lines.append('Helper fallback: '+state['fallback']['reason'])
            label.configure(text='\n'.join(lines)+'\nLow volume, missing words or an accent do not prove noise. Captions remain available. CM5 speed/thermals are not yet qualified.')
        self._page_update=update;update()
    def _choose_noise(self,value):
        if self._call('noise_route',value):self.show_noise()
