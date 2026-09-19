"""Bind numerical source immediately after passed controls; see S2_README.md."""
import argparse,hashlib
from pathlib import Path
from s0_common import read,save

def bind(report):
    report=Path(report);result=report/"final_policy_controls.json"
    cfg=read(report/"EXTRACTION_CONFIG.json")
    if read(result)["status"]!="PASSED" or hashlib.sha256(result.read_bytes()).hexdigest()!=cfg["final_policy_controls_sha256"]:
        raise ValueError("Passed controls and frozen config must match")
    rows=[]
    for name in ("s2_signal.py","s2_controls.py","s1_signal.py","s1_synthetic.py"):
        path=Path(__file__).parent/name
        if path.stat().st_mtime_ns>result.stat().st_mtime_ns:raise ValueError("Code changed after controls: "+name)
        rows.append({"path":str(path.resolve()),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                     "scope":"Exact numerical/control source, unchanged since passed controls"})
    out=report/"CONTROL_CODE_BINDINGS.json"
    if out.exists():
        old={r["path"]:r["sha256"] for r in read(out)}
        if old!={r["path"]:r["sha256"] for r in rows}:raise ValueError("Existing code gate differs")
        print("Existing successful code gate verified.")
    else:save(out,rows);print("Successful numerical code gate written.")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--report",required=True);bind(p.parse_args().report)
