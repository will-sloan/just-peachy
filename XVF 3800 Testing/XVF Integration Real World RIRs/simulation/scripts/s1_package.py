"""Build and validate the bounded S1 review handoff. See ../S1_README.md."""
import argparse
import collections
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import time
import zipfile
import psutil
from s0_common import SIM, ROOT, REPO, read, save, now, HashCache

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def git(args, cwd):
    p=subprocess.run(["git",*args],cwd=cwd,capture_output=True,text=True,encoding="utf-8")
    if p.returncode:raise RuntimeError(p.stderr)
    return p.stdout.strip().splitlines()

def total_bytes(root):
    return sum(p.stat().st_size for p in Path(root).rglob("*") if p.is_file())

def build(report, derived, started):
    report=Path(report).resolve();derived=Path(derived).resolve()
    if not report.is_relative_to(SIM/"reports/S1") or not derived.is_relative_to(SIM/"derivatives/S1"):
        raise ValueError("Only local S1 output roots are permitted")
    run_id=report.name
    if derived.name!=run_id:raise ValueError("Run directories must agree")
    selected=read(report/"selected_pilot_manifest.json")["recordings"]
    active=read(report/"active_campaign_manifest.json")
    ms=[read(report/"records"/r["run_id"]/"metrics.json") for r in selected]
    cfg=read(report/"extraction_config.json")
    policy=read(report/"qc_policy.json")
    synth=read(report/"synthetic_results.json")
    plots=read(report/"plot_results.json")
    tests=read(report/"unit_test_results.json")
    if synth["status"]!="PASSED" or tests["status"]!="PASSED":raise ValueError("Required verification failed")
    if read(report/"visual_qa.json")["status"]!="REVIEWED":raise ValueError("Plot visual review missing")
    if len(ms)!=12 or any(m.get("exception") for m in ms):raise ValueError("Incomplete pilot")
    # Selected input receipts, small immutable parents, extractor code and saved WAVs.
    cache=HashCache();receipts=[]
    for group in read(report/"input_bindings.json").values():
        if isinstance(group,list):
            for f in group:receipts.append(cache.bind(f["path"],f["sha256"]))
    for m in ms:
        for f in m["inputs"]+m["outputs"]+m["code_bindings"]:
            receipts.append(cache.bind(f["path"],f["sha256"]))
        for filename,field in [("extraction_config.json","extraction_config_sha256"),("qc_policy.json","qc_policy_sha256"),("scope_and_room_context.v3.json","scope_overlay_sha256")]:
            if sha(report/filename)!=m[field]:raise ValueError("Analysis configuration changed after processing")
    if any(r["status"]!="BOUND" for r in receipts):raise ValueError("Input, output or code binding changed")
    cache.flush()
    save(report/"final_binding_check.json",{"status":"PASSED","receipt_count":len(receipts),
         "fresh_hashes":cache.fresh,"cached_stat_validated_receipts":cache.hits,"bytes_newly_hashed":cache.bytes,
         "scope":"Selected inputs, bound immutable S0 parents and supplied S1 pack, extractor code, all generated WAVs; not a repeat acquisition audit",
         "receipts":receipts})
    counts=collections.Counter(m["status"] for m in ms)
    summary=[]
    for r,m in zip(selected,ms):
        x=m["response_metrics"];t=m["timing"]
        summary.append({"pilot_order":r["pilot_order"],"run_id":r["run_id"],"room":r["room_table"],
            "angle_deg":r["speaker_angle_deg_effective"],"distance_m":r["source_distance_m_effective"],
            "orientation":r["orientation"],"obstructed":r["obstructed"],"status":m["status"],
            "marker_ppm":t["marker_regression_ppm"],"working_half_width_ppm":t["working_half_width_ppm"],
            "selected_ppm":t["selected_ppm"],"concentration_improvement_pct":100*t["sweep_concentration_improvement_fraction"],
            "candidate_duration_sec":x["candidate_duration_sec"],"cutoff_low_hz":x["supported_candidate_band_hz"][0],
            "cutoff_high_hz":x["supported_candidate_band_hz"][1],
            "worst_residual_energy_db":max(m["reconstruction"]["relative_residual_energy_db"]),
            "max_relative_level_change_db":max(map(abs,x["relative_level_change_db"])),
            "max_removed_energy_fraction":max(x["energy_removed_fraction_per_mic"]),
            "max_early_pair_delay_change_samples":max(abs(p["candidate_delay_change_samples"]) for p in x["pairwise_delays"]),
            "regeneration_identical":m["regeneration"]["byte_identical"],"processing_sec":m["processing_sec"],
            "qualified_rir_available":False,"simulation_ready":False})
    with (report/"pilot_summary.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    manifest=[]
    for r,m in zip(selected,ms):
        candidate=next(o for o in m["outputs"] if o["role"]=="candidate_4ch")
        alt_ppm=0.0 if m["timing"]["selected_ppm"] else m["timing"]["marker_regression_ppm"]
        alt_variant=next(v for v in m["timing"]["clock_sensitivity"] if v["ppm"]==alt_ppm)
        alt_ratio=1+alt_ppm*1e-6
        alt_origin={"ppm":alt_ppm,"beta_landmark_sec":alt_variant["beta_landmark_sec"],
                    "time_zero_sample":math.ceil(160000*alt_ratio)-1,
                    "capture_crop_start_sample":round((alt_variant["beta_landmark_sec"]+3*alt_ratio-.1)*16000),
                    "capture_crop_stop_sample":round((alt_variant["beta_landmark_sec"]+16*alt_ratio-.08)*16000),
                    "time_axis_sec":"(sample_index - time_zero_sample)/16000",
                    "derived_from":"Saved clock sensitivity and unchanged extractor/config; no new signal processing"}
        alternate=next(o for o in m["outputs"] if o["role"]=="alternate_clock_full_diagnostic")
        if alternate["frames"]!=alt_origin["capture_crop_stop_sample"]-alt_origin["capture_crop_start_sample"]+alt_origin["time_zero_sample"]:
            raise ValueError("Alternate diagnostic origin/length inconsistency")
        manifest.append({**m,"metadata":{k:r[k] for k in ("room_table","orientation","obstructed","speaker_angle_deg_effective","source_distance_m_effective","angle_label_interval","unmeasured_geometry")},
             "alternate_clock_full_response_origin":alt_origin,
             "candidate_handoff_relative_path":"candidates/"+r["run_id"]+".wav",
             "candidate_local_path":candidate["path"],"candidate_sha256":candidate["sha256"],
             "metric_field_caveats":{
                 "worker_peak_rss_bytes":"Legacy field name: a single end-of-processing RSS observation, NOT the worker lifetime peak.",
                 "MARKER_SWEEP_CLOCK_DISAGREEMENT":"Marker correction did not meet the initial 3% concentration-improvement gate; this does not establish a contradictory marker measurement.",
                 "supported_candidate_band_hz":"Common FIR half-amplitude cutoffs, not a calibrated flat/useful acoustic band.",
                 "candidate_delay_change_samples":"Common early window is untouched by crop/taper; zero change is expected and does not independently validate TDOA."}})
    save(report/"rir_pilot_manifest.json",{"schema_version":"jp_s1_rir_pilot_v1","run_id":run_id,
        "count":12,"status_counts":dict(counts),"simulation_ready":False,"qualified_rir_available":False,
        "channel_order":["MIC0","MIC1","MIC2","MIC3"],"wave_format":"16 kHz four-channel WAV FLOAT32, no peak normalization",
        "extraction_config_sha256":sha(report/"extraction_config.json"),"qc_policy_sha256":sha(report/"qc_policy.json"),
        "scope_overlay_sha256":sha(report/"scope_and_room_context.v3.json"),"recordings":manifest})
    execut=[read(p) for p in sorted(report.glob("execution_*.json"))]
    measured=[e for e in execut if e["processed_this_invocation"]>0]
    batch=max(measured,key=lambda e:e["processed_this_invocation"])
    resources={"timestamp_utc":now(),"drives":[{"drive":d,"total_bytes":shutil.disk_usage(d+"/").total,
        "free_bytes":shutil.disk_usage(d+"/").free} for d in ["C:","D:","F:","G:"]],
        "available_ram_bytes":psutil.virtual_memory().available,
        "physical_drive_mapping_source":"resource_before.json WMI associations; no new device/hardware query",
        "owned_child_process_count":len(psutil.Process().children(recursive=True))}
    save(report/"resource_after.json",resources)
    stage_elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(started.replace("Z","+00:00"))).total_seconds()
    resource_report={"started_utc":started,"report_snapshot_utc":now(),"stage_elapsed_through_report_sec":stage_elapsed,
        "wall_clock_scope":"Includes implementation, investigation, plotting, review and report preparation; excludes time after this snapshot.",
        "synthetic_elapsed_sec":synth["elapsed_sec"],"real_extraction_invocations_elapsed_sec":sum(e["elapsed_sec"] for e in measured),
        "first_record_processing_sec":ms[0]["processing_sec"],"plot_elapsed_sec":plots["elapsed_sec"],
        "four_worker_batch_records":batch["processed_this_invocation"],"four_worker_batch_elapsed_sec":batch["elapsed_sec"],
        "four_worker_batch_records_per_minute":batch["processed_this_invocation"]/batch["elapsed_sec"]*60,
        "observed_process_tree_rss_max_bytes":max(e["peak_process_tree_rss_bytes"] for e in measured),
        "memory_measurement_limit":"15-second sampled process-tree RSS, not a true peak. Sub-15-second initial work may fall between samples; summed RSS can double-count shared pages.",
        "minimum_available_ram_bytes":min(e["minimum_available_ram_bytes"] for e in measured),
        "minimum_output_disk_free_bytes":min(e["minimum_free_disk_bytes"] for e in measured),
        "derived_bytes":total_bytes(derived),"report_bytes_before_final_packaging":total_bytes(report),
        "limits":{k:cfg[k] for k in ("workers_max","inner_threads","task_ram_cap_gib","min_available_ram_gib","scratch_cap_gib","free_disk_floor_gib","handoff_cap_mib")},
        "forecast_121_numerical_sec_from_batch":121*batch["elapsed_sec"]/batch["processed_this_invocation"],
        "forecast_121_numerical_sec_from_serial_first":121*ms[0]["processing_sec"],
        "forecast_121_plot_sec":121*plots["elapsed_sec"]/12,
        "forecast_121_derivative_bytes":121*total_bytes(derived)/12,
        "forecast_limit":"Simple measured pilot extrapolation, not S2 execution or guaranteed runtime; same workload, load, no new searches. Reporting, failures, revised policy and I/O can change costs.",
        "cleanup":"Worker pool exited; owned file handles closed. Full diagnostic evidence retained; no unrelated process/cache/data deletion."}
    save(report/"resource_report.json",resource_report)
    after={"main_commit":git(["rev-parse","HEAD"],REPO)[0],"main_branch":git(["branch","--show-current"],REPO)[0],
           "main_status":git(["status","--short","--untracked-files=normal"],REPO),
           "nested_branch":git(["branch","--show-current"],ROOT)[0],
           "nested_status":git(["status","--short","--untracked-files=normal"],ROOT)}
    save(report/"git_after.json",after)
    save(report/"execution_issues.json",{"unrecovered_failures":0,"issues":[
        {"event":"Existing H2 environment lacked plotting dependency","resolution":"Used existing Anaconda base scientific environment; no install or H2 modification."},
        {"event":"psutil 5.9 disk_usage raised SystemError on Python 3.12","resolution":"Switched free-space query to standard shutil.disk_usage before first real worker was submitted; no acoustic processing failure."}],
        "development_policy_adjustments":policy["policy_adjustments"],
        "unused_config_field":"tail_required_below_noise_sec=0.1 is not used by this implementation; actual tail policy is last ANY-channel block >4x floor plus 40ms and 60ms common taper. Freeze/remove unused field in reviewed S2 policy.",
        "non_extractor_changes_after_scoring":"Added plotting, targeted tests, reporting/packaging and README only; extractor code hashes checked unchanged."})
    save(report/"method_references.json",{"references":[{"title":"Farina, Simultaneous measurement of impulse response and distortion with a swept-sine technique, AES 108 (2000)",
        "url":"https://angelofarina.it/Public/Papers/134-AES00.PDF","use":"Conceptual ESS inverse reference; implementation and numerical tolerances verified with local known-FIR fixtures."}],
        "not_claimed":"Synchronized higher-order harmonic identification, loudspeaker equalization, independent acoustic calibration."})
    aggregate={"scope":{k:active[k] for k in ("original_audit_candidates","original_audit_excluded_count","active_count","scope_excluded_count","metadata_geometry_groups","active_room_counts","active_pose_counts")},
        "pilot_attempted":12,"results":dict(counts),"synthetic_checks_passed":int(synth["checks_passed"]),"synthetic_checks_total":synth["checks_total"],
        "unit_tests_passed":tests["tests_run"],"max_candidate_relative_level_change_db":max(r["max_relative_level_change_db"] for r in summary),
        "max_common_window_removed_energy_fraction":max(r["max_removed_energy_fraction"] for r in summary),
        "max_candidate_early_pair_delay_change_samples":max(r["max_early_pair_delay_change_samples"] for r in summary),
        "all_candidates_regenerate_exactly":all(r["regeneration_identical"] for r in summary),
        "max_active_distance_m":max(r["source_distance_m_effective"] for r in active["recordings"]),
        "min_active_distance_m":min(r["source_distance_m_effective"] for r in active["recordings"]),
        "simulation_ready":False,"S2_readiness":"REQUIRES_REVIEWED_FROZEN_POLICY_AND_SEPARATE_AUTHORIZATION"}
    save(report/"metrics.json",aggregate)
    table=["| # | Room | Angle / m | Clock ppm (marker ± working half-width → selected) | Duration s | Worst residual dB | Result |",
           "|---:|---|---|---|---:|---:|---|"]
    for r in summary:
        table.append(f'| {r["pilot_order"]} | {r["room"]} | {r["angle_deg"]:+g}° / {r["distance_m"]:g} | {r["marker_ppm"]:.2f} ± {r["working_half_width_ppm"]:.2f} → {r["selected_ppm"]:.2f} | {r["candidate_duration_sec"]:.3f} | {r["worst_residual_energy_db"]:.1f} | '+("Limited band/tail" if r["selected_ppm"] else "Timing review")+" |")
    flat=plots["filter_characterization"][0]["filter_only_flat_within_0_1_db_hz"]
    drive_text="; ".join(f'{d["drive"]} {d["free_bytes"]/1024**3:.2f} GiB free' for d in resources["drives"])
    text=f"""# S1 RIR pilot review handoff

Run {run_id}. S1 is complete with review required. Exactly 12 selected recordings produced provisional four-channel candidates: four PROVISIONAL_LIMITED_BAND_TAIL and eight PROVISIONAL_TIMING_REVIEW, with zero input/processing failures. All remain qualified_rir_available=false and simulation_ready=false. S2 has not started.

## Scope and inherited measurement evidence

Historical acquisition audit: 127 eligible and 52 excluded. Current scope removes only six exact Loeb Caf candidates, retaining Upper Loeb: **121 active**, five room labels, 51 metadata geometry groups; 51 flat clear, 50 upright clear, 20 flat obstructed. Excluded measurements are forbidden for noise/stress/training use as well. Original capture/audit status is preserved. Every active source was originally REVIEW; early PASS diagnostics do not enter the campaign.

Active effective distances range {aggregate["min_active_distance_m"]:g}–{aggregate["max_active_distance_m"]:g} m; none exceeds 5 m. Both exact 100 m → 1.00 m user corrections remain bound to original identity/timestamp/hash. Signed angle centers remain unchanged with ±5 degrees user-estimated half-width. This is neither a percentage nor independently calibrated position accuracy. S0's sign evidence is inherited, not re-estimated or used to fit the recovered response; linear front/rear ambiguity remains. Unknown XYZ, heights, yaw and the library alias remain unknown.

Pilot entries 1–10 retain S0 order; entries 11/12 are the supplied Upper Loeb +30°/0.90 m and −90°/1.37 m paths. Full exact IDs, timestamps and hashes are in selected_pilot_manifest.json; selection_delta.json records the two substitutions. Only these 12 underwent numerical extraction.

## Results

{chr(10).join(table)}

All candidates are 16 kHz FLOAT32 WAV, channel order MIC0, MIC1, MIC2, MIC3, without peak normalization. Candidate duration is the stored common window, including about 20 ms before significant energy; it is not RT60. The raw untrimmed ESS convolution and the alternate-clock full diagnostic remain local with hashes. First significant band-limited energy is reported separately from strongest early energy; neither proves a direct path.

Across all 48 channels, common cropping/tapering removed at most {aggregate["max_common_window_removed_energy_fraction"]*100:.4f}% of energy relative to the already band-limited 2.8-second core. This does **not** quantify energy outside the band or captured tail. Relative total-energy levels changed by at most {aggregate["max_candidate_relative_level_change_db"]:.6f} dB. All six early-window GCC delay changes were zero because the shared early window was left intact; this is a preservation check, not independent angle validation. Fresh same-input numerical regeneration yielded identical FLOAT32 samples for all 12. No unchanged-condition acoustic repeat exists.

The regularized frequency-domain cross-check on entries 1 and 12 agreed to less than 0.075 dB at the 90th percentile of absolute magnitude difference across 300–6000 Hz for each channel. Both methods use the same capture and source. Reconstructed-sweep residuals are descriptive, band-matched internal consistency; do not report WER, DER or independent speech quality from them.

## Timing interpretation and review

Three separately templated markers, three common frequency bands and four channels suggest approximately −8.1 to −11.0 ppm reference-clock mismatch. Start and end marker waveforms differ and were not assumed interchangeable. Working intervals are heuristic uncertainty ranges, not calibrated confidence intervals. The acoustic bulk intercept includes capture/playback offset, device delay, propagation and filter/group-delay effects that cannot be separately identified here.

The pre-scoring policy requires marker evidence excluding zero, coherence ≥0.65, bounded uncertainty and at least 3% improvement in an early-energy concentration diagnostic before applying drift. Four records meet it. Eight retain zero drift and their marker-clock alternatives because concentration gain is insufficient. The code flag MARKER_SWEEP_CLOCK_DISAGREEMENT means failure of this conservative conjunction; it does not prove inconsistent marker measurements. Entry 9 improves by 2.96%, just below the gate; no threshold was retuned to change its status. Sensitivity is sometimes nonmonotonic, so concentration is not an independent clock estimator or a global optimization objective.

No microphone was independently resampled, aligned, normalized or corrected to match angle/distance labels. One reference-clock mapping is used for all four capture channels. The common crop removes an inseparable bulk origin; never add a guessed distance/speed-of-sound delay to these candidates.

## Method, scaling, noise and supported response

See METHOD_AND_LIMITATIONS.md for exact equations, numerical choices, units and caveats, and extraction_config.json for the processed configuration. The archived 48 kHz PCM16 source with SHA-256 cba5b09d4d3963d508340711210804d2dd80cf62741a60a2544120e60acbf488 is resampled through a documented antialias filter and multiplied by the recorded −6 dB software scalar exactly once. The estimated response maps post-software-gain numerical drive to recorded Category 3 full-scale samples. Gain 10, SYS_DELAY −32 and unknown analog transfer remain included; the common landmark anchor absorbs bulk latency without selectively undoing the device delay. KRK, room, table, objects and microphones remain part of the transfer.

The reverse-sweep, amplitude-weighted ESS inverse uses linear convolution and a known-source transfer calibration. Conceptual reference: [Farina, AES 2000](https://angelofarina.it/Public/Papers/134-AES00.PDF). Numerical accuracy here is supported by six independent-resampler known-FIR fixtures, passing {synth["checks_total"]}/{synth["checks_total"]} checks, plus {tests["tests_run"]} targeted tests.

Noise comes from a verified 1.25-second interval before the first acoustic marker; post-sweep audio is never assumed noise-only. No record triggered the 6 dB pre-noise stationarity or pre-sweep gap-excess warning. The short interval cannot establish long-duration stationarity. No unrelated quiet waveform was subtracted.

All selected records support the common nominal FIR cutoffs 160–6400 Hz under the development per-band ≥10 dB sweep-plus-noise/pre-noise power rule. Cutoffs are half-amplitude (about −6 dB); this filter alone is within ±0.1 dB over approximately **{flat[0]:.1f}–{flat[1]:.1f} Hz**. Neither figure certifies the acoustic transfer as flat or every narrow frequency as reliable. The 513-tap centered filter is shared across channels. A conservative response-noise floor combines propagated pre-noise power with late-core empirical power, which may include real decay. The common last-significant-block rule adds 40 ms margin and a 60 ms cosine taper. Weak late reflections may be lost. Full untrimmed diagnostics remain available for review. No RT60 is certified and no clean tail is invented.

## Context for later simulation

- Arise Kitchen Main Table: breakfast countertop/high-seated dining position in a kitchen, one open end leading to a hallway.
- Arise 5th floor low table: round low-seating coffee spot/table, one open end leading to a hallway.
- Upper Loeb: slightly high four-person booth at the side of a large restaurant with very high ceilings; perpendicular to a wall, window on one side and open restaurant on the other.
- Arise Floor 2 Kitchen: rectangular dining table in a kitchen/enclosed room, one open wall and a perpendicular hallway/wall arrangement described as T-shaped.
- Library Conference Room: square table in an enclosed conference-room-like setting with concrete/glass on most surrounding surfaces.

These qualitative user descriptions are context, not room dimensions, measured seating/ceiling heights, RT60 or isolation. No room model was fitted from them. The V5 Word workbook remains the design guide with its S0 hash, unchanged. Earlier planning instructions in documents do not authorize later execution.

## Resources, actual elapsed time and forecast

Existing Anaconda base scientific packages were used without installation or H2 changes. First real case: {ms[0]["processing_sec"]:.2f} s numerical processing; all real extraction invocations: {resource_report["real_extraction_invocations_elapsed_sec"]:.2f} s wall time. The remaining {batch["processed_this_invocation"]} records ran with four workers in {batch["elapsed_sec"]:.2f} s ({resource_report["four_worker_batch_records_per_minute"]:.2f} records/min). Synthetic fixtures: {synth["elapsed_sec"]:.2f} s; 13 plots: {plots["elapsed_sec"]:.2f} s. End-to-report elapsed: {stage_elapsed/60:.1f} minutes, including implementation, analysis and review.

Maximum observed 15-second-sampled process-tree RSS was {resource_report["observed_process_tree_rss_max_bytes"]/1024**3:.3f} GiB; minimum sampled available RAM was {resource_report["minimum_available_ram_bytes"]/1024**3:.2f} GiB. These are sampled observations, not true instantaneous peaks. The legacy per-record worker_peak_rss_bytes field is a single end-of-processing observation and must not be interpreted as a peak. One inner numerical thread per worker; no GPU work.

Fresh free space: **{drive_text}**. C: is the WD_BLACK SN850X SSD; G: is the Kingston SNVS2000G SSD. G: now has substantially more free space than the S0 snapshot. D: is now mostly empty, but remains an HDD. No drive relocation was necessary. The exact byte snapshots and mapping evidence are in resource_before.json/resource_after.json.

Local full derivatives occupy {resource_report["derived_bytes"]/1024**2:.2f} MiB, within the 5 GiB cap; C: remains above the 50 GiB reserve. A simple 121-record extrapolation is {resource_report["forecast_121_numerical_sec_from_batch"]/60:.1f} minutes from measured batch throughput or {resource_report["forecast_121_numerical_sec_from_serial_first"]/60:.1f} minutes using serial first-case cost, plus about {resource_report["forecast_121_plot_sec"]/60:.1f} minutes of plotting. This is a forecast under similar load and unchanged method, not an executed S2 result. No multi-hour search was launched.

The worker pool closed cleanly. No unrelated process, cache or data was deleted. Two recoverable environment/API issues are documented in execution_issues.json; no real record failed. Main Git tracked state and H2 assets were not changed; no commit/push or nested repository repair occurred.

## Handoff and next gate

Report directory: {report}

Full local derivatives: {derived}

Handoff: {SIM/"handoffs"/("S1_CHATGPT_HANDOFF_"+run_id+".zip")}

The ZIP includes this report, detailed method, config/policy, active/selected manifests, per-record evidence, 13 plots, small code/test files and all 12 candidate WAVs. It excludes original captures, full diagnostic WAVs, NPZ intermediates, model weights, vendor bundles and enrollment data. Local full-output hashes remain in the manifest. FILE_INVENTORY.json lists payloads; SHA256SUMS.txt covers them and the inventory; an external receipt hashes the ZIP without a self-hash cycle.

S1 is ready for ChatGPT review. S2 requires a reviewed, frozen timing/band/tail policy, a decision about the eight timing-review cases and explicit separate authorization. No production simulation, physical replay, hardware control or full-121 expansion has been performed. See NEXT_PHASE_INPUTS.md for exact hashes and review questions.
"""
    (report/"S1_REPORT.md").write_text(text,encoding="utf-8")
    (report/"PHASE_SUMMARY.md").write_text(f"""# S1 phase summary

S1 {run_id}: COMPLETE, REVIEW_REQUIRED. 121 active; six exact Loeb Caf scope exclusions; original 52 audit exclusions preserved. Exactly 12 processed: four provisional limited-band/tail, eight provisional timing-review, zero failures. 26 synthetic checks and six targeted tests passed. All 12 candidates regenerate exactly; none is simulation-ready.

Read S1_REPORT.md, METHOD_AND_LIMITATIONS.md and NEXT_PHASE_INPUTS.md. All four microphone channels retain the measured scaling and relative timing. Full diagnostics remain local; all 12 small FLOAT32 candidates are in the handoff. SSD snapshot: {drive_text}.

STOP after review handback. No S2, hardware, H2/model changes or training was performed.
""",encoding="utf-8")
    next_files=["active_campaign_manifest.json","selected_pilot_manifest.json","scope_and_room_context.v3.json",
                "extraction_config.json","qc_policy.initial.json","qc_policy.json","rir_pilot_manifest.json",
                "synthetic_results.json","unit_test_results.json","metrics.json"]
    refs=[{"path":str(report/n),"sha256":sha(report/n)} for n in next_files]
    next_text=["# Inputs for review before S2","",
        "S1 is complete, but the development policy is NOT frozen or independently confirmed. No automatic S2.",
        "","## Exact artifacts",""]
    for f in refs:next_text += [f'- {f["path"]}',f'  SHA-256: {f["sha256"]}']
    next_text += ["","## Decisions required before a separately authorized expansion","",
        "1. Review the shared-clock acceptance rule against saved zero/marker/working-bound sensitivity. All marker estimates are near −10 ppm, but eight miss the 3% sweep concentration criterion. Preserve those classifications until a reviewed policy specifies their allowed use. Do not retune merely to turn this pilot green.",
        "2. Freeze the declared band, conservative noise-floor/tail policy and uncertainty treatment. The unused tail_required_below_noise_sec field must be removed or explicitly implemented in a new reviewed configuration; it did not govern S1.",
        "3. If any extractor behavior changes, assign a new configuration/code identity and revalidate synthetic recovery and affected pilot results before full expansion. This pilot is developmental, not a confirmatory holdout.",
        "4. Keep active eligibility exactly 121; preserve six Loeb Caf and 52 historical exclusions, both 1.00 m corrections and ±5 degree labels. Do not use nominal distances/angles to adjust channel delays.",
        "5. Continue marking physical replay, independent speech/scene validation, DoA/diarization performance and CM5 readiness as separate later gates. S0's H2 elapsed-time evidence issue and USB 16/16 status are deferred to their later authorized stages.",
        "","## Timing-review records",""]
    next_text += [f'- {m["pilot_order"]}: {m["run_id"]}' for m in ms if m["status"]=="PROVISIONAL_TIMING_REVIEW"]
    next_text += ["","Use S1_README.md for exact PowerShell/CMD commands. Resume verifies code/config/input/output hashes. It never expands the selected manifest beyond 12.",
        "The Word design guide remains C:\\Users\\amiri\\Downloads\\XVF_Measurement_V5.docx, SHA-256 c9a6badcd83065ae9f865de841c077f00668a480e1f0170c115c514e30a99db6.",
        "Full local WAVs and all provenance paths are in rir_pilot_manifest.json. Candidate files in the ZIP can be inspected without the original recordings; reproducible extraction requires the original bound local inputs.",""]
    (report/"NEXT_PHASE_INPUTS.md").write_text("\n".join(next_text),encoding="utf-8")
    commands=[f'"{SIM/"scripts"/n}" --report "{report}"'+(f' --derived "{derived}" --limit {limit} --workers {workers}' if n=="s1_run.py" else "")
        for n,limit,workers in [("s1_synthetic.py",0,0),("s1_run.py",1,1),("s1_run.py",12,4),("s1_plots.py",0,0)]]
    save(report/"run_manifest.json",{"stage_id":"S1","run_id":run_id,"status":"COMPLETE","readiness":"REVIEW_REQUIRED",
         "started_utc":started,"finished_report_utc":now(),"actual_numerical_commands":commands,
         "command_note":"Commands above were invoked with C:/Users/amiri/anaconda3/python.exe. Preparation pack, unit-test and packaging commands are documented in S1_README.md; initialization and resource/Git reads used PowerShell.",
         "code_commit":after["main_commit"],"inputs_for_next_review":refs,"counts":aggregate["scope"],
         "hardware_access_performed":False,"H2_modified":False,"S2_started":False})
    save(report/"status.json",{"stage":"S1","status":"COMPLETE","readiness":"REVIEW_REQUIRED","updated_utc":now(),"completed":12,"failed":0,"total":12,"simulation_ready":False})
    # Allowlisted payload roots. Inventory and sums intentionally do not hash themselves.
    payload={}
    excluded={"FILE_INVENTORY.json","SHA256SUMS.txt","handoff_receipt.json","package_validation.json"}
    for p in report.rglob("*"):
        if p.is_file() and p.suffix in (".json",".jsonl",".md",".csv",".png") and p.name not in excluded:
            payload["report/"+p.relative_to(report).as_posix()]=p
    for name in ["S1_README.md","CONTEXT.md","DECISIONS.md"]:
        payload["simulation/"+name]=SIM/name
    for name in ["s0_common.py","s1_prepare.py","s1_signal.py","s1_synthetic.py","s1_run.py","s1_plots.py","s1_package.py"]:
        payload["simulation/scripts/"+name]=SIM/"scripts"/name
    payload["simulation/tests/test_s1.py"]=SIM/"tests/test_s1.py"
    for m in manifest:payload[m["candidate_handoff_relative_path"]]=Path(m["candidate_local_path"])
    inventory=[{"path":name,"bytes":p.stat().st_size,"sha256":sha(p)} for name,p in sorted(payload.items())]
    save(report/"FILE_INVENTORY.json",{"hash_scope":"Payload files only; this inventory is hashed by SHA256SUMS.txt, which is covered by the external ZIP hash.","files":inventory})
    payload["FILE_INVENTORY.json"]=report/"FILE_INVENTORY.json"
    sums="".join(f'{sha(p)}  {name}\n' for name,p in sorted(payload.items()))
    (report/"SHA256SUMS.txt").write_text(sums,encoding="utf-8")
    payload["SHA256SUMS.txt"]=report/"SHA256SUMS.txt"
    folder=SIM/"handoffs";folder.mkdir(exist_ok=True)
    path=folder/("S1_CHATGPT_HANDOFF_"+run_id+".zip")
    temp=path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temp,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,p in sorted(payload.items()):z.write(p,name)
    if temp.stat().st_size>cfg["handoff_cap_mib"]*1024**2:raise RuntimeError("Handoff exceeds size cap")
    checks=[]
    def check(name,condition):
        checks.append({"name":name,"passed":bool(condition)})
        if not condition:raise RuntimeError("Package validation: "+name)
    with zipfile.ZipFile(temp) as z:
        check("CRC",z.testzip() is None)
        check("exact_unique_membership",len(z.namelist())==len(payload) and set(z.namelist())==set(payload))
        for name,p in payload.items():
            if name!="SHA256SUMS.txt":check("sha256:"+name,hashlib.sha256(z.read(name)).hexdigest()==sha(p))
        check("12_candidates",sum(n.startswith("candidates/") for n in z.namelist())==12)
        check("no_original_capture_wavs",all(n.startswith("candidates/") for n in z.namelist() if n.endswith(".wav")))
        check("all_candidate_identities_selected",all(n[11:-4] in {r["run_id"] for r in selected} for n in z.namelist() if n.startswith("candidates/")))
        check("no_excluded_input_selection",all(r["room_table"]!="Loeb Caf" and r["original_status"] in ("PASS","REVIEW") for r in selected))
        check("all_outputs_provisional",all(not m["simulation_ready"] and not m["qualified_rir_available"] for m in ms))
        check("scratch_and_free_space",resource_report["derived_bytes"]<5*1024**3 and shutil.disk_usage(str(SIM)).free>50*1024**3)
    temp.replace(path)
    digest=sha(path)
    (folder/(path.name+".sha256")).write_text(digest+"  "+path.name+"\n",encoding="utf-8")
    validation={"status":"PASSED","checks_passed":len(checks),"checks_total":len(checks),"checks":checks,
                "scope":"External validation receipt intentionally omitted from ZIP to avoid self-reference."}
    save(report/"package_validation.json",validation)
    receipt={"path":str(path),"sha256":digest,"bytes":path.stat().st_size,"files":len(payload),
        "size_cap_mib":cfg["handoff_cap_mib"],"created_utc":now(),"checks_passed":len(checks),
        "total_elapsed_through_package_sec":(datetime.now(timezone.utc)-datetime.fromisoformat(started.replace("Z","+00:00"))).total_seconds(),
        "external_only_no_circular_self_hash":True}
    save(report/"handoff_receipt.json",receipt)
    save(folder/(path.stem+".receipt.json"),receipt)
    print(json.dumps(receipt,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--report",required=True);p.add_argument("--derived",required=True);p.add_argument("--started-utc",required=True)
    a=p.parse_args();build(a.report,a.derived,a.started_utc)
