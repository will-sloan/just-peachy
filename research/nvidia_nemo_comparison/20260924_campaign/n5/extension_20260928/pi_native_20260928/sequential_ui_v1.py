"""In-window portrait controls for saved sequential ASR; README_SEQUENTIAL_GUI_V1.md."""


def ui_class(Base):
    class SequentialUI(Base):
        def _build(self):
            super()._build()
            self.button(self.shell,'Saved file: Sherpa + Nemotron',self.show_sequential,key='sequential_open',height=48).pack(before=self.body,fill='x')
        def show_sequential(self):
            self.page='sequential';frame=self._page('Saved transcription and refinement',back=self.home)
            self._paragraph_label(frame,'Initial captions use Sherpa. Nemotron runs after the primary model closes. Both revisions stay available. Saved file only; no speaker labels.',True)
            state=self.label(frame,'Ready',size='small_font_px');state.pack(fill='x')
            controls={}
            for label,action in [('Transcribe saved file','start'),('Refine with Nemotron','refine'),('Cancel / keep primary','cancel'),('Save revisions','save'),('Reopen saved revisions','open')]:
                def invoke(a=action):
                    if a=='open':self._call('seq_action',a,path=self.controller.seq_snapshot()['saved'])
                    else:self._call('seq_action',a)
                controls[action]=self.button(frame,label,invoke,key='seq_'+action,height=48)
                controls[action].pack(fill='x',padx=self.px(8),pady=self.px(2))
            primary=self._paragraph_label(frame,'Primary: pending')
            refined=self._paragraph_label(frame,'Refinement: pending')
            def update():
                value=self.controller.seq_snapshot();busy=value['owned']
                state.configure(text=value['phase']+(' · '+value['error'] if value['error'] else ''))
                allowed=dict(start=not busy,refine=not busy and value['primary'] is not None,cancel=busy,
                             save=not busy and value['primary'] is not None and value['saved'] is None,
                             open=not busy and value['saved'] is not None)
                for action,button in controls.items():button.configure(state='normal' if allowed[action] else 'disabled')
                primary.configure(text='Primary (Sherpa):\n'+(value['primary_text'] or 'Pending'))
                refined.configure(text='Refinement (Nemotron):\n'+(value['refined_text'] or 'Pending'))
            self.seq_widgets=dict(state=state,primary=primary,refined=refined,controls=controls)
            self._page_update=update;update()
    return SequentialUI
