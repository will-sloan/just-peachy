"""Independent S6D intake and angle aggregate verification. See README_S6D_ROOT_REVIEW.md."""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

def bind(path):
    p=Path(path).resolve()
    return {"path":str(p),"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}

def verify(b):
    actual=bind(b["path"])
    assert actual==b,(actual,b)
    return actual

def main(pack, report, output):
    assert not output.exists(), "Use fresh receipt path"
    pack=pack.resolve()
    checksum=pack/"CHECKSUMS_SHA256.txt"
    entries=[]
    for line in checksum.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():continue
        sha, name=line.split(None,1)
        p=(pack/name.strip()).resolve()
        assert p.is_relative_to(pack), name
        actual=bind(p)
        assert actual["sha256"]==sha, name
        entries.append(actual)
    result_path=report/"angles/eval_v1/RESULT.json"
    result=json.loads(result_path.read_text())
    csv_path=report/"angles/eval_v1/TURN_RESCORES.csv"
    rows=list(csv.DictReader(csv_path.open(newline="",encoding="utf-8-sig")))
    assert len(rows)==result["rows"]==13986
    groups=defaultdict(list)
    turn_groups=defaultdict(dict)
    for row in rows:
        width=float(row["evaluator_half_width_deg"])
        assert float(row["manual_original_half_width_deg"])==5.
        groups[(row["stream"],width)].append(row)
        key=(row["stream"],row["case_id"],row["utterance_label"])
        assert width not in turn_groups[key]
        turn_groups[key][width]=row
    assertions=0
    def close(a,b):
        nonlocal assertions
        assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-7),(a,b)
        assertions+=1
    for key, versions in turn_groups.items():
        assert set(versions)=={0.,2.,5.}
        interval=[]
        for width in [5.,2.,0.]:
            row=versions[width]
            for field in ("nominal_native_deg","support_sec","usable_sec"):
                close(float(row[field]),float(versions[5.][field]))
            assert row["stable_large_nominal_error"]==versions[5.]["stable_large_nominal_error"]
            if row["nominal_error_mean_deg"]:
                close(float(row["nominal_error_mean_deg"]),float(versions[5.]["nominal_error_mean_deg"]))
                interval.append(float(row["interval_error_mean_deg"]))
            else:assert not row["interval_error_mean_deg"]
        assert all(a<=b+1e-8 for a,b in zip(interval,interval[1:]))
    for summary in result["summary"]:
        group=groups[(summary["stream"],float(summary["evaluator_half_width_deg"]))]
        support=sum(float(x["support_sec"]) for x in group)
        usable=sum(float(x["usable_sec"]) for x in group)
        close(support,summary["support_sec"]);close(usable,summary["usable_sec"])
        assert len(group)==summary["all_turns"]==777
        assert sum(float(x["usable_sec"])>0 for x in group)==summary["usable_turns"]
        assert sum(x["stable_large_nominal_error"]=="True" for x in group)==summary["stable_large_nominal_error_turns"]
        assert len({x["case_id"] for x in group if x["stable_large_nominal_error"]=="True"})==summary["stable_large_nominal_error_cases"]
        for metric in ("nominal_error_mean_deg","interval_error_mean_deg"):
            weighted=sum(float(x[metric])*float(x["usable_sec"]) for x in group if x[metric])
            close(weighted/usable,summary[metric])
        for threshold in (0,5,10,20,35):
            metric=f"interval_within_{threshold}_deg_sec"
            value=sum(float(x[metric]) for x in group)
            close(value,summary[metric])
            close(value/support,summary[f"interval_within_{threshold}_deg_fraction_of_all_support"])
            close(value/usable,summary[f"interval_within_{threshold}_deg_fraction_of_usable_support"])
    case_bindings=[verify(x["result"]) for x in result["cases"]]
    assert len(case_bindings)==240
    assert result["new_model_calls"]==result["new_hardware_passes"]==0
    assert not result["operational_parameters_changed"]
    selected=[x for x in result["summary"] if x["stream"]=="selected_processed"]
    receipt={"schema":"s6d-root-intake-angle-review.v1","status":"PASS_SCOPED_INDEPENDENT_VERIFICATION",
        "created_utc":datetime.now(timezone.utc).isoformat(),"reviewer":"root independent of angle helper author",
        "helper":bind(__file__),"readme":bind(Path(__file__).with_name("README_S6D_ROOT_REVIEW.md")),
        "pack_checksum_manifest":bind(checksum),"pack_members_verified":len(entries),"pack_bindings":entries,
        "result":bind(result_path),"turn_csv":bind(csv_path),"case_files_verified":len(case_bindings),
        "rows_independently_aggregated":len(rows),"numeric_assertions":assertions,"selected_processed_summary":selected,
        "source_review":["Whole signed interval folded before interval-error scoring; 0 and 180 remain distinct.",
            "Nominal coarse-sector behavior retained; supplementary allowed interval sectors use separately disclosed boundary snapping.",
            "Stable-wrong counts and support are unchanged across5/2/0; width cannot repair measured azimuth.",
            "Frozen prediction hash/evaluator graph comparison is scoped to fixed predictions; it is not a new native pipeline determinism test."],
        "new_model_calls":0,"new_hardware_calls":0,
        "limitations":["Independent aggregate and case-file binding verification; not a second raw-telemetry rescore.",
            "No human listening or physical direction accuracy qualification inferred.","S6D broader scope remains in progress."]}
    with output.open("x",encoding="utf-8") as f:json.dump(receipt,f,indent=2,allow_nan=False);f.write("\n")
    print(json.dumps({"status":receipt["status"],"pack_members":len(entries),"rows":len(rows),"numeric_assertions":assertions,"receipt":bind(output)}))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pack",type=Path,required=True);p.add_argument("--report",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();main(a.pack,a.report,a.output)
