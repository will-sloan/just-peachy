"""Native broker qualification component; README_FIELD_LOCAL_CAPSULE_V1.md."""
import hashlib
import json
import time
from field_operator_session_ledger_v4 import read
from field_operator_session_plan_v3 import state

CONTRACT=dict(schema='just-peachy.one-session-visible-qualification.v1',count=1,stop_after_samples=80000)
class Driver:
    def __init__(self,ui,config):
        if config.get('qualification')!=CONTRACT or ui.broker.ledger.plan['count']!=1:
            raise ValueError('Exact one-slot qualification')
        self.ui=ui;self.phase=0;self.done=False;self.started=time.monotonic()
        self.buttons=[];self.history=[];self.sessions=[];self.initial=list(ui.broker.ledger.plan['slot_names'])
    def invoke(self,name,widget):
        from d1_visible_controls_v2 import check_box
        root=self.ui.root;root.update_idletasks()
        if not root.winfo_viewable() or root.winfo_geometry()!='480x800+0+0' or str(widget.cget('state'))=='disabled':
            raise RuntimeError('Actual visible enabled chooser control required')
        bounds=check_box(root,widget)
        if len(self.buttons)>=8:raise ValueError('Chooser button cardinality')
        self.buttons.append(dict(control=name,bounds=bounds))
        widget.invoke()
        if self.ui.fault:raise RuntimeError(self.ui.fault)
        self.phase+=1
    def complete(self,count):
        b=self.ui.broker
        if b.current is not None or b.proc is not None:return False
        records=b.ledger.records()
        if any(state(records[n])!='CLOSED' for n in self.initial[:count]):return False
        if len(b.ledger.history())!=count:raise RuntimeError('Complete saved histories required')
        self.sessions=[]
        for slot in self.initial[:count]:
            root=b.ledger.root/'recordings'/slot
            value=read(root/'receipts/RESULT.json')
            if value['status']!='INTERACTIVE_RETURN_REQUESTED' or value.get('qualification',{}).get('complete') is not True or value.get('source_samples',0)<80000:
                raise RuntimeError('Actual saved capture child workflow missing')
            self.sessions.append(dict(slot=slot,owner=value['owner'],source_samples=value['source_samples'],
                child_qualification=value['qualification']))
        if count==2 and self.sessions[0]['owner']==self.sessions[1]['owner']:raise RuntimeError('Independent child processes required')
        return True
    def history_open(self,index):
        ui=self.ui
        ui.list.selection_clear(0,'end');ui.list.selection_set(index)
        self.invoke('history-'+ui.rows[index]['slot'],ui.open)
        value=ui.last_history
        if value['slot']!=ui.rows[index]['slot'] or value['read_only'] is not True:raise RuntimeError('Actual historical consumer')
        self.history.append(dict(value))
    def tick(self):
        if self.done:return
        if time.monotonic()-self.started>170:raise TimeoutError('One-session workflow')
        if self.phase==0:self.invoke('new-first',self.ui.new)
        elif self.phase==1:
            if self.complete(1):self.history_open(0)
        elif self.phase==2:
            if len(self.history)!=1 or len(self.sessions)!=1:raise RuntimeError('One-session evidence missing')
            self.invoke('close',self.ui.close_button);self.done=True
    def snapshot(self):
        return dict(schema=CONTRACT['schema'],complete=self.done,phase=self.phase,buttons=self.buttons,
            sessions=self.sessions,history=self.history,physical_touch_tested=False,
            native_accuracy_tested=False,automatic_explicit_button_driver=True)
