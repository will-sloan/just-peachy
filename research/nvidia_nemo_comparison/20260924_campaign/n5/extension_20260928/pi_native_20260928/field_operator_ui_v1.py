"""Actual installed interactive FieldUI derivative; README_FIELD_OPERATOR_V2.md."""
import ast
from pathlib import Path

def ui_class(entry,prototype,context,request_return):
    tree=ast.parse(Path(entry.__file__).read_bytes())
    nodes=[n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='FieldUI']
    if len(nodes)!=1:raise ValueError('Installed FieldUI shape changed')
    env=dict(entry.__dict__,PrototypeUI=prototype)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),
                 str(entry.__file__)+':operator-field-ui','exec'),env)
    class OperatorUI(env['FieldUI']):
        def button(self,parent,text,command,*args,**kwargs):
            # These old controls have no admitted writers/actions in this child.
            unavailable=('New transcript Â· text only','Rename','Add note',
                'Export text and user annotations','Choose listening output',
                'Mark problem','Listening output','Review this utterance',
                'Listen to this interval','User correction','Undo this correction')
            blocked=any(str(text).startswith(x) for x in unavailable)
            if blocked:
                text=str(text)+' Â· unavailable'
                command=lambda:None
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
        def _show_status(self):
            super()._show_status()
            self.preview_label.configure(text='Nemotron-3 Diarizer / Delayed')
        def close(self):
            # Main loop owns Stop/Close/join/Tk destruction. Never join in a callback.
            request_return('OPERATOR_RETURN')
        def _call(self,name,*args,**kwargs):
            if name not in ('session_action','start_live','stop','close','select_backend','switch'):
                self._notice='Unavailable in this recording process.'
                self._show_status()
                return False
            return super()._call(name,*args,**kwargs)
        def _session_command(self,action,**values):
            try:
                if action=='new':
                    if self.controller._delivery_new_requested or self.controller._delivery_attempted:
                        raise ValueError('Return to modes before creating another recording.')
                    if values.get('audio') is not True or values.get('consent') is not True:
                        raise ValueError('Create a consented audio draft.')
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
                self._notice='Only a complete audio archive is available.'
                self._show_status();return
            destination=str(context['actions'].destination)
            self.confirm('Export private recording?',
                'This local ZIP contains the complete recording and its labels. It stays unencrypted on this device.',
                'I consent Â· Export',
                lambda:self._session_command('export',identifier=identifier,path=destination,audio=True,consent=True),
                cancel=lambda:self.show_session(identifier))
        def _import_archive(self):
            self.confirm('Restore exported recording?',
                'Restore this process exported recording into its original ID. Existing recordings are never overwritten.',
                'Import recording',
                lambda:self._session_command('import',path=str(context['actions'].destination),consent=True),
                cancel=self.show_sessions)
        def toggle_listening(self):
            if not self._running() and not self.controller._delivery_new_requested:
                self._notice='Create an audio draft in History before Start.'
                self.show_sessions();self._show_status();return
            if not self._running() and self.controller._delivery_attempted:
                self._notice='This recording is closed. Return to modes for another process.'
                self._show_status();return
            return super().toggle_listening()
        def _paragraph_label(self,parent,value,muted=False):
            if value.startswith('Archive ') or value.startswith('Private data '):
                value='One recording, up to 120 seconds. Stop releases capture. Save before full export; import restores the exported recording. Nothing is removed automatically.'
            elif value.startswith('No conversations yet'):
                value='Create an audio draft, then press Start. Recording needs explicit consent.'
            return super()._paragraph_label(parent,value,muted)
    return OperatorUI
