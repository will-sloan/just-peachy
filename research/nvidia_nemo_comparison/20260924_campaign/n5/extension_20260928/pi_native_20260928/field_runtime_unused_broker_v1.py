"""Preserve and close genuinely unused brokers; README_RUNTIME_UNUSED_BROKER_V1.md."""
import hashlib

PINS={
 'code/field_operator_health_v1.py':'b6cfc4de6c3281180179519f9f347c1d8e3569d3311e80ed97257e527351bd27',
 'code/field_runtime_journal_v3.py':'3ff6f58e33701f2d5b532a4aae81794d0e5b38552af7dbc927fe67ad4c765f37',
 'code/field_runtime_backup_v2.py':'2d1b2bacfe8c892b7df849df1a5f8843fbc9cff6b182851b1777e7ce4a8e4380',
}


def derive(modules):
    result=dict(modules)
    for name,pin in PINS.items():
        if type(result.get(name)) is not bytes or hashlib.sha256(result[name]).hexdigest()!=pin:
            raise ValueError('Exact previously installed source required')
    def change(name,old,new):
        text=result[name].decode()
        if text.count(old)!=1:raise ValueError('Changed reviewed closure boundary')
        text=text.replace(old,new);compile(text,name,'exec');result[name]=text.encode()
    name='code/field_operator_health_v1.py'
    change(name,"    status='CLOSED_HISTORY_AVAILABLE' if complete and quiescent and not gaps else 'FENCED_PRESERVED'",
"""    unused=bool(slots) and all(s['state']=='UNUSED' for s in slots)
    if unused and quiescent and not gaps:
        # An absent child is accepted only with every allocated child slot UNUSED,
        # an empty recordings parent and actual successful broker/gate closure.
        if any((root/'recordings').iterdir()):
            raise ValueError('Unused broker has unexpected recording bytes')
        broker=read(root/'broker/RESULT.json');gate=read(root/'broker/GATE_RESULT.json')
        if broker['status']!='BROKER_CLOSED' or broker['capture_closed'] is not True or broker['cleanup_errors']!=[]:
            raise ValueError('Actual unused broker closure')
        if any(gate.get(k) is not True for k in ('logical_success','capture_closed','worker_exact_dead','pipe_closed')) or gate['returncode']!=0:
            raise ValueError('Actual unused broker gate closure')
        if len(owners)!=3 or {x['path'] for x in owners}!={'broker/STAGE_OWNER.json','broker/GATE_OWNER.json','broker/OWNER.json'}:
            raise ValueError('Exactly three closed broker owners, no invented child')
    status=('CLOSED_UNUSED_BROKER' if unused and quiescent and not gaps else
            'CLOSED_HISTORY_AVAILABLE' if complete and quiescent and not gaps else 'FENCED_PRESERVED')""")
    name='code/field_runtime_journal_v3.py'
    change(name,"health['status']!='CLOSED_HISTORY_AVAILABLE'",
                "health['status'] not in ('CLOSED_HISTORY_AVAILABLE','CLOSED_UNUSED_BROKER')")
    change(name,"                   'broker/GATE_OWNER.json','slot-01/STARTED.json','slot-01/CLOSED.json')",
"""                   'broker/GATE_OWNER.json','broker/RESULT.json')
            unused=health['status']=='CLOSED_UNUSED_BROKER'
            if not unused:names+=('slot-01/STARTED.json','slot-01/CLOSED.json')""")
    change(name,"successful=True,capture_closed=True)",
                "successful=True,capture_closed=True,recording_created=not unused,disposition='CANCELLED_BEFORE_RECORDING' if unused else 'CLOSED_RECORDING')")
    name='code/field_runtime_backup_v2.py'
    change(name,"health['status']!='CLOSED_HISTORY_AVAILABLE'",
                "health['status'] not in ('CLOSED_HISTORY_AVAILABLE','CLOSED_UNUSED_BROKER')")
    if set(result)!=set(modules):raise ValueError('Original manager cardinality retained')
    return result
