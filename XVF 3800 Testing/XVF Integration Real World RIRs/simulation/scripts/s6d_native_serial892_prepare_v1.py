"""Build one serial892 metadata proposal; see README_S6D_NATIVE_SERIAL892_PREPARE_V1.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
R = SIM / "reports/S6D/20260913T195357Z"
G = Path("G:/Just_Peachy_S6D/20260913T195357Z")
PRIOR = R / "runner/native_remaining892_preparation_v2/PREPARATION_RESULT.json"
PRIOR_SHA = "fabab6c7971b81e1e6c32f4713a1ad3a78d44a49d59396ec060c457cad8fa3f8"
CONSTRAINT = R / "runner/native_concurrency_estimands_v1/SOURCE_CONCURRENCY_CONSTRAINTS_V1.json"
CONSTRAINT_SHA = "a10d348913d502e85faa69fb7213e746e080fe2221c6661810f570a39283af4e"

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def bind(path):
    p = Path(path).resolve()
    data = p.read_bytes()
    return dict(path=str(p), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

def verify(b):
    if bind(b["path"]) != b:
        raise ValueError("Changed metadata/source binding: " + b["path"])
    return b

def pinned(path, sha):
    b = bind(path)
    if b["sha256"] != sha:
        raise ValueError("Changed pinned authority: " + str(path))
    return b

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def write(path, value):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
    return bind(path)

def unique(rows):
    result = {}
    for b in rows:
        if b["path"] in result and result[b["path"]] != b:
            raise ValueError("Conflicting source binding")
        result[b["path"]] = b
    return list(result.values())

def excluded(value, keys):
    return {k: v for k, v in value.items() if k not in keys}

def prepare(output, payload):
    output, payload = output.resolve(), payload.resolve()
    if output.parent != R / "runner" or payload.parent != G / "runner":
        raise ValueError("Bounded fresh R/runner and G/runner directories required")
    if output.exists() or payload.exists():
        raise ValueError("Fresh directories required; prior epochs will not be overwritten")
    prior_b = pinned(PRIOR, PRIOR_SHA)
    constraint_b = pinned(CONSTRAINT, CONSTRAINT_SHA)
    prior = read(PRIOR)
    constraint = read(CONSTRAINT)
    if constraint["recommendation"]["mandatory_speaker_name_efficacy"] != "CONTROLLED_SERIAL":
        raise ValueError("Serial allocation authority differs")
    metadata = [prior["matrix"], prior["forecast"], *prior["manifests"]]
    metadata += [g[k] for g in prior["groups"] for k in ("queue", "approval_proposal", "root_admission_proposal")]
    for b in unique(metadata):
        verify(b)
    old_matrix = read(prior["matrix"]["path"])
    groups = prior["groups"]
    if [g["group"] for g in groups] != [f"worker_{i}_{phase}" for i in range(1, 5) for phase in ("pilot", "continuation")]:
        raise ValueError("Unexpected prior deterministic partition")
    if old_matrix["accepted_credits"] != 0 or len(old_matrix["conditional_credits"]) != 68:
        raise ValueError("Conditional credit authority differs")
    old_queues = [read(g["queue"]["path"]) for g in groups]
    old_manifests = [read(b["path"]) for b in prior["manifests"]]
    original_jobs = [j for m in old_manifests for j in m["jobs"]]
    original_qjobs = [j for q in old_queues for j in q["jobs"]]
    identifiers = [j["job_id"] for j in original_jobs]
    if len(identifiers) != 892 or len(set(identifiers)) != 892 or identifiers != [j["job_id"] for j in original_qjobs]:
        raise ValueError("Prior 892 membership or deterministic order differs")
    if identifiers != [row["job_id"] for row in old_matrix["rows"]]:
        raise ValueError("Prior matrix order differs")
    for m in old_manifests:
        if m["limits"] != old_manifests[0]["limits"] or m["limits"]["cpu_affinity"] != [12, 13, 14, 15]:
            raise ValueError("Allocation changed")
        if m["limits"]["cpu_threads_each"] != 1 or m["limits"]["cell_timeout_sec"] != 180.:
            raise ValueError("Per-cell limits changed")
    # Verify unique source/metadata files only. Do not open PCM, models, journals or active results.
    core_sources = unique([b for q in old_queues for j in q["jobs"] for b in j["source_bindings"]])
    for b in core_sources:
        verify(b)
    approval_template = read(groups[0]["approval_proposal"]["path"])
    for b in approval_template["executable_bindings"]:
        verify(b)
    output.mkdir(parents=True)
    payload.mkdir(parents=True)
    data = payload / "data"
    data.mkdir()
    native, protocol, state = payload / "native_outputs", payload / "protocol", payload / "state"
    prerequisites = [
        "Root retains the exact C065/C088 GUIv3 T0/V0 candidate after controlled native176 analysis.",
        "All68 exact predeclared native176 credits are independently accepted with full-source audit, protocol closure and owner exit; accepted credit count remains zero here.",
        "Controlled native176/Tk/HOST allocation is closed or explicitly separated; this queue has exactly one neural worker and no other neural session may overlap it.",
        "The four-way native proposals remain unapproved and are not alternative efficacy evidence.",
        "C>=50GiB, G>=75GiB and the shared40GiB new-payload cap cover future outputs; original deadline and45-minute reserve remain unchanged.",
        "Root reviews literal queue, all892 cells, exact executable/environment/source/model/audio/gallery bindings and unchanged completion predicates before authorization.",
        "Failures, stopped prefixes and incomplete credits remain adverse; no timeout extension, sample dropping, favorable-repeat selection or silent replacement is permitted.",
    ]
    matrix = deepcopy(old_matrix)
    for row, oldrow in zip(matrix["rows"], old_matrix["rows"]):
        row.update(source_worker=oldrow["worker"], source_phase=oldrow["phase"], worker=1, phase="serial",
                   output=str(native / f"profile_{oldrow['worker']}" / row["job_id"]))
    matrix.update(schema="s6d-native-serial-full-bank.v1", status="CONDITIONAL_SERIAL_PROPOSAL_NOT_ADMITTED",
                  prior_parallel_matrix=prior["matrix"], source_preparation=prior_b, source_concurrency_constraint=constraint_b,
                  prerequisites=prerequisites, pilot_jobs=0, continuation_jobs=0, serial_jobs=892,
                  partition="one serial worker; V2 workers1..4 concatenated, each original4+219 order retained; no outcome selection",
                  parallel_pilot_required=False, maximum_total_neural_workers_during_queue=1)
    matrix_b = write(data / "CONDITIONAL_MATRIX.json", matrix)
    manifests, new_jobs = [], []
    for i, original in enumerate(old_manifests, 1):
        m = deepcopy(original)
        for job in m["jobs"]:
            job.update(output=str(native / f"profile_{i}" / job["job_id"]),
                       scientific_role="FULL_BANK_CONTROLLED_SERIAL_SOURCE_PACED_NATIVE_CONFIRMATION")
        m.update(payload_root=str(native / f"profile_{i}"), status="CONDITIONAL_SERIAL_FULL_BANK_ROOT_ADOPTION_REQUIRED",
                 created_utc=datetime.now(timezone.utc).isoformat(), approved=False, approval=None, model_jobs_started=0,
                 prior_parallel_manifest=prior["manifests"][i-1], conditional_matrix=matrix_b,
                 concurrency_scope=dict(serial_within_this_worker=True, maximum_total_NN_workers_across_all_studies=1,
                                        no_other_neural_sessions_during_queue=True, logical_cpu_affinity=[12, 13, 14, 15],
                                        physical_core_isolation=False, CM5_benchmark=False))
        manifests.append(write(data / f"SERIAL_PROFILE_{i}_MANIFEST.json", m))
        new_jobs.extend(m["jobs"])
    new_jobmap = {j["job_id"]: j for j in new_jobs}
    qjobs = []
    for pos, (old, oldq) in enumerate(zip(original_jobs, original_qjobs)):
        i = pos // 223
        mb = manifests[i]
        job = new_jobmap[old["job_id"]]
        pp, op = protocol / job["job_id"], Path(job["output"])
        qj = deepcopy(oldq)
        qj.update(heartbeat_path=str(pp / "HEARTBEAT.json"), completion_path=str(pp / "COMPLETION.json"),
                  stop_request_path=str(pp / "STOP_REQUEST.json"), scientific_role=job["scientific_role"])
        qj["argv"][7], qj["argv"][9] = mb["path"], mb["sha256"]
        replaced = {prior["manifests"][i]["path"], prior["matrix"]["path"]}
        qj["source_bindings"] = unique([b for b in oldq["source_bindings"] if b["path"] not in replaced] + [mb, matrix_b, constraint_b])
        arts = qj["expected_artifacts"]
        arts[0]["path"] = qj["completion_path"]
        arts[1]["path"] = str(op / "RESULT.json")
        arts[2]["path"] = str(op / "FULL_SOURCE_AUDIT.json")
        for art in arts:
            art["expected_fields"]["manifest.sha256"] = mb["sha256"]
        arts[0]["expected_fields"]["completion_audit.path"] = arts[2]["path"]
        qjobs.append(qj)
    q = deepcopy(old_queues[0])
    q.update(created_utc=datetime.now(timezone.utc).isoformat(), production_status="CONDITIONAL_SERIAL_PROPOSAL_NOT_ADMITTED",
             preparation=matrix_b, group="serial892", jobs=qjobs,
             allocation_constraint=dict(source=constraint_b, maximum_total_NN_workers_across_all_studies=1,
                                        no_other_neural_sessions_during_queue=True))
    qb = write(data / "QUEUE.json", q)
    approval = deepcopy(approval_template)
    approval.update(queue_sha256=qb["sha256"], authorization_ref=str(data / "ROOT_ADMISSION.json"),
                    approved_job_sha256=[], proposed_job_sha256=[digest(j) for j in qjobs],
                    approval_state="NOT_APPROVED_CONDITIONAL_SERIAL_ROOT_REVIEW_REQUIRED")
    ab = write(data / "APPROVAL_PROPOSAL.json", approval)
    rb = write(data / "ROOT_ADMISSION_PROPOSAL.json",
               dict(schema="s6d-native-serial-root-admission-proposal.v1", status="NOT_ADMITTED", queue=qb,
                    manifests=manifests, matrix=matrix_b, allocation=constraint_b,
                    prerequisite_status={p: "PENDING" for p in prerequisites}, accepted_native176_credit_count=0,
                    proposed_native176_credit_count=68, exact_new_jobs=892, root_review_passed=False,
                    maximum_total_NN_workers_across_all_studies=1, no_other_neural_sessions_during_queue=True,
                    parallel_pilot_required=False, no_authority_to_launch=True, deadline_not_extended=True))
    # Actual metadata readback: test allowed deltas, not scientific values or model behavior.
    q2 = read(qb["path"])
    ms2 = [read(b["path"]) for b in manifests]
    js2 = [j for m in ms2 for j in m["jobs"]]
    if [j["job_id"] for j in q2["jobs"]] != identifiers or [j["job_id"] for j in js2] != identifiers:
        raise ValueError("Serialized membership changed")
    if read(matrix_b["path"])["conditional_credits"] != old_matrix["conditional_credits"]:
        raise ValueError("Conditional credits changed")
    for old, new, oldq, newq in zip(original_jobs, js2, original_qjobs, q2["jobs"]):
        if excluded(old, {"output", "scientific_role"}) != excluded(new, {"output", "scientific_role"}):
            raise ValueError("Native scientific job changed")
        qmutable = {"argv", "heartbeat_path", "completion_path", "stop_request_path", "source_bindings", "expected_artifacts", "scientific_role"}
        if excluded(oldq, qmutable) != excluded(newq, qmutable):
            raise ValueError("Native protocol limits or guards changed")
        if [x for n, x in enumerate(oldq["argv"]) if n not in (7, 9)] != [x for n, x in enumerate(newq["argv"]) if n not in (7, 9)]:
            raise ValueError("Native executable/helper/arguments changed")
        for a, b in zip(oldq["expected_artifacts"], newq["expected_artifacts"]):
            if excluded(a, {"path", "expected_fields"}) != excluded(b, {"path", "expected_fields"}):
                raise ValueError("Artifact guard changed")
            mutable = {"manifest.sha256", "completion_audit.path"}
            if excluded(a["expected_fields"], mutable) != excluded(b["expected_fields"], mutable):
                raise ValueError("Scientific artifact predicate changed")
    if any(p.exists() for p in (native, protocol, state, data / "APPROVAL.json", data / "ROOT_ADMISSION.json")):
        raise ValueError("Preparation must not create runtime outputs or authorization")
    forecast_old = read(prior["forecast"]["path"])
    forecast = {k: deepcopy(forecast_old[k]) for k in (
        "pilot_payload_authority", "pilot_runtime_memory_authority", "historical_source_seconds_per_cell",
        "historical_native_cell_wall_seconds_approx", "historical_max_process_tree_rss_bytes",
        "historical_max_process_tree_uss_bytes", "new_source_seconds", "serial_wall_hours_source_length_scaled",
        "new_payload_max_observed_cell_scaled_bytes", "new_payload_max_observed_cell_scaled_gib", "payload_scope",
        "source_timeout_seconds", "supervisor_timeout_seconds", "stall_seconds", "heartbeat_stale_seconds",
        "stop_grace_seconds", "no_timeout_extensions")}
    forecast.update(status="HISTORICAL_SINGLE_CELL_ARITHMETIC_FORECAST_NOT_NEW_PERFORMANCE",
                    prior_forecast=prior["forecast"], concurrency_maximum=1,
                    logical_cpu_affinity=[12,13,14,15], physical_core_isolation=False, CM5_result=False,
                    memory_scope="Historical one-stack peak only; add supervisor, Python/observers and unrelated host overhead.",
                    throughput_scope="77–83s historical44.695s cells; source-scaled19.399–20.910h forecast. Actual serial host conditions and per-cell overhead may differ; no new timing measured.",
                    no_other_neural_sessions_during_queue=True)
    fb = write(output / "FORECAST.json", forecast)
    checks = dict(exact_new_jobs=892, exact_conditional_credits=68, accepted_credits=0,
                  exact_old_job_ids_and_order=True, scientific_job_fields_unchanged_except_output_and_role=True,
                  exact_pcm_profile_gallery_settings_frames=True, exact_executable_helper_argv_except_manifest_binding=True,
                  exact_protocol_limits_and_artifact_predicates=True, exact_campaign_storage_and_source_guards=True,
                  one_neural_worker_required=True, fresh_runtime_paths_absent=True, no_authorization_created=True,
                  unique_source_metadata_bindings_verified=len(core_sources))
    check_b = write(output / "DATA_READBACK_REVIEW_V1.json", dict(status="PASS_METADATA_ONLY", checks=checks,
                         queue=qb, manifests=manifests, matrix=matrix_b, original=prior_b, constraint=constraint_b,
                         no_models=True, no_hardware=True, no_fixtures_or_scientific_runs=True))
    result = dict(schema="s6d-native-serial892-preparation.v1", status="CONDITIONAL_SERIAL_DATA_PREPARED_NOT_ADMITTED",
                  source=bind(__file__), source_readme=bind(Path(__file__).with_name("README_S6D_NATIVE_SERIAL892_PREPARE_V1.md")),
                  prior_preparation=prior_b, source_concurrency_constraint=constraint_b, matrix=matrix_b,
                  manifests=manifests, queue=qb, approval_proposal=ab, root_admission_proposal=rb, forecast=fb,
                  readback_review=check_b, runner=prior["runner"], wrapper=prior["wrapper"], evidence=prior["evidence"],
                  original_native176_queue=prior["original_native176_queue"], conditional_credits=68, accepted_credits=0,
                  new_jobs=892, worker_count=1, group="serial892", state_dir=str(state),
                  approval_path=str(data / "APPROVAL.json"), admission_path=str(data / "ROOT_ADMISSION.json"),
                  prerequisites=prerequisites, no_launches=True, no_models=True, no_hardware=True,
                  no_audio_or_active_results_opened=True, no_production_authorization_created=True,
                  source_protocol_unchanged=True, created_utc=datetime.now(timezone.utc).isoformat())
    result_b = write(output / "PREPARATION_RESULT.json", result)
    print(json.dumps(dict(status=result["status"], result=result_b, queue=qb, readback=check_b, jobs=892, workers=1)))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.output, args.payload)
