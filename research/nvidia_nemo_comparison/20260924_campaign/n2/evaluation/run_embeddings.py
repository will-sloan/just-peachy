"""Extract matched E0/E1 saved windows and private runtime galleries; see README.md."""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import uuid

for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_variable] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import numpy as np
import psutil
import soundfile as sf

from prepare import HERE, bind, fingerprint, frozen_save, load, sha
from scoring import SCORING_VERSION, calibrate_c


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def model(args):
    sys.path.insert(0, str(Path(args.source) / "vendor"))
    if args.encoder == "E1":
        from edge_speech_pipeline.titanet_embedding import TitanetEmbedding
        instance = TitanetEmbedding(args.titanet_manifest, threads=1)
        native = instance.namespace
        namespace = {"model_sha256": native["backend_sha256"], "preprocessing": native["preprocessing_version"],
                     "dimension": 192, "normalization": "L2", "minimum_samples": 8000,
                     "onnx_sha256": native["onnx_sha256"], "frontend_sha256": native["frontend_sha256"]}
        source_files = [Path(args.source) / "vendor/edge_speech_pipeline/titanet_embedding.py"]
    else:
        from edge_speech_pipeline.models import SpeakerModels
        from edge_speech_pipeline.config import PipelineConfig, AssetSpec
        admission = load(args.baseline_admission)
        assets = tuple(AssetSpec(x["component_id"], Path(x["path"]), x["sha256"], "unused") for x in admission["contract"]["models"])
        config = replace(PipelineConfig(), assets=assets, speaker_threads=1)
        instance = SpeakerModels(config)
        namespace = {"model_sha256": config.asset("redimnet2_b2_fp32").sha256,
                     "preprocessing": "original_redimnet2_b2_fp32_graph_waveform_mono16k_gain1",
                     "dimension": 192, "normalization": "L2", "minimum_samples": 8000}
        source_files = [Path(args.source) / "vendor/edge_speech_pipeline/models.py", Path(args.source) / "vendor/edge_speech_pipeline/config.py"]
    return instance, namespace, [bind(p) for p in source_files]


def verification_curve(pairs):
    """Empirical pairwise EER descriptive only, no gate threshold returned."""
    positives = sum(bool(p[1]) for p in pairs)
    negatives = len(pairs)-positives
    if not positives or not negatives:
        return {"status":"UNAVAILABLE_SINGLE_CLASS", "positive_pairs":positives, "negative_pairs":negatives, "eer":None}
    ordered = sorted(pairs,key=lambda p:p[0],reverse=True)
    false_accepts, true_accepts = 0, 0
    previous = (0.0,1.0)
    eer = None
    i = 0
    while i < len(ordered):
        score = ordered[i][0]
        while i < len(ordered) and ordered[i][0] == score:
            true_accepts += bool(ordered[i][1])
            false_accepts += not bool(ordered[i][1])
            i += 1
        far, frr = false_accepts/negatives, 1-true_accepts/positives
        if far >= frr:
            old_far,old_frr = previous
            ratio = (old_frr-old_far) / ((far-old_far)-(frr-old_frr)) if (far-old_far)-(frr-old_frr) else 0
            eer = old_far + ratio*(far-old_far)
            break
        previous = (far,frr)
    return {"status":"EMPIRICAL_CORRELATED_PAIR_DIAGNOSTIC", "positive_pairs":positives, "negative_pairs":negatives,
            "eer":eer, "scope":"Every admitted window-vs-profile pair; reused same-source/identity pairs are correlated; no independent trial confidence or deployment threshold"}


def score_windows(query_windows, vectors, profiles):
    if not profiles:
        return [], [], len(query_windows)
    matrix = np.stack([np.asarray(p["vector"],np.float32) for p in profiles])
    rows, pairs = [], []
    for window in query_windows:
        if window["window_id"] not in vectors:
            continue
        values = matrix @ vectors[window["window_id"]]
        order = np.argsort(-values,kind="stable")
        top = profiles[int(order[0])]
        second = float(values[order[1]]) if len(order)>1 else -1.0
        known = any(p["identity"] == window["identity"] for p in profiles)
        row = {"role":window["role"], "source_id":window.get("source_id",window["window_id"]),
               "window_id":window["window_id"], "identity":window["identity"], "is_known":known,
               "winner_correct":top["identity"] == window["identity"], "winner_profile_id":top["profile_id"],
               "score":float(values[order[0]]), "margin":float(values[order[0]])-second}
        rows.append(row)
        pairs.extend((float(value),p["identity"] == window["identity"]) for value,p in zip(values,profiles))
    return rows,pairs,len(query_windows)-len(rows)


def build_galleries(out, manifest, rosters, vectors, namespace, manifest_hash):
    by_window = {w["window_id"]:w for w in manifest["windows"]}
    templates = {}
    for template in manifest["gallery_templates"]:
        if template["status"] != "AVAILABLE" or any(w not in vectors for w in template["window_ids"]):
            continue
        weights = np.asarray([by_window[w]["estimated_active_seconds"] for w in template["window_ids"]],np.float64)
        matrix = np.stack([vectors[w] for w in template["window_ids"]])
        v = np.average(matrix,axis=0,weights=weights).astype(np.float32)
        v /= np.linalg.norm(v)
        templates[(template["domain"],template["position"],template["stream"],template["requested_active_seconds"],template["identity"])] = (template,v)
    conditions = []
    for roster in rosters["primary"]:
        domain = roster["domain"]
        domains = sorted({(k[1],k[2]) for k in templates if k[0] == domain})
        for position,stream in domains:
            conditions.append((roster,15,position,stream,False))
    # Same eligible people at all three durations, additional diagnostic only.
    for roster in rosters["primary"]:
        if roster["domain"] == "clean_source" and roster["mode"] != "none":
            for tier in [5,15,30]:
                conditions.append((roster,tier,"original","mono16k",True))
    summaries = []
    for roster,tier,position,stream,matched in conditions:
        intended = roster["intended_identities"]
        selected = set(intended)
        if matched:
            selected &= set(rosters["matched_5_15_30_clean_identities"])
        profiles = []
        for identity in sorted(selected):
            item = templates.get((roster["domain"],position,stream,tier,identity))
            if item is None:
                continue
            template,vector = item
            profile_id = str(uuid.uuid5(uuid.NAMESPACE_URL,"just-peachy:N2:research:"+identity))
            profiles.append({"profile_id":profile_id,"name":"Research " + profile_id[:8],"identity":identity,
                             "vector":vector.tolist(),"unique_sec":template["unique_estimated_active_seconds"],
                             "provenance":{"template_id":template["template_id"],"window_ids":template["window_ids"],
                                           "source_ids":template["source_ids"],"window_manifest_sha256":manifest_hash,
                                           "aggregation":"estimated-active-duration weighted mean of unit clip embeddings then L2; no duplicated audio"}})
        condition_id = f"{roster['n2_condition_id']}_{tier}s_{position}_{stream}" + ("_matched" if matched else "")
        gid = "gallery_" + fingerprint(condition_id)[:20]
        profile_hash = fingerprint(profiles)
        provenance = {"encoder_sha256":namespace["model_sha256"],"preprocessing_sha256":fingerprint(namespace),
                      "window_manifest_sha256":manifest_hash,"gallery_sha256":profile_hash,"roster_sha256":fingerprint(roster),
                      "enrollment_domain":roster["domain"],"input_domain":"clean_source","reference_seconds":tier,"vector_dimension":192}
        cw = [w for w in manifest["windows"] if w["role"] == "C"]
        crows,cpairs,cmissing = score_windows(cw,vectors,profiles)
        gate = calibrate_c(crows,provenance)
        qrows,qpairs,qmissing = score_windows(manifest["diagnostic_Q_windows"],vectors,profiles)
        operational_gate = {"status":"UNCALIBRATED_REJECT_ALL","score_threshold":None,"margin_threshold":0.05,
                            "domain":"XVF_query","namespace_sha256":fingerprint(namespace),
                            "namespace":namespace,"gallery_profiles_sha256":profile_hash,"C_gate_sha256":gate["gate_sha256"],
                            "profile_ids":sorted(p["profile_id"] for p in profiles),
                            "reason":"Processed C source projection not admitted; clean C cannot certify processed-query false-known rate",
                            "calibration_rows_sha256":gate["C_rows_sha256"],"window_manifest_sha256":manifest_hash}
        operational_gate["gate_sha256"] = fingerprint(operational_gate)
        runtime_profiles = [{k:v for k,v in p.items() if k != "identity"} for p in profiles]
        gallery = {"schema":"just-peachy.n2.gallery.v1","namespace":namespace,"profiles":runtime_profiles,
                   "domain":roster["domain"],"duration_sec":tier,"roster_id":condition_id,"calibration":operational_gate,
                   "mode":roster["mode"],"position":position,"stream":stream,
                   "intended_size":len(selected),"original_roster_intended_size":len(intended),"available_size":len(profiles),
                   "unavailable_count":len(selected)-len(profiles),"matched_duration_diagnostic":matched}
        atomic(out / "galleries" / f"{gid}.json",gallery)
        atomic(out / "scores" / f"{gid}.json",{"C_rows":crows,"Q_rows_evaluator_only":qrows,"C_calibration":gate})
        supported_q = len(qrows)
        known_q = [r for r in qrows if r["is_known"]]
        stranger_q = [r for r in qrows if not r["is_known"]]
        summaries.append({"gallery_id":gid,"roster_id":condition_id,"mode":roster["mode"],"domain":roster["domain"],
                          "position":position,"stream":stream,"tier_seconds":tier,"matched_duration_diagnostic":matched,
                          "intended_size":len(selected),"original_roster_intended_size":len(intended),"available_size":len(profiles),"unavailable_count":len(selected)-len(profiles),
                          "matched_eligible_size":len(selected),"matched_eligible_unavailable_count":len(selected)-len(profiles),
                          "original_roster_excluded_by_matched_design":len(intended)-len(selected),
                          "gallery":bind(out / "galleries" / f"{gid}.json"),"scores":bind(out / "scores" / f"{gid}.json"),
                          "C_gate_status":gate["status"],"operational_Q_gate_status":"UNCALIBRATED_REJECT_ALL",
                          "C_false_known_count":gate["false_known_count"],"C_negative_sources":gate["negative_unique_sources"],
                          "C_positive_sources":gate["positive_unique_sources"],"C_missing_windows":cmissing,
                          "C_verification":verification_curve(cpairs),"Q_verification_evaluator_only":verification_curve(qpairs),
                          "Q_window_denominator":len(manifest["diagnostic_Q_windows"]),"Q_supported_windows":supported_q,
                          "Q_missing_or_no_gallery_windows":qmissing,"Q_known_reference_windows":len(known_q),
                          "Q_known_top1_correct_uncalibrated":sum(r["winner_correct"] for r in known_q),
                          "Q_known_reference_stranger_windows":len(stranger_q),"Q_accepted_names":0,
                          "all_Q_names_rejected_reason":"INPUT_DOMAIN_CALIBRATION_UNAVAILABLE"})
    atomic(out / "GALLERY_INDEX.json",{"schema":"n2-gallery-index-v1","namespace":namespace,"conditions":summaries})
    return summaries


def main(args):
    process = psutil.Process()
    if os.name == "nt":
        process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    else:
        process.nice(10)
    process.cpu_affinity([args.cpu])
    out = Path(args.out) / args.encoder
    out.mkdir(parents=True,exist_ok=True)
    lock = out / "RUNNING.json"
    with lock.open("x",encoding="utf-8") as handle:
        json.dump({"pid":os.getpid(),"process_create_time":process.create_time()},handle)
    started = time.monotonic()
    try:
        manifest = load(args.manifest)
        rosters = load(Path(args.manifest).with_name("ROSTERS.json"))
        instance,namespace,model_code = model(args)
        contract = {"encoder":args.encoder,"namespace":namespace,"manifest":bind(args.manifest),"rosters":bind(Path(args.manifest).with_name("ROSTERS.json")),
                    "model_code":model_code,"runner_sha256":sha(__file__),"scoring_sha256":sha(HERE / "scoring.py"),
                    "scoring_version":SCORING_VERSION,"threads":1,"cpu_affinity":[args.cpu],"priority":"below_normal",
                    "versions":{k:importlib.metadata.version(k) for k in ["numpy","soundfile","onnxruntime"]},
                    "delivery":"accelerated_file_component_not_streaming_latency","no_microphones":True}
        frozen_save(out / "ADMISSION.json",contract)
        contract_hash = fingerprint(contract)
        vectors,receipts = {},[]
        all_windows = manifest["windows"] + manifest["diagnostic_Q_windows"]
        audio_seen = {}
        for index,window in enumerate(all_windows):
            wid = window["window_id"]
            wp = out / "windows" / f"{wid}.json"
            key = fingerprint({"contract":contract_hash,"window":window})
            if wp.exists():
                receipt = load(wp)
                if receipt["cache_key"] != key:
                    raise ValueError("Window cache provenance mismatch")
            else:
                t0=time.perf_counter()
                receipt={"window_id":wid,"role":window["role"],"cache_key":key,"status":"UNAVAILABLE","reason":None}
                if window.get("status","AVAILABLE") != "AVAILABLE":
                    receipt["reason"]="MANIFEST_WINDOW_UNAVAILABLE"
                elif window["end_sample"]-window["start_sample"] < namespace["minimum_samples"]:
                    receipt["reason"]="BELOW_MODEL_MINIMUM_SPAN_NO_PADDING"
                else:
                    path=window["audio"]["path"]
                    if path not in audio_seen:
                        if sha(path) != window["audio"]["sha256"]:
                            raise ValueError("Changed waveform")
                        audio_seen[path]=window["audio"]["sha256"]
                    elif audio_seen[path] != window["audio"]["sha256"]:
                        raise ValueError("Conflicting waveform binding")
                    audio,rate=sf.read(path,start=window["start_sample"],stop=window["end_sample"],dtype="float32")
                    if rate != 16000 or audio.ndim != 1 or len(audio) != window["end_sample"]-window["start_sample"] or window["gain"] != 1:
                        raise ValueError("Waveform format/span/gain mismatch")
                    vector=np.asarray(instance.embed(audio),np.float32)
                    if vector.shape != (192,) or not np.isfinite(vector).all() or abs(float(np.linalg.norm(vector))-1)>1e-4:
                        raise ValueError("Invalid model vector")
                    receipt.update(status="COMPLETE",vector=vector.tolist(),elapsed_ms=(time.perf_counter()-t0)*1000,
                                   process_rss_bytes=process.memory_info().rss,source_frames=len(audio))
                atomic(wp,receipt)
            receipts.append({k:v for k,v in receipt.items() if k != "vector"})
            if receipt["status"] == "COMPLETE":
                admitted_vector=np.asarray(receipt["vector"],np.float32)
                if admitted_vector.shape != (192,) or not np.isfinite(admitted_vector).all() or abs(float(np.linalg.norm(admitted_vector))-1)>1e-4:
                    raise ValueError("Invalid cached model vector")
                vectors[wid]=admitted_vector
            if index % 25 == 0 or index+1 == len(all_windows):
                progress={"encoder":args.encoder,"completed_windows":index+1,"total_windows":len(all_windows),"elapsed_s":time.monotonic()-started,"rss_bytes":process.memory_info().rss,"pid":os.getpid()}
                atomic(out / "PROGRESS.json",progress)
                print(json.dumps(progress),flush=True)
        summaries=build_galleries(out,manifest,rosters,vectors,namespace,sha(args.manifest))
        final={"schema":"n2-component-embedding-result-v1","status":"COMPLETE","encoder":args.encoder,"namespace":namespace,
               "completed_utc":datetime.now(timezone.utc).isoformat(),"elapsed_seconds":time.monotonic()-started,
               "window_denominator":len(all_windows),"supported_windows":len(vectors),"unsupported_windows":len(all_windows)-len(vectors),
               "peak_observed_rss_bytes":max((r.get("process_rss_bytes",0) for r in receipts),default=0),
               "cpu_seconds":sum(process.cpu_times()[:2]),"resource_scope":"single one-thread encoder process; concurrent campaign work may exist; not isolated/CM5 benchmark",
               "component_only_not_integrated_streaming":True,"windows":receipts,"galleries":summaries,"contract_sha256":contract_hash}
        atomic(out / "RESULT.json",final)
        atomic(HERE / f"{args.encoder}_COMPONENT_RECEIPT.json",{k:v for k,v in final.items() if k not in {"windows","galleries"}} | {"private_result":bind(out / "RESULT.json"),"gallery_conditions":len(summaries)})
        print(json.dumps({"status":"COMPLETE","encoder":args.encoder,"supported_windows":len(vectors),"gallery_conditions":len(summaries)}),flush=True)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--encoder",choices=["E0","E1"],required=True)
    parser.add_argument("--source",default=str(HERE.parents[4] / "prototype"))
    parser.add_argument("--manifest",default="G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/WINDOW_MANIFEST.json")
    parser.add_argument("--out",default="G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/component")
    parser.add_argument("--baseline-admission",default="G:/Just_Peachy_N1/20260924_campaign/local/baseline_screen_v1/ADMISSION.json")
    parser.add_argument("--titanet-manifest",default="G:/Just_Peachy_N1/20260924_campaign/local/n2/titanet/export/titanet_manifest.json")
    parser.add_argument("--cpu",type=int,default=4)
    main(parser.parse_args())
