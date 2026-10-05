"""Prepare a narrow manual-lifetime idle check. See README_MANUAL_IDLE_CHECK.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast
import hashlib
import json
import os
from pathlib import Path
import time
import uuid


def main():
    here=Path(__file__).resolve().parent
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    out=private/'audit-preparation'/('manual-idle-source-'+uuid.uuid4().hex);out.mkdir()
    me=psutil.Process();started=time.time()
    def write(name,raw):
        with (out/name).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        assert (out/name).read_bytes()==raw
    def put(name,value):write(name,json.dumps(value,sort_keys=True,allow_nan=False).encode())
    put('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    put('HOST_SCOPE.json',dict(issued_unix=started,maximum_seconds=600,maximum_bytes=2*1024**2,native_action=False))
    raw=(here.parent/'launch_production_idle_action_v2.py').read_bytes()
    tree=ast.parse(raw)
    assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONTROL_SOURCE' for t in n.targets))
    control=ast.literal_eval(assignment.value)
    old="receipt['runtime_max_seconds']!=7200"
    new="receipt['runtime_max_seconds'] is not None or receipt.get('deadline_monotonic') is not None\n            or receipt.get('lifetime_policy')!='manual_stop_storage_guarded'"
    assert control.count(old)==1
    changed=control.replace(old,new).replace('Actual standard production7200-second nested unit differs','Actual manual-Stop guarded production unit differs')
    def once(text,before,after):
        assert text.count(before)==1, before
        return text.replace(before,after)
    changes={
        "folders=list(owners.iterdir())":"folders=[p for p in owners.iterdir() if p.name not in request['prior_owner_names']]",
        "scope.duration_seconds(state['RuntimeMaxUSec'])!=7200":"state['RuntimeMaxUSec']!='infinity'",
        "production_scope_runtime_seconds=7200":"production_scope_runtime_seconds=None,lifetime_policy='manual_stop_storage_guarded'",
        "if text in ('Start','Exit to desktop')":"if text in ('OK · open application','Exit to desktop')",
        "if text=='Start'":"if text=='OK · open application'",
        "send(start[0],'state','disabled')":"send(start[0],'configure','-state','disabled')",
        "if not int(send(start[0],'instate','disabled'))":"if str(send(start[0],'cget','-state'))!='disabled'",
        "if base.exists() and (not base.is_dir() or next(base.iterdir(),None) is not None):":"if base.exists() and (base.is_symlink() or not base.is_dir()):",
        "if list((Path(request['data_root'])/'launches').iterdir()):":"if any(p.name not in request['prior_launch_names'] for p in (Path(request['data_root'])/'launches').iterdir()):",
        "worker_records=len(list((base/'launches').iterdir())) if (base/'launches').is_dir() else None":"worker_records=len([p for p in (base/'launches').iterdir() if p.name not in request['prior_launch_names']]) if (base/'launches').is_dir() else 0\n    base=registration['root'] if registration else out/'absent-owner'\n    if registration:\n        mirror=mirror/'unit-owners'/base.name;mirror.mkdir(parents=True)"}
    for before,after in changes.items():changed=once(changed,before,after)
    fn=next(n for n in ast.parse(changed).body if isinstance(n,ast.FunctionDef) and n.name=='inspect_optional_policy')
    replacement='''def inspect_optional_policy(send, splitlist, start):
    """Read the real chooser; never open model/capture workers."""
    if str(send(start,'cget','-state'))!='disabled':raise ValueError('Chooser launch must remain disabled')
    todo=['.'];widgets=[]
    while todo:
        widget=todo.pop();widgets.append((widget,str(send('winfo','class',widget))))
        if len(widgets)>512:raise ValueError('Bounded chooser widgets')
        todo.extend(splitlist(send('winfo','children',widget)))
    boxes=[w for w,k in widgets if k=='Listbox'];sources=[w for w,k in widgets if k=='TCombobox']
    if len(boxes)!=1 or len(sources)!=1:raise ValueError('Actual single backend/source chooser required')
    labels=tuple(splitlist(send(boxes[0],'get',0,'end')))
    required={'Pyannote + ReDimNet','Pyannote + NeMo TitaNet','Pyannote + Anonymous','Nemotron Delayed + ReDimNet','Nemotron Delayed + TitaNet','Nemotron Delayed + Anonymous','Nemotron Chunk52 + ReDimNet ◇'}
    if not required.issubset(labels) or not 30<=len(labels)<=256:raise ValueError('Retained backend variants missing')
    if tuple(splitlist(send(sources[0],'cget','-values')))!=('live','saved') or str(send(sources[0],'get'))!='live':raise ValueError('Independent Live/Saved selector required')
    return dict(actual_controls=True,profile_count=len(labels),source_choices=['live','saved'],model_or_capture_worker_started=False,optional_refiner_promoted=False)
'''
    control_lines=changed.splitlines(keepends=True);control_lines[fn.lineno-1:fn.end_lineno]=[replacement]
    changed=''.join(control_lines)
    compile(changed,'<manual-stop-idle-control>','exec')
    text=raw.decode();lines=text.splitlines(keepends=True)
    assert assignment.end_lineno==assignment.lineno
    lines[assignment.lineno-1]='CONTROL_SOURCE = '+repr(changed)+'\n'
    result=''.join(lines)
    result=once(result,"if data_root.exists() and (not data_root.is_dir() or next(data_root.iterdir(),None) is not None):", "if data_root.exists() and (data_root.is_symlink() or not data_root.is_dir()):")
    result=once(result,"    out.mkdir();put=helper['put']", "    prior_owners=sorted(p.name for p in (data_root/'unit-owners').iterdir()) if (data_root/'unit-owners').exists() else []\n    prior_launches=sorted(p.name for p in (data_root/'launches').iterdir()) if (data_root/'launches').exists() else []\n    if len(prior_owners)>256 or len(prior_launches)>4096:raise ValueError('Bounded existing runtime metadata')\n    out.mkdir();put=helper['put']")
    result=once(result,"data_root_precondition='absent_or_empty'", "data_root_precondition='preserved_existing_store',prior_owner_names=prior_owners,prior_launch_names=prior_launches")
    result=result.encode();compile(result,'<manual-stop-idle-action>','exec')
    before={n.name:ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)}
    after={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(result).body if isinstance(n,ast.FunctionDef)}
    assert set(before)==set(after) and {n for n in before if before[n]!=after[n]}=={'dispatch'}
    for name,value in [('ORIGINAL.py',raw),('CONTROL_ORIGINAL.py',control.encode()),('CONTROL_CHANGED.py',changed.encode()),('ACTION.py',result),('ACTION.restore.py',result),('README.md',(here/'README_MANUAL_IDLE_CHECK.md').read_bytes()),('PREPARER.py',Path(__file__).read_bytes())]:write(name,value)
    target=here/'launch_manual_idle_action_v2.py'
    with target.open('xb') as stream:stream.write(result);stream.flush();os.fsync(stream.fileno())
    assert target.read_bytes()==result
    assert sum(p.stat().st_size for p in out.iterdir())<2*1024**2 and time.time()-started<600
    put('SOURCE_CLOSED.json',dict(independent_restore=True,original_sha256=hashlib.sha256(raw).hexdigest(),new_sha256=hashlib.sha256(result).hexdigest(),native_action=False,changed_outer_functions=['dispatch'],existing_data_preserved=True,closed_unix=time.time()))
    print(json.dumps(dict(status='PASS',output=str(out),target=str(target))))


if __name__=='__main__':main()
