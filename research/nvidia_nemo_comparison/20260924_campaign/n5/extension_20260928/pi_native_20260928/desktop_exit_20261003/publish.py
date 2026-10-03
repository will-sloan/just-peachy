"""Back up/publish the desktop-first change and refresh the small handoff; README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import ast,hashlib,io,json,os,shutil,time,zipfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
E=Path(__file__).parent
W=Path('G:/Just_Peachy_N1/20260924_campaign/worktree')
P=W/'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
C=P.parents[1]/'completion_20261001'
B=W.parent/'local/n5/research-extension-20260928/pi-native-20260928';D=B/'desktop-exit-20261003'
O=D/'publication-v2';O.mkdir()
now=datetime.now(timezone.utc);end=time.monotonic()+600;used=0;maximum=24*1024**2
sha=lambda r:hashlib.sha256(r).hexdigest()
enc=lambda v:(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def put(p,r,replace=False):
 global used
 assert time.monotonic()<end and len(r)<=2*1024**2 and used+len(r)<=maximum
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('wb' if replace else 'xb') as f:assert f.write(r)==len(r);f.flush();os.fsync(f.fileno())
 assert p.read_bytes()==r;used+=len(r)
def save(n,v):put(O/n,enc(v))
me=psutil.Process();save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
save('SCOPE.json',dict(issued_utc=now.isoformat(),expires_utc=(now+timedelta(seconds=600)).isoformat(),maximum_bytes=maximum,purpose='DESKTOP_EXIT_DOCUMENTATION_SOURCE_HANDOFF'))
for drive,floor in [('C:/',50),('G:/',75)]:assert shutil.disk_usage(drive).free>=floor*1024**3+maximum
r=json.loads((D/'reopen-v2/RESULT.json').read_bytes());smoke=r['desktop_exit']
assert smoke['status']=='EXIT_REOPEN_EXIT_DESKTOP_PASS' and smoke['autostart_disabled'] is True and smoke['capture_started'] is False
assert smoke['second_exit']['exact_owner_dead'] is True and smoke['final_manager_state']['MainPID']=='0'
assert json.loads((D/'reopen-v2/NATIVE_CLOSURE.json').read_bytes())['exact_pid_absent'] is True
installation=json.loads((B/'field-runtime-v28-install/RESULT.json').read_bytes())
policy=json.loads((B/'field-runtime-v28-install/RELEASE.json').read_bytes())
assert len(policy['profiles'])==10 and len(policy['allocation']['recording_slots'])==4
preserved=json.loads((B/'field-runtime-v27-preservation-desktop-v1/BACKUP.json').read_bytes())
assert preserved['status']=='COMPLETE_REBOOT_INTERRUPTED_MANAGER_PC_COPY' and preserved['verified_complete_stream_and_readback'] is True
plan=json.loads((D/'exit-reopen-v1/RETIREMENT_PLAN.json').read_bytes())
inspection=json.loads((D/'inspection-after-exit-v1/RESULT.json').read_bytes())
desktop={row['path'].rsplit('/',1)[-1]:row for row in inspection['desktop_startup_files'] if '/Desktop/' in row['path']}
assert len(desktop)==11 and all('field-runtime-v28-' in name for name in desktop)
for key,pin in plan['retained'].items():assert {k:desktop[key.split('/')[-1]][k] for k in ('bytes','sha256')}==pin
index=dict(schema='just-peachy.desktop-first-release.v1',observed_utc=r['utc'],release_id='field-runtime-v28',native_root=installation['root'],
 status='DESKTOP_IDLE_NORMAL_EXIT_AND_SHORTCUT_REOPEN_VERIFIED',startup='Desktop only; application login autostart disabled',
 exit_location='Main profile manager: Exit to desktop; return from recording screen first',
 profiles=list(sorted(policy['profiles'])),remaining_recording_slots=4,remaining_launch_slots=14,
 shared_motion_capsule_sha256='3383fa869e7357cfa7f9ef410be6dcb40972feb40cea7aebee9d71dd526e4d80',
 autostart_sha256=smoke['autostart_sha256'],rollback_also_preserves_disabled_autostart=True,
 validation=dict(shortcut_reopen=True,visible_exit_button=True,normal_exit=True,capture_started=False,models_executed=False,
 reboot_performed=False,physical_touch_tested=False,original_observer_timeout_preserved=True),
 evidence=dict(install=str(B/'field-runtime-v28-install'),old_runtime_preservation=str(B/'field-runtime-v27-preservation-desktop-v1'),
 first_observer=str(D/'exit-reopen-v1'),post_exit_readonly=str(D/'inspection-after-exit-v1'),reopen=str(D/'reopen-v2')),
 historical_motion_evidence='MOTION_RELEASE_INDEX.json; v27 recording/resource results remain historical, not new v28 tests',
 older_shortcuts_preserved=plan['destination'],retained_shortcuts=11,
 limitations=['Original finite recording/launch/duration limits remain','No new physical reboot/noisy-world/model-quality result'])
guide='''# Desktop startup and Exit

The current runtime is **field-runtime-v28**. The Pi is left at the desktop with
capture off. Login autostart is disabled, including the baseline startup copy
used by this release's rollback. Choose any of the ten current desktop profile
shortcuts to open the app idle; recording still requires New and Start.

To leave the application, press **Exit to desktop** at the bottom of the main
profile manager. From a recording screen, Stop, Save if wanted, Return to modes,
and close the recording broker first. Wait for the local backup to finish; Exit
refuses to close an active recording. Then select another shortcut as needed.

Exit and one actual shortcut reopening were verified on the Pi. The final state
is no manager process, capture closed and hardware/research leases free. All ten
shortcut targets were checked. No recording, model test or reboot was performed
for this edit. The disabled login entry was read back from disk; physical reboot
validation remains separate.

The former v27 session had been interrupted by a reboot. Its entire manager tree
and completed recording were copied and verified without fabricating an EXIT or
editing its journal. Eleven old desktop icons were backed up and preserved under
the v28 profiles directory. The desktop now has ten v28 profiles plus rollback.

The same mounted BMI270 and audio/model capsule is retained. Read MODE_GUIDE and
MOTION_GUIDE for backend choices and motion limitations. Four recording slots and
fourteen manager/helper launch slots remain after this UI check; existing 120s
microphone/Chunk52,30s saved Streaming and24h idle limits remain unchanged.

The older `renew_motion_runtime.py` wrapper predates desktop-first startup and
expects a Close label. Do not use it unchanged for v28. The desktop-aware installer
and previous-batch binder are in `desktop_exit_20261003`; its README documents the
executed one-time deployment. A future batch renewal must preserve the disabled
autostart and Exit button and use fresh version/owner/resource bindings. Never
replay the consumed v28 deployment commands or overwrite a closed runtime.

DESKTOP_RELEASE_INDEX.json identifies the current deployment and receipts.
DESKTOP_HANDOFF_RECEIPT.json identifies the refreshed small ChatGPT archive.
Older motion/model evidence and all previous archives remain preserved.
'''
changes={C/'DESKTOP_GUIDE.md':guide.encode(),C/'DESKTOP_RELEASE_INDEX.json':enc(index),P/'DESKTOP_FIRST_FINDINGS_V1.md':guide.encode()}
banner='''> Current October3 update: **v28, desktop-first startup**. Use the ten desktop
> shortcuts; choose **Exit to desktop** in the main manager to close normally.
> Four recording slots remain. See [DESKTOP_GUIDE.md](DESKTOP_GUIDE.md) and
> DESKTOP_RELEASE_INDEX.json. Earlier v27 measurements below remain historical.

'''
for name in ('START_HERE.md','MODE_GUIDE.md','FINAL_OPERATOR_GUIDE.md','INSTALL_HEALTH_AND_RECOVERY.md','CURRENT_RUNTIME_PROGRESS.md','CHATGPT_HANDOFF.md','PATHS_AND_BACKUPS.md','BACKEND_COMBINATIONS.md','OFFLINE_ACCEPTANCE.md','COMPLETION_PLAN.md','FINISH_CHECKLIST.md'):
 p=C/name;t=p.read_text(encoding='utf-8')
 if name in ('START_HERE.md','MODE_GUIDE.md','FINAL_OPERATOR_GUIDE.md','INSTALL_HEALTH_AND_RECOVERY.md'):
  t=t.replace('field-runtime-v27','field-runtime-v28').replace('version27 profile','version28 profile')
  t=t.replace('three recording slots remaining','four recording slots remaining').replace('three recording slots left','four recording slots left')
  t=t.replace('It was left idle, capture off, display 270,','It is left at the desktop, capture off, display 270,')
  t=t.replace('The Pi starts idle with capture off;','The Pi stays at the desktop after login; a shortcut opens the app idle with capture off;')
  t=t.replace('three remain after the motion integration recording','all four remain in v28; the motion integration recording is preserved in v27')
  if name=='START_HERE.md':
   t=t.replace('The changed shared integration passed one native','The retained v27 shared integration passed one native')
   t=t.replace('Use the new motion renewal command; the historical Refresh-JustPeachy wrapper\nand 91,554,957-byte v23 kit omit the new integration.','Follow DESKTOP_GUIDE for renewal limitations; older renewal wrappers do not preserve this desktop-first change. The 91,554,957-byte v23 kit omits motion.')
  if name=='MODE_GUIDE.md':
   start=t.index('```powershell',t.index('## Copy to the PC and renew')) if '```powershell' in t[t.index('## Copy to the PC and renew'):] else -1
   # Retain the documented offload command; replace only the old renewal subsection.
   line=t.index("& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./renew_motion_runtime.py")
   lo=t.rfind('\n',0,t.rfind('~~~',0,line));hi=t.index('## Mounted motion',line)
   t=t[:lo]+'\n\nDesktop-first renewal: see DESKTOP_GUIDE.md. Do not execute the older motion renewal wrapper unchanged; its launcher would restore automatic startup and its old Close-button selector is obsolete.\n\n'+t[hi:]
  if name=='INSTALL_HEALTH_AND_RECOVERY.md':
   lo=t.index('Use `renew_motion_runtime.py`');hi=t.index('The rollback shortcut',lo)
   t=t[:lo]+'Use DESKTOP_GUIDE.md for the current desktop-aware installer/binder and renewal constraints. The old renewal wrapper must not be replayed unchanged.\n\n'+t[hi:]
   t=t.replace('restores the baseline startup;','restores the backed-up baseline with login autostart still disabled;')
 first,rest=t.split('\n',1);changes[p]=(first+'\n\n'+banner+rest.lstrip('\n')).encode()
for p in (W/'DELIVERY_START_HERE.md',P/'MASTER_BACKEND_MODE_GUIDE.md',P/'STATUS.md'):
 t=p.read_text(encoding='utf-8');first,rest=t.split('\n',1)
 note='Current release: field-runtime-v28, desktop-first startup, verified normal Exit/reopen/Exit, capture off. Use completion_20261001/DESKTOP_GUIDE.md and DESKTOP_RELEASE_INDEX.json. Earlier v27 motion evidence remains historical.\n\n'
 changes[p]=(first+'\n\n'+note+rest.lstrip('\n')).encode()
for name in ('ACCEPTANCE.json','FINISH_CHECKLIST.json'):
 v=json.loads((C/name).read_bytes());v['as_of_utc']=now.isoformat();v['current_release']='field-runtime-v28'
 v['desktop_first_addendum']=index
 changes[C/name]=enc(v)
for source in sorted(E.glob('*')):
 if source.suffix not in ('.py','.md'):continue
 raw=source.read_bytes()
 if source.suffix=='.py':ast.parse(raw)
 changes[P/'desktop_exit_20261003'/source.name]=raw
before={}
for p,raw in changes.items():
 rel=p.relative_to(W).as_posix()
 if p.exists():
  old=p.read_bytes();put(O/'before-backup'/rel,old);put(O/'before-restore'/rel,old);before[rel]=dict(bytes=len(old),sha256=sha(old))
 put(O/'after-backup'/rel,raw);put(O/'after-restore'/rel,raw)
save('BEFORE_CLOSED.json',before)
for p,raw in changes.items():put(p,raw,replace=p.exists())
# Keep the previous curated handoff's source selections; replace current guides.
old_receipt=json.loads((C/'MOTION_HANDOFF_RECEIPT.json').read_bytes());old_zip=Path(old_receipt['path']).read_bytes()
assert sha(old_zip)==old_receipt['sha256'] and len(old_zip)==old_receipt['bytes']
with zipfile.ZipFile(io.BytesIO(old_zip)) as z:members={n:z.read(n) for n in z.namelist()}
for n in list(members):
 p=C/Path(n).name
 if p in changes:members[n]=changes[p]
 if Path(n).name in ('MOTION_HANDOFF_RECEIPT.json','DESKTOP_HANDOFF_RECEIPT.json'):del members[n]
members['DESKTOP_GUIDE.md']=guide.encode();members['DESKTOP_RELEASE_INDEX.json']=enc(index)
for p,raw in changes.items():
 if p.parent==P/'desktop_exit_20261003':members['desktop_exit_source/'+p.name]=raw
assert sum(map(len,members.values()))<10*1024**2
out=io.BytesIO()
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for n,raw in sorted(members.items()):z.writestr(n,raw)
archive=out.getvalue();assert len(archive)<20*1024**2
name='JustPeachy-desktop-v28-ChatGPT-handoff.zip'
put(O/name,archive);put(O/'independent-restore'/name,archive)
with zipfile.ZipFile(io.BytesIO((O/'independent-restore'/name).read_bytes())) as z:
 assert set(z.namelist())==set(members)
 for n,raw in members.items():
  assert z.read(n)==raw;put(O/'expanded-restore'/n,raw)
receipt=dict(schema='just-peachy.desktop-handoff.v1',path=str(O/name),bytes=len(archive),sha256=sha(archive),members=len(members),independent_zip_and_expanded_restore=True,complete_member_readback=True,private_audio_or_models=False,previous_receipt=old_receipt)
for name in ('DESKTOP_HANDOFF_RECEIPT.json','MOTION_HANDOFF_RECEIPT.json'):
 p=C/name;raw=enc(receipt)
 if p.exists():
  original=p.read_bytes();put(O/'before-backup'/p.relative_to(W),original);put(O/'before-restore'/p.relative_to(W),original)
 put(O/'after-backup'/p.relative_to(W),raw);put(O/'after-restore'/p.relative_to(W),raw);put(p,raw,replace=p.exists());changes[p]=raw
save('PUBLICATION.json',dict(files={p.relative_to(W).as_posix():dict(bytes=len(raw),sha256=sha(raw)) for p,raw in changes.items()},handoff=receipt,native_writes=False))
print(json.dumps(dict(files=len(changes),bytes=sum(map(len,changes.values())),handoff=str(O/'JustPeachy-desktop-v28-ChatGPT-handoff.zip'),publication_bytes=used)))
