"""480x800 broker chooser; README_FIELD_OPERATOR_BROKER_V1.md."""
from field_operator_session_plan_v2 import next_slot

class Chooser:
    """UI wiring; prepare(root) must perform the separately admitted native stage.

    This adapter is deliberately not a CLI or installer. No production stage or
    resource admission is created by displaying the chooser.
    """
    def __init__(self,broker,prepare):
        import tkinter as tk
        if not callable(prepare):raise ValueError('Native staging boundary required')
        self.broker=broker;self.prepare=prepare;self.closed=False;self.fault=None
        self.root=tk.Tk(screenName=':0');self.root.withdraw();self.root.configure(bg='#111827')
        self.root.report_callback_exception=lambda kind,value,tb:self.fail(kind.__name__+': '+str(value))
        tk.Label(self.root,text='Just Peachy',font=('DejaVu Sans',24),bg='#111827',fg='white').pack(pady=12)
        tk.Label(self.root,text='Nemotron-3 Diarizer',font=('DejaVu Sans',16),bg='#111827',fg='white').pack()
        self.status=tk.Label(self.root,text='Capture is off',wraplength=440,bg='#111827',fg='white',font=('DejaVu Sans',12))
        self.status.pack(pady=10)
        self.new=tk.Button(self.root,text='New recording / Delayed',command=self.start,font=('DejaVu Sans',15),height=2)
        self.new.pack(fill='x',padx=12,pady=6)
        for label in ('Streaming / live unavailable','Chunk 52 / live unavailable'):
            tk.Button(self.root,text=label,state='disabled',font=('DejaVu Sans',12)).pack(fill='x',padx=12,pady=3)
        self.list=tk.Listbox(self.root,height=5,font=('DejaVu Sans',13),exportselection=False)
        self.list.pack(fill='x',padx=12,pady=6)
        self.open=tk.Button(self.root,text='Open saved history',command=self.open_selected,font=('DejaVu Sans',14),height=2)
        self.open.pack(fill='x',padx=12)
        self.text=tk.Text(self.root,height=9,wrap='word',font=('DejaVu Sans',12))
        self.text.pack(fill='both',expand=True,padx=12,pady=6);self.text.configure(state='disabled')
        tk.Button(self.root,text='Close',command=self.close,font=('DejaVu Sans',15),height=2).pack(fill='x',padx=12,pady=8)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh()
        from d1_visible_controls_v2 import visible
        visible(self.root)

    def refresh(self):
        self.rows=self.broker.ledger.history()
        self.list.delete(0,'end')
        for row in self.rows:self.list.insert('end',row['slot']+' / saved recording')
        try:next_slot(self.broker.ledger.plan,self.broker.ledger.records())
        except RuntimeError:self.new.configure(state='disabled')
        else:self.new.configure(state='normal')
        self.open.configure(state='normal' if self.rows else 'disabled')

    def start(self):
        if self.fault or self.broker.current is not None:return
        self.new.configure(state='disabled');self.open.configure(state='disabled')
        self.status.configure(text='Preparing an independent recording')
        root=self.broker.reserve()
        self.prepare(root)
        self.broker.accept_staged(root)
        self.root.withdraw()

    def open_selected(self):
        selected=self.list.curselection()
        if len(selected)!=1:raise ValueError('Select a saved recording')
        result=self.broker.open_history(self.rows[selected[0]]['slot'])
        metadata=result['metadata'];rows=result['rows']
        content=metadata.get('title','Saved recording')+'\n'
        content+='Stored captions: '+str(len(rows))+'\n\n'
        if not rows:content+='No caption rows were stored in this recording.'
        else:
            for row in rows:
                content+=str(row.get('final_formatted_text') or row.get('archived_final_formatted_text') or row.get('text',''))+'\n'
        self.text.configure(state='normal');self.text.delete('1.0','end')
        self.text.insert('1.0',content[:32768]);self.text.configure(state='disabled')
        self.status.configure(text='Saved history / capture is off')

    def fail(self,reason):
        self.broker.abort.set()  # Stop signal precedes UI diagnostics.
        self.broker.failed=True;self.fault=str(reason)[:1024]
        self.new.configure(state='disabled');self.open.configure(state='disabled')
        self.status.configure(text='Recording stopped: '+self.fault)

    def tick(self):
        if self.closed:return
        try:
            if not self.fault and self.broker.poll():
                self.refresh();self.root.deiconify()
                from d1_visible_controls_v2 import visible
                visible(self.root);self.status.configure(text='Recording process closed / capture is off')
        except BaseException as exc:self.fail(type(exc).__name__+': '+str(exc))
        self.root.update()

    def close(self):
        if self.broker.proc is not None and self.broker.proc.poll() is None:
            self.status.configure(text='Use Return in the recording screen first.');return
        self.broker.close();self.closed=True;self.root.destroy()
