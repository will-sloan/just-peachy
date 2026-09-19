"""Execute the frozen full library with one canonical WAV per ID. See S2_README.md."""
import os
for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):os.environ[k]="1"
import argparse, concurrent.futures, hashlib, json, multiprocessing, shutil, threading, time, traceback
from pathlib import Path
import numpy as np
import psutil
import soundfile as sf
from scipy import fft
from s0_common import SIM,read,save,now,HashCache
import s1_signal as s1
import s2_signal as s2

CONSUMED={"request.json","microphones_4ch.wav","excitation_original.wav","signal_timing.json","playback.json",
          "capture_configuration.json","capture_gain_delay_lock.json","identity.json","quality.json"}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def tidy(x):
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {k:tidy(v) for k,v in x.items()}
    if isinstance(x,(tuple,list)):return [tidy(v) for v in x]
    return x

def key_hash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def process(row,cfg):
    start=time.monotonic();p=Path(row["absolute_run_path"])/"02_raw/pass_01_amplified"
    info=sf.info(p/"microphones_4ch.wav")
    if (info.samplerate,info.channels,info.frames,info.subtype)!=(16000,4,350647,"PCM_24"):raise ValueError("Canonical capture format mismatch")
    y,fs=sf.read(p/"microphones_4ch.wav",dtype="float64",always_2d=True)
    if not np.isfinite(y).all() or np.max(abs(y))>=1:raise ValueError("Nonfinite or full-scale-clipped capture")
    recorded=read(p/"capture_configuration.json");lock=read(p/"capture_gain_delay_lock.json");identity=read(p/"identity.json")
    if (recorded["category"],recorded["container_bits"],recorded["microphone_gain"],recorded["system_delay_samples"])!=(3,24,[10],[-32]):
        raise ValueError("Category/gain/delay contract mismatch")
    if lock["observed"]!={"AUDIO_MGR_MIC_GAIN":[10],"AUDIO_MGR_SYS_DELAY":[-32]}:raise ValueError("Saved gain/delay lock mismatch")
    if identity["AUDIO_MGR_MIC_GAIN"]!=[10] or identity["AUDIO_MGR_SYS_DELAY"]!=[-32] or identity["AEC_NUM_MICS"]!=[4]:
        raise ValueError("Saved device identity/capture contract mismatch")
    playback=read(p/"playback.json");request=read(Path(row["absolute_run_path"])/"request.json")
    timing=read(p/"signal_timing.json")["signals"][request["excitation_id"]]
    if playback["requested_gain_db"]!=-6 or playback["same_clock_as_capture"] is not False or timing["sweep_onset_sec"]!=3 or timing["sweep_end_sec"]!=13:
        raise ValueError("Saved excitation/playback contract mismatch")
    hints=[a["sample"]/fs for a in read(p/"quality.json")["acoustic_markers"]["markers"]]
    source=s1.source_at_16k(p/"excitation_original.wav",cfg)
    r=s2.extract(y,source,hints,cfg)
    c=r["candidate"];m=r["response_metrics"];t=r["timing"];n=r["noise"];checks=cfg["checks"]
    failures=[];limitations=[]
    if c.ndim!=2 or c.shape[1]!=4 or not np.isfinite(c).all():failures.append("NONFINITE_OR_INVALID_FOUR_CHANNEL_RESPONSE")
    if min(m["rms_per_mic"])<=1e-12:failures.append("ZERO_OR_VANISHING_RESPONSE_CHANNEL")
    if max(m["peak_abs_per_mic"])>checks["candidate_peak_abs_failure"]:failures.append("GROSS_RESPONSE_SCALING")
    if min(a["peak_to_model_noise_db"] for a in m["arrivals"])<checks["peak_to_noise_failure_db"]:failures.append("NO_DEFENSIBLE_EARLY_RESPONSE_ABOVE_NOISE")
    worst=max(r["residual"]["relative_residual_energy_db"])
    if worst>checks["residual_failure_db"]:failures.append("RECONSTRUCTION_ERROR_EXCEEDS_OBSERVED_ENERGY")
    elif worst>checks["residual_warning_db"]:limitations.append("ELEVATED_SAME_SWEEP_RESIDUAL")
    if max(abs(a["candidate_delay_change_samples"]) for a in m["pairwise_delays"])>checks["early_pair_preservation_tolerance_samples"]:
        failures.append("COMMON_WINDOW_CHANGED_RELATIVE_EARLY_TIMING")
    if max(abs(v) for v in m["relative_level_change_db"])>checks["relative_level_warning_db"]:limitations.append("WINDOW_CHANGES_RELATIVE_ENERGY_LEVELS")
    if max(m["energy_removed_fraction_per_mic"])>checks["removed_energy_warning_fraction"]:limitations.append("MORE_THAN_1_PERCENT_FINITE_CORE_ENERGY_REMOVED")
    if max(m["pre_arrival_energy_db_vs_early_window"])>checks["ringing_warning_db"]:limitations.append("ELEVATED_PRE_ONSET_ENERGY")
    if m["tail_cap_reached"]:limitations.append("TAIL_REACHES_FINITE_HORIZON")
    if n["marker_tail_or_nonstationarity_warning"]:limitations.append("PRE_SWEEP_GAP_EXCESS_OR_MARKER_TAIL")
    if max(n["stationarity_three_block_power_range_db"])>checks["tail_noise_warning_db"]:limitations.append("PRE_NOISE_NONSTATIONARITY")
    weak=[b["band_hz"] for b in n["bands"] if not b["supported_all_channels"] and b["band_hz"][0]<7300]
    if weak:limitations.append("LOCAL_FREQUENCY_INTERVALS_BELOW_SUPPORT_RULE")
    if t["status"]=="CONSERVATIVE_ZERO_FALLBACK":limitations.append("CLOCK_EVIDENCE_INCONCLUSIVE_ZERO_FALLBACK")
    material=any(v["max_early_pair_delay_change_samples"]>checks["fallback_material_pair_change_samples"] or
                 v["max_relative_level_change_db"]>checks["fallback_material_level_change_db"] for v in t["fallback_sensitivity"])
    if material:limitations.append("CLOCK_UNCERTAINTY_MATERIALLY_AFFECTS_SPATIAL_METRICS")
    status="FAILED" if failures else "EXTRACTED_WITH_LIMITATIONS" if limitations else "EXTRACTED"
    concise_noise={k:v for k,v in n.items() if not k.startswith("psd_")}
    residual={k:v for k,v in r["residual"].items() if k not in ("frequency_hz","observed_psd","residual_psd")}
    details={"run_id":row["run_id"],"status":status,"failure_reasons":failures,"limitations":limitations,
        "weak_frequency_intervals_hz":weak,"original_acquisition_status":row["original_status"],"capture_audit_pass":row["capture_audit_pass"],
        "clock":t,"noise":concise_noise,"response":m,"same_sweep_reconstruction":residual,"zero_drift_comparison":r["zero_comparison"],
        "gain_convention":cfg["gain_convention"],"capture_domain":cfg["capture_domain"],
        "inverse_calibration":r["selected"]["calibration"],
        "time_origin":{"analysis_anchor_sec":cfg["analysis_anchor_sec"],"common_bulk_landmark_intercept_sec":r["selected"]["beta_landmark_sec"],
            "capture_crop_start_sample":r["selected"]["capture_crop_start_sample"],"capture_crop_stop_sample":r["selected"]["capture_crop_stop_sample"],
            "full_convolution_time_zero_sample":len(r["selected"]["inverse"])-1,
            "export_start_relative_to_core_sec":m["common_crop_start_sample_in_core"]/fs,
            "onset_in_export_sec":m["first_energy_sec_in_output"],"absolute_distance_or_device_delay_separately_known":False,
            "convention":"Common crop retains about 50ms before significant energy. Removed bulk latency is inseparable; never add a guessed distance/c delay."},
        "offline_extraction_checks_pass":not failures,
        "can_proceed_to_hil_proof":not failures and not material,
        "hil_gate_note":"Ready as an input to later HIL proof within declared limits; replay domain/gain/delay and independent scenes still need validation" if not material else "Resolve clock-sensitive spatial metrics before spatial HIL proof; response remains usable for limited offline inspection.",
        "physical_replay_validated":False,"independent_acoustic_validation":False,"simulation_ready":False,
        "processing_sec":time.monotonic()-start,"worker_rss_at_end_bytes":psutil.Process().memory_info().rss,
        "candidate_float32_samples_sha256":hashlib.sha256(c.astype("<f4").tobytes()).hexdigest()}
    freq=fft.rfftfreq(65536,1/fs);H=fft.rfft(r["processed"],65536,axis=0)
    qc={"core_early":r["core"][:6400:2].astype("float32"),"core_stride":2,"block_power":r["block_power"].astype("float32"),
        "frequency_hz":freq[::16],"response_db":s1.db20(H[::16]).astype("float32")}
    return {"metrics":tidy(details),"candidate":c.astype("float32") if not failures else None,"qc":qc}

class Monitor:
    def __init__(self,report,cfg,total,resumed):
        self.report=report;self.cfg=cfg;self.total=total;self.done=resumed;self.resumed=resumed
        self.warnings=0;self.failed=0;self.started=time.monotonic();self.stop=threading.Event();self.error=None
        self.peak=0;self.min_avail=10**20;self.min_disk=10**20;self.current=""
    def sample(self):
        p=psutil.Process();rss=p.memory_info().rss
        for child in p.children(recursive=True):
            try:rss+=child.memory_info().rss
            except psutil.NoSuchProcess:pass
        avail=psutil.virtual_memory().available;disk=shutil.disk_usage(str(SIM)).free
        self.peak=max(self.peak,rss);self.min_avail=min(self.min_avail,avail);self.min_disk=min(self.min_disk,disk)
        if rss>16*1024**3 or avail<16*1024**3 or disk<50*1024**3:self.error="RAM/free-disk resource guard crossed"
        elapsed=time.monotonic()-self.started;rate=(self.done-self.resumed)/elapsed
        row={"stage":"S2_ALL_121","utc":now(),"completed":self.done,"total":self.total,"resumed":self.resumed,"warning_count":self.warnings,
            "failure_count":self.failed,"elapsed_sec":elapsed,"records_per_minute":rate*60,"eta_sec":(self.total-self.done)/rate if rate else None,
            "rss_process_tree_bytes":rss,"available_ram_bytes":avail,"free_disk_bytes":disk,"current":self.current,"resource_error":self.error}
        save(self.report/"status.json",row)
        with (self.report/"heartbeat.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(row)+"\n")
    def __enter__(self):
        self.sample()
        def loop():
            while not self.stop.wait(15):self.sample()
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();return self
    def __exit__(self,*args):self.stop.set();self.thread.join();self.sample()

def run(report,library,workers):
    report=Path(report).resolve();library=Path(library).resolve()
    if not library.is_relative_to(SIM/"rir_library"):raise ValueError("Library must be a version under simulation/rir_library")
    if workers!=4:raise ValueError("Frozen full-run contract uses four CPU workers")
    cfg=read(report/"EXTRACTION_CONFIG.json");cfgsha=sha(report/"EXTRACTION_CONFIG.json")
    if read(report/"final_policy_controls.json")["status"]!="PASSED" or sha(report/"final_policy_controls.json")!=cfg["final_policy_controls_sha256"]:
        raise ValueError("Final controls/config gate mismatch")
    for b in read(report/"CONTROL_CODE_BINDINGS.json"):
        if sha(b["path"])!=b["sha256"]:raise ValueError("Numerical source changed after controls")
    active=read(report/"ACTIVE_INPUTS.json");rows=active["recordings"]
    if len(rows)!=121 or len({r["run_id"] for r in rows})!=121:raise ValueError("Expected 121 unique active IDs")
    if any(r["room_table"]=="Loeb Caf" or r["original_status"] not in ("PASS","REVIEW") or not 0<r["source_distance_m_effective"]<=5 for r in rows):
        raise ValueError("Eligibility/distance mismatch")
    library.mkdir(parents=True,exist_ok=True);(library/"wav").mkdir(exist_ok=True)
    if (library/"EXTRACTION_CONFIG.json").exists() and sha(library/"EXTRACTION_CONFIG.json")!=cfgsha:raise ValueError("Different library contents: choose next version")
    if not (library/"EXTRACTION_CONFIG.json").exists():shutil.copyfile(report/"EXTRACTION_CONFIG.json",library/"EXTRACTION_CONFIG.json")
    cache=HashCache()
    codes=[cache.bind(Path(__file__).parent/n) for n in ("s2_run.py","s2_signal.py","s1_signal.py","s0_common.py")]
    code_identity=key_hash([{"path":b["path"],"sha256":b["sha256"]} for b in codes])
    jobs=[];resumed=[];allbindings=[]
    for row in rows:
        bound=[cache.bind(f["path"],f["sha256"]) for f in row["file_bindings"] if Path(f["path"]).name in CONSUMED]
        if len(bound)!=len(CONSUMED) or any(b["status"]!="BOUND" for b in bound):raise ValueError("Missing/mismatched consumed input: "+row["run_id"])
        allbindings+=bound
        identity=key_hash({"inputs":[(b["path"],b["sha256"]) for b in bound],"config_sha":cfgsha,"code":code_identity,
            "scope_sha":sha(report/"SCOPE_CONTEXT.json")})
        receipt=report/"records"/(row["run_id"]+".json")
        if receipt.exists():
            old=read(receipt)
            if old["resume_key"]==identity and old["status"]!="FAILED" and cache.bind(old["output"]["path"],old["output"]["sha256"])["status"]=="BOUND":
                resumed.append(row["run_id"]);continue
            if old["resume_key"]!=identity:raise ValueError("Existing receipt differs; preserve this version and create next")
        jobs.append((row,bound,identity))
    cache.flush();save(report/"CONSUMED_INPUT_BINDINGS.json",{"fresh_hashes":cache.fresh,"cached_receipts":cache.hits,"bindings":allbindings,"codes":codes})
    save(report/"EXTRACTION_CODE_BINDINGS.json",codes)
    start=time.monotonic();start_utc=now();results=[]
    with Monitor(report,cfg,121,len(resumed)) as monitor:
        if monitor.error:raise RuntimeError(monitor.error)
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers,mp_context=multiprocessing.get_context("spawn")) as pool:
            pending={};it=iter(jobs)
            def submit_one():
                job=next(it,None)
                if job is not None:pending[pool.submit(process,job[0],cfg)]=job
            for _ in range(4):submit_one()
            while pending:
                done,_=concurrent.futures.wait(pending,timeout=1,return_when=concurrent.futures.FIRST_COMPLETED)
                if monitor.error:
                    for future in pending:future.cancel()
                    raise RuntimeError(monitor.error)
                for future in done:
                    row,bound,identity=pending.pop(future);failure=None
                    try:r=future.result()
                    except Exception as exc:
                        # One same-code retry for transient/recoverable per-record errors.
                        try:r=pool.submit(process,row,cfg).result()
                        except Exception as retry:
                            failure={"type":type(retry).__name__,"message":str(retry),"first_error":str(exc),"traceback":traceback.format_exc()}
                    if failure:
                        m={"run_id":row["run_id"],"status":"FAILED","failure_reasons":[failure["type"]+": "+failure["message"]],
                           "limitations":[],"exception":failure,"can_proceed_to_hil_proof":False,"simulation_ready":False,"output":None}
                    else:
                        m=r["metrics"];m["output"]=None
                        if r["candidate"] is not None:
                            path=library/"wav"/(row["run_id"]+"_rir.wav");tmp=path.with_suffix(".wav.tmp")
                            sf.write(tmp,r["candidate"],16000,subtype="FLOAT",format="WAV")
                            os.replace(tmp,path);head=sf.info(path)
                            if (head.samplerate,head.channels,head.subtype)!=(16000,4,"FLOAT"):raise RuntimeError("Output header verification failed")
                            m["output"]={"path":str(path),"library_relative_path":"wav/"+path.name,"sha256":sha(path),"bytes":path.stat().st_size,
                                "frames":head.frames,"sample_rate_hz":16000,"channels":["MIC0","MIC1","MIC2","MIC3"],"subtype":"FLOAT"}
                        (report/"qc_arrays").mkdir(exist_ok=True)
                        np.savez_compressed(report/"qc_arrays"/(row["run_id"]+".npz"),**r["qc"])
                    m.update(resume_key=identity,inputs=bound,extraction_config_sha256=cfgsha,extractor_code_identity=code_identity,
                        recorded_utc=row["recorded_utc"],geometry={k:row[k] for k in ("room_table","recorder_position","orientation","obstructed","source_distance_m_original","source_distance_m_effective",
                            "speaker_angle_deg_original","speaker_angle_deg_effective","geometry_correction_applied","angle_label_interval","unmeasured_geometry","distance_binding")},
                        original_status=row["original_status"],updated_utc=now())
                    save(report/"records"/(row["run_id"]+".json"),m)
                    monitor.done+=1;monitor.failed+=m["status"]=="FAILED";monitor.warnings+=m["status"]=="EXTRACTED_WITH_LIMITATIONS";monitor.current=row["run_id"]
                    elapsed=time.monotonic()-start;completed=monitor.done-len(resumed);rate=completed/elapsed
                    print(f'S2 {monitor.done}/121 | {m["status"]} | elapsed {elapsed:.1f}s | {rate*60:.1f}/min | ETA {(121-monitor.done)/rate:.1f}s | limited {monitor.warnings} | failed {monitor.failed} | {row["run_id"]}',flush=True)
                    results.append({"run_id":row["run_id"],"status":m["status"]});submit_one()
    storage=sum(p.stat().st_size for root in (report,library) for p in root.rglob("*") if p.is_file())
    if storage>cfg["scratch_cap_gib"]*1024**3:raise RuntimeError("Task output/scratch storage exceeds 5GiB")
    save(report/("execution_"+str(time.time_ns())+".json"),{"started_utc":start_utc,"finished_utc":now(),"elapsed_sec":time.monotonic()-start,
         "processed":len(jobs),"resumed_ids":resumed,"results":results,"worker_count":4,"inner_threads":1,
         "observed_process_tree_rss_max_bytes":monitor.peak,"minimum_available_ram_bytes":monitor.min_avail,"minimum_free_disk_bytes":monitor.min_disk,
         "memory_scope":"15-second sampled aggregate process RSS, not an instantaneous peak or enforced hard limit",
         "report_and_library_bytes":storage,"owned_workers_closed":True})
    print("All 121 IDs accounted for. Canonical manifest/package are the next step.",flush=True)
    return 0

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--report",required=True);p.add_argument("--library",required=True);p.add_argument("--workers",type=int,default=4)
    a=p.parse_args();raise SystemExit(run(a.report,a.library,a.workers))
