"""Independent rendered-table check; see README."""
from pathlib import Path
import csv, io, json, hashlib
from datetime import datetime, timezone
S=Path(__file__).resolve().parent
R=S.parent/"reports/S6C/20260910T123540Z"
P=R/"compact_score_tables/final_supplement_v1/PACED_NATIVE_RESULTS_SOURCE_BINDINGS.json"
OUT=R/"independent_review/PACED_DOCUMENT_ROOT_REVIEW_V1.json"
cache={}
checks=0
def b(p):
 p=Path(p).resolve();raw=p.read_bytes()
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def exact(d):
 global checks
 p=d["path"]
 if p not in cache: cache[p]=Path(p).read_bytes()
 raw=cache[p]
 assert len(raw)==d["bytes"] and hashlib.sha256(raw).hexdigest()==d["sha256"],p
 checks+=1
 return raw
def table(d):return list(csv.DictReader(io.StringIO(exact(d).decode("utf-8-sig"))))
def number(v):return "NA" if v in (None,"","null") else str(int(float(v)))
def selected(rows,key):
 found=[r for r in rows if all(r.get(k)==str(v) for k,v in key.items())]
 assert len(found)<=1,key
 return found[0] if found else {}
def cellstr(row,fields):
 return " / ".join(number(row.get(k)) for k in fields)
def main():
 global checks
 if OUT.exists():raise FileExistsError(OUT)
 data=json.loads(P.read_bytes());doc=exact(data["document"]).decode("utf-8")
 assert len(data["score_authorities"])==64
 admitted={}
 for a in data["score_authorities"]:
  exact(a["authority"])
  for t in a["tables"]:admitted[t["path"]]=t
 assert len(data["rendered_core_rows"])==72 and len(data["rendered_gallery_rows"])==20
 total=0
 for item in data["rendered_core_rows"]:
  assert item["source"]==admitted[item["source"]["path"]]
  rows=table(item["source"])
  primary=selected(rows,item["row_keys"][0]);complete=selected(rows,item["row_keys"][1])
  fields=[v.strip() for v in item["rendered_row"].strip("|").split("|")]
  assert item["rendered_row"] in doc
  assert fields[1]==item["asr_tap"]+"→"+item["identity_tap"]
  assert fields[2]==str(item["repetition"])
  assert fields[4]==cellstr(primary,["word_errors","word_reference_words"])
  assert fields[5]==cellstr(complete,["cp_first_final_errors","cp_latest_revised_errors","cp_latest_revised_reference_words"])
  unknown=complete.get("unknown_fraction")
  expect="NA" if unknown in (None,"","null") else f"{100*float(unknown):.1f}"
  assert fields[6]==expect,(fields[6],expect)
  assert fields[7]=="/".join(number(complete.get(k)) for k in ("return_consistent","return_inconsistent","return_unknown"))
  key={k:v for k,v in item["row_keys"][0].items() if k!="population"}
  count=sum(int(r["scenes"]) for r in rows if all(r.get(k)==v for k,v in key.items()) and r["population"] in {"PRIMARY_NONOVERLAP","COMPLETE_OVERLAP","INCOMPLETE_REFERENCE","STRICT_EMPTY_REFERENCE"})
  assert int(fields[3])==count,(fields,count)
  total+=count; checks+=9
 assert total==596
 for item in data["rendered_gallery_rows"]:
  assert item["source"]==admitted[item["source"]["path"]]
  row=selected(table(item["source"]),item["key"]); assert row
  cells=[v.strip() for v in item["rendered_row"].strip("|").split("|")]
  assert item["rendered_row"] in doc
  assert cells[1]==item["key"]["stream"]+"→"+item["key"]["identity_tap"]
  assert cells[2]==str(item["repetition"])
  assert cells[4]==cellstr(row,["correct_name_samples","wrong_known_name_samples","unknown_name_samples"])
  assert cells[5]==number(row["sole_active_samples"])
  assert cells[6]==cellstr(row,["first_correct_name_observed_turns","first_correct_name_missing_turns"])
  checks+=7
 assert "cp_first_display_label_final_words" in doc and "Continuous diagnostics did not run" in doc
 receipt=dict(schema="s6c-paced-document-independent-root-review.v1",status="PASS_RENDERED_NUMERICAL_AND_SCOPE_REVIEW",created_utc=datetime.now(timezone.utc).isoformat(),document=data["document"],source_manifest=b(P),checked_source_files=[b(p) for p in cache],checks=checks,core_rows=72,gallery_rows=20,core_cells=total,reviewer="root (independent of Cues author)",helper=b(__file__),readme=b(S/"README_S6C_REVIEW_PACED_DOCUMENT_V1.md"),limitations=["Descriptive original aggregate projection; not new scoring, confidence intervals, neural parity or campaign acceptance.","Gallery ALL table is not a substitute for enrolled/withheld or missing-turn rows, which remain in complete tables.","First-final cp, first-display labels on final words, modeled-name scoring and actual wall emission remain distinct."])
 OUT.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
 print(json.dumps(dict(status=receipt["status"],checks=checks,receipt=b(OUT))))
if __name__=="__main__":main()
