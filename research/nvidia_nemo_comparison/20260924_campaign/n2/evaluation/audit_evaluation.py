"""Verify N2 private manifests, completed vectors and executable tests; see README.md."""
from datetime import datetime,timezone
import io
from pathlib import Path
import unittest

import numpy as np

from prepare import HERE,bind,fingerprint,load,sha
from run_embeddings import atomic


def main():
    local=Path("G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation")
    manifest_receipt=load(local/"MANIFEST_RECEIPT.json")
    checked=0
    for ref in manifest_receipt["inputs"]+manifest_receipt["outputs"]:
        if sha(ref["path"])!=ref["sha256"]:raise ValueError("Prepared input/output hash drift")
        checked+=1
    regression_receipt=load(HERE/"REGRESSION_PREPARATION_RECEIPT_V1.json")
    regression_source=local.parent.parent/"data/REGRESSION_AUDIO_ONLY.json"
    regression_output=local/"REGRESSION_AUDIO_ONLY.json"
    for path,expected in [(regression_source,regression_receipt["source_manifest"]["sha256"]),
                          (regression_output,regression_receipt["output_manifest"]["sha256"]),
                          (local/"EVALUATOR_TRUTH.json",regression_receipt["truth_sha256"]),
                          (HERE/"prepare_regression.py",regression_receipt["generator_sha256"])]:
        if sha(path)!=expected:raise ValueError("Frozen regression manifest binding drift")
        checked+=1
    original=load(regression_source);normalized=load(regression_output)
    aliases=regression_receipt["scheduler_aliases"]
    if len(aliases)!=8 or fingerprint(aliases)!=regression_receipt["alias_receipt_sha256"]:
        raise ValueError("Frozen regression alias receipt changed")
    expected=dict(original,jobs=[dict(job,job_id=aliases[job["job_id"]]) for job in original["jobs"]])
    if normalized!=expected:raise ValueError("Regression changed a field beyond the scheduler ID")
    decision_path=HERE/"NOMINAL_PROFILE_DECISION_V1.json"
    if sha(decision_path)!="09b86b287ae76f64f13bddd26ae30a7aa26d3f6ab12f94c2093e176ebdf30eac":
        raise ValueError("Immutable nominal profile decision v1 changed")
    decision=load(decision_path)
    if fingerprint({k:v for k,v in decision.items() if k!="decision_payload_sha256"})!=decision["decision_payload_sha256"]:
        raise ValueError("Nominal decision payload binding changed")
    for name,key in [("protocol.json","original_protocol_sha256"),
                     ("PROTOCOL_AMENDMENT_01.json","collar_amendment_sha256"),
                     ("native_profiles/NATIVE_PROFILE_SUMMARY.json","native_full_summary_sha256")]:
        if sha(HERE/name)!=decision["bindings"][key]:raise ValueError("Nominal decision evidence binding changed")
        checked+=1
    vectors=[];executed=[]
    for encoder in ["E0","E1"]:
        base=local/"component"/encoder
        admission=load(base/"ADMISSION.json")
        snapshot=local/"executed_source_v1/run_embeddings.py"
        if sha(snapshot)!=admission["runner_sha256"]:raise ValueError("Executed extraction source snapshot mismatch")
        executed.append({"encoder":encoder,"admission":bind(base/"ADMISSION.json"),"executed_runner":bind(snapshot),
                         "executed_scoring":bind(local/"executed_source_v1/scoring.py"),"current_reviewed_runner":bind(HERE/"run_embeddings.py")})
        total=0
        for path in (base/"windows").glob("*.json"):
            row=load(path)
            if row["status"]=="COMPLETE":
                value=np.asarray(row["vector"],np.float32)
                if value.shape!=(192,) or not np.isfinite(value).all() or abs(float(np.linalg.norm(value))-1)>1e-4:
                    raise ValueError("Malformed stored embedding")
                total+=1
        if total!=1194:raise ValueError("Missing actual component vectors")
        vectors.append({"encoder":encoder,"actual_stored_vectors_checked":total,"dimension":192,"finite_unit_vectors":True})
        safe=load(base/"RUNTIME_GALLERY_INDEX_SAFE.json")
        for condition in safe["conditions"]:
            if sha(condition["gallery"]["path"])!=condition["gallery"]["sha256"]:raise ValueError("Runtime gallery payload drift")
            checked+=1
    suite=unittest.defaultTestLoader.discover(str(HERE),pattern="test_*.py")
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    if not result.wasSuccessful():raise RuntimeError(stream.getvalue())
    report={"schema":"n2-evaluation-audit-v1","status":"ACTUALLY_RUN_PASS","utc":datetime.now(timezone.utc).isoformat(),
            "tests_run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped),
            "manifest_and_gallery_hashes_verified":checked,"vectors":vectors,"executed_source_receipts":executed,
            "regression_alias_jobs_verified":len(aliases),"nominal_profile_decision_v1_verified":True,
            "current_code":[bind(p) for p in sorted(HERE.glob("*.py"))],"test_output":stream.getvalue(),
            "models_called_by_audit":0,"hardware_calls":0,"N1_frozen_inputs_unchanged":True,
            "scope":"unit/regression, metadata integrity and stored vector admission; numerical execution receipts separate; no hardware or independent deployment certification"}
    atomic(HERE/"EVALUATION_AUDIT.json",report)
    print({"status":report["status"],"tests":result.testsRun,"vector_count":sum(v["actual_stored_vectors_checked"] for v in vectors),"bound_inputs_outputs":checked})


if __name__=="__main__":main()
