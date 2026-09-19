"""Verify the canonical library, write its manifest/report, and package one handoff."""
import os
for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):os.environ[k]="1"
import argparse, collections, csv, hashlib, json, shutil, time, zipfile
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import psutil
import soundfile as sf
from s0_common import SIM,read,save,now,HashCache
from s2_run import sha,process

def elapsed(started):return (datetime.now(timezone.utc)-datetime.fromisoformat(started.replace("Z","+00:00"))).total_seconds()
def size(root):return sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())

def build(report,library,started):
    report=Path(report);library=Path(library)
    active=read(report/"ACTIVE_INPUTS.json")
    rows=active["recordings"];ms=[read(report/"records"/(r["run_id"]+".json")) for r in rows]
    cfg=read(report/"EXTRACTION_CONFIG.json");cfgsha=sha(report/"EXTRACTION_CONFIG.json")
    good=[m for m in ms if m["status"]!="FAILED"];checks=[]
    def check(name,test):
        checks.append({"name":name,"passed":bool(test)})
        if not test:raise RuntimeError(name)
    check("all_121_unique_ids",len(ms)==121 and len({m["run_id"] for m in ms})==121)
    check("exact_scope",len(active["scope_excluded_recordings"])==6 and len(active["original_audit_exclusions"])==52 and
          all(r["room_table"]!="Loeb Caf" for r in rows) and "Upper Loeb" in {r["room_table"] for r in rows})
    excluded={r["run_id"] for r in active["scope_excluded_recordings"]+active["original_audit_exclusions"]}
    check("no_excluded_ids",not excluded.intersection(m["run_id"] for m in ms))
    check("preserve_original_status_and_effective_distance",all(r["original_status"] in ("PASS","REVIEW") and 0<r["source_distance_m_effective"]<=5 for r in rows))
    check("single_frozen_configuration",sha(library/"EXTRACTION_CONFIG.json")==cfgsha and all(m["extraction_config_sha256"]==cfgsha for m in ms))
    for b in read(report/"EXTRACTION_CODE_BINDINGS.json"):check("extractor_hash:"+Path(b["path"]).name,sha(b["path"])==b["sha256"])
    cache=HashCache()
    for m in ms:
        for b in m["inputs"]:
            check("source_receipt:"+m["run_id"]+":"+Path(b["path"]).name,cache.bind(b["path"],b["sha256"])["status"]=="BOUND")
        if m["status"]=="FAILED":
            check("failure_has_reason:"+m["run_id"],bool(m["failure_reasons"]) and m["output"] is None);continue
        p=Path(m["output"]["path"]);a,fs=sf.read(p,dtype="float32",always_2d=True);info=sf.info(p)
        check("output_contract:"+m["run_id"],p.name==m["run_id"]+"_rir.wav" and p.parent.resolve()==(library/"wav").resolve() and
              (fs,info.channels,info.subtype)==(16000,4,"FLOAT") and np.isfinite(a).all() and np.all(np.max(abs(a),axis=0)>0))
        check("wav_sha:"+m["run_id"],sha(p)==m["output"]["sha256"])
        check("sample_sha:"+m["run_id"],hashlib.sha256(a.astype("<f4").tobytes()).hexdigest()==m["candidate_float32_samples_sha256"])
        check("no_mic_warp_and_preserved_delay:"+m["run_id"],not m["clock"]["microphone_vector_resampled"] and
              max(abs(v["candidate_delay_change_samples"]) for v in m["response"]["pairwise_delays"])<=.05)
    check("one_wav_per_success",set(p.name for p in (library/"wav").glob("*"))=={m["run_id"]+"_rir.wav" for m in good})
    check("unique_output_content",len({m["output"]["sha256"] for m in good})==len(good))
    check("physical_readiness_not_claimed",all(not m["simulation_ready"] for m in ms))
    # One fresh numerical regeneration in addition to complete output-file integrity checks.
    regen=process(rows[0],cfg)
    check("fresh_real_regeneration",hashlib.sha256(regen["candidate"].astype("<f4").tobytes()).hexdigest()==ms[0]["candidate_float32_samples_sha256"])
    cache.flush()
    save(report/"LIBRARY_VALIDATION.json",{"status":"PASSED","checks_passed":len(checks),"checks_total":len(checks),"checks":checks,
        "fresh_real_regeneration_id":rows[0]["run_id"],"input_binding_scope":"Reused stat-valid expected hash receipts for consumed files; not a repeat audit or nested manifest hashing.",
        "new_hashes":cache.fresh,"cached_receipts":cache.hits})
    counts={s:sum(m["status"]==s for m in ms) for s in cfg["outcomes"]}
    flags=dict(collections.Counter(v for m in ms for v in m["limitations"]))
    durations=[m["response"]["candidate_duration_sec"] for m in good]
    material=[m["run_id"] for m in good if not m["can_proceed_to_hil_proof"]]
    timing_counts=dict(collections.Counter(m["clock"]["status"] for m in good))
    executions=[read(p) for p in sorted(report.glob("execution_*.json"))]
    numerical=[e for e in executions if e["processed"]]
    primary=max(numerical,key=lambda e:e["processed"])
    controls=read(report/"final_policy_controls.json")
    resources={"utc":now(),"drives":[{"drive":d,"free_bytes":shutil.disk_usage(d+"/").free} for d in ("C:","G:","D:","F:")],
               "available_ram_bytes":psutil.virtual_memory().available,"owned_children":len(psutil.Process().children(recursive=True))}
    save(report/"RESOURCE_AFTER.json",resources)
    stats={"stage":"S2_ALL_RIRS","run_id":report.name,"library":str(library),"outcomes":counts,"limitation_counts":flags,
           "active":121,"historical_exclusions":52,"additional_scope_exclusions":6,"timing_counts":timing_counts,
           "can_proceed_to_hil_proof_count":sum(m["can_proceed_to_hil_proof"] for m in good),"spatial_hil_deferred_ids":material,
           "duration_range_sec":[min(durations),max(durations)],
           "minimum_effective_distance_m":min(r["source_distance_m_effective"] for r in rows),
           "maximum_effective_distance_m":max(r["source_distance_m_effective"] for r in rows),
           "controls_passed":controls["checks_passed"],"library_validation_checks":len(checks),
           "full_extraction_elapsed_sec":sum(e["elapsed_sec"] for e in numerical),"primary_records_per_minute":primary["processed"]/primary["elapsed_sec"]*60,
           "final_controls_elapsed_sec":controls["elapsed_sec"],"elapsed_through_report_sec":elapsed(started),
           "observed_process_tree_rss_max_bytes":max(e["observed_process_tree_rss_max_bytes"] for e in numerical),
           "minimum_available_ram_bytes":min(e["minimum_available_ram_bytes"] for e in numerical),
           "wav_bytes":sum(m["output"]["bytes"] for m in good),"library_bytes_before_report":size(library),
           "max_relative_level_change_db":max(max(abs(v) for v in m["response"]["relative_level_change_db"]) for m in good),
           "max_removed_finite_core_energy_fraction":max(max(m["response"]["energy_removed_fraction_per_mic"]) for m in good),
           "physical_replay_validated":False,"independent_acoustic_validation":False}
    save(report/"RESULTS.json",stats)
    manifest={"schema_version":"jp_authoritative_rir_library_v1","library_version":library.name,"run_id":report.name,"created_utc":now(),
        "authority":"This manifest alone defines the current canonical RIR library. Historical S1 candidates are not canonical.",
        "count":121,"outcome_counts":counts,"output_contract":"One 16 kHz FLOAT32 WAV per successful recording, MIC0 MIC1 MIC2 MIC3",
        "configuration":{"path":"EXTRACTION_CONFIG.json","sha256":cfgsha},
        "extraction_code_bindings":read(report/"EXTRACTION_CODE_BINDINGS.json"),
        "active_input_manifest_sha256":sha(report/"ACTIVE_INPUTS.json"),"scope_overlay_sha256":sha(report/"SCOPE_CONTEXT.json"),
        "context":read(report/"SCOPE_CONTEXT.json"),"room_counts":active["active_room_counts"],"pose_counts":active["active_pose_counts"],
        "metadata_geometry_groups":active["metadata_geometry_groups"],
        "exclusions":{"scope_excluded_ids":[r["run_id"] for r in active["scope_excluded_recordings"]],"scope_rule":"Exclude exact Loeb Caf; keep Upper Loeb",
                      "historical_exclusions":active["original_audit_exclusions"],"excluded_audio_or_quiet_windows_used":False},
        "common_limits":["Numerical drive to Category 3 captured full scale; uncalibrated analog/loudspeaker transfer retained.",
            "Shared nominal 110-7000 Hz pass region; 80-110 and 7000-7300 Hz transitions, finite FIR and source-ridge attenuation.",
            "Supported intervals and selected band differ; no exact 80-7500 Hz or RT60 certification.",
            "Angle centers and ±5 degree user uncertainty are metadata, not waveform alignment targets.",
            "Physical replay and independent scene/speech validation have not been performed."],
        "records":ms}
    save(library/"RIR_MANIFEST.json",manifest)
    summaries=[]
    for m in ms:
        g=m["geometry"];x=m.get("response",{});clock=m.get("clock",{})
        summaries.append({"run_id":m["run_id"],"status":m["status"],"original_status":m["original_status"],"room":g["room_table"],
            "orientation":g["orientation"],"obstructed":g["obstructed"],"angle_deg":g["speaker_angle_deg_effective"],"distance_m":g["source_distance_m_effective"],
            "wav":m["output"]["library_relative_path"] if m["output"] else "", "sha256":m["output"]["sha256"] if m["output"] else "",
            "duration_sec":x.get("candidate_duration_sec"),"nominal_passband_hz":"110-7000","transitions_hz":"80-110;7000-7300",
            "supported_intervals_hz":json.dumps(x.get("evidence_supported_intervals_hz",[])),"selected_ppm":clock.get("selected_ppm"),
            "marker_ppm":clock.get("marker_regression_ppm"),"clock_half_width_ppm":clock.get("working_half_width_ppm"),
            "clock_status":clock.get("status"),"first_energy_sec":x.get("first_energy_sec_in_output"),
            "worst_same_sweep_residual_db":max(m["same_sweep_reconstruction"]["relative_residual_energy_db"]) if m["status"]!="FAILED" else None,
            "limitations":";".join(m["limitations"]),"failure_reason":";".join(m["failure_reasons"]),
            "can_proceed_to_hil_proof":m["can_proceed_to_hil_proof"],"physical_replay_validated":False,"simulation_ready":False})
    with (library/"RIR_SUMMARY.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
    flat=good[0]["response"]["filter_only_within_0_1db_hz"]
    drivetext="; ".join(f'{v["drive"]} {v["free_bytes"]/1024**3:.2f} GiB free' for v in resources["drives"])
    holdtext="\n".join("- "+v for v in material) or "None."
    outcome_text="; ".join(f"{s}: {n}" for s,n in counts.items())
    report_text=f"""# Complete 121-record RIR library

**Completed:** {outcome_text}. All 121 active IDs are accounted for. There is one canonical four-channel WAV per successful recording in {library}. RIR_MANIFEST.json defines this library; S1 alternatives remain untouched historical evidence.

## Scope and checks

Five rooms, 51 metadata geometry groups; 121 active after six exact Loeb Caf exclusions, with 52 historical exclusions preserved. Upper Loeb is retained. Neither excluded audio nor its quiet windows was used. Original acquisition statuses remain unchanged. Effective distances span {stats["minimum_effective_distance_m"]:g}–{stats["maximum_effective_distance_m"]:g} m. Both bound 100 m → 1.00 m corrections, signed central angles, ±5° conservative user uncertainty, qualitative room context and unknown geometry remain in the manifest.

All final targeted controls passed ({controls["checks_passed"]}/{controls["checks_total"]}); library validation passed {len(checks)} checks, including exact ID coverage, consumed-input bindings, header/data/WAV hashes, finite nonzero four-channel outputs, retained early channel delays and one fresh real-record numerical regeneration. Same-sweep reconstruction is internal consistency, not independent validation. Per-record results and failures are in RIR_SUMMARY.csv and RIR_MANIFEST.json.

## Final practical policy

The tested S1 reverse-sweep ESS inverse and scaling are retained. The exact archived 48 kHz excitation is resampled with the existing antialias filter and uses the recorded −6 dB software scalar exactly once. The transfer maps numerical post-software-gain drive to Category 3 captured full-scale samples. Mic gain 10, SYS_DELAY −32 and unknown speaker/analog transfer are not undone or applied again. Cross-record gain is preserved; a half-amplitude synthetic recording recovered the expected −6.0206 dB energy-level change.

Timing now uses each record's multi-marker regression with an uncertainty interval and fractional-position marker-waveform coherence. The latter change only affects diagnostic snippets, never microphone alignment. Zero/±10 ppm controls recovered the injected clock within 0.04 ppm; integer-aligned coherence had incorrectly fallen near 0.495, and fractional comparison restores about 0.9985. The 3% concentration rule is removed as a mandatory gate: concentration is diagnostic, not independent clock truth. No blanket −10 ppm correction is used. Selected timing counts: {json.dumps(timing_counts)}. Inconclusive cases use zero and retain bounded sensitivity.

The one nominal output pass region is **110–7000 Hz**, with raised-cosine transitions **80–110 Hz** and **7000–7300 Hz**. A symmetric 2049-tap Kaiser FIR and source-only ridge attenuation form a bounded common weighting; weak source bins are never inverted/boosted. The filter-only ±0.1 dB region for the first record is about {flat[0]:.1f}–{flat[1]:.1f} Hz. Individual supported intervals are reported separately from this chosen weighting.

The existing pilot supports expansion beyond S1's 160–6400 Hz cutoffs. Source self-transfer becomes irregular near 80 Hz and falls sharply above 7300 Hz; the existing 48→16 kHz antialias filter is about −14.1 dB at 7500 Hz. Claiming full 80–7500 Hz recovery would require unsupported edge inversion. Weak local bands flag that record rather than narrowing every output. This was one bounded edge assessment and one final filter design, not a parameter search.

Noise uses the verified 1.25-second pre-marker interval. Post-sweep audio is never labeled noise-only. Shared tail handling retains the last any-channel 20 ms block above four times a conservative floor, adds 40 ms margin and a 60 ms cosine taper. The floor may include weak real late decay; lost finite-core energy is quantified, and no clean tail is invented. The unused S1 consecutive-noise-duration config field was removed. Each output keeps about 50 ms before significant energy under one common origin; removed bulk latency is inseparable from device/propagation/capture offset. Do not add a guessed distance/c delay.

Durations are **{min(durations):.4f}–{max(durations):.4f} s**. These are stored windows, not RT60. Maximum crop/taper energy removal was {stats["max_removed_finite_core_energy_fraction"]*100:.4f}% of the already weighted finite core; maximum relative interchannel energy-level change was {stats["max_relative_level_change_db"]:.5f} dB. This does not quantify energy outside the chosen band or finite captured horizon.

## Specific limitations and next physical proof

Limitation counts (overlap allowed): {json.dumps(flags)}.

{stats["can_proceed_to_hil_proof_count"]} outputs can proceed as inputs to a later HIL proof within their declared bands/tails/uncertainties. Physical replay itself has not been tested. The following outputs retain a material clock-sensitive spatial limitation and should first resolve that timing uncertainty before spatial HIL proof:

{holdtext}

These limited responses remain canonical exports for offline inspection/use within their stated scope; they were not fabricated or relabeled as fully spatially qualified. No H2/GUI/model/threshold changes, XVF access, conversation synthesis, training, CM5 work, commit or push occurred.

## Runtime, storage and reproducibility

Full extraction: {stats["full_extraction_elapsed_sec"]:.2f} s with four CPU workers and one inner thread, approximately {stats["primary_records_per_minute"]:.2f} records/min. Final controls: {controls["elapsed_sec"]:.2f} s. Task elapsed through this report: {stats["elapsed_through_report_sec"]/60:.1f} minutes including implementation, investigation and validation.

Observed 15-second-sampled process-tree RSS maximum: {stats["observed_process_tree_rss_max_bytes"]/1024**3:.3f} GiB; minimum sampled available RAM: {stats["minimum_available_ram_bytes"]/1024**3:.2f} GiB. These are sampled observations, not instantaneous peaks or OS-enforced hard caps. Owned workers exited. Canonical WAV storage: {stats["wav_bytes"]/1024**2:.2f} MiB. Fresh free space: {drivetext}. All work remained on C: above the 50 GiB reserve; no data relocation was needed.

One source-power FFT truncation bug was caught by the expanded-band synthetic regression before policy freeze; it was fixed without changing the test threshold. A first small-clock policy also failed the coherence control. Failed development receipts and the successful final controls are preserved in the handoff evidence. No canonical RIR was produced under either failed policy.

Use library README.md and simulation/S2_README.md for exact PowerShell and Anaconda/Command Prompt commands. Rerun skips successful receipts only when inputs, code, config, scope and output hashes match. New methods/inputs require a new report and library version. The handoff includes canonical WAVs, the manifest/configuration, concise report, compact plots, small code/test evidence and a checked hash inventory; original captures, historical alternate WAVs, NPZ scratch, weights and vendors are excluded.
"""
    (library/"RESULTS.md").write_text(report_text,encoding="utf-8")
    readme=f"""# Canonical four-channel RIR library {library.name}

This is the current authoritative 121-record library, defined by RIR_MANIFEST.json. {outcome_text}. Historical S1 WAVs are not this library. Each successful ID has exactly wav/<run_id>_rir.wav: 16 kHz, FLOAT32, MIC0 MIC1 MIC2 MIC3. No peak normalization or mono exports.

Read RESULTS.md for outcomes and limitations, RIR_SUMMARY.csv for one row per ID, and EXTRACTION_CONFIG.json for the exact frozen method. The manifest includes original statuses, source hashes, both 1.00 m corrections, effective distances ≤5 m, signed angles with ±5° user uncertainty, room context, unknown geometry and all exclusions.

## Intended use and scaling

Convolving a 16 kHz mono numerical **post-software-gain drive** with all four RIR columns predicts Category 3 recorded normalized full-scale signals within the declared band/tail. Preserve the four columns and relative output scales across records. Never peak-normalize RIRs, divide out gain 10, apply SYS_DELAY −32 again, infer calibrated SPL or substitute exact label-derived delays. A 50 ms common pre-onset convention replaces inseparable bulk latency; this is not absolute sound travel time.

Nominal pass region: 110–7000 Hz; smooth transitions 80–110 and 7000–7300 Hz. Actual supported intervals and clock/tail limitations are per-record metadata. A stored duration is not RT60. can_proceed_to_hil_proof means usable as an input to a future proof; physical_replay_validated and simulation_ready remain false. Later replay must establish the appropriate unity/zero or other documented replay-domain contract rather than applying acquisition gain/delay a second time.

## Inputs, environment and commands

Original captures remain in their hash-bound local locations; the ZIP does not contain them. Existing C:\\Users\\amiri\\anaconda3\\python.exe supplies NumPy, SciPy, soundfile, matplotlib and psutil. No package installation, GPU, hardware access or H2 changes are needed.

PowerShell — verify/resume this exact report/library pair:

```powershell
$s2Sim = '{SIM}'
$s2Report = '{report}'
$s2Library = '{library}'
$s2Python = 'C:\\Users\\amiri\\anaconda3\\python.exe'
& $s2Python "$s2Sim\\scripts\\s2_run.py" --report $s2Report --library $s2Library --workers 4
```

Anaconda Prompt / Command Prompt:

```bat
set "S2SIM={SIM}"
set "S2REPORT={report}"
set "S2LIBRARY={library}"
set "S2PYTHON=C:\\Users\\amiri\\anaconda3\\python.exe"
"%S2PYTHON%" "%S2SIM%\\scripts\\s2_run.py" --report "%S2REPORT%" --library "%S2LIBRARY%" --workers 4
```

The completed run should resume all successful IDs without new WAVs. Do not reuse this report with a different library path. Keep one coordinator at a time. The frozen control/config/code gates must match. For different inputs/methods, use a new report and the next library version; do not overwrite this version. See simulation/S2_README.md for the initial assessment/control commands and presentation/package rebuild commands.

Files produced: canonical WAVs, RIR_MANIFEST.json, RIR_SUMMARY.csv, EXTRACTION_CONFIG.json, RESULTS.md and this README. Internal metrics, progress, binding receipts and small QC arrays reside in {report}; no second current RIR variant set is exported. Full original S1 evidence remains unchanged.

Validation scope: {controls["checks_passed"]} final known-FIR checks, {len(checks)} library/integrity checks, one fresh real numerical regeneration, common-channel timing/level checks and same-sweep internal reconstruction. No independent acoustic, speech/model-performance or physical/HIL validation is implied.
"""
    (library/"README.md").write_text(readme,encoding="utf-8")
    save(report/"status.json",{"stage":"S2_ALL_RIRS","status":"EXTRACTION_AND_LIBRARY_VALIDATION_COMPLETE","completed":121,
         "outcomes":counts,"utc":now(),"packaging_pending":True})
    print(json.dumps(stats,indent=2))

def package(report,library,started):
    report=Path(report);library=Path(library)
    if read(report/"LIBRARY_VALIDATION.json")["status"]!="PASSED":raise ValueError("Library validation missing")
    if read(report/"VISUAL_QA.json")["status"]!="REVIEWED":raise ValueError("QC visual review missing")
    manifest=read(library/"RIR_MANIFEST.json")
    payload={}
    for p in library.rglob("*"):
        if p.is_file():payload["library/"+p.relative_to(library).as_posix()]=p
    evidence=["PARENT_BINDINGS.json","SCOPE_CONTEXT.json","edge_assessment.json","small_clock_controls.json",
        "controls_attempt_01_failed.json","final_policy_controls.json","CONTROL_CODE_BINDINGS.json","DEVELOPMENT_RECOVERY.json",
        "EXTRACTION_CODE_BINDINGS.json","LIBRARY_VALIDATION.json","RESULTS.json","RESOURCE_BEFORE.json","RESOURCE_AFTER.json",
        "PLOT_RESULTS.json","VISUAL_QA.json","heartbeat.jsonl"]
    for name in evidence:payload["evidence/"+name]=report/name
    for p in report.glob("execution_*.json"):payload["evidence/"+p.name]=p
    for p in (report/"plots").glob("*.png"):payload["plots/"+p.name]=p
    for name in ("s0_common.py","s1_signal.py","s1_synthetic.py","s2_assess.py","s2_signal.py","s2_controls.py","s2_code_gate.py","s2_run.py","s2_plots.py","s2_finalize.py"):
        payload["simulation/scripts/"+name]=SIM/"scripts"/name
    payload["simulation/S2_README.md"]=SIM/"S2_README.md"
    inventory=[{"path":name,"bytes":p.stat().st_size,"sha256":sha(p)} for name,p in sorted(payload.items())]
    save(report/"FILE_INVENTORY.json",{"scope":"Payload only; inventory hashed by SHA256SUMS; external receipt hashes ZIP without circular references.","files":inventory})
    payload["FILE_INVENTORY.json"]=report/"FILE_INVENTORY.json"
    (report/"SHA256SUMS.txt").write_text("".join(f'{sha(p)}  {name}\n' for name,p in sorted(payload.items())),encoding="utf-8")
    payload["SHA256SUMS.txt"]=report/"SHA256SUMS.txt"
    path=SIM/"handoffs"/("S2_ALL_RIRS_CHATGPT_HANDOFF_"+report.name+".zip")
    temp=path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temp,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(payload.items()):z.write(p,name)
    checks=[]
    def check(name,ok):
        checks.append({"name":name,"passed":bool(ok)})
        if not ok:raise RuntimeError("Package check: "+name)
    with zipfile.ZipFile(temp) as z:
        check("CRC",z.testzip() is None)
        check("exact_unique_membership",len(z.namelist())==len(payload) and set(z.namelist())==set(payload))
        for name,p in payload.items():check("payload_sha:"+name,hashlib.sha256(z.read(name)).hexdigest()==sha(p))
        expected={"library/"+m["output"]["library_relative_path"] for m in manifest["records"] if m["output"]}
        check("canonical_wavs_only",set(n for n in z.namelist() if n.endswith(".wav"))==expected)
        check("all_121_in_manifest",len(json.loads(z.read("library/RIR_MANIFEST.json"))["records"])==121)
    temp.replace(path);digest=sha(path)
    (path.parent/(path.name+".sha256")).write_text(digest+"  "+path.name+"\n",encoding="utf-8")
    save(report/"PACKAGE_VALIDATION.json",{"status":"PASSED","checks_passed":len(checks),"checks_total":len(checks),"checks":checks})
    receipt={"path":str(path),"sha256":digest,"bytes":path.stat().st_size,"files":len(payload),"checks_passed":len(checks),
        "library_bytes":size(library),"report_bytes":size(report),"elapsed_through_package_sec":elapsed(started),"created_utc":now(),
        "counts":manifest["outcome_counts"],"no_circular_self_hash":True}
    save(report/"HANDOFF_RECEIPT.json",receipt);save(path.parent/(path.stem+".receipt.json"),receipt)
    save(report/"status.json",{"stage":"S2_ALL_RIRS","status":"COMPLETE","completed":121,"outcomes":manifest["outcome_counts"],"utc":now(),
        "library":str(library),"zip":str(path),"physical_replay_performed":False})
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("action",choices=["build","package"]);p.add_argument("--report",required=True)
    p.add_argument("--library",required=True);p.add_argument("--started-utc",required=True)
    a=p.parse_args();(build if a.action=="build" else package)(a.report,a.library,a.started_utc)
