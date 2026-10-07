"""Actual installed interactive FieldUI derivative; README_FIELD_OPERATOR_V2.md."""
import ast
from pathlib import Path

def ui_class(entry,prototype,context,request_return):
    tree=ast.parse(Path(entry.__file__).read_bytes())
    nodes=[n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='FieldUI']
    if len(nodes)!=1:raise ValueError('Installed FieldUI shape changed')
    import inspect,textwrap
    drawing=textwrap.dedent(inspect.getsource(prototype._update_spatial_visualization))
    old='Startup frame · turn %.1f° · drift possible'
    if drawing.count(old)!=1:raise ValueError('Actual spatial legend boundary')
    drawing=drawing.replace(old,'Device beams · relative turn %.1f°')
    namespace=dict(prototype._update_spatial_visualization.__globals__)
    exec(compile(drawing,'<mounted-device-visualization>','exec'),namespace)
    class MountedPrototype(prototype):
        _update_spatial_visualization=namespace['_update_spatial_visualization']
    env=dict(entry.__dict__,PrototypeUI=MountedPrototype)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),
                 str(entry.__file__)+':operator-field-ui','exec'),env)
    class OperatorUI(env['FieldUI']):
        def button(self,parent,text,command,*args,**kwargs):
            # These old controls have no admitted writers/actions in this child.
            unavailable=('Rename','Add note',
                'Export text and user annotations','Choose listening output',
                'Mark problem','Listening output','Review this utterance',
                'Listen to this interval','User correction','Undo this correction')
            if kwargs.get('key')=='new_text':
                text='Audio recording off · keep transcript'
            elif kwargs.get('key')=='new_audio':
                text='Record processed audio…'
            blocked=any(str(text).startswith(x) for x in unavailable)
            if blocked:
                text=str(text)+' Â· unavailable'
                command=lambda:None
            if kwargs.get('key')=='motion':
                text='Orientation graphic · show / hide';command=self._toggle_motion_debug
            widget=super().button(parent,text,command,*args,**kwargs)
            if blocked:widget.button.configure(state='disabled')
            return widget
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            # One persistent 48px control outside scrollable history pages.
            self.operator_return=self.button(self.root,'Return to modes',self.close,
                                               key='operator_return',height=48)
            self.operator_return.pack(side='bottom',fill='x',before=self.body)
            self.root.protocol('WM_DELETE_WINDOW',self.close)
            self.show_sessions()

        def _toggle_motion_debug(self):
            import tkinter as tk
            if getattr(self,'_motion_debug',None) is None:
                self._motion_debug=tk.Canvas(self.root,width=78,height=88,bg='#20242a',highlightthickness=1,highlightbackground='#777777')
                self._motion_debug.bind('<Button-1>',self._motion_debug_zero)
                self._motion_debug_zero_value=0.;self._motion_debug_last=-1.
            self._motion_debug_visible=not getattr(self,'_motion_debug_visible',False)
            if self._motion_debug_visible:
                self._motion_debug.place(relx=1.,x=-4,y=4,anchor='ne');self.root.tk.call('raise',self._motion_debug._w)
            else:self._motion_debug.place_forget()
        def _motion_debug_zero(self,event=None):
            motion=self.snapshot.get('motion') or {}
            if motion.get('valid'):
                self._motion_debug_zero_value=motion['yaw_deg'];self._motion_debug_last=-1.
                self._draw_motion_debug()
        def _draw_motion_debug(self):
            if not getattr(self,'_motion_debug_visible',False):return
            import math,time
            now=time.monotonic()
            if now-getattr(self,'_motion_debug_last',-1.)<.1:return
            self._motion_debug_last=now
            motion=self.snapshot.get('motion') or {};canvas=self._motion_debug
            canvas.delete('all')
            valid=motion.get('valid') is True
            angle=math.radians(-(motion.get('yaw_deg',0.)-self._motion_debug_zero_value)) if valid else 0.
            c,s=math.cos(angle),math.sin(angle)
            def point(x,y):return 39+x*c-y*s,33+x*s+y*c
            corners=[point(x,y) for x,y in ((-14,-23),(14,-23),(14,23),(-14,23))]
            color='#70d7ac' if valid else '#999999'
            canvas.create_polygon(*[v for xy in corners for v in xy],outline=color,fill='',width=2)
            if valid:canvas.create_line(*point(0,14),*point(0,-17),fill=color,width=2,arrow='last')
            state=motion.get('state','WAITING') if valid else 'NOT READY'
            canvas.create_text(39,68,text=str(state)[:12],fill=color,font=('TkDefaultFont',8))
            canvas.create_text(39,81,text='tap: visual zero',fill='#dddddd',font=('TkDefaultFont',7))

        def _show_status(self):
            super()._show_status()
            self._draw_motion_debug()
            status=self._session_data()
            archive=status.get('archive') or status.get('last_archive') or {}
            samples=archive.get('source_samples',0)
            state='Processed audio' if archive.get('audio_enabled') else 'Audio off'
            timing=f"{samples/16000:.1f}s / 120s" if archive else 'Choose recording before Start'
            motion=self.snapshot.get('motion') or {}
            motion_line=('Motion ready · turn %.1f°' % motion.get('yaw_deg',0)) if motion.get('valid') else 'Motion: '+str(motion.get('reason','initializing'))[:60]
            if context['runtime_profile']['selection']['input_kind']=='saved':motion_line='Saved audio: current motion does not change recorded directions'
            self.preview_label.configure(text=context['runtime_profile']['label']+'\n'+state+' · '+timing+'\n'+motion_line)
        def show_sessions(self):
            super().show_sessions()
            after=self.actions['new_audio'].master
            def new_raw():
                from tkinter import messagebox
                if messagebox.askyesno('Record raw microphones','Store four physical microphone channels and processed model audio locally? Copy recordings to your PC after testing.',parent=self.root):
                    self._session_command('new',audio=True,consent=True,raw_microphones=True)
            live_input=context['runtime_profile']['selection']['input_kind']=='microphone'
            holder=self.button(after.master,'Record raw MIC0–MIC3 + processed…' if live_input else 'Raw microphones unavailable for saved input',new_raw)
            holder.button.configure(state='normal' if live_input else 'disabled')
            holder.pack(after=after,fill='x',padx=self.px(12),pady=self.px(3))
            self._paragraph_label(after.master,'Raw stores four physical microphone taps at16kHz with processed model audio. Raw files are included in full recording offload to the PC; the conversation ZIP contains processed audio and text only.',True)

        def close(self):
            # Main loop owns Stop/Close/join/Tk destruction. Never join in a callback.
            request_return('OPERATOR_RETURN')
        def _call(self,name,*args,**kwargs):
            if name not in ('session_action','start_live','start_file','stop','close','select_backend','switch'):
                self._notice='Unavailable in this recording process.'
                self._show_status()
                return False
            return super()._call(name,*args,**kwargs)
        def _session_command(self,action,**values):
            try:
                if action=='new':
                    if self.controller._delivery_new_requested or self.controller._delivery_attempted:
                        raise ValueError('Return to modes before creating another recording.')
                    if type(values.get('audio')) is not bool or type(values.get('consent')) is not bool or values['audio'] != values['consent']:
                        raise ValueError('Choose audio Off or consented Processed.')
                else:
                    checked=values
                    if action=='save' and not values:
                        checked={'identifier':self.controller.conversation_id}
                    context['actions'].check(self.controller,action,checked)
            except (ValueError,RuntimeError) as exc:
                self._notice=str(exc);self._show_status();return False
            return super()._session_command(action,**values)
        def _session_export(self,identifier,audio):
            if audio is not True:
                self._notice='Use full private export for the complete saved transcript and any selected audio.'
                self._show_status();return
            destination=str(context['actions'].destination)
            self.confirm('Export private recording?',
                'This local ZIP contains the complete saved transcript, events and any selected audio. It stays unencrypted on this device.',
                'I consent Â· Export',
                lambda:self._session_command('export',identifier=identifier,path=destination,audio=True,consent=True),
                cancel=lambda:self.show_session(identifier))
        def _import_archive(self):
            self.confirm('Restore exported recording?',
                'Restore this process exported recording into its original ID. Existing recordings are never overwritten.',
                'Import recording',
                lambda:self._session_command('import',path=str(context['actions'].destination),consent=True),
                cancel=self.show_sessions)
        def _start_saved_file(self,path):
            if self._call('start_file',path):self.home()

        def toggle_listening(self):
            if not self._running() and not self.controller._delivery_new_requested:
                self._notice='Choose Audio off or Processed in History before Start.'
                self.show_sessions();self._show_status();return
            if not self._running() and self.controller._delivery_attempted:
                self._notice='This recording is closed. Return to modes for another process.'
                self._show_status();return
            if context['runtime_profile']['selection']['input_kind']=='saved':
                if self._running():return self._call('stop')
                maximum=30 if context['runtime_profile']['selection']['engine_mode']=='streaming' else 120
                return self.keyboard('Prepared mono16k PCM16 WAV (up to '+str(maximum)+'s)',
                    str(Path.home()/'JustPeachy/data/'),self._start_saved_file,cancel=self.home)
            return super().toggle_listening()
        def _paragraph_label(self,parent,value,muted=False):
            if value.startswith('Archive ') or value.startswith('Private data '):
                value='One recording, up to 120 seconds. Stop releases capture. Save before full export; import restores the exported recording. Nothing is removed automatically.'
            elif value.startswith('No conversations yet'):
                value='Choose Audio off to keep text/events only, or Processed to save exact model-input audio with consent. Then press Start.'
            return super()._paragraph_label(parent,value,muted)
    return OperatorUI
