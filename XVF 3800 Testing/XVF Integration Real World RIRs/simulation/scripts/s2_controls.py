"""Targeted final-policy regressions, frozen before full extraction."""
import os
for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):os.environ[k]="1"
import argparse, copy, hashlib, time
from pathlib import Path
import numpy as np
from scipy import fft, signal
import soundfile as sf
from s0_common import SIM,read,save,now,Progress
import s1_signal as s1
import s2_signal as s2
from s1_synthetic import fixture,recovery_checks
from s2_assess import S1,BANDS

def configuration():
    cfg=read(S1/"extraction_config.json")
    for key in ("candidate_band_edges_hz","candidate_fir_taps","clock_sweep_min_concentration_improvement_fraction",
                "tail_required_below_noise_sec","crosscheck_pilot_orders","crosscheck_fd_regularization_relative","handoff_cap_mib"):
        cfg.pop(key,None)
    cfg.update(schema_version="jp_canonical_rir_v1",clock_min_coherence=.65,clock_max_reliable_half_width_ppm=25.,
        common_pre_arrival_margin_sec=.05,noise_bands_hz=BANDS,noise_welch_nperseg=4096,
        output_weighting={"nominal_passband_hz":[110,7000],"lower_transition_hz":[80,110],"upper_transition_hz":[7000,7300],
            "shape":"Raised cosine edges; symmetric 2049-tap Kaiser 8.6 FIR approximation; source ridge attenuation <=1",
            "fir_taps":2049,"source_power_ridge_relative":1e-6,"filter_group_delay_compensated_samples":1024,
            "no_inverse_stopband_or_per_mic_eq":True},
        clock_policy="Per-record marker estimate with fractionally aligned marker-coherence diagnostic; concentration diagnostic only; zero if interval contains zero or conservative fallback with bounded sensitivity.",
        tail_policy="Last ANY-channel 20ms block >4x conservative noise floor; 40ms margin plus 60ms common cosine taper; pre-margin50ms",
        outcomes=["EXTRACTED","EXTRACTED_WITH_LIMITATIONS","FAILED"],
        checks={"finite_nonzero_required":True,"residual_warning_db":-15,"residual_failure_db":0,
            "ringing_warning_db":-15,"removed_energy_warning_fraction":.01,"relative_level_warning_db":.1,
            "tail_noise_warning_db":6,"early_pair_preservation_tolerance_samples":.05,
            "fallback_material_pair_change_samples":1.0,"fallback_material_level_change_db":1.0,
            "peak_to_noise_failure_db":6,"candidate_peak_abs_failure":100.,
            "band_support_min_db":10,"input_peak_abs_limit":1.},
        source_preservation=True,canonical_wav_contract="one 16kHz FLOAT32 WAV with MIC0-MIC3 per successful recording")
    return cfg

def run(report):
    report=Path(report)
    if (report/"EXTRACTION_CONFIG.json").exists():raise ValueError("Final configuration already frozen")
    cfg=configuration();save(report/"DRAFT_CONFIG.json",cfg)
    row=read(S1/"selected_pilot_manifest.json")["recordings"][0]
    p=Path(row["absolute_run_path"])/"02_raw/pass_01_amplified/excitation_original.wav"
    raw,_=sf.read(p);source=s1.source_at_16k(p,cfg)
    fixtures=[("zero",0,1e-8,False,False),("minus10",-10,1e-8,False,False),("plus10",10,1e-8,False,False),
              ("noisy_plus200",200,5e-5,False,False),("minus200",-200,1e-8,False,False),
              ("late_reflection",0,1e-8,True,False),("marker_tail",0,1e-7,False,True)]
    results=[];start=time.monotonic()
    with Progress(report,"S2_targeted_final_policy_controls",len(fixtures)) as progress:
        for name,ppm,std,late,contaminated in fixtures:
            y,h,hints=fixture(raw,ppm,std,late,contaminated)
            r=s2.extract(y,source,hints,cfg);timing=r["timing"];rec=recovery_checks(r["core"],h,cfg)
            checks={"finite":bool(np.isfinite(r["candidate"]).all()),"four_nonzero_channels":bool(np.all(np.max(abs(r["candidate"]),axis=0)>0)),
                    "marker_ppm_error":abs(timing["marker_regression_ppm"]-ppm)<(8 if std>1e-7 else 1),
                    "common_timing_preserved":max(abs(a["candidate_delay_change_samples"]) for a in r["response_metrics"]["pairwise_delays"])<.05}
            if not contaminated:
                checks.update(selected_clock_error=abs(timing["selected_ppm"]-ppm)<8,
                    gain=rec["max_midband_gain_error_db"]<.4,relative_delay=rec["max_pairwise_delay_error_samples"]<.35)
                f=fft.rfftfreq(131072,1/16000);use=(f>=125)&(f<=6800)
                actual=abs(fft.rfft(r["core"],131072,axis=0));truth=abs(fft.rfft(h,131072,axis=0))
                expanded_error=s1.db20(actual[use]/(truth[use]+1e-30))
                checks["expanded_band_p95_gain_error"]=bool(np.percentile(abs(expanded_error),95)<.4)
            else:checks["marker_tail_flag"]=r["noise"]["marker_tail_or_nonstationarity_warning"]
            if late:
                peak=int(np.argmax(abs(r["core"][:4000,0])));ix=peak+11200
                checks["late_reflection_in_candidate"]=bool(ix<r["response_metrics"]["common_taper_start_sample_in_core"] and abs(np.argmax(abs(r["core"][ix-8:ix+9,0]))-8)<=1)
            if name=="zero":
                again=s2.extract(y,source,hints,cfg)
                checks["deterministic"]=np.array_equal(r["candidate"].astype("float32"),again["candidate"].astype("float32"))
                checks["reverse_channels_detected"]=recovery_checks(r["core"][:,::-1],h,cfg)["max_pairwise_delay_error_samples"]>.35
                checks["double_gain_detected"]=recovery_checks(r["core"]*10**(-6/20),h,cfg)["max_midband_gain_error_db"]>5
                aligned=np.column_stack([np.roll(r["core"][:,m],int(round(rec["peak_samples"][0]-rec["peak_samples"][m]))) for m in range(4)])
                checks["independent_alignment_detected"]=recovery_checks(aligned,h,cfg)["max_pairwise_delay_error_samples"]>.35
                # Across-record amplitude invariance: source drive scaling must not be normalized away.
                quieter=s2.extract(y*.5,source,hints,cfg)
                q=quieter["response_metrics"]["candidate_energy_per_mic"];base=r["response_metrics"]["candidate_energy_per_mic"]
                checks["across_record_gain_preserved"]=bool(max(abs(s1.db10(np.array(q)/base)+6.020599913))<.01)
                checks["reference_resampler_rejects_microphone_vector"]=False
                try:s1.sinc_sample(np.ones((10,4)),np.arange(5))
                except ValueError:checks["reference_resampler_rejects_microphone_vector"]=True
            results.append({"name":name,"true_ppm":ppm,"selected_ppm":timing["selected_ppm"],"estimated_ppm":timing["marker_regression_ppm"],
                "legacy_coherence":timing["legacy_integer_aligned_median_wavelet_coherence"],"fractional_coherence":timing["median_wavelet_coherence"],
                "recovery":rec,"checks":checks,"passed":all(checks.values())})
            progress.done+=1
            print(f'{name}: selected {timing["selected_ppm"]:.4f} ppm, coherence {timing["median_wavelet_coherence"]:.4f}, pass={all(checks.values())}, failed={[k for k,v in checks.items() if not v]}',flush=True)
            save(report/"final_policy_controls.json",{"status":"RUNNING","cases":results})
    final={"status":"PASSED" if all(r["passed"] for r in results) else "FAILED","cases":results,
        "checks_passed":sum(sum(bool(v) for v in r["checks"].values()) for r in results),
        "checks_total":sum(len(r["checks"]) for r in results),"elapsed_sec":time.monotonic()-start,
        "supersedes_failed_small_control_policy":True,"synthetic_not_acoustic_validation":True}
    save(report/"final_policy_controls.json",final)
    if final["status"]!="PASSED":return 2
    cfg["frozen_utc"]=now();cfg["final_policy_controls_sha256"]=hashlib.sha256((report/"final_policy_controls.json").read_bytes()).hexdigest()
    cfg["edge_assessment_sha256"]=hashlib.sha256((report/"edge_assessment.json").read_bytes()).hexdigest()
    save(report/"EXTRACTION_CONFIG.json",cfg)
    print("Final configuration frozen after targeted controls.",flush=True)
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--report",required=True);raise SystemExit(run(p.parse_args().report))
