"""Normal Exit of the exact failed-idle build26 GUI. README_FIRST_START_REPAIR.md."""
import hashlib,json,os,re,time
from pathlib import Path
PACKAGE='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-26'
PIN='f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0'
def closed(owner):
 if Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=owner['boot_id']:return True
 try:return int(Path('/proc',str(owner['pid']),'stat').read_text().rsplit(')',1)[1].split()[19])!=owner['start_ticks']
 except FileNotFoundError:return True
def run(payload,baseline):
 if payload.get('package_manifest_sha256')!=PIN or baseline['boot_id']!=payload['owner']['boot_id']:raise ValueError('Exact fresh package/boot')
 owner=payload['owner'];outer=payload['supervisor'];unit=payload['unit']
 if closed(owner) or closed(outer):raise ValueError('Current idle GUI must still match')
 expected={owner['pid'],outer['pid']}
 if {row['pid'] for row in baseline['current_project_processes']}!=expected:raise ValueError('Other app/worker must remain untouched')
 if hashlib.sha256(Path(PACKAGE,'PACKAGE_MANIFEST.json').read_bytes()).hexdigest()!=PIN:raise ValueError('Package drift')
 receipt=json.loads(Path(payload['unit_ownership']).read_bytes())
 if receipt['owner']!=owner or receipt['unit']!=unit:raise ValueError('Actual currentGUIunit')
 env=Path('/proc',str(owner['pid']),'environ').read_bytes()
 if len(env)>32768:raise ValueError('Bounded environment')
 values=dict(x.split(b'=',1) for x in env.split(b'\0') if b'=' in x)
 for key in ('DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR'):
  if key.encode() in values:os.environ[key]=values[key.encode()].decode()
 import tkinter as tk
 control=tk.Tk();control.withdraw()
 calls=0;reply_error=None
 try:
  matches=[]
  for app in control.tk.splitlist(control.tk.call('winfo','interps')):
   try:
    pid=int(control.tk.call('send',app,'pid'))
    if pid==owner['pid']:matches.append(app)
   except tk.TclError:pass
  if len(matches)!=1:raise ValueError('Exactly the current owned Tk interpreter')
  app=matches[0]
  def send(*args):return control.tk.call('send',app,*args)
  if not str(send('wm','title','.')).startswith('Just Peachy'):raise ValueError('Current portrait title')
  def buttons():
   todo=['.'];rows=[];count=0
   while todo:
    w=todo.pop();count+=1
    if count>512:raise ValueError('Bounded widget inventory')
    if str(send('winfo','class',w)) in ('Button','TButton'):rows.append((w,str(send(w,'cget','-text'))))
    todo.extend(control.tk.splitlist(send('winfo','children',w)))
   return rows
  exits=[w for w,text in buttons() if text=='Exit to desktop']
  if not exits:
   settings=[w for w,text in buttons() if text.lstrip('● ').strip()=='Settings']
   if len(settings)!=1:raise ValueError('Settings button ambiguous')
   send(settings[0],'invoke');send('update','idletasks')
   exits=[w for w,text in buttons() if text=='Exit to desktop']
  if len(exits)!=1 or closed(owner):raise ValueError('Normal Exit control missing')
  calls+=1
  try:send(exits[0],'invoke')
  except tk.TclError as error:reply_error=str(error)[:1024]
 finally:control.destroy()
 deadline=time.monotonic()+25
 while not (closed(owner) and closed(outer)):
  if time.monotonic()>deadline:raise TimeoutError('Normal Exit pending; no forced termination')
  time.sleep(.1)
 return dict(status='NORMAL_CURRENT_GUI_EXITED',owner=owner,supervisor=outer,exit_invocations=calls,reply_error=reply_error,exact_owners_gone=True,capture_started=False,firmware_command_sent=False,data_deleted=False)
if 'PAYLOAD' in globals():RESULT=run(PAYLOAD,BASELINE)

