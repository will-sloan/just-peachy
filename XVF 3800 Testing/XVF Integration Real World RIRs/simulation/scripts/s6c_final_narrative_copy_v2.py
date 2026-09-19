"""Copy reviewed narratives with the documented encoding correction."""
from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
S=Path(__file__).resolve().parent;R=S.parent/"reports/S6C/20260910T123540Z"
def b(p):
 raw=p.read_bytes();return dict(path=str(p.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def main():
 out=R/"handoff_final_v2"
 if out.exists():raise FileExistsError(out)
 initial=json.loads((R/"handoff_final_v1/NARRATIVE_PREPARATION_RECEIPT.json").read_bytes())
 pairs=[]
 for x in initial["outputs"]:
  p=Path(x["path"]);assert b(p)==x
  pairs.append((p,p.name))
 pairs.extend([(R/"handoff_final_v1/OPERATING_COMMANDS.md","OPERATING_COMMANDS.md"),(R/"handoff_drafts/PACED_NATIVE_RESULTS.md","PACED_NATIVE_RESULTS.md")])
 content={name:p.read_bytes() for p,name in pairs}
 old=content["RUNTIME_RESULTS.md"].decode("utf-8")
 assert old.count("1.98\u20132.29 seconds")==1
 content["RUNTIME_RESULTS.md"]=old.replace("1.98\u20132.29 seconds","1.98 to 2.29 seconds").encode("utf-8")
 assert all("\ufffd" not in raw.decode("utf-8") for raw in content.values())
 out.mkdir()
 for name,raw in content.items():(out/name).write_bytes(raw)
 rec=dict(schema="s6c-final-narrative-copy.v2",status="COMPLETE_NARRATIVE_COPY_WITH_PORTABLE_RANGE_TEXT",created_utc=datetime.now(timezone.utc).isoformat(),prior_preparation=b(R/"handoff_final_v1/NARRATIVE_PREPARATION_RECEIPT.json"),sources=[b(p) for p,n in pairs],outputs=[b(out/n) for p,n in pairs],correction="Replace valid U+2013 range separator with plain 'to' in unchanged1.98 to2.29-second startup range for console portability. Original UTF-8 was valid; first pre-write attempt rejected an incorrect U+FFFD assumption and wrote no outputs.",helper=b(Path(__file__)),readme=b(S/"README_S6C_FINAL_NARRATIVE_COPY_V2.md"),whole_study_complete=False)
 p=out/"NARRATIVE_COPY_RECEIPT.json";p.write_text(json.dumps(rec,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(dict(receipt=b(p),runtime=b(out/"RUNTIME_RESULTS.md"),documents=len(pairs))))
if __name__=="__main__":main()
