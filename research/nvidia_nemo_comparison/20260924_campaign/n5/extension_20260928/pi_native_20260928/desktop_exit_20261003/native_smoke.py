# Injected bounded native fragment. See README.md; not a standalone CLI.
import shlex,time,tkinter as tk
assert RID=='field-runtime-v28' and len(alive_candidate)==1 and not current_operations
auto=home/'.config/autostart/just-peachy.desktop'
automatic=auto.read_bytes()
assert b'\nHidden=true\n' in automatic and b'\nX-GNOME-Autostart-enabled=false\n' in automatic
assert automatic==(profiles/'autostart/just-peachy.desktop').read_bytes()
rollback_original=(root/(RID+'-activation')/'backup/autostart.desktop').read_bytes()
assert b'Hidden=true' in rollback_original and b'X-GNOME-Autostart-enabled=false' in rollback_original
shortcuts={}
for profile in runtime_policy['profiles']:
 path=home/'Desktop'/('just-peachy-'+RID+'-'+profile+'.desktop')
 raw=path.read_bytes();assert raw==(profiles/'desktop'/(profile+'.desktop')).read_bytes()
 assert b'Hidden=true' not in raw
 line=next(line for line in raw.decode().splitlines() if line.startswith('Exec='))
 argv=shlex.split(line[5:]);assert argv==[str(profiles/'bin/launch-profile'),'--profile',profile]
 shortcuts[profile]=dict(sha256=sha(raw),argv=argv)
assert len(shortcuts)==10
control=tk.Tk();control.withdraw()
rows_script='set todo [list .];set rows {};while {[llength $todo]} {set w [lindex $todo 0];set todo [lrange $todo 1 end];foreach c [winfo children $w] {lappend todo $c;if {[winfo class $c] eq "Button"} {lappend rows [list $c [$c cget -text] [$c cget -state] [winfo viewable $c]]}}};return $rows'
def close_idle(owner):
 assert owner['boot_id']==boot and ticks(owner['pid'])==owner['start_ticks']
 matches=[]
 for app in control.tk.splitlist(control.tk.call('winfo','interps')):
  if app==control.tk.call('tk','appname'):continue
  if int(control.tk.call('send',app,'pid'))==owner['pid']:matches.append(app)
 assert len(matches)==1
 app=matches[0]
 rows=[control.tk.splitlist(r) for r in control.tk.splitlist(control.tk.call('send',app,('apply',('',rows_script))))]
 buttons=[r for r in rows if r[1]=='Exit to desktop' and r[2]=='normal' and str(r[3])=='1']
 assert len(buttons)==1
 assert any(r[1]=='New recording' and r[2]=='normal' for r in rows)
 assert all(p.read_text().strip()=='closed' for p in Path('/proc/asound').glob('card*/pcm*c/sub*/status'))
 geometry=str(control.tk.call('send',app,('wm','geometry','.')))
 control.tk.call('send','-async',app,(buttons[0][0],'invoke'))
 end=time.monotonic()+15
 while ticks(owner['pid'])==owner['start_ticks']:
  assert time.monotonic()<end,'Normal exit timeout';time.sleep(.05)
 service=unit_state(unit)
 assert service['MainPID']=='0' and service['ActiveState']=='inactive' and service['ExecMainStatus']=='0'
 records=[p.parent for p in (root/RID/'launches').glob('*/OWNER.json') if strict(p.read_bytes())['owner']==owner]
 assert len(records)==1
 exit_record=strict((records[0]/'EXIT.json').read_bytes())
 assert exit_record['owner']==owner and exit_record['status']=='IDLE_CAPTURE_OFF' and exit_record['exit_is_intent'] is True
 assert not (records[0]/'FAILURE.json').exists()
 return dict(owner=owner,geometry=geometry,button='Exit to desktop',natural_unit_exit=service,exact_owner_dead=True,exit=exit_record)
try:
 first_exit=close_idle(manager)
 # One actual shortcut reopen proves the closed journal remains usable.
 launched=command(shortcuts['d1-delayed']['argv']);assert launched['returncode']==0
 end=time.monotonic()+15
 while True:
  service=unit_state(unit);pid=int(service['MainPID'])
  if pid>0 and service['ActiveState']=='active':
   match=[p for p in (root/RID/'launches').glob('*/OWNER.json') if strict(p.read_bytes())['owner'].get('pid')==pid and strict(p.read_bytes())['owner'].get('boot_id')==boot]
   if len(match)==1:
    owner=identity(strict(match[0].read_bytes())['owner'])
    # Wait for the visible Exit control, not only process creation.
    ready=False
    for app in control.tk.splitlist(control.tk.call('winfo','interps')):
     if app==control.tk.call('tk','appname'):continue
     if int(control.tk.call('send',app,'pid'))!=pid:continue
     rows=[control.tk.splitlist(r) for r in control.tk.splitlist(control.tk.call('send',app,('apply',('',rows_script))))]
     ready=any(r[1]=='Exit to desktop' and str(r[3])=='1' for r in rows)
    if ready:break
  assert time.monotonic()<end,'Shortcut reopen timeout';time.sleep(.1)
 assert owner!=manager
 second_exit=close_idle(owner)
finally:control.destroy()
assert auto.read_bytes()==automatic
assert all(p.read_text().strip()=='closed' for p in Path('/proc/asound').glob('card*/pcm*c/sub*/status'))
for lock in (root/'B05_PREVIEW_DISPATCH.lock',home/'JustPeachy/data/xvf-hardware.lock'):
 with lock.open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not any((root/RID/'recordings').glob('*/*.json'))
smoke_result=dict(status='EXIT_REOPEN_EXIT_DESKTOP_PASS',first_exit=first_exit,second_exit=second_exit,shortcuts=shortcuts,
 autostart_sha256=sha(automatic),autostart_disabled=True,rollback_autostart_disabled=True,
 capture_started=False,recordings_created=0,final_manager_state=unit_state(unit),reboot_tested=False)
