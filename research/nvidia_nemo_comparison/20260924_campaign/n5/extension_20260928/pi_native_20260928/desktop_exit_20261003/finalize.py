"""Reconcile the renewal wording and final handoff/index before Git; README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import hashlib,io,json,os,zipfile
from pathlib import Path
E=Path(__file__).parent;W=Path('G:/Just_Peachy_N1/20260924_campaign/worktree')
P=W/'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928';C=P.parents[1]/'completion_20261001'
D=W.parent/'local/n5/research-extension-20260928/pi-native-20260928/desktop-exit-20261003'
O=D/'final-review-v1';O.mkdir()
sha=lambda r:hashlib.sha256(r).hexdigest()
enc=lambda v:(json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
used=0
def put(p,r,replace=False):
 global used
 assert used+len(r)<16*1024**2 and len(r)<2*1024**2
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('wb' if replace else 'xb') as f:assert f.write(r)==len(r);f.flush();os.fsync(f.fileno())
 assert p.read_bytes()==r;used+=len(r)
me=psutil.Process();put(O/'REGISTERED_OWNER.json',enc(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
publication=json.loads((D/'publication-v2/PUBLICATION.json').read_bytes());files=publication['files']
changes={}
p=C/'MODE_GUIDE.md';t=p.read_text(encoding='utf-8')
t=t.replace('After exhaustion use the explicit PC batch-refresh command below.','After exhaustion follow the desktop-aware renewal requirements below.')
t=t.replace('For a fresh batch, after Stop/Save/Return/broker Close and local backup, use\nthe new motion-preserving wrapper. The old Refresh-JustPeachy reconstructs v23\nand omits this integration. From the host motion directory:\n\n\n','For a fresh batch, preserve completed recordings and local backups first.\n')
changes[p]=t.encode()
p=C/'START_HERE.md';changes[p]=p.read_text(encoding='utf-8').replace('**The prepared CM5 now runs field-runtime-v28 with mounted BMI270 integration.**','**The prepared CM5 has field-runtime-v28 installed with mounted BMI270 integration.**').encode()
for name in ('finalize.py','README.md'):changes[P/'desktop_exit_20261003'/name]=(E/name).read_bytes()
def apply(p,r):
 rel=p.relative_to(W).as_posix()
 if p.exists():
  old=p.read_bytes();put(O/'before-backup'/rel,old);put(O/'before-restore'/rel,old)
 put(O/'after-backup'/rel,r);put(O/'after-restore'/rel,r);put(p,r,p.exists())
 files[rel]=dict(bytes=len(r),sha256=sha(r))
for p,r in changes.items():apply(p,r)
old=json.loads((C/'DESKTOP_HANDOFF_RECEIPT.json').read_bytes());raw=Path(old['path']).read_bytes();assert sha(raw)==old['sha256']
with zipfile.ZipFile(io.BytesIO(raw)) as z:members={n:z.read(n) for n in z.namelist()}
for n in list(members):
 p=C/Path(n).name
 if p in changes:members[n]=changes[p]
for p,r in changes.items():
 if p.parent==P/'desktop_exit_20261003':members['desktop_exit_source/'+p.name]=r
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
 for n,r in sorted(members.items()):z.writestr(n,r)
raw=buf.getvalue();name='JustPeachy-desktop-v28-final-ChatGPT-handoff.zip'
put(O/name,raw);put(O/'independent-restore'/name,raw)
with zipfile.ZipFile(io.BytesIO((O/'independent-restore'/name).read_bytes())) as z:
 assert set(z.namelist())==set(members)
 for n,r in members.items():assert z.read(n)==r;put(O/'expanded-restore'/n,r)
receipt=dict(schema='just-peachy.desktop-handoff.v1',path=str(O/name),bytes=len(raw),sha256=sha(raw),members=len(members),independent_zip_and_expanded_restore=True,complete_member_readback=True,private_audio_or_models=False,previous_receipt=old)
for name in ('DESKTOP_HANDOFF_RECEIPT.json','MOTION_HANDOFF_RECEIPT.json'):apply(C/name,enc(receipt))
for rel,pin in files.items():
 r=(W/rel).read_bytes();assert pin==dict(bytes=len(r),sha256=sha(r))
put(O/'PUBLICATION.json',enc(dict(files=files,handoff=receipt,whole_whitelist_readback=True)))
print(json.dumps(dict(files=len(files),handoff=receipt['path'],bytes=receipt['bytes'],sha256=receipt['sha256'])))
