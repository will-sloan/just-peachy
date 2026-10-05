"""Normal Exit of one verified idle build17 app, never TERM/KILL. See README.md."""
import os
from pathlib import Path
import subprocess
import time

bound = BASELINE['bound_idle_gui']
receipt = bound['receipt']
owner = receipt['owner']
def ticks(pid):
    try: return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError: return None
def exact():
    if ticks(owner['pid']) != owner['start_ticks']:
        raise ValueError('Exact idle GUI changed before its normal Exit')
exact()
raw = Path('/proc',str(owner['pid']),'environ').read_bytes()
if len(raw)>65536: raise ValueError('Bounded GUI environment required')
env = dict(item.decode().split('=',1) for item in raw.split(b'\0') if b'=' in item)
for key in ('DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR'):
    if key in env: os.environ[key] = env[key]
import tkinter as tk
control = tk.Tk(); control.withdraw()
matches=[]
for interpreter in control.tk.splitlist(control.tk.call('winfo','interps')):
    if len(matches)>1: raise ValueError('Unique exact GUI interpreter required')
    try: pid=int(control.tk.call('send',interpreter,'pid'))
    except tk.TclError: continue
    if pid==owner['pid']: matches.append(interpreter)
if len(matches)!=1: raise ValueError('Normal Exit requires the exact actual Tk app')
app=matches[0]
def send(*args):
    exact()
    return control.tk.call('send',app,control.tk.call('list',*args))
title=str(send('wm','title','.'))
if not title.startswith('Just Peachy'): raise ValueError('Expected actual application window')
callback=str(send('wm','protocol','.','WM_DELETE_WINDOW'))
if not callback or len(callback)>256: raise ValueError('Normal application Close callback required')
send(callback)
deadline=time.monotonic()+20
while ticks(owner['pid'])==owner['start_ticks'] and time.monotonic()<deadline:
    time.sleep(.1)
closed=ticks(owner['pid'])!=owner['start_ticks']
control.destroy()
if not closed: raise TimeoutError('Normal GUI Exit did not close; no termination attempted')
state=subprocess.run(['systemctl','--user','show',receipt['unit'],'-p','ActiveState','-p','MainPID','-p','ExecMainStatus'],capture_output=True,text=True,timeout=5)
if state.returncode not in (0,1) or len(state.stdout)>8192: raise RuntimeError('Bounded final unit properties')
properties=dict(line.split('=',1) for line in state.stdout.splitlines())
if properties['MainPID']!='0' or properties['ActiveState'] not in ('inactive','failed'):
    raise RuntimeError('Normal app service remains owned')
RESULT=dict(status='NORMAL_IDLE_GUI_EXIT',owner=owner,title=title,unit=receipt['unit'],
    exact_gui_absent=True,unit_properties=properties,term_sent=False,kill_sent=False,
    capture_started=False,files_changed=False,outside_owner=bound['outside_owner'])
