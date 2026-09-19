"""Bounded policy evidence for the full library; see ../S2_README.md."""
import os
for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):os.environ[k]="1"
import argparse, copy, hashlib, json, shutil, time
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal, fft
import psutil
from s0_common import SIM, read, save, now, HashCache, Progress
import s1_signal as s1
from s1_synthetic import fixture, recovery_checks

S1=SIM/"reports/S1/20260908T185148Z"
BANDS=[[80,100],[100,125],[125,160],[160,250],[250,500],[500,1000],[1000,2000],[2000,4000],[4000,6400],[6400,6800],[6800,7100],[7100,7300],[7300,7500]]

def assess(report):
    report=Path(report);report.mkdir(parents=True,exist_ok=True)
    if (report/"edge_assessment.json").exists():raise ValueError("Assessment already recorded; reuse it")
    cache=HashCache();cfg=read(S1/"extraction_config.json")
    selected=read(S1/"selected_pilot_manifest.json")["recordings"]
    active=read(S1/"active_campaign_manifest.json")
    if len(active["recordings"])!=121 or active["scope_excluded_count"]!=6 or active["original_audit_excluded_count"]!=52:
        raise ValueError("Scope reconciliation mismatch")
    receipts=[]
    for row in selected:
        for f in row["s1_file_bindings"]:
            receipts.append(cache.bind(f["path"],f["sha256"]))
    for m in read(S1/"rir_pilot_manifest.json")["recordings"]:
        for f in m["code_bindings"]:receipts.append(cache.bind(f["path"],f["sha256"]))
    if any(f["status"]!="BOUND" for f in receipts):raise ValueError("S1 binding mismatch")
    for name in ["active_campaign_manifest.json","selected_pilot_manifest.json","scope_and_room_context.v3.json","extraction_config.json","qc_policy.json","synthetic_results.json","unit_test_results.json"]:
        receipts.append(cache.bind(S1/name))
    cache.flush();save(report/"PARENT_BINDINGS.json",receipts)
    save(report/"ACTIVE_INPUTS.json",active)
    save(report/"SCOPE_CONTEXT.json",read(S1/"scope_and_room_context.v3.json"))
    save(report/"RESOURCE_BEFORE.json",{"utc":now(),"drives":[{"drive":d,"free_bytes":shutil.disk_usage(d+"/").free,"total_bytes":shutil.disk_usage(d+"/").total} for d in ("C:","G:","D:","F:")],
          "available_ram_bytes":psutil.virtual_memory().available,"environment":{"python":os.sys.version,"numpy":np.__version__,"soundfile":sf.__version__}})
    original=Path(selected[0]["absolute_run_path"])/"02_raw/pass_01_amplified/excitation_original.wav"
    src=s1.source_at_16k(original,cfg);raw,fs=sf.read(original,dtype="float64")
    ref=src[3*16000:13*16000];inv,cal=s1.ess_inverse(ref,cfg,1.)
    nf=fft.next_fast_len(len(ref)+len(inv)-1);f=fft.rfftfreq(nf,1/16000)
    transfer=fft.rfft(ref,nf)*fft.rfft(inv,nf)*np.exp(2j*np.pi*f*(len(inv)-1)/16000)
    taps=signal.firwin(385,7400,fs=48000,window=("kaiser",8.6))
    aa_f,aa_h=signal.freqz(taps,worN=131072,fs=48000)
    source_bands=[]
    for lo,hi in BANDS:
        ix=(f>=lo)&(f<hi)
        source_bands.append({"band_hz":[lo,hi],"self_transfer_db_p10_median_p90":np.percentile(s1.db20(transfer[ix]),[10,50,90]).tolist(),
           "source_48_to_16_filter_db_at_edges":np.interp([lo,hi],aa_f,s1.db20(aa_h)).tolist()})
    rows=[];start=time.monotonic()
    with Progress(report,"S2_bounded_pilot_edge_assessment",12) as progress:
        for row in selected:
            m=read(S1/"records"/row["run_id"]/"metrics.json")
            p=Path(row["absolute_run_path"])/"02_raw/pass_01_amplified"
            y,fs=sf.read(p/"microphones_4ch.wav",always_2d=True)
            a,b=m["noise"]["window_capture_samples"];noise=y[a:b]
            beta=m["full_response_origin"]["beta_landmark_sec"];ratio=1+m["timing"]["selected_ppm"]*1e-6
            sweep=y[round((beta+3*ratio)*fs):round((beta+13*ratio)*fs)]
            freq,pn=signal.welch(noise,fs=fs,nperseg=4096,noverlap=2048,axis=0,scaling="density")
            _,py=signal.welch(sweep,fs=fs,nperseg=4096,noverlap=2048,axis=0,scaling="density")
            metrics=[]
            for lo,hi in BANDS:
                ix=(freq>=lo)&(freq<hi)
                power_noise=np.trapz(pn[ix],freq[ix],axis=0)
                power_sweep=np.trapz(py[ix],freq[ix],axis=0)
                margin=s1.db10(power_sweep/(power_noise+1e-30))
                metrics.append({"band_hz":[lo,hi],"sweep_plus_noise_to_pre_noise_db":margin.tolist(),"supported_all_mics_10db":bool(min(margin)>=10)})
            rows.append({"run_id":row["run_id"],"pilot_order":row["pilot_order"],"bands":metrics})
            progress.done+=1
    save(report/"edge_assessment.json",{"scope":"One assessment of existing pilot/source; no output-filter parameter sweep or independent acoustic validation",
        "source_self_transfer_bands":source_bands,"records":rows,"elapsed_sec":time.monotonic()-start,
        "source_gain_convention":cfg["gain_convention"],"proposed_selection_not_frozen":True})
    results=[]
    with Progress(report,"S2_small_clock_controls",3) as progress:
        for ppm in [0,-10,10]:
            y,h,hints=fixture(raw,ppm,1e-8)
            timing=s1.marker_clock(y,src,hints,cfg)
            zero=s1.extract_variant(y,src,timing,0,cfg)
            marker=s1.extract_variant(y,src,timing,timing["marker_regression_ppm"],cfg)
            improvement=marker["concentration"]/zero["concentration"]-1
            reliable=timing["within_search_contract"] and abs(timing["marker_regression_ppm"])>timing["working_half_width_ppm"] and timing["median_wavelet_coherence"]>=.65
            chosen=marker if reliable else zero
            checks=recovery_checks(chosen["core"],h,cfg)
            results.append({"true_ppm":ppm,"marker_ppm":timing["marker_regression_ppm"],"working_half_width_ppm":timing["working_half_width_ppm"],
                "coherence":timing["median_wavelet_coherence"],"concentration_improvement_fraction":improvement,
                "old_gate_selected_ppm":marker["ppm"] if reliable and improvement>=.03 else 0,
                "marker_evidence_policy_selected_ppm":chosen["ppm"],"recovery":checks,
                "marker_error_below_1ppm":abs(timing["marker_regression_ppm"]-ppm)<1,
                "selected_error_below_1ppm":abs(chosen["ppm"]-ppm)<1})
            progress.done+=1
            print(json.dumps({k:v for k,v in results[-1].items() if k!="recovery"}),flush=True)
    save(report/"small_clock_controls.json",{"cases":results,"status":"PASSED" if all(r["selected_error_below_1ppm"] for r in results) else "FAILED",
        "policy_conclusion":"Concentration is a same-response shape diagnostic; reliable multi-marker evidence determines the one common clock. No population-wide ppm applied."})
    save(report/"ASSESSMENT_CONFIG.json",cfg)
    print(json.dumps({"source_edges":source_bands,"pilot_band_support_counts":[{"band":band,"supported":sum(r["bands"][i]["supported_all_mics_10db"] for r in rows),
        "worst_margin_db":min(min(r["bands"][i]["sweep_plus_noise_to_pre_noise_db"]) for r in rows)} for i,band in enumerate(BANDS)]},indent=2),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--report",required=True);assess(p.parse_args().report)
