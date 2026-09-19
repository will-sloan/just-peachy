"""One metadata-only resource snapshot; see README."""
from pathlib import Path
from datetime import datetime, timezone
import os, json, hashlib, subprocess, psutil
S=Path(__file__).resolve().parent;SIM=S.parent
R=SIM/"reports/S6C/20260910T123540Z"
OUT=R/"storage/FINAL_RESOURCE_SNAPSHOT_V1.json"
def utc():return datetime.now(timezone.utc).isoformat()
def point():
 return dict(utc=utc(),available_ram_bytes=psutil.virtual_memory().available,
 disk_free_bytes={d:psutil.disk_usage(d).free for d in ("C:/","G:/")})
def walk(root):
 stats={};errors=[];files=total=0
 def error(e):errors.append(dict(path=str(e.filename),error=str(e)))
 for base,dirs,names in os.walk(root,followlinks=False,onerror=error):
  keep=[]
  for n in dirs:
   p=Path(base)/n
   try:
    st=p.lstat()
    if p.is_symlink() or getattr(st,"st_file_attributes",0)&1024:
     errors.append(dict(path=str(p),error="REPARSE_POINT_NOT_FOLLOWED"))
    else:keep.append(n)
   except OSError as e:error(e)
  dirs[:]=keep
  for n in names:
   p=Path(base)/n
   try:
    st=p.lstat()
    if p.is_symlink() or getattr(st,"st_file_attributes",0)&1024:
     errors.append(dict(path=str(p),error="REPARSE_POINT_NOT_COUNTED"));continue
    k=p.suffix.lower() or "[none]";v=stats.setdefault(k,dict(files=0,bytes=0))
    v["files"]+=1;v["bytes"]+=st.st_size;files+=1;total+=st.st_size
   except OSError as e:error(e)
 return dict(root=str(root),files=files,bytes=total,by_extension=stats,errors=errors)
def binding(p):
 raw=Path(p).read_bytes();return dict(path=str(Path(p).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def main():
 if OUT.exists():raise FileExistsError(OUT)
 start=point()
 roots=[R,SIM/"staging/s6c/20260910T123540Z",Path("G:/Just_Peachy_S6C/20260910T123540Z")]
 rows=[walk(p) for p in roots]
 command="Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,OperationalStatus,Size | ConvertTo-Json -Compress -Depth 3"
 try:
  q=subprocess.run(["powershell","-NoProfile","-Command",command],capture_output=True,text=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
  health=dict(returncode=q.returncode,reported_disks=json.loads(q.stdout) if q.returncode==0 and q.stdout.strip() else None,error=q.stderr.strip() or None)
 except Exception as e:health=dict(returncode=None,reported_disks=None,error=str(e))
 end=point();total=sum(v["bytes"] for v in rows);errors=sum(len(v["errors"]) for v in rows)
 doc=dict(schema="s6c-final-resource-snapshot.v1",status="OBSERVED_METADATA_SNAPSHOT_WITH_FLAGS" if errors else "OBSERVED_METADATA_SNAPSHOT",
 start=start,end=end,new_namespace_walk=rows,new_namespace_total_bytes=total,new_namespace_cap_bytes=120*1024**3,
 within_namespace_cap=None if errors else total<=120*1024**3,
 reserve_checks=dict(c_free_above_50GiB=end["disk_free_bytes"]["C:/"]>=50*1024**3,g_free_above_75GiB=end["disk_free_bytes"]["G:/"]>=75*1024**3,ram_above_12GiB=end["available_ram_bytes"]>=12*1024**3),
 physical_disk_status=health,helper=binding(__file__),readme=binding(S/"README_S6C_FINAL_RESOURCE_SNAPSHOT_V1.md"),
 scope="Single non-atomic directory-stat interval during report writing; logical file lengths, not allocated bytes/deduplicated extents. No payload contents or H2 folders read. No deletion, process termination or device benchmark. Reported Windows disk health is not a SMART surface/endurance test.")
 OUT.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(dict(status=doc["status"],total_GiB=total/1024**3,errors=errors,end=end,within_cap=doc["within_namespace_cap"],reserve_checks=doc["reserve_checks"],physical_disk_status=health,receipt=binding(OUT))))
if __name__=="__main__":main()

