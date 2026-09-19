"""Verify and copy immutable compatible S6B scores; README_S6B_SCORE_TRANSFER.md."""
from __future__ import annotations
import argparse,csv,hashlib,json,os,tempfile
from importlib.metadata import version
from pathlib import Path
from s6b_analysis import read,bind,digest,save,SCHEMA

SIM=Path(__file__).resolve().parents[1]
def exact(binding):
    path=Path(binding["path"])
    if bind(path)!=binding:raise ValueError("Changed bound file: "+str(path))
    return read(path)
def index_rows(index):
    expected={(p,s,c) for p in index["profiles"] for s in ("O0","O1") for c in index["case_ids"]}
    rows={(r["profile_id"],r["stream"],r["case_id"]):r for r in index["rows"]}
    if len(rows)!=len(index["rows"]) or set(rows)!=expected or index["status"]!="COMPLETE":raise ValueError("Complete unique prediction index required")
    if any(r.get("status","COMPLETE")!="COMPLETE" for r in rows.values()):raise ValueError("Failed prediction row")
    return rows
def preflight(source,target,target_index,common,supports):
    if source.resolve()==target.resolve():raise ValueError("Cannot transfer into source")
    if (target/"ANALYSIS_RECEIPT.json").exists() or (target/"HEARTBEAT.json").exists():raise ValueError("Target core analysis already started")
    receipt=read(source/"ANALYSIS_RECEIPT.json")
    if receipt["status"]!="COMPLETE_REQUESTED_INDEX" or receipt["unscored"]:raise ValueError("Incomplete source analysis")
    coverage_binding=next(b for b in receipt["tables"] if Path(b["path"]).resolve()==(source/"COVERAGE.csv").resolve())
    if bind(source/"COVERAGE.csv")!=coverage_binding:raise ValueError("Changed completed COVERAGE table")
    source_rows=index_rows(exact(receipt["index"]));target_rows=index_rows(target_index)
    if not set(source_rows)<=set(target_rows):raise ValueError("Target does not contain every source key")
    with (source/"COVERAGE.csv").open(encoding="utf-8-sig",newline="") as f:coverage=list(csv.DictReader(f))
    ck=[(r["profile_id"],r["stream"],r["case_id"]) for r in coverage]
    if len(ck)!=len(set(ck)) or set(ck)!=set(source_rows) or receipt["scored"]!=len(ck):raise ValueError("Coverage key/count mismatch")
    checked_supports=set();plan=[]
    for row in coverage:
        pid,stream,cid=row["profile_id"],row["stream"],row["case_id"]
        key=(pid,stream,cid);item=target_rows[key]
        if row["status"]!="SCORED" or source_rows[key]["result"]!=item["result"]:raise ValueError("Failed/changed prediction binding")
        value=exact(item["result"])
        if (value["profile_id"],value["stream"],value["case_id"])!=key:raise ValueError("Prediction identity mismatch")
        sb=supports[cid,stream]
        if sb["path"] not in checked_supports:exact(sb);checked_supports.add(sb["path"])
        identity=dict(prediction=item["result"],support=sb,**common)
        score_binding=json.loads(row["result"]);expected_source=source/"scores"/pid/cid/(stream+".json")
        if source.resolve() not in expected_source.resolve().parents:raise ValueError("Source score escapes analysis directory")
        if Path(score_binding["path"]).resolve()!=expected_source.resolve():raise ValueError("Coverage score path outside expected source")
        score=exact(score_binding)
        if (score["profile_id"],score["stream"],score["case_id"])!=key:raise ValueError("Score key mismatch")
        if score["analysis_identity"]!=identity or score["analysis_key"]!=digest(identity):raise ValueError("Changed scoring dependency/key")
        dest=target/"scores"/pid/cid/(stream+".json")
        if target.resolve() not in dest.resolve().parents:raise ValueError("Destination score escapes analysis directory")
        if dest.exists() and dest.read_bytes()!=expected_source.read_bytes():raise ValueError("Existing target differs; refusing overwrite")
        plan.append(dict(source=score_binding,destination=str(dest),key=list(key),analysis_key=score["analysis_key"]))
    return plan,dict(source_receipt=bind(source/"ANALYSIS_RECEIPT.json"),coverage=coverage_binding,source_index=receipt["index"])
def publish_no_replace(dest,raw):
    """Publish complete bytes atomically without replacing a concurrent file."""
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode="wb",dir=dest.parent,prefix=".s6b-score-",suffix=".tmp",delete=False) as f:
            temp=Path(f.name);f.write(raw);f.flush();os.fsync(f.fileno())
        try:
            os.link(temp,dest)
            return True
        except FileExistsError:
            if dest.read_bytes()!=raw:raise ValueError("Concurrent target differs; refusing overwrite")
            return False
    finally:
        if temp is not None and temp.exists():temp.unlink()

def copy_plan(plan):
    copied=existing=0
    for item in plan:
        source=Path(item["source"]["path"]);dest=Path(item["destination"]);raw=source.read_bytes()
        if len(raw)!=item["source"]["bytes"] or hashlib.sha256(raw).hexdigest()!=item["source"]["sha256"]:raise ValueError("Source changed after admission")
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():
            if dest.read_bytes()!=raw:raise ValueError("Target changed after admission")
            existing+=1
        else:
            if publish_no_replace(dest,raw):copied+=1
            else:existing+=1
        if dest.read_bytes()!=raw:raise ValueError("Copy verification mismatch")
    return dict(copied=copied,existing_exact=existing)
def tests():
    with tempfile.TemporaryDirectory(prefix="s6b_score_transfer_") as td:
        root=Path(td);source=root/"source";target=root/"target";source.mkdir()
        pred=root/"prediction.json";save(pred,dict(profile_id="P",stream="O0",case_id="c"))
        pred1=root/"prediction1.json";save(pred1,dict(profile_id="P",stream="O1",case_id="c"))
        support=root/"support.json";save(support,dict(support={}))
        common=dict(bank={"fixture":"bank"},codes=[],packages={"fixture":"1"},metric_schema="fixture")
        items=[];coverage=[]
        for stream,path in (("O0",pred),("O1",pred1)):
            item=dict(profile_id="P",stream=stream,case_id="c",result=bind(path));items.append(item)
            identity=dict(prediction=item["result"],support=bind(support),**common)
            score=source/"scores"/"P"/"c"/(stream+".json")
            save(score,dict(profile_id="P",stream=stream,case_id="c",analysis_identity=identity,analysis_key=digest(identity)))
            coverage.append(dict(profile_id="P",stream=stream,case_id="c",status="SCORED",result=json.dumps(bind(score))))
        index=dict(status="COMPLETE",profiles=["P"],case_ids=["c"],rows=items);index_path=root/"index.json";save(index_path,index)
        with (source/"COVERAGE.csv").open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=list(coverage[0]));w.writeheader();w.writerows(coverage)
        save(source/"ANALYSIS_RECEIPT.json",dict(status="COMPLETE_REQUESTED_INDEX",unscored=0,scored=2,index=bind(index_path),tables=[bind(source/"COVERAGE.csv")]))
        supports={("c","O0"):bind(support),("c","O1"):bind(support)}
        plan,_=preflight(source,target,index,common,supports);assert copy_plan(plan)==dict(copied=2,existing_exact=0)
        assert copy_plan(plan)==dict(copied=0,existing_exact=2)
        def reject(action):
            try:action()
            except (ValueError,KeyError):return
            raise AssertionError("Expected rejection")
        reject(lambda:preflight(source,target,index,{**common,"packages":{"fixture":"2"}},supports))
        raw=pred.read_bytes();pred.write_bytes(raw+b" ")
        reject(lambda:preflight(source,target,index,common,supports));pred.write_bytes(raw)
        sp=Path(plan[0]["source"]["path"]);raw=sp.read_bytes();sp.write_bytes(raw+b" ")
        reject(lambda:preflight(source,target,index,common,supports))
        reject(lambda:copy_plan(plan));sp.write_bytes(raw)
        dest=Path(plan[0]["destination"]);raw=dest.read_bytes();dest.write_bytes(raw+b" ")
        reject(lambda:preflight(source,target,index,common,supports));dest.write_bytes(raw)
        cp=source/"COVERAGE.csv";raw=cp.read_bytes();cp.write_bytes(raw+b" ")
        reject(lambda:preflight(source,target,index,common,supports));cp.write_bytes(raw)
        save(target/"HEARTBEAT.json",{})
        reject(lambda:preflight(source,target,index,common,supports))
        from unittest.mock import patch
        interrupted=target/"interrupted.json"
        with patch.object(os,"link",side_effect=OSError("fixture interrupted before publication")):
            try:publish_no_replace(interrupted,b"complete bytes")
            except OSError:pass
            else:raise AssertionError("Expected interrupted publication")
        assert not interrupted.exists() and not list(target.glob(".s6b-score-*.tmp"))
    return dict(status="PASS",checks=10,scope="Actual score-transfer path: exact atomic copy/resume, changed package/prediction/score/coverage, conflicting destination, active target, post-admission byte change and interrupted publication.")
def run(args):
    report=args.report;source=report/args.source_analysis_subdir;target=report/args.target_analysis_subdir;out=report/args.receipt_subdir
    for p in (source,target,out):
        if p.resolve()==report.resolve() or report.resolve() not in p.resolve().parents:raise ValueError("All directories must be report children")
    index_path=args.target_index if args.target_index.is_absolute() else report/args.target_index
    inputs=read(report/"INPUT_INDEX.json");supports={(r["case_id"],r["stream"]):r["support"] for r in inputs["rows"]}
    codes=[bind(Path(__file__).parent/name) for name in ("s6b_analysis.py","s6a_text_metrics.py","s6a_cue_score.py","s6a_support_metrics.py","s6a_baseline_results.py","s4_h2_analysis.py","s5_statistics.py")]
    packages={name:version(name) for name in ("numpy","scipy","meeteval")}
    if packages["meeteval"]!="0.4.3":raise ValueError("Pinned MeetEval0.4.3 required")
    common=dict(bank=bind(SIM/"scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json"),codes=codes,packages=packages,metric_schema=SCHEMA)
    plan,sources=preflight(source,target,read(index_path),common,supports)
    counts=dict(copied=0,existing_exact=0) if args.verify_only else copy_plan(plan)
    receipt=dict(status="VERIFIED_COMPATIBLE_NO_COPY" if args.verify_only else "COMPLETE_VERIFIED_SCORE_TRANSFER",code=bind(__file__),tests=tests(),
        **sources,target_prediction_index=bind(index_path),current_input_index=bind(report/"INPUT_INDEX.json"),current_dependencies=common,
        planned=len(plan),**counts,target_analysis_directory=str(target),scores=plan,
        scope="Exact per-output metrics only. No source mutation or aggregate/receipt copy. Fresh core run must reverify current predictions/supports/keys and rebuild all final aggregates. Boundary checks do not lock files against later arbitrary mutation.")
    save(out/"SCORE_TRANSFER_RECEIPT.json",receipt)
    return {k:receipt[k] for k in ("status","planned","copied","existing_exact")}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",type=Path,default=SIM/"reports/S6B/20260909T230840Z")
    p.add_argument("--source-analysis-subdir",default="r0_full_analysis_v1")
    p.add_argument("--target-analysis-subdir",default="full_analysis_v1")
    p.add_argument("--target-index",type=Path,default=Path("PREDICTION_INDEX.json"))
    p.add_argument("--receipt-subdir",default="score_transfer_v1")
    p.add_argument("--verify-only",action="store_true");p.add_argument("--test",action="store_true")
    a=p.parse_args();print(json.dumps(tests() if a.test else run(a),indent=2))
if __name__=="__main__":main()
