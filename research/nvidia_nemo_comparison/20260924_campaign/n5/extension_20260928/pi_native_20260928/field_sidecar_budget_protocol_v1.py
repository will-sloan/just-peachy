"""Small sidecar boundary cases only; README_FIELD_SIDECAR_BUDGET_V1.md."""
import copy
import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path
from unittest.mock import patch
import field_sidecar_budget_v1 as caps
import field_dependencies_v2 as pins

def run(root,a):
    pins.configure_output(root,a['target_output_max_bytes'])
    plan=pins.read(root/'FIELD_WHOLE_RUN_ALLOCATION_V1.json')
    assert sum(plan['retained_component_maxima'].values())+sum(x['maximum_bytes'] for x in plan['sidecar_groups'].values())==plan['target_maximum_bytes']==76*1024**2
    assert plan['host_target_copy_maximum_bytes']==plan['target_maximum_bytes']
    assert plan['host_target_copy_maximum_bytes']+plan['host_metadata_maximum_bytes']==plan['host_maximum_bytes']==80*1024**2
    assert plan['combined_request_bytes']==plan['target_maximum_bytes']+plan['host_maximum_bytes']==156*1024**2
    assert not any(plan[k] for k in ['whole_run_integrated','capture_admitted','policy_changed'])
    for value in plan['sidecar_groups'].values():caps.validate(value)
    outcomes=[]
    fixture=root/'fixtures';fixture.mkdir()
    base=dict(maximum_bytes=128,maximum_file_bytes=96,maximum_files=4,maximum_write_bytes=96,minimum_free_bytes=5*1024**3)
    def fresh(name,**kw):
        d=fixture/name;d.mkdir();return caps.GroupWriter(d,{**base,**kw})
    def inventory(folder):
        return {x.name:(os.readlink(x) if x.is_symlink() else dict(bytes=x.stat().st_size,sha256=pins.sha(x))) for x in folder.iterdir()}
    def rejection(name,writer,call,error=caps.BudgetExceeded):
        before=inventory(writer.root)
        try:call()
        except error as exc:row=dict(case=name,rejected=True,error=type(exc).__name__+': '+str(exc),unchanged=inventory(writer.root)==before)
        else:raise AssertionError('Sidecar boundary accepted: '+name)
        assert row['unchanged'];pins.exclusive(root/(name+'-CASE.json'),row);outcomes.append(row)
    def passed(name,writer):
        row=dict(case=name,rejected=False,snapshot=writer.snapshot(),inventory=inventory(writer.root));pins.exclusive(root/(name+'-CASE.json'),row);outcomes.append(row)
    # Complete UTF8 bytes are measured before any write; no truncation.
    w=fresh('utf8');v={'value':'\u00e9\u6c49\\"'};raw=caps.encoded(v)
    w.json('control.json',v);assert (w.root/'control.json').read_bytes()==raw
    w.jsonl('trace.jsonl',v);assert (w.root/'trace.jsonl').read_bytes()==raw+b'\n'
    passed('utf8-exact',w)
    rejection('nonfinite',w,lambda:w.json('nan.json',{'x':float('nan')}),ValueError)
    rejection('write-limit',w,lambda:w.write('huge.bin',b'x'*97))
    w=fresh('file');w.write('one.log',b'a'*90,append=True)
    rejection('append-file-limit',w,lambda:w.write('one.log',b'b'*7,append=True))
    w=fresh('group');w.write('one.bin',b'a'*80)
    rejection('group-limit',w,lambda:w.write('two.bin',b'b'*49))
    rejection('replace-old-plus-temp',w,lambda:w.write('one.bin',b'b'*60,replace=True))
    w.write('one.bin',b'c'*40,replace=True);assert (w.root/'one.bin').read_bytes()==b'c'*40 and not list(w.root.glob('*.pending'))
    passed('replacement-committed',w)
    w=fresh('count',maximum_files=1);w.write('one.bin',b'a')
    rejection('file-count',w,lambda:w.write('two.bin',b'b'))
    rejection('flat-path',w,lambda:w.write('../escape',b'x'),ValueError)
    rejection('pending-name',w,lambda:w.write('input.pending',b'x'),ValueError)
    # Inject free-space return only; no physical disk exhaustion.
    w=fresh('floor');w.write('old.json',b'{}')
    with patch.object(caps.shutil,'disk_usage',return_value=type('Space',(),{'free':5*1024**3})()):
        rejection('free-floor-injected',w,lambda:w.write('new.json',b'{}'))
    w=fresh('busy');w.snapshot()
    with (w.root/'.budget.guard').open('r+b') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        rejection('busy-guard',w,lambda:w.write('new.json',b'{}'),BlockingIOError)
    w=fresh('nonregular');w.write('original.json',b'{}');real_stat=caps.os.stat
    def nonregular(path,*args,**kwargs):
        value=real_stat(path,*args,**kwargs)
        if path=='original.json' and kwargs.get('follow_symlinks') is False:
            fields=list(value);fields[0]=stat.S_IFLNK|0o777;return os.stat_result(fields)
        return value
    with patch.object(caps.os,'stat',side_effect=nonregular):
        rejection('nonregular-stat-injected',w,lambda:w.write('new.json',b'{}'),ValueError)
    # Retain a deliberate pending file from an injected mid-write failure.
    w=fresh('interrupted');w.write('old.json',b'old');real_write=caps.os.write
    def broken(fd,data):
        real_write(fd,bytes(data[:2]));raise OSError('injected write fault after two bytes')
    with patch.object(caps.os,'write',side_effect=broken):
        try:w.write('old.json',b'new value',replace=True)
        except OSError:pass
        else:raise AssertionError('Injected write did not fail')
    assert (w.root/'old.json').read_bytes()==b'old' and (w.root/'old.json.pending').read_bytes()==b'ne'
    passed('partial-temp-preserved',w)
    rejection('pending-blocks-retry',w,lambda:w.write('next.json',b'{}'))
    # Invalid policies create no group guard or files.
    for name,change in [('unknown-key',{'extra':1}),('bool-limit',{'maximum_bytes':True}),('wrong-floor',{'minimum_free_bytes':1}),('bad-order',{'maximum_write_bytes':97}),('overmax-files',{'maximum_files':129})]:
        d=fixture/name;d.mkdir();bad={**base,**change}
        pins.exclusive(root/(name+'-INPUT.json'),bad)
        try:caps.GroupWriter(d,bad)
        except ValueError as exc:row=dict(case=name,rejected=True,error=str(exc),unchanged=not list(d.iterdir()))
        else:raise AssertionError('Invalid policy accepted')
        assert row['unchanged'];pins.exclusive(root/(name+'-CASE.json'),row);outcomes.append(row)
    pins.exclusive(root/'SIDECAR_CASES.json',outcomes)
    return dict(status='PASS_NATIVE_SIDECAR_PREWRITE_BOUNDARIES_ONLY',cases=len(outcomes),rejections=sum(x['rejected'] for x in outcomes),
                models=False,capture=False,GUI=False,audio=False,controller=False,whole_run_integrated=False,capture_admitted=False,
                policy_changed=False,full_target_bytes=plan['target_maximum_bytes'],full_host_bytes=plan['host_maximum_bytes'],
                normal_and_failed_writes_preserved=True,ownership_closed=True)
