"""Bounded dispatcher review; README_TEST_S6C_PACED_DISPATCH_DESIGN_V1.md."""
import argparse, hashlib, importlib.util, json, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
PINS={"s6c_paced_dispatch_v1.py":"c6a241b4f9f611ceae073a7948cb80051ac4474c2f4464d5c441a948e5e4cecd",
"test_s6c_paced_dispatch_v1.py":"cd6f40ab2dd933fa5f36a8b6b5e5cd63509293c29bb6a2831dbbdb95722b3986",
"README_S6C_PACED_DISPATCH_V1.md":"d4e205c94f8c1223d9e2fab6453a76549363343c666e29d5d337faec0c6da7d0"}
def binding(p):
 b=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def load(name,file):
 p=HERE/file;assert binding(p)["sha256"]==PINS[file]
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
D=load("s6c_paced_dispatch_v1","s6c_paced_dispatch_v1.py")
T=load("_dispatch_owner_tests","test_s6c_paced_dispatch_v1.py")
def run(output):
 output=Path(output);assert not output.exists();names=[]
 def reject(name,fn):
  try:fn()
  except (ValueError,KeyError,TypeError):names.append(name);return
  raise AssertionError("Unexpected admission: "+name)
 # No source or real runtime metadata is created for these JSON closure fixtures.
 for historical in (False,True):
  for fault in ("missing_owner_list","wrong_job_key","unknown_native_child"):
   with tempfile.TemporaryDirectory(prefix="s6c_dispatch_review_") as td:
    report,batch,inv,item,plan,owner,quiet=T.fixture(Path(td),historical)
    path=batch/"jobs/j1/COMPLETE.json";v,_=D.read(path)
    if fault=="missing_owner_list":v["owned_processes"]=[]
    elif fault=="wrong_job_key":v["job_key"]="other"
    path.write_text(json.dumps(v),encoding="utf-8")
    if not historical:
     p=inv/"OUTCOME.json";done,_=D.read(p);done["rows"][0]["completion"]=D.binding(path);p.write_text(json.dumps(done),encoding="utf-8")
     p=inv/"CLOSURE.json";closed,_=D.read(p);closed["outcome"]=D.binding(inv/"OUTCOME.json");p.write_text(json.dumps(closed),encoding="utf-8")
    def inspect(o):return {"alive":None if fault=="unknown_native_child" and o["pid"]==102 else False}
    with patch.object(D,"REPORT",report):
     reject(str(historical)+"_"+fault,lambda:D.completion(item,plan,owner,quiet,inspect))
 # Source-bound queue/authority admission exercised against in-memory documents.
 h=D.binding(HERE/"s6c_paced_epoch4_fast_v2.py")
 root=D.REPORT/"paced_candidates/dispatcher_fixture_fast_v2"
 pb=dict(path=str(root/"MANIFEST.json"),bytes=1,sha256="0"*64)
 qb=dict(path=str(D.REPORT/"queue_fixture.json"),bytes=1,sha256="1"*64)
 ab=dict(path=str(D.REPORT/"authority_fixture.json"),bytes=1,sha256="2"*64)
 expiry=min(datetime.now(timezone.utc)+timedelta(minutes=30),D.DEADLINE).isoformat()
 baseplan=dict(schema="s6c-canonical-paired-paced.v1",report_root=str(root),jobs=[dict(job_id="one")],sources=[h],deadline_utc=expiry)
 basequeue=dict(schema="s6c-serial-paced-queue.v1",status="REGISTERED_FINITE_QUEUE",namespace="synthetic_only",items=[dict(item_id="a",helper=h,manifest=pb,cells=1,output_root=str(root))])
 baseauthority=dict(schema="s6c-serial-paced-authority.v1",status="AUTHORIZED_SERIAL_QUIET_PACED",queue=qb,dispatcher=D.binding(HERE/"s6c_paced_dispatch_v1.py"),all_other_model_hil_work_stopped=True,all_heavy_analysis_stopped=True,expires_utc=expiry)
 for fault in (None,"quiet_false","foreign_dispatcher","foreign_queue","duplicate_manifest","wrong_cells","outside_root","expired","beyond_stage"):
  q=json.loads(json.dumps(basequeue));a=json.loads(json.dumps(baseauthority));p=json.loads(json.dumps(baseplan))
  if fault=="quiet_false":a["all_heavy_analysis_stopped"]=False
  if fault=="foreign_dispatcher":a["dispatcher"]["sha256"]="3"*64
  if fault=="foreign_queue":a["queue"]["sha256"]="4"*64
  if fault=="duplicate_manifest":q["items"].append(dict(q["items"][0],item_id="b"))
  if fault=="wrong_cells":q["items"][0]["cells"]=2
  if fault=="outside_root":p["report_root"]=str(D.REPORT/"other/dispatcher_fixture_fast_v2")
  if fault=="expired":a["expires_utc"]="2000-01-01T00:00:00Z"
  if fault=="beyond_stage":a["expires_utc"]="2099-01-01T00:00:00Z"
  docs={qb["path"]:(q,qb),ab["path"]:(a,ab),pb["path"]:(p,pb)}
  def read(path,expected=None):
   value,b=docs[str(path)];assert expected==b;return value,b
  with patch.object(D,"read",read):
   if fault:reject("authority_"+fault,lambda:D.admit(qb,ab))
   else:assert len(D.admit(qb,ab)[4])==1;names.append("authority_finite_in_memory")
 assert D.finite_owner(dict(pid=True,creation_time=1.)) is False;names.append("bool_pid_rejected")
 assert D.finite_owner(dict(pid=1,creation_time=float("nan"))) is False;names.append("nonfinite_creation_rejected")
 for file,sha in PINS.items():assert binding(HERE/file)["sha256"]==sha
 output.mkdir(parents=True)
 result=dict(status="PASS_SOURCE_AND_TINY_FIXTURES_ONLY",checks=len(names),names=names,
  sources=[binding(HERE/x) for x in PINS]+[binding(Path(__file__)),binding(HERE/"README_TEST_S6C_PACED_DISPATCH_DESIGN_V1.md")],
  actual_queues_created=0,dispatches=0,native_calls=0,runtime_payload_reads=0,
  scope="Finite authorization, exact original closure/grid/owner proof and no cleanup power. In-memory admission and synthetic closure only; original runner validates the full scientific manifest before work. Final V7/native/scientific acceptance remains separate.")
 path=output/"INDEPENDENT_CHECKS.json";path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8");print(json.dumps(binding(path),indent=2))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--output",required=True);run(p.parse_args().output)

