"""Prepare pinned desktop-first derivatives; see README.md. No Pi contact."""
import psutil
psutil.Process().cpu_affinity([14])
import ast, hashlib, json, os, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
E=Path(__file__).parent
H=E.parent/'imu_integration_20261002'
B=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
P=Path('G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928')
D=B/'desktop-exit-20261003'
def put(path,raw):
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    assert path.read_bytes()==raw
def enc(v):return json.dumps(v,sort_keys=True,indent=2).encode()
prep=D/('source-'+sys.argv[1]);prep.mkdir()
me=psutil.Process();put(prep/'REGISTERED_OWNER.json',enc(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
def replace(s,old,new):
    assert s.count(old)==1,(old[:120],s.count(old))
    return s.replace(old,new)
s=(H/'operator-tools-v1/preserve_runtime_batch_v1.py').read_text()
node=next(n for n in ast.parse(s).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='NATIVE' for t in n.targets))
n=ast.literal_eval(node.value)
if sys.argv[1]=='review-v3':
    for lo,hi in [(160,190),(260,340),(375,448)]:
        print('\n'.join(f'{i+1}: {v}' for i,v in enumerate(n.splitlines()) if lo<=i+1<=hi))
    sys.exit(0)
n=replace(n,"assert op['owner']==dict(pid=live_manager,start_ticks=ticks(live_manager),boot_id=boot)","assert op['owner']==strict((root/RID/'launches/launch-01/OWNER.json').read_bytes())['owner'] and op['owner']['boot_id']!=boot")
n=replace(n,"assert candidate_unit['ActiveState']=='active' and candidate_unit['SubState']=='running'\nassert len(alive_candidate)==1 and not allowed_live","assert RID=='field-runtime-v27'\nassert candidate_unit['ActiveState']=='inactive' and candidate_unit['MainPID']=='0'\nassert not alive_candidate and not allowed_live")
lo=n.index('manager_owner=alive_candidate[0]');hi=n.index('roots=[root/RID]',lo)
n=n[:lo]+"""manager_record=strict((root/RID/'launches/launch-01/OWNER.json').read_bytes())
assert manager_record['purpose']=='USER_RUNTIME_MANAGER' and manager_record['policy_sha256']==POLICY_SHA
manager_owner=identity(manager_record['owner'])
assert manager_owner['boot_id']!=boot
assert not (root/RID/'launches/launch-01/EXIT.json').exists()
exit_record=None
final_service=unit_state(unit)
assert final_service['MainPID']=='0' and final_service['ActiveState']=='inactive'
for p in Path('/proc/asound').glob('card*/pcm*c/sub*/status'):assert p.read_text().strip()=='closed'
print(json.dumps(dict(preservation_phase='REBOOT_INTERRUPTED_MANAGER_PRESERVED',owner=manager_owner,current_boot=boot)),file=sys.stderr,flush=True)
"""+n[hi:]
n=n.replace("assert ticks(manager_owner['pid'])!=manager_owner['start_ticks']","assert manager_owner['boot_id']!=boot")
n=n.replace('CLOSED_RUNTIME_BATCH_CENSUS','REBOOT_INTERRUPTED_RUNTIME_BATCH_CENSUS')
n=replace(n,'exact_manager_dead=True,service=final_service','manager_old_boot_only=True,service=final_service')
n=replace(n,"value['native_writes']='NORMAL_CLOSED_MANAGER_UI_CLOSE_AND_PINNED_ROLLBACK'","value['native_writes']=False")
n=replace(n,"requested=False\nif not first.exists():","requested=False\nassert first.exists(), 'Historical rollback only; no new rollback action'\nif not first.exists():")
n=replace(n,"assert ticks(rollback_owner['pid'])!=rollback_owner['start_ticks']","assert not (rollback_owner['boot_id']==boot and ticks(rollback_owner['pid'])==rollback_owner['start_ticks'])")
compile(n,'<reboot-preservation>','exec')
lines=s.splitlines(True);s=''.join(lines[:node.lineno-1])+'NATIVE='+repr(n)+'\n'+''.join(lines[node.end_lineno:])
s=s.replace("list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))","list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))+list((a.private/'desktop-exit-20261003').rglob('NATIVE_OWNER.json'))")
s=s.replace('normal_close_and_pinned_rollback=True','normal_close_and_pinned_rollback=False')
s=s.replace('native_writes="CLOSED_MANAGER_NORMAL_UI_CLOSE"','native_writes=False')
s=replace(s,"if not preserved['exact_manager_dead'] or preserved['status']!='CLOSED_RUNTIME_BATCH_CENSUS':","if preserved['manager_old_boot_only'] is not True or preserved['normal_manager_exit'] is not None or preserved['manager_owner']['boot_id']==who['boot_id'] or preserved['status']!='REBOOT_INTERRUPTED_RUNTIME_BATCH_CENSUS':")
s=s.replace('COMPLETE_CLOSED_RUNTIME_BATCH_PC_COPY','COMPLETE_REBOOT_INTERRUPTED_MANAGER_PC_COPY')
s=s.replace('native_utility_exact_absent=True,manager_exact_dead=True','native_utility_exact_absent=True,manager_old_boot_only=True')
bind=(H/'operator-tools-v1/bind_previous_mounted.py').read_text()
bind=replace(bind,"if backup['status'] not in ('COMPLETE_CLOSED_RUNTIME_BATCH_PC_COPY','COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY') or backup['manager_exact_dead'] is not True or backup['native_utility_exact_absent'] is not True or backup['verified_complete_stream_and_readback'] is not True:","interrupted=backup['status']=='COMPLETE_REBOOT_INTERRUPTED_MANAGER_PC_COPY'\n    if backup['status'] not in ('COMPLETE_CLOSED_RUNTIME_BATCH_PC_COPY','COMPLETE_FAILED_SOURCE_AND_MANAGER_PC_COPY','COMPLETE_REBOOT_INTERRUPTED_MANAGER_PC_COPY') or backup.get('manager_old_boot_only' if interrupted else 'manager_exact_dead') is not True or backup['native_utility_exact_absent'] is not True or backup['verified_complete_stream_and_readback'] is not True:")
bind=replace(bind,"    failed_previous=backup['status']", "    if interrupted:\n        proof=read(preservation/'RESULT.json');p=proof['preservation']\n        if rid!='field-runtime-v27' or p['status']!='REBOOT_INTERRUPTED_RUNTIME_BATCH_CENSUS' or p['normal_manager_exit'] is not None or p['manager_owner']['boot_id']==proof['utility_owner']['boot_id'] or backup['recording_success'] is not True:\n            raise ValueError('Exact interrupted old-boot manager preservation')\n        if (preservation/'tree'/rid/'launches/launch-01/EXIT.json').exists():raise ValueError('Do not invent an exit for interrupted manager')\n    failed_previous=backup['status']")
outputs={'preserve_interrupted.py':s,'bind_previous_mounted.py':bind}
for name in ('inspect_deployment.py','install_mounted_runtime.py'):
    t=(H/'operator-tools-v1'/name).read_text()
    t=t.replace(repr(str(H/'deployment-tools-v5')),repr(str(E)))
    # Windows literal in old source uses doubled separators.
    t=t.replace("'C:\\\\Users\\\\amiri\\\\Documents\\\\GitHub\\\\just-peachy\\\\Resumes\\\\imu_integration_20261002\\\\deployment-tools-v5'",repr(str(E)))
    t=t.replace("list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))","list((a.private/'imu-integration-20261002').rglob('NATIVE_OWNER.json'))+list((a.private/'desktop-exit-20261003').rglob('NATIVE_OWNER.json'))")
    if name=='install_mounted_runtime.py':
        t=replace(t,'    manager=derive_manager(manager)','''    manager=derive_manager(manager)
    key='code/field_runtime_manager_v11.py'
    old=b"self.exit=tk.Button(self.ui,text='Close',command=self.close"
    assert manager[key].count(old)==1
    manager[key]=manager[key].replace(old,b"self.exit=tk.Button(self.ui,text='Exit to desktop',command=self.close")
    compile(manager[key],key,'exec')
    renderer=source_bytes['prepare_runtime_activation_v8.py']
    old=b"files['autostart/just-peachy.desktop']=files['desktop/d1-delayed.desktop']"
    assert renderer.count(old)==1
    renderer=renderer.replace(old,b"files['autostart/just-peachy.desktop']=files['desktop/d1-delayed.desktop']+b'Hidden=true\\\\nX-GNOME-Autostart-enabled=false\\\\n'")
    compile(renderer,'<desktop-first-renderer>','exec')
    source_bytes['prepare_runtime_activation_v8.py']=renderer''')
    outputs[name]=t
for name,source in outputs.items():
    raw=source.encode();compile(raw,name,'exec')
    put(E/name,raw);put(prep/(name+'.backup'),raw);put(prep/(name+'.restore'),raw)
for name in ('prepare.py','README.md'):
    raw=(E/name).read_bytes();put(prep/(name+'.backup'),raw);put(prep/(name+'.restore'),raw)
put(prep/'SOURCE_CLOSED.json',enc(dict(utc=datetime.now(timezone.utc).isoformat(),files={n:dict(bytes=len(t.encode()),sha256=hashlib.sha256(t.encode()).hexdigest()) for n,t in outputs.items()},native_executed=False)))
print(json.dumps({'prepared':list(outputs),'backup':str(prep)}))
