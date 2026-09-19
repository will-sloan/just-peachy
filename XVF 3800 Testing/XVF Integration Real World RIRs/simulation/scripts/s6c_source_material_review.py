"""Read-only S6C prepared-source audit. See README_S6C_SOURCE_MATERIAL_REVIEW.md."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, hashlib, json, math, sys
import numpy as np
import soundfile as sf
sys.dont_write_bytecode=True
SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/"reports/S6C/20260910T123540Z"

def read(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def bind(p):
 p=Path(p).resolve();raw=p.read_bytes()
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def verify(b):
 actual=bind(b["path"])
 assert all(actual[k]==b[k] for k in ("bytes","sha256")),b["path"]
 return actual
def close(a,b):assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-8),(a,b)

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
 out=a.output.resolve()
 if REPORT.resolve() not in out.parents or out.exists():raise ValueError("Fresh output under current S6C report required")
 import s6c_sources as src
 source_code=bind(Path(src.__file__));source_readme=bind(Path(src.__file__).with_name("README_S6C_SOURCES.md"))
 root=REPORT/"enrollment_inventory/v2";receipt_path=root/"PREPARATION_RECEIPT.json";receipt=read(receipt_path)
 assert receipt["status"]=="PASS_SOURCE_ACCOUNTING_ONLY"
 for key in ("manifest","tier_coverage"):verify(receipt[key])
 manifest=read(receipt["manifest"]["path"])
 authorities=[]
 for key in ("preparation_code_admission","inventory_receipt","candidate_freeze","query_manifest"):
  authorities.append(verify(manifest[key]))
 frozen=read(manifest["candidate_freeze"]["path"]);queries=read(manifest["query_manifest"]["path"])["rows"]
 accepted=manifest["accepted_sources"];rejected=manifest["rejected_candidates"];coverage=manifest["coverage"]
 assert len(accepted)==receipt["accepted_clips"]==752
 assert len(rejected)==receipt["rejected_clips"]==2
 assert len(queries)==777 and len({r["source_id"] for r in queries})==449 and len({r["identity"] for r in queries})==43
 assert Counter(r["s6c_role"] for r in accepted)==receipt["role_counts"]
 frozen_by={r["source_id"]:r for r in frozen["candidates"]}
 assert len(frozen_by)==len(frozen["candidates"])
 assert len(accepted)+len(rejected)+len(manifest["unneeded_frozen_candidates_not_decoded"])==len(frozen_by)
 seen=set();e=[];c=[];bytes_checked=0;original_bytes=0;checks=0;verified_hashes=[]
 for row in accepted:
  assert row["source_id"] not in seen;seen.add(row["source_id"])
  assert row["s6c_role"] in ("E","C")
  assert row["quality_disposition"] in ("PASS","REVIEW") and row["whole_clip"] is True and row["source_gain_applied"]==1.
  assert row["dataset"] in ("CMU ARCTIC","HiFiTTS","Common Voice") and row["native_eligibility"]
  assert row["source_crop_native_samples"]==[0,row["native_samples"]]
  for k in ("source_binding","decoded_16k_binding","preparation_clip_receipt"):verify(row[k]);checks+=1
  original_bytes+=row["source_binding"]["bytes"];bytes_checked+=row["decoded_16k_binding"]["bytes"]
  checkpoint=read(row["preparation_clip_receipt"]["path"])
  src.validate_clip_record(checkpoint,frozen_by[row["source_id"]],manifest["candidate_freeze"]["sha256"])
  assert checkpoint["source"]=={k:v for k,v in row.items() if k!="preparation_clip_receipt"}
  x,rate=sf.read(row["decoded_16k_binding"]["path"],dtype="float32")
  assert rate==16000 and x.ndim==1 and len(x)==row["samples"] and np.isfinite(x).all()
  assert hashlib.sha256(x.astype("<f4").tobytes()).hexdigest()==row["decoded_pcm_sha256"]
  close(row["duration_sec"],len(x)/rate)
  estimated=src.active_stats(x)
  assert estimated==row["quality"],row["source_id"]
  hard,review=src.qc_reasons(estimated,row["duration_sec"])
  assert not hard and review==row["quality_review_flags"]
  assert row["quality_disposition"]==("REVIEW" if review else "PASS")
  verified_hashes.append(dict(source_id=row["source_id"],source_sha256=row["source_binding"]["sha256"],decoded_sha256=row["decoded_16k_binding"]["sha256"],decoded_pcm_sha256=row["decoded_pcm_sha256"],checkpoint_sha256=row["preparation_clip_receipt"]["sha256"]))
  (e if row["s6c_role"]=="E" else c).append(row);checks+=7
 def keys(rows,fn):return {fn(r) for r in rows if fn(r) not in (None,"")}
 pair_counts={}
 for label,fn in (("source_ids",lambda r:r["source_id"]),("native_paths",lambda r:src.source_path_key(r["source_binding"]["path"])),("original_hashes",lambda r:r["source_binding"]["sha256"]),("decoded_hashes",lambda r:r["decoded_pcm_sha256"]),("normalized_text",lambda r:src.text_key(r["transcript"])),("native_prompt_ids",src.native_prompt_key)):
  groups={role:keys(rows,fn) for role,rows in (("E",e),("C",c),("Q",queries))}
  for a,b in (("E","C"),("E","Q"),("C","Q")):
   overlap=groups[a]&groups[b];assert not overlap,(label,a,b,overlap);pair_counts[a+"_"+b+"_"+label]=0;checks+=1
 assert len({r["source_binding"]["sha256"] for r in accepted})==len(accepted)
 assert len({r["decoded_pcm_sha256"] for r in accepted})==len(accepted)
 assert not keys(accepted,lambda r:r["parent_book"])&keys(queries,lambda r:r["parent_book"])
 assert not keys(e,lambda r:r["parent_chapter"])&keys(c,lambda r:r["parent_chapter"])
 assert not keys(accepted,lambda r:r["source_binding"]["sha256"])&set(frozen["forbidden_original_hashes"])
 assert not keys(accepted,lambda r:r["decoded_pcm_sha256"])&set(frozen["forbidden_decoded_hashes"])
 by_id=defaultdict(list)
 for row in coverage:by_id[row["identity"]].append(row)
 sparse=[]
 for person in frozen["people"]:
  pid=person["identity"];erows=[r for r in e if r["identity"]==pid];crows=[r for r in c if r["identity"]==pid]
  actual=sorted(by_id[pid],key=lambda r:r["requested_usable_seconds"])
  expected=src.nested_tiers(erows)
  assert len(actual)==len(expected)==3
  for row,wanted in zip(actual,expected):
   assert all(row[k]==v for k,v in wanted.items()),pid
   assert row["canonical_Q_kept_regardless_of_enrollment"] is True
   assert row["calibration_source_ids"]==[r["source_id"] for r in crows]
   close(row["calibration_estimated_usable_seconds"],sum(r["quality"]["active_seconds_estimated"] for r in crows))
   for x in row["source_ids"]:assert x in {r["source_id"] for r in erows}
   if row["status"]!="AVAILABLE":sparse.append({k:row[k] for k in ("identity","dataset","requested_usable_seconds","status","actual_estimated_usable_seconds","duration_shortfall_seconds")})
   checks+=5
  for lo,hi in zip(actual,actual[1:]):assert hi["source_ids"][:len(lo["source_ids"])]==lo["source_ids"]
 tier_counts={str(t):sum(r["requested_usable_seconds"]==t and r["status"]=="AVAILABLE" for r in coverage) for t in (5,15,30)}
 assert tier_counts==receipt["tier_available_people"]
 assert len({r["identity"] for r in c})==receipt["calibration_people_any"]
 assert bytes_checked==receipt["new_decoded_bytes"]
 assert bind(Path(src.__file__))==source_code and bind(Path(src.__file__).with_name("README_S6C_SOURCES.md"))==source_readme
 value=dict(schema="s6c.independent_source_material_review.v1",status="PASS",checks=checks,
  receipt=bind(receipt_path),manifest=receipt["manifest"],tier_coverage=receipt["tier_coverage"],authorities=authorities,
  code=bind(Path(__file__)),readme=bind(Path(__file__).with_name("README_S6C_SOURCE_MATERIAL_REVIEW.md")),
  reviewed_source_code=source_code,reviewed_source_readme=source_readme,
  accepted_sources=len(accepted),roles=dict(Counter(r["s6c_role"] for r in accepted)),rejected_sources=len(rejected),
  source_pool_metadata_identities=len(frozen["people"]),query_metadata_identities=43,query_occurrences=777,query_source_ids=449,
  enrollment_tier_available_people=tier_counts,calibration_people_with_any=len({r["identity"] for r in c}),
  coverage_rows=len(coverage),sparse_tier_rows=sparse,zero_intersections=pair_counts,
  decoded_bytes_rehashed_and_redecoded=bytes_checked,original_bytes_rehashed=original_bytes,
  prepared_source_bindings=verified_hashes,
  scope="Every accepted original/decoded/checkpoint binding verified. Every decoded PCM hash, exact numerical activity estimator and QC disposition recomputed. Frozen row identities, E/C/Q native parents/hash/text/prompt exclusions, nested tiers and sparse coverage independently checked. No neural inference or hardware.",
  limitations=["Numerical active seconds are estimated speech support, not phonetic truth.","Different whole clips/chapter IDs are not proven independent recording sessions.","HiFi same-book different-chapter fallbacks remain explicit.","Corpus-qualified metadata identities are not globally verified people.","Clean-source templates deliberately mismatch the XVF domain; templates/identification have not been scored here.","Source-pool E/C coverage does not authorize using strangers in a tested gallery's templates or calibration."])
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open("x",encoding="utf-8") as f:json.dump(value,f,indent=2,allow_nan=False);f.write("\n")
 print(json.dumps(dict(status="PASS",checks=checks,accepted=len(accepted),tiers=tier_counts,receipt=bind(out))))
if __name__=="__main__":main()

