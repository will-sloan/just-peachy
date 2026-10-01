"""Native broker qualification component; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V1.md."""
import time

CONTRACT={'schema':'just-peachy.operator-session-qualification.v1','stop_after_samples':80000}

class Driver:
    def __init__(self,root,ui,controller,context,admission):
        if admission.get('qualification')!=CONTRACT:
            raise ValueError('Exact bounded qualification contract required')
        self.root=root;self.ui=ui;self.controller=controller;self.context=context
        self.phase=0;self.buttons=[];self.started=time.monotonic();self.source=None
        self.done=False;self.stop_samples=None
    def invoke(self,key=None,text=None):
        from d1_visible_controls_v2 import check_box
        import tkinter as tk
        self.root.update_idletasks()
        if key is not None:
            widget=self.ui.actions[key]
        else:
            def walk(w):
                for child in w.winfo_children():
                    yield child
                    yield from walk(child)
            matches=[w for w in walk(self.root) if isinstance(w,tk.Button) and str(w.cget('text')).startswith(text)]
            if len(matches)!=1:raise RuntimeError('Exact real button not found: '+str(text))
            widget=matches[0]
        if str(widget.cget('state'))=='disabled':raise RuntimeError('Required real button disabled')
        canvas=widget.master
        while canvas is not None and not isinstance(canvas,tk.Canvas):canvas=getattr(canvas,'master',None)
        if canvas is not None:
            for _ in range(5):
                self.root.update_idletasks()
                top=widget.winfo_rooty()-canvas.winfo_rooty()
                if top>=0 and top+widget.winfo_height()<=canvas.winfo_height():break
                box=canvas.bbox('all')
                if not box:raise RuntimeError('Missing scroll extent')
                canvas.yview_moveto(max(0,(canvas.canvasy(top)-8)/box[3]))
            self.root.update_idletasks()
            top=widget.winfo_rooty()-canvas.winfo_rooty()
            if top<0 or top+widget.winfo_height()>canvas.winfo_height():
                raise RuntimeError('Control clipped by scroll viewport')
        bounds=check_box(self.root,widget)
        if len(self.buttons)>=20:raise RuntimeError('Button receipt cardinality')
        self.buttons.append(dict(control=key or text,bounds=bounds))
        widget.invoke()
        self.phase+=1
    def tick(self):
        if self.done:return
        if time.monotonic()-self.started>180:raise TimeoutError('Qualification workflow deadline')
        c=self.controller;actions=self.context['actions']
        if c.commands.unfinished_tasks:return
        self.ui.poll()
        if self.phase==0:self.invoke('new_audio')
        elif self.phase==1:self.invoke('confirm')
        elif self.phase==2:
            if not c.conversation_id or not c._delivery_new_requested:return
            self.ui.home();self.invoke('start_stop')
        elif self.phase==3:self.invoke('confirm')
        elif self.phase==4:
            if c.state!='RUNNING' or c.engine is None:return
            self.source=getattr(c.engine,'_source',None)
            if self.source is None or self.source.sent<CONTRACT['stop_after_samples']:return
            self.stop_samples=self.source.sent
            self.ui.home();self.invoke('start_stop')
        elif self.phase==5:
            if c.engine is not None or c.archive is not None:return
            self.ui.show_sessions();self.invoke('save_session')
        elif self.phase==6:
            if actions.counts.get('save')!=1:return
            if self.source is None or self.source.thread.is_alive():raise RuntimeError('Source remains before Return')
            self.invoke('operator_return');self.done=True
    def snapshot(self):
        return dict(schema=CONTRACT['schema'],complete=self.done,phase=self.phase,
                    stop_requested_at_samples=self.stop_samples,buttons=self.buttons,
                    real_control_invocations=len(self.buttons),physical_touch_tested=False)
