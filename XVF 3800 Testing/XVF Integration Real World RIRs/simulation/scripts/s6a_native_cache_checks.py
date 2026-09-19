"""Read-only native completed-result mutation fixtures. See README_s6a_native_cache_checks.md."""
from __future__ import annotations
import argparse
import copy
import hashlib
import inspect
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
from unittest.mock import patch

NUMERIC_ENV_KEYS=("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS")
for key in NUMERIC_ENV_KEYS:os.environ[key]="1"

from s6a_runtime_profile import atomic, sha, utc


def binding(path):
    p=Path(path)
    return {"path":str(p),"sha256":sha(p),"bytes":p.stat().st_size}


def changed_digest(label, value):
    return hashlib.sha256(json.dumps({"prospective_dependency":label,"original":value},sort_keys=True).encode()).hexdigest()


def run(args):
    import s6a_probes as probes
    sys.path.insert(0,str(args.repo/"Software Validation from Datasets/Evaluation Tool/app"))
    from edge_speech_pipeline.research_profiles import ResearchProfile
    manifest_path=args.report/"PROBE_JOB_MANIFEST_V2.json"
    manifest=json.loads(manifest_path.read_text())
    selected=None
    for job in manifest["jobs"]:
        path=Path(job["report_dir"])/"run_receipt.json"
        if job["profile_id"]=="P0X1" and path.exists() and json.loads(path.read_text()).get("status")=="COMPLETE":
            selected=job
            break
    if selected is None:raise RuntimeError("need one complete cue-enabled V2 P0X1 result")
    original_path=Path(selected["report_dir"])/"run_receipt.json"
    original=json.loads(original_path.read_text())
    if original["job_key"]!=selected["job_key"] or original["identity"]!=selected["identity"]:
        raise RuntimeError("selected completed source identity differs")
    args.output.mkdir(parents=True,exist_ok=False)
    fixture=args.output/"isolated_completed_copy"
    fixture.mkdir()
    isolated_receipt=fixture/"run_receipt.json"
    shutil.copyfile(original_path,isolated_receipt)
    base=copy.deepcopy(selected)
    base["report_dir"]=str(fixture)
    # Only this destination changes; immutable scientific/execution identity is exact.
    base["payload_root"]=str(args.output/"NEVER_CREATED_PAYLOAD")

    protected={str(manifest_path),str(original_path)}
    def collect(x):
        if isinstance(x,dict):
            if "path" in x and "sha256" in x and Path(x["path"]).is_file():
                protected.add(str(Path(x["path"])))
            for y in x.values():collect(y)
        elif isinstance(x,list):
            for y in x:collect(y)
    collect(selected);collect(original)
    for name in ("audio_spool.pcm16","session_summary.json","events.jsonl"):
        p=Path(original["session_dir"])/name
        if p.exists():protected.add(str(p))
    before={p:binding(p) for p in sorted(protected)}
    isolated_before=binding(isolated_receipt)
    calls={"launch_guard":0,"subprocess":0,"save":0,"native_completion_verification":0}
    def forbid(name):
        def fail(*a,**k):
            calls[name]+=1
            raise RuntimeError("test forbids "+name+"; no model launch or receipt mutation allowed")
        return fail
    verify=probes.verify_native_completion
    def count_verify(*a,**k):
        calls["native_completion_verification"]+=1
        return verify(*a,**k)
    changes=[]
    profile_original=json.loads(Path(selected["profile"]["path"]).read_text())
    fields=[
        ("endpoint_rule1","asr","endpoint_rule1_silence_sec",1.6),
        ("endpoint_rule2","asr","endpoint_rule2_silence_sec",.8),
        ("endpoint_rule3","asr","endpoint_rule3_utterance_sec",25.),
        ("decoder","asr","decoding_method","modified_beam_search"),
        ("blank_penalty","asr","blank_penalty",.1),
        ("host_dispatch","asr","journal_read_ms",50),
        ("segmentation_stride","segmentation","hop_sec",.5),
        ("segmentation_post_policy","segmentation","post_policy","posterior_hysteresis"),
        ("embedding_span","embedding","window_sec",1.),
        ("embedding_cadence","embedding","hop_sec",.75),
        ("embedding_quality_rms","embedding","minimum_rms",.001),
        ("tracker_policy","tracker","cosine_threshold",.4),
        ("tap_declaration","input","tap","O1"),
        ("model_threads","runtime","asr_threads",1),
        ("display_timing","punctuation","partial_display_min_interval_sec",.1),
    ]
    for label,section,field,value in fields:
        profile=copy.deepcopy(profile_original)
        profile[section][field]=value
        ResearchProfile.from_dict(profile)  # A supported prospectively changed profile, never executed.
        encoded=json.dumps(profile,indent=2).encode()
        pb={**selected["profile"],"sha256":hashlib.sha256(encoded).hexdigest(),"bytes":len(encoded)}
        job=copy.deepcopy(base);job["profile"]=pb;job["identity"]["profile"]=pb
        changes.append((label,job,{"profile_field":section+"."+field,"new_value":value,"supported_profile_validation":"PASS"}))
    profile=copy.deepcopy(profile_original);profile["input"]["already_gained"]=False;profile["input"]["gain"]=1.1
    ResearchProfile.from_dict(profile)
    encoded=json.dumps(profile,indent=2).encode();pb={**selected["profile"],"sha256":hashlib.sha256(encoded).hexdigest(),"bytes":len(encoded)}
    job=copy.deepcopy(base);job["profile"]=pb;job["identity"]["profile"]=pb
    changes.append(("explicit_input_gain",job,{"profile_fields":{"input.already_gained":False,"input.gain":1.1},"supported_profile_validation":"PASS"}))
    for field in ("audio","raw_audio","telemetry"):
        job=copy.deepcopy(base)
        job["identity"][field]["sha256"]=changed_digest(field,job["identity"][field])
        mirror={"audio":"input_audio","raw_audio":"raw_audio","telemetry":"telemetry"}[field]
        job[mirror]=copy.deepcopy(job["identity"][field])
        changes.append((field+"_content",job,{"dependency":field,"mutation":"prospective content hash; original bytes never changed"}))
    job=copy.deepcopy(base);job["identity"]["gain_once"]=1.;job["adapter"]["gain_scalar"]=1.
    changes.append(("upstream_once_only_gain",job,{"dependency":"gain_once","new_value":1.}))
    job=copy.deepcopy(base);job["stream"]="O1"
    job["identity"]["raw_audio"]["path"] += ".prospective_O1"
    job["raw_audio"]=copy.deepcopy(job["identity"]["raw_audio"])
    changes.append(("physical_output_tap_binding",job,{"dependency":"stream/raw audio path","mutation":"prospective other tap, no file read"}))
    job=copy.deepcopy(base);job["identity"]["telemetry"]=None;job["telemetry"]=None
    changes.append(("telemetry_absent",job,{"dependency":"telemetry","new_value":None}))
    for field in ("code","assets"):
        job=copy.deepcopy(base);job["identity"][field][0]["sha256"]=changed_digest(field,job["identity"][field][0])
        changes.append((field+"_binding",job,{"dependency":field,"mutation":"prospective dependency hash; original bytes never changed"}))
    for field in ("provider","process_lifecycle","schema"):
        job=copy.deepcopy(base);job["identity"][field]+=":PROSPECTIVE_MUTATION"
        changes.append((field,job,{"dependency":field,"mutation":"prospective changed execution contract"}))
    rows=[]
    with patch.object(probes,"launch_allowed",forbid("launch_guard")),patch.object(probes.subprocess,"Popen",forbid("subprocess")),patch.object(probes,"save",forbid("save")),patch.object(probes,"verify_native_completion",count_verify):
        exact=probes.run_job(base)
        if exact["status"]!="COMPLETE_REUSED":raise AssertionError("exact completed identity did not reuse")
        if calls["native_completion_verification"]!=1:raise AssertionError("exact reuse did not validate full native audio/completion")
        rows.append({"test":"exact_identity_reuses","status":"PASS","actual_return":exact["status"],"native_completion_verified":True})
        for label,job,detail in changes:
            job["job_key"]=probes.stable_hash(job["identity"])
            if job["job_key"]==base["job_key"]:raise AssertionError("mutation did not change key")
            old_calls=copy.deepcopy(calls)
            try:
                probes.run_job(job)
            except AssertionError as exc:
                frames=traceback.extract_tb(exc.__traceback__)
                if not any(Path(f.filename).resolve()==Path(probes.__file__).resolve() and f.name=="run_job" for f in frames):
                    raise AssertionError("rejection did not originate in actual reuse path") from exc
                if calls!=old_calls:raise AssertionError("mutation reached verification or launch")
                if binding(isolated_receipt)!=isolated_before:raise AssertionError("isolated receipt changed")
                rows.append({"test":label,"status":"PASS","result":"completed_identity_rejected_before_inference_or_write",**detail})
            else:
                raise AssertionError("changed identity unexpectedly reused: "+label)
        # Also prove the content-identity equality guard matters if an inconsistent caller supplies an old key.
        inconsistent=copy.deepcopy(changes[0][1]);inconsistent["job_key"]=base["job_key"]
        old_calls=copy.deepcopy(calls)
        try:probes.run_job(inconsistent)
        except AssertionError:
            if calls!=old_calls:raise AssertionError("identity-only mismatch reached verification or launch")
            rows.append({"test":"changed_identity_with_unchanged_key_rejected","status":"PASS","result":"actual identity equality guard rejects"})
        else:raise AssertionError("changed identity with stale key reused")
    after={p:binding(p) for p in sorted(protected)}
    if before!=after:raise AssertionError("protected active input or completed evidence changed")
    if binding(isolated_receipt)!=isolated_before:raise AssertionError("copied receipt changed")
    if sorted(p.name for p in fixture.iterdir())!=["run_receipt.json"]:raise AssertionError("unexpected fixture output")
    if Path(base["payload_root"]).exists():raise AssertionError("inference payload directory created")
    if any(calls[k] for k in ("launch_guard","subprocess","save")):raise AssertionError("forbidden operation reached")
    receipt={"schema":"s6a_native_completed_reuse_mutations_v1","status":"PASS","created_utc":utc(),
             "tests":len(rows),"exact_reuses":1,"mutation_rejections":len(rows)-1,"rows":rows,"guard_calls":calls,
             "source_job":{"case_id":selected["case_id"],"stream":selected["stream"],"profile_id":selected["profile_id"],"job_key":selected["job_key"]},
             "active_receipt_before":before[str(original_path)],"active_receipt_after":after[str(original_path)],
             "protected_file_count":len(protected),"protected_files_unchanged":True,
             "protected_bindings":list(before.values()),"isolated_receipt_unchanged":True,
             "actual_run_job_source":binding(probes.__file__),"actual_run_job_symbol_sha256":hashlib.sha256(inspect.getsource(probes.run_job).encode()).hexdigest(),
             "test_source":binding(__file__),"no_models_launched":True,"no_active_manifest_input_or_receipt_mutation":True,
             "scope":"Conservative complete-result reuse rejection using actual run_job, plus supported profile validation. Alternative graphs/decoder settings are not executed by this test; this is not a minimal upstream DAG hit/miss test."}
    atomic(args.output/"NATIVE_CACHE_MUTATION_RECEIPT.json",receipt)
    atomic(args.report/"NATIVE_CACHE_MUTATION_RECEIPT.json",receipt)
    print(json.dumps({"status":"PASS","tests":len(rows),"mutation_rejections":len(rows)-1,"protected_files":len(protected),"model_launches":0,"receipt":str(args.output/"NATIVE_CACHE_MUTATION_RECEIPT.json")}),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True);p.add_argument("--report",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    run(p.parse_args())


if __name__=="__main__":main()

