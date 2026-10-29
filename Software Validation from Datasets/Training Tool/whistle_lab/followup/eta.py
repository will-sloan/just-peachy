"""Read-only whole-campaign ETA. Small metadata only; never scans audio per poll."""
from __future__ import annotations
import math
import statistics
import time
import extension
from shared import BASE, HOME, LAB, read_json, policy, run_dir, atomic_json


def write_profile(train, dev, panel, destination=None):
    """Call once when manifests are built, not from the dashboard request path."""
    frame = __import__('pandas').concat([train, dev], ignore_index=True)
    value={"rows":len(frame),"training_rows":len(train),"development_rows":len(dev),
           "physical_audio_hours":float(frame.duration_seconds.sum()/3600),
           "panel_audio_seconds":float(panel.duration_seconds.sum()),
           "buckets":[{"audio_seconds":int(a),"tokens":int(t),"rows":int(n)} for (a,t),n in frame.groupby(["audio_capacity","token_capacity"]).size().items()],
           "updated_at":time.time(),"source":"qualified pool" if destination is None else "expanded pool before level exclusions"}
    atomic_json(destination or HOME/"eta_profile.json",value)
    return value


def compute_seconds(profile, benchmark, config, calibration=1.):
    """Map pool bucket counts to existing measured shapes, then calibrate to live speed."""
    lookup={(s["audio_seconds"],s["tokens"]):s for s in benchmark.get("shapes",[])}
    total=0.
    for bucket in profile.get("buckets",[]):
        seconds,tokens=bucket["audio_seconds"],bucket["tokens"]
        size=max(1,min(config["max_batch_size"],config["batch_audio_seconds"]//seconds,config["batch_tokens"]//tokens))
        shape=lookup.get((seconds,tokens))
        if shape is None:
            step=.25
        else:
            ratio=size/shape["batch_size"]
            step=max(shape["compute_seconds"]*(.35+.65*ratio),shape["load_seconds"]*ratio)+.02
        total+=math.ceil(bucket["rows"]/size)*step
    return total*config.get("epochs",3)*calibration


def estimate(now=None):
    now=time.time() if now is None else now
    initial=read_json(BASE/"status.json")
    state=read_json(HOME/"queue.json",{"stage":"waiting_initial","jobs":[]})
    control=read_json(HOME/"control.json")
    paused=bool(control.get("paused") or read_json(BASE/"control.json").get("paused"))
    blocked=bool(state.get("blocked") or initial.get("phase") in ("needs_attention","failed") or read_json(HOME/"status.json").get("phase") in ("needs_attention","failed"))
    profile=read_json(HOME/"eta_profile.json")
    benchmark=read_json(BASE/"benchmark.json")
    p=policy(); original=read_json(LAB/"config.json")
    jobs=state.get("jobs",[])
    components=[]
    def add(name,low,high,basis):
        components.append({"name":name,"low_seconds":max(0,float(low)),"high_seconds":max(0,float(high)),"basis":basis})
    initial_done=initial.get("phase") in ("trained","exporting","evaluating","complete")
    remaining=0. if initial_done else max(0,float(initial.get("remaining_seconds") or 0))
    add("Current initial training",remaining*.9,remaining*1.2,"rolling measured training throughput")
    base_rtf=[m["rtf"] for m in read_json(BASE/"smoke_summary.json").get("metrics",[]) if m.get("rtf") is not None]
    rtf=max(.03,statistics.median(base_rtf)) if base_rtf else .15
    panel_seconds=profile.get("panel_audio_seconds",10000)
    score_one=max(120,panel_seconds*rtf)
    initial_scored=read_json(BASE/"evaluation_summary.json").get("complete") is True
    if not initial_scored: add("Initial export and comparison",600,3600,"planning allowance; initial comparison not complete")
    audit=read_json(HOME/"audio_quality.json")
    if not audit.get("complete"):
        audit_status=read_json(HOME/"quality_status.json")
        n=audit_status.get("completed_files",0); total=audit_status.get("total_files",0)
        if n>=50 and total>n:
            value=audit_status.get("elapsed_seconds",0)*(total-n)/n
            add("Recording-level audit",value*.6,value*2,"measured file rate; file lengths vary")
        else: add("Recording-level audit",1800,10800,"unmeasured; one cached CPU pass")
    if not read_json(HOME/"baseline/scores.json").get("complete"):
        add("Expanded-pool baseline scoring",score_one*2,score_one*6,"native runtime smoke RTF scaled to three development decodes")
    pilot_count=5+len(state.get("weight_jobs",["pending"]))+1
    elapsed=float(initial.get("elapsed_seconds") or 0)
    pilot_training_low=pilot_training_high=pilot_overhead_low=pilot_overhead_high=0.
    observed_full_ratio=None
    speeds={}
    for job in jobs:
        if job["spec"].get("production"): continue
        folder=run_dir(job["name"]); status=read_json(folder/"status.json")
        elapsed+=float(status.get("elapsed_seconds") or 0)
        if status.get("step",0)>=1000:
            speeds[job["name"]]=float(status.get("elapsed_seconds",0))/status["step"]
    if "method_full" in speeds:
        reference=state.get("selected_lora","mix_reference")
        if reference in speeds: observed_full_ratio=speeds["method_full"]/max(speeds[reference],1e-6)
    for number in range(pilot_count):
        job=[j for j in jobs if not j["spec"].get("production")][number] if number<len([j for j in jobs if not j["spec"].get("production")]) else None
        if job and job.get("unavailable"): continue
        folder=run_dir(job["name"]) if job else None
        if folder and read_json(folder/"scores.json").get("complete"): continue
        status=read_json(folder/"status.json") if folder else {}
        if not (folder and (folder/"model_manifest.json").exists()):
            used=float(status.get("elapsed_seconds") or 0)
            cap=max(0,p["pilot_max_active_seconds"]-used)
            measured=status.get("remaining_seconds")
            guess=min(cap,float(measured)) if measured is not None else min(cap,p["pilot_steps"]*.2)
            pilot_training_low+=guess*.75
            pilot_training_high+=min(cap,guess*1.5) if measured is not None else cap
            if not (folder and read_json(folder/"preflight.json").get("complete")):
                pilot_overhead_low+=300; pilot_overhead_high+=1800
        pilot_overhead_low+=score_one*1.4+120
        pilot_overhead_high+=score_one*4+600
    add("Remaining pilot training",pilot_training_low,pilot_training_high,"at most seven bounded pilots; measured current run where available")
    add("Pilot compilation, exports and scoring",pilot_overhead_low,pilot_overhead_high,"cached compilation and native decode estimates; not training time")
    # Correct shape-only estimates with the initial run's real, end-to-end speed.
    raw_total=sum(s["batches_per_epoch"]*max(s["compute_seconds"],s["load_seconds"])*original["epochs"] for s in benchmark.get("shapes",[]))
    measured_total=float(initial.get("elapsed_seconds") or 0)+float(initial.get("remaining_seconds") or 0)
    calibration=max(.7,min(3.,measured_total/raw_total)) if raw_total and measured_total else 1.3
    large={**original,"epochs":p["final_epochs"]}
    small={**large,"max_batch_size":8,"batch_audio_seconds":60,"batch_tokens":1024}
    lora=compute_seconds(profile,benchmark,large,calibration) or 30*3600
    full_base=compute_seconds(profile,benchmark,small,calibration) or 45*3600
    full_low=full_base*(max(1.,observed_full_ratio*.8) if observed_full_ratio else 1.4)
    full_high=full_base*(max(1.2,observed_full_ratio*1.4) if observed_full_ratio else 3.)
    decision=read_json(HOME/"production_decision.json")
    mode=decision.get("recipe",{}).get("method","lora") if decision else "undecided"
    production=run_dir("production_all_audio")
    prod_status=read_json(production/"status.json")
    elapsed+=float(prod_status.get("elapsed_seconds") or 0)
    model_ready=(production/"model_manifest.json").exists()
    if not model_ready:
        if prod_status.get("remaining_seconds") is not None and prod_status.get("step",0)>=100:
            low,high=prod_status["remaining_seconds"]*.85,prod_status["remaining_seconds"]*1.25
            basis="measured final-fit throughput"
        elif mode=="lora": low,high,basis=lora*.8,lora*1.35,"selected LoRA; measured initial shapes scaled to expanded pool"
        elif mode=="full": low,high,basis=full_low,full_high,"selected full tuning; pilot speed ratio if available"
        else: low,high,basis=lora*.8,max(lora*1.35,full_high),"method undecided: LoRA-to-full-tuning planning range"
        add("Final three-pass production fit",low,high,basis)
        add("Final compilation and export",300,2400,"planning allowance; deployment artifact required")
    first_model_ready=model_ready
    current_production_remaining=prod_status.get("remaining_seconds") if not first_model_ready else 0.
    amendment=extension.plan()
    extension_decision=read_json(HOME/"extension_production_decision.json")
    extra_fit_status="not_authorized"
    conditional_fit_high=0.
    if amendment:
        for name in extension.PILOTS:
            folder=run_dir(name)
            if read_json(folder/"scores.json").get("complete"): continue
            status=read_json(folder/"status.json")
            if not (folder/"model_manifest.json").exists():
                used=float(status.get("elapsed_seconds") or 0)
                cap=max(0.,amendment["pilot_max_active_seconds"]-used)
                measured=status.get("remaining_seconds")
                guess=min(cap,float(measured)) if measured is not None else min(cap,amendment["pilot_steps"]*speeds.get("mix_reference",.25))
                add(name.replace('_',' ')+" training",guess*.75,min(cap,guess*1.5) if measured is not None else cap,"declared 30,000-update / two-active-hour / three-pass cap; actual exposure may differ")
                if not read_json(folder/"preflight.json").get("complete"):
                    add(name.replace('_',' ')+" compilation",300,1800,"cached compilation planning allowance")
            add(name.replace('_',' ')+" export and scoring",score_one*1.4+120,score_one*4+600,"same development panel; decode identical exports once")
        # The low scenario retains the current model. The high scenario includes
        # one additional fit; never imply that this conditional cost is certain.
        first_duration=float(prod_status.get("elapsed_seconds") or 0)+float(prod_status.get("remaining_seconds") or 0)
        fit_estimate=first_duration if prod_status.get("step",0)>=100 else lora
        if not extension_decision:
            extra_fit_status="conditional_on_development_gain"
            conditional_fit_high=fit_estimate*1.25+2400
            add("Conditional additional production fit and export",0,conditional_fit_high,"only if an omission passes all development and exposure guards; conservative full-pool upper scenario")
            model_ready=False
        elif extension_decision.get("rerun_required"):
            extra_fit_status="required_by_development_decision"
            refit=run_dir(extension.REFIT)
            rs=read_json(refit/"status.json")
            elapsed+=float(rs.get("elapsed_seconds") or 0)
            model_ready=(refit/"model_manifest.json").exists()
            if not model_ready:
                remaining=rs.get("remaining_seconds")
                if remaining is not None and rs.get("step",0)>=100:
                    lo,hi=float(remaining)*.85,float(remaining)*1.25
                    basis="measured additional-fit throughput"
                else:
                    # Candidate-specific row count is available after preparation;
                    # until then retain a broad full-pool upper estimate.
                    count=read_json(refit/"data_audit.json").get("training_rows")
                    fraction=count/profile.get("rows",count) if count else 1.
                    lo,hi=fit_estimate*fraction*.65,fit_estimate*min(1.,fraction*1.5)*1.25
                    basis="first production speed scaled to retained views; duration mix not yet measured"
                add("Selected additional three-pass fit",lo,hi,basis)
                add("Additional production compilation and export",300,2400,"planning allowance")
        else:
            extra_fit_status="skipped_no_qualifying_gain"
            model_ready=first_model_ready
    low=sum(x["low_seconds"] for x in components); high=sum(x["high_seconds"] for x in components)
    if model_ready: low=high=0.
    complete=read_json(HOME/"summary.json").get("complete") is True
    if amendment:
        unscored=sum(not read_json(run_dir(name)/"test_scores.json").get("complete") for name in ([extension.FIRST,extension.REFIT] if extension_decision.get("rerun_required") else [extension.FIRST]))
        # A conditional second test belongs only in the upper scenario.
        possible_extra=1 if not extension_decision else 0
        final_eval=(score_one*.5*unscored,score_one*2*(unscored+possible_extra))
    else:
        final_eval=(score_one*.5,score_one*2)
    if complete: final_eval=(0.,0.)
    if complete: low=high=0.; components=[]
    result={"updated_at":now,"remaining_to_production":{"low_seconds":low,"high_seconds":high},"remaining_to_campaign_complete":{"low_seconds":low+final_eval[0],"high_seconds":high+final_eval[1]},"projected_production_finish_utc":{"earliest":None if paused or blocked else now+low,"latest":None if paused or blocked else now+high},"production_method":mode,"production_model_ready":model_ready,"campaign_complete":complete,"paused":paused,"blocked":blocked,"active_training_elapsed_seconds":elapsed,"estimated_overall_percent":100. if complete else 100*elapsed/max(elapsed+(low+high)/2,1),"components":components,"scenarios_full_fit":{"lora_seconds":lora,"full_low_seconds":full_low,"full_high_seconds":full_high},"confidence":"measured current run; future stages estimated until their benchmarks complete","notes":["Includes initial work, audio audit, bounded pilots, scoring, final fit and export.","Final matched test is included only in campaign-complete ETA.","Excludes user pauses, sleep, failures, synchronization and setup on another computer.","A planning range is not a statistical confidence interval; it changes with the chosen method and retained pool."]}
    result.update(first_production_model_ready=first_model_ready,
        current_production_remaining_seconds=current_production_remaining,
        extension_authorized=bool(amendment),additional_production_fit=extra_fit_status,
        conditional_additional_fit_upper_seconds=conditional_fit_high,
        selected_production_run=extension_decision.get("selected_production_run"),
        maximum_training_runs=amendment.get("maximum_training_runs",p["maximum_training_runs"]))
    if extra_fit_status=="conditional_on_development_gain":
        result["remaining_if_current_recipe_retained"]={"low_seconds":low,"high_seconds":max(low,high-conditional_fit_high)}
    if amendment:
        result["confidence"]=("current fit measured; added pilots estimated; upper scenario includes one conditional refit" if not extension_decision else "development recipe fixed; active fit measured where available; pending exports and scoring estimated")
        result["notes"].append("The current production export is preserved. It is not campaign completion while the predeclared omission comparison remains. Additional fit is skipped if no omission qualifies.")
    return result
