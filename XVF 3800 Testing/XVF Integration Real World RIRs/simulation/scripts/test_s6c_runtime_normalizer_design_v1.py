"""Normalizer source/fixture review; README_TEST_S6C_RUNTIME_NORMALIZER_DESIGN_V1.md."""
import argparse, ast, hashlib, importlib.util, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
SIM=HERE.parent
REPORT=SIM/"reports/S6C/20260910T123540Z"
FINAL="d94507a8f7f4246b8f6a377b22fd50b9c2487761a3638e32bd650d49ac953b0b"
README="912e4ccf5cb6278bbb51c2d1e59a21106062d367c18529e849d99df370697068"
OLD=SIM/"staging/s6c/20260910T123540Z/runtime_normalization/before_guard_review_v1"
def bind(path):
 raw=path.read_bytes();return dict(path=str(path.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def funcs(raw):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef)}
def run(output):
 p=HERE/"s6c_runtime_metadata_normalizer_v1.py";assert bind(p)["sha256"]==FINAL
 assert bind(HERE/"README_S6C_RUNTIME_METADATA_NORMALIZER_V1.md")["sha256"]==README
 spec=importlib.util.spec_from_file_location("_reviewed_normalizer",p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 names=[]
 def check(name,value):assert value,name;names.append(name)
 def reject(name,fn):
  try:fn()
  except (ValueError,KeyError,TypeError):names.append(name);return
  raise AssertionError(name)
 inherited=m.checks();check("36 held checks",inherited["checks"]==36)
 before=funcs((OLD/p.name).read_bytes());after=funcs(p.read_bytes())
 check("only three existing functions changed",{n for n in before if before[n]!=after[n]}=={"c_tail","run","checks"})
 check("two added identity-only helpers",set(after)-set(before)=={"native_session","require_distinct_runtime_sessions"})
 source=dict(duration_samples=16000,duration_sec=1.)
 native=dict(status="COMPLETE",source_duration_sec=1.,final_telemetry=dict(source_duration_sec=1.,asr_cursor_sec=1.,scheduler=dict(closed=True,pending_events=0),audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0))
 final=dict(source_samples=16000,identity_samples=16000,state="COMPLETED",event_and_transcript_handles_closed=True,resident_bundle_lease_retained=False,live_lanes_at_finalization=[])
 check("missing error remains unavailable",m.c_tail(native,final,source)["tail_complete"] is None)
 check("explicit no-error proof accepted",m.c_tail(native,dict(final,finalization_error=None),source)["tail_complete"] is True)
 check("false is not no-error proof",m.c_tail(native,dict(final,finalization_error=False),source)["tail_complete"] is None)
 r=dict(native_result=dict(path="C:/fixture/A/RESULT.json",sha256="a"),native_session_dir="C:/fixture/A/session",repetition=1)
 r2=dict(native_result=dict(path="C:/fixture/B/RESULT.json",sha256="b"),native_session_dir="C:/fixture/B/session",repetition=2)
 check("separate physical repeat accepted",m.require_distinct_runtime_sessions([r,r2])==[r,r2])
 reject("same path under changed hash",lambda:m.require_distinct_runtime_sessions([r,dict(r2,native_result=dict(path="c:/fixture/a/result.JSON",sha256="b"))]))
 reject("same session case variant",lambda:m.require_distinct_runtime_sessions([r,dict(r2,native_session_dir="c:/FIXTURE/a/SESSION")]))
 reject("missing native session",lambda:m.native_session({}))
 reject("mixed journal sessions",lambda:m.native_session(dict(native_journals={"a":{"path":"C:/a/audio.pcm16"},"b":{"path":"C:/b/identity.pcm16"}})))
 b00=dict(profile_id="B00",duration_sec=1.,input_pcm_sha256="pcm")
 n=dict(status="COMPLETE",native_pcm_exact=True,asr_cursor_complete=True,source_duration_sec=1.,journal=dict(sha256="pcm",bytes=32000),summary=dict(telemetry=dict(asr_cursor_sec=1.,audio_frames_dropped=0,portaudio_input_overflows=0,raw_capture_reserve_failures=0)))
 t=m.historical_tail(n,b00)
 check("B00 retains limited tail scope",t["tail_complete"] is True and t["dispatch_tail_proof"] is None and t["drain_available"] is False)
 check("same metadata cannot qualify B36",m.historical_tail(n,dict(b00,profile_id="B36"))["tail_complete"] is None)
 check("empty owner never completed",m.owners_closed([]) is None)
 output=Path(output);assert not output.exists();output.mkdir(parents=True)
 (output/"REPRODUCED_SOURCE_CHECKS.json").write_text(json.dumps(inherited,indent=2)+"\n",encoding="utf-8")
 value=dict(schema="s6c.runtime_normalizer_independent_review.v1",status="PASS_SOURCE_AND_TINY_FIXTURES_ONLY",independent_checks=len(names),names=names,
  inherited_checks=36,inherited_receipt=bind(output/"REPRODUCED_SOURCE_CHECKS.json"),
  source_bindings=[bind(p),bind(HERE/"README_S6C_RUNTIME_METADATA_NORMALIZER_V1.md"),bind(Path(__file__)),bind(HERE/"README_TEST_S6C_RUNTIME_NORMALIZER_DESIGN_V1.md"),bind(OLD/"INDEX.json")],
  resolved_findings=["Missing finalization_error no longer qualifies C full-tail proof.","Actual native result path/hash/session dedup rejects overlapping continuous requests; distinct physical repetitions remain separate."],
  source_schema_review=["Original canonical/sentinel/cross completed measurement and V7 owner schema.","Original S6A B00 versus S6B B01/B36 selected_jobs/cell_chain and dispatch availability.","C-long admit_closed and B36-long closed APIs; continuous source never passes a canonical name/scoring API.","Actual registered C condition hashes and historical original-row digest semantics.","Physical IDs/owner observations from explicit V7 inventory; failed native-complete rows retain failure status."],
  limitations=["Source and synthetic admission only; actual completed metadata normalization remains unexecuted by reviewer.","Original strict source/observer/native chains and final assembler are still required.","B00 tail scope is full journal/cursor, not research dispatch/drain, lexical correctness or acoustic clipping.","No final scientific, operating or whole-study acceptance."],
  actual_normalizations=0,models=0,payload_or_runtime_reads=0)
 out=output/"REVIEW_RECEIPT.json";out.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8");print(json.dumps(bind(out),indent=2))
if __name__=="__main__":
 a=argparse.ArgumentParser();a.add_argument("--output",required=True);run(a.parse_args().output)

