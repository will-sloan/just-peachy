"""Read-only S6D device/host preflight; see README_S6D_PREFLIGHT_V2.md."""
from pathlib import Path
import argparse, datetime, hashlib, json, msvcrt, socket, sys, time
import psutil, shutil, traceback
SIM=Path(__file__).resolve().parents[1]
ROOT=SIM.parent
sys.path.insert(0,str(ROOT))
from measurement_app.core import Control, devices, HOST
def binding(path):
 p=Path(path); b=p.read_bytes()
 return {"path":str(p),"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}
def run(report):
 report=Path(report).resolve()
 if not report.is_relative_to((SIM/"reports/S6D").resolve()): raise ValueError("Report must be below SIM/reports/S6D")
 report.mkdir(parents=True,exist_ok=False)
 result={"schema":"jp_s6d_readonly_preflight.v1","started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"audio_streams_opened":0,"setters_issued":0,"errors":[]}
 lock=None; owned=False
 try:
  result["resources"]={"memory_available_bytes":psutil.virtual_memory().available,"disks":{d:{"free_bytes":shutil.disk_usage(d+":\\").free,"total_bytes":shutil.disk_usage(d+":\\").total} for d in ["C","G"]}}
  result["reserve_checks"]={"C_50GiB":result["resources"]["disks"]["C"]["free_bytes"]>=50*1024**3,"G_75GiB":result["resources"]["disks"]["G"]["free_bytes"]>=75*1024**3}
  proc=[]
  for p in psutil.process_iter(["pid","name","create_time","cmdline"]):
   try:
    args=p.info["cmdline"] or []; cmd=" ".join(args)
    if p.pid!=__import__("os").getpid() and any(x in cmd.lower() for x in ["maintain_h2_storage.py","s45_hardware.py","s4_hardware.py","s3_hardware.py","s6d_hardware","edge_speech_pipeline"]):
     proc.append({"pid":p.pid,"creation_time":p.info["create_time"],"name":p.info["name"],"argv":args})
   except (psutil.NoSuchProcess,psutil.AccessDenied): pass
  result["relevant_processes"]=proc
  blockers=[p for p in proc if any(x in " ".join(p["argv"]).lower() for x in ["s45_hardware.py","s4_hardware.py","s3_hardware.py","s6d_hardware"])]
  if blockers: raise RuntimeError("Existing hardware process: inspect exact owner before access")
  for port in [8765,8766,8767]:
   with socket.socket() as s:
    s.settimeout(.3)
    if s.connect_ex(("127.0.0.1",port))==0: raise RuntimeError("Existing recorder service on port "+str(port))
  lock=(ROOT/"measurement_app/hardware.lock").open("r+b"); lock.seek(0); msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1); owned=True
  result["hardware_lock_acquired"]=True
  inventory=devices()
  result["xvf_endpoints"]=[d for d in inventory if "XVF" in d["name"].upper() or "XMOS" in d["name"].upper()]
  result["other_endpoint_count"]=len(inventory)-len(result["xvf_endpoints"])
  if not result["xvf_endpoints"]: raise RuntimeError("No XVF/XMOS audio endpoint enumerated")
  c=Control(report/"commands")
  identity={n:c.values(n) for n in ["VERSION","AEC_MIC_ARRAY_TYPE","AEC_NUM_MICS","AEC_MIC_ARRAY_GEO","AUDIO_MGR_MIC_GAIN","AUDIO_MGR_REF_GAIN","AUDIO_MGR_SYS_DELAY","USB_BIT_DEPTH","I2S_INPUT_PACKED","I2S_DAC_DSP_ENABLE"]}
  identity["build_reply"]=c.query("BLD_MSG");result["identity"]=identity
  result["expected_build"]=(identity["VERSION"]==[3,2,1] and identity["AEC_MIC_ARRAY_TYPE"]==[1] and identity["AEC_NUM_MICS"]==[4] and "ua-io48-lin" in identity["build_reply"])
  names=["AUDIO_MGR_OP_ALL","AUDIO_MGR_OP_PACKED","AUDIO_MGR_OP_UPSAMPLE","AEC_ASROUTONOFF","AEC_ASROUTGAIN","GPO_PORT_PIN_INDEX"]
  result["routing_snapshot"]={n:c.values(n) for n in names}
  dump=c.query("--dump-params"); (report/"initial_params_dump.txt").write_text(dump,encoding="utf8")
  result["dump"]=binding(report/"initial_params_dump.txt")
  result["status"]="READ_ONLY_PREFLIGHT_COMPLETE" if result["expected_build"] else "UNEXPECTED_BUILD_BLOCKED"
  result["playback_authorized_by_this_receipt"]=False
  result["remaining_playback_gates"]=["Fresh user analog-output-silenced confirmation","Qualified exact six-output routing and safe transport","Explicit source-bound finite capture ledger and independent source review"]
 except Exception as e:
  result["errors"].append({"type":type(e).__name__,"message":str(e),"traceback":traceback.format_exc()})
  result["status"]="READ_ONLY_PREFLIGHT_BLOCKED"
 finally:
  if owned:
   lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
  if lock:lock.close()
  result["hardware_lock_released"]=owned
  result["finished_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
  result["sources"]=[binding(__file__),binding(Path(__file__).with_name("README_S6D_PREFLIGHT_V2.md")),binding(ROOT/"measurement_app/core.py"),binding(HOST)]
  (report/"PREFLIGHT.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf8")
 return result
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--report",required=True);a=p.parse_args();r=run(a.report)
 print(json.dumps({k:r.get(k) for k in ["status","expected_build","xvf_endpoints","reserve_checks","errors","audio_streams_opened","setters_issued","hardware_lock_released"]},indent=2))

