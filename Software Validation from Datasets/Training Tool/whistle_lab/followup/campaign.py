"""Windows singleton supervisor, sequential experiment policy and local dashboard."""
from __future__ import annotations
import argparse
import ctypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import traceback
import extension
from shared import BASE, HOME, LAB, SOURCE, DATASETS, atomic_json, read_json, run_dir, initial_complete, paused, update_status, policy, freeze_policy


def normalized(weights):
    total=sum(weights.values())
    return {d:float(v/total) for d,v in weights.items()}


def ablations():
    batch={"max_batch_size":8,"batch_audio_seconds":60,"batch_tokens":1024}
    result=[{"name":"mix_reference","spec":dict(batch)}]
    for ds in DATASETS:
        result.append({"name":"only_"+ds,"spec":{**batch,"datasets":[ds]}})
    return result


def method_jobs(weights):
    common={"dataset_weights":weights,"max_batch_size":8,"batch_audio_seconds":60,"batch_tokens":1024}
    return [{"name":"method_full","spec":{**common,"method":"full","learning_rate":1e-5},"optional":True}]


def wsl_path(path):
    value=Path(path).absolute().as_posix()
    return "/mnt/"+value[0].lower()+value[2:]


def job_complete(job):
    if job.get("unavailable"): return True
    name="test_scores.json" if job["spec"].get("production") else "scores.json"
    return read_json(run_dir(job["name"])/name).get("complete") is True


def advance(state):
    """Append immutable stages only after all evidence for the previous stage exists."""
    from decide import result, choose, paired
    initial=read_json(LAB/"config.json")["dataset_weights"]
    stage=state["stage"]
    if stage=="baseline":
        state.update(stage="ablations",jobs=ablations())
    elif stage=="ablations":
        reference=result("mix_reference")
        singles={d:result("only_"+d) for d in DATASETS}
        # One bounded proposal, not a causal attribution claim or a weight search.
        baseline=read_json(HOME/"baseline/scores.json")["models"]["base_w4a8"]
        effects={d:baseline["macro_wer"]-singles[d]["macro_wer"] for d in DATASETS}
        best=max(effects,key=effects.get)
        weights=dict(initial); weights[best]*=1.5
        spec={**state["jobs"][0]["spec"],"dataset_weights":normalized(weights)}
        atomic_json(HOME/"dataset_contributions.json",{"single_dataset_macro_wer_gain_over_base":effects,"single_dataset":singles,"reference":reference,"caution":"Short standalone adaptation results do not measure a dataset's causal marginal contribution to a mixture; training exposure can differ at the epoch/time caps"})
        proposals=[{"name":"weight_once","spec":spec}] if effects[best]>0 else []
        state.update(stage="weights",weight_jobs=[j["name"] for j in proposals]); state["jobs"].extend(proposals)
    elif stage=="weights":
        decision=choose("mix_reference",state["weight_jobs"])
        atomic_json(HOME/"weight_decision.json",decision)
        selected=read_json(run_dir(decision["selected"])/"config.json")["dataset_weights"]
        state.update(stage="methods",selected_weights=selected,selected_lora=decision["selected"])
        state["jobs"].extend(method_jobs(selected))
    elif stage=="methods":
        candidates=[j["name"] for j in state["jobs"] if j["name"]=="method_full" and not j.get("unavailable")]
        decision=choose(state["selected_lora"],candidates)
        atomic_json(HOME/"method_decision.json",decision)
        selected=decision["selected"]
        spec=dict(next(j["spec"] for j in state["jobs"] if j["name"]==selected))
        spec.update(production=True,seed=policy()["seed"])
        if spec.get("method","lora")=="lora" and policy()["final_lora_use_original_batch_limits"]:
            original=read_json(LAB/"config.json")
            spec.update({key:original[key] for key in ("max_batch_size","batch_audio_seconds","batch_tokens")})
        atomic_json(HOME/"production_decision.json",{"selected_method_run":selected,"recipe":spec,"second_seed_confirmation":False,"bounded_screening_only":True,"development_folded_into_training":True,"frozen_test_preserved":True,"real_product_validation_available":False})
        state.update(stage="production"); state["jobs"].append({"name":"production_all_audio","spec":spec})
    elif stage=="production" and extension.plan():
        if not extension.exported(extension.FIRST):
            raise ValueError("Existing production export must finish before the amendment")
        extension.start(state)
    elif stage=="extension_pilots":
        extension.choose_recipe(state)
    elif stage=="extension_production":
        if not extension.exported(extension.REFIT):
            raise ValueError("Amended production export is incomplete")
        state.update(stage="final_comparison")
    elif stage=="final_comparison":
        comparison=extension.finish_comparison(state,read_json(BASE/"evaluation_summary.json"))
        selected=state["selected_production_run"]
        state.update(stage="complete",completed_at=time.time())
        atomic_json(HOME/"summary.json",{"complete":True,"dataset_contributions":read_json(HOME/"dataset_contributions.json"),"weight_selection":read_json(HOME/"weight_decision.json"),"method_selection":read_json(HOME/"production_decision.json"),"extension":read_json(HOME/"extension_snapshot.json"),"extension_selection":read_json(HOME/"extension_decision.json"),"production_selection":read_json(HOME/"extension_production_decision.json"),"final_test":read_json(run_dir(selected)/"test_scores.json"),"matched_comparison":comparison,"initial_comparison":read_json(BASE/"evaluation_summary.json"),"final_models":str(run_dir(selected)),"preserved_first_production_models":str(run_dir(extension.FIRST)),"licenses":read_json(BASE/"release_review.json"),"real_product_validation_available":False,"independent_age_test_available":False})
    elif stage=="production":
        state.update(stage="complete",completed_at=time.time())
        atomic_json(HOME/"summary.json",{"complete":True,"dataset_contributions":read_json(HOME/"dataset_contributions.json"),"weight_selection":read_json(HOME/"weight_decision.json"),"method_selection":read_json(HOME/"production_decision.json"),"final_test":read_json(run_dir("production_all_audio")/"test_scores.json"),"matched_comparison":read_json(HOME/"matched_comparison.json"),"initial_comparison":read_json(BASE/"evaluation_summary.json"),"final_models":str(run_dir("production_all_audio")),"licenses":read_json(BASE/"release_review.json"),"real_product_validation_available":False})
    else: raise ValueError("Unknown campaign stage")
    if len(state["jobs"])>extension.plan().get("maximum_training_runs",policy()["maximum_training_runs"]):
        raise ValueError("Hard experiment count exceeded")
    atomic_json(HOME/"queue.json",state)


def launch(script,name,flags=()):
    import psutil
    config=read_json(LAB/"config.json")
    folder=HOME/"baseline" if name=="baseline" else run_dir(name)
    folder.mkdir(parents=True,exist_ok=True)
    command=["wsl.exe","-d",config["wsl_distribution"],"--",config["wsl_python"],"-u",wsl_path(SOURCE/script),name,*flags]
    with (folder/("train.log" if script=="worker.py" else "score.log")).open("a",encoding="utf-8") as log:
        log.write(f"\nLaunched {script} {time.strftime('%Y-%m-%d %H:%M:%S')}\n"); log.flush()
        child=None
        saved=read_json(HOME/"worker.json")
        try:
            owned=psutil.Process(saved["windows_pid"])
            args=owned.cmdline()
            if saved.get("script")==script and saved.get("run")==name and wsl_path(SOURCE/script) in args and name in args and abs(owned.create_time()-saved["started_at"])<10:
                child=owned
                log.write("Reattached to surviving owned WSL launcher; no new worker started.\n"); log.flush()
        except (KeyError,psutil.Error): pass
        if child is None:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            atomic_json(HOME/"worker.json",{"windows_pid":child.pid,"script":script,"run":name,"started_at":time.time()})
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            while True:
                try:
                    code=child.wait(timeout=10)
                    return 0 if code is None else code
                except (subprocess.TimeoutExpired,psutil.TimeoutExpired):
                    progress=read_json(folder/("status.json" if script=="worker.py" else "scoring_status.json"))
                    update_status("training" if script=="worker.py" else "evaluating",current_run=name,progress=progress,message=f"{name}: {'GPU training' if script=='worker.py' else 'native-runtime scoring'}")
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def supervise():
    from prepare import prepare_pool,prepare_run
    while True:
        try:
            if paused():
                update_status("paused",message="Follow-ups paused; original-run pause is also respected")
                time.sleep(10); continue
            if not initial_complete():
                update_status("waiting_initial",message="Waiting for original fine-tuning AND its matched comparison")
                time.sleep(15); continue
            freeze_policy()
            extension.freeze()
            state=read_json(HOME/"queue.json",{"stage":"baseline","jobs":[],"created_at":time.time()})
            if state["stage"]=="complete":
                update_status("complete",message="Experiments, full-coverage production training and frozen-test comparison complete")
                time.sleep(30); continue
            if state.get("blocked"):
                update_status("needs_attention",message=state["blocked"])
                time.sleep(30); continue
            if shutil.disk_usage(HOME).free < policy()["minimum_free_disk_gib"]*1024**3:
                update_status("needs_attention",message="Less than 12 GiB free; waiting without deleting data or checkpoints")
                time.sleep(30); continue
            if not (HOME/"pool.json").exists():
                update_status("preparing",message="Auditing expanded microphone pool")
                prepare_pool()
            if not read_json(HOME/"audio_quality.json").get("complete"):
                from quality import audit_pool
                if not audit_pool(): continue
            if state["stage"]=="baseline":
                if read_json(HOME/"baseline/scores.json").get("complete"):
                    advance(state); continue
                code=launch("score.py","baseline",["--baseline"])
                job=None
            else:
                # Preserve the ongoing fit, then decide the amendment before any frozen test.
                if extension.transition_after_export(state):
                    advance(state); continue
                job=next((j for j in extension.eligible_jobs(state) if not job_complete(j)),None)
                if job is None:
                    advance(state); continue
                name=job["name"]
                update_status("preparing",current_run=name,message="Preparing immutable experiment inputs")
                prepare_run(name,job["spec"])
                if not (run_dir(name)/"model_manifest.json").exists():
                    code=launch("worker.py",name)
                else:
                    code=launch("score.py",name,["--final"] if job["spec"].get("production") else [])
            if code in (0,73,75):
                time.sleep(60 if code==73 else 5); continue
            log_path=run_dir(job["name"])/"train.log" if job else HOME/"baseline/score.log"
            tail=""
            if log_path.exists():
                with log_path.open("rb") as handle:
                    handle.seek(max(0,log_path.stat().st_size-12000)); tail=handle.read().decode("utf-8",errors="replace")
            if job and job.get("optional") and any(token in tail for token in ("RESOURCE_EXHAUSTED","out of memory","CUDA_ERROR_OUT_OF_MEMORY")):
                job["unavailable"]="RTX 3080 memory limit at the declared batch sizes; checkpoint/log retained"
                atomic_json(HOME/"queue.json",state)
                continue
            key=job["name"] if job else "baseline"
            retries=state.setdefault("failures",{})
            retries[key]=retries.get(key,0)+1
            if retries[key]>=3:
                state["blocked"]=f"{key} failed three attempts; inspect its log and resume explicitly"
            atomic_json(HOME/"queue.json",state)
            update_status("failed",message=f"{key} exited {code}; saved state retained",attempt=retries[key])
            time.sleep(30)
        except Exception as error:
            update_status("needs_attention",message=str(error),traceback=traceback.format_exc())
            # Preserve the error and require an explicit resume instead of looping on bad inputs.
            state=read_json(HOME/"queue.json",{"stage":"baseline","jobs":[]})
            state["blocked"]=str(error)
            atomic_json(HOME/"queue.json",state)
            time.sleep(30)


def payload():
    from eta import estimate
    queue=read_json(HOME/"queue.json",{"stage":"waiting_initial","jobs":[]})
    jobs=[]
    for job in queue["jobs"]:
        score=read_json(run_dir(job["name"])/("test_scores.json" if job["spec"].get("production") else "scores.json"))
        chosen=score.get("models",{}).get(score.get("selected"),{})
        jobs.append({"name":job["name"],"complete":job_complete(job),"exported":extension.exported(job["name"]),"unavailable":job.get("unavailable"),"method":job["spec"].get("method","lora"),"role":score.get("role","frozen_test" if job["spec"].get("production") else "development"),"macro_wer":chosen.get("macro_wer"),"datasets":chosen.get("datasets",{}),"negative_probes":chosen.get("negative_probes",{})})
    initial=read_json(BASE/"status.json")
    amendment=extension.plan()
    planned=[j["name"] for j in extension.pilot_jobs(amendment) if j["name"] not in {x["name"] for x in jobs}]
    return {"status":read_json(HOME/"status.json"),"control":read_json(HOME/"control.json"),"stage":queue["stage"],"jobs":jobs,"planned_extension_jobs":planned,"extension":amendment,"extension_decision":read_json(HOME/"extension_decision.json"),"extension_production_decision":read_json(HOME/"extension_production_decision.json"),"pool":read_json(HOME/"pool.json"),"quality":read_json(HOME/"audio_quality.json"),"campaign_eta":estimate(),"limits":{"training_runs":amendment.get("maximum_training_runs",policy()["maximum_training_runs"]),"pilot_steps":policy()["pilot_steps"],"pilot_seconds":policy()["pilot_max_active_seconds"]},"initial":{k:initial.get(k) for k in ("phase","percent","remaining_seconds")},"production_decision":read_json(HOME/"production_decision.json"),"server_time":time.time()}


def control(action):
    value=read_json(HOME/"control.json")
    value.update(paused=action=="pause",changed_at=time.time())
    atomic_json(HOME/"control.json",value)
    if action=="resume":
        queue=read_json(HOME/"queue.json")
        if queue:
            queue.pop("blocked",None); queue["failures"]={}
            atomic_json(HOME/"queue.json",queue)
    return value


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,data,code=200,kind="application/json"):
        self.send_response(code); self.send_header("Content-Type",kind+"; charset=utf-8"); self.send_header("Cache-Control","no-store")
        origin=self.headers.get("Origin")
        if self.command=="GET" and origin in {"http://127.0.0.1:8766","http://localhost:8766"}:
            self.send_header("Access-Control-Allow-Origin",origin); self.send_header("Vary","Origin")
        self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        if self.path=="/api/status": self.reply(json.dumps(payload(),allow_nan=False).encode())
        elif self.path=="/api/eta":
            from eta import estimate
            self.reply(json.dumps(estimate(),allow_nan=False).encode())
        elif self.path in ("/","/index.html"): self.reply((SOURCE/"index.html").read_bytes(),kind="text/html")
        else: self.reply(b'{}',404)
    def do_POST(self):
        allowed={"http://127.0.0.1:8767","http://localhost:8767"}
        if self.path!="/api/control" or self.headers.get("X-Whistle-Control")!="local" or (self.headers.get("Origin") and self.headers["Origin"] not in allowed):
            self.reply(b'{}',403); return
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0<length<=1024: raise ValueError()
            action=json.loads(self.rfile.read(length))["action"]
            if action not in ("pause","resume"): raise ValueError()
            self.reply(json.dumps(control(action)).encode())
        except (ValueError,KeyError): self.reply(b'{}',400)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--action",choices=["watch","pause","resume","status","prepare"],default="watch")
    args=parser.parse_args()
    HOME.mkdir(parents=True,exist_ok=True)
    if args.action in ("pause","resume"):
        print(json.dumps(control(args.action))); return
    if args.action=="status": print(json.dumps(payload(),indent=2)); return
    if args.action=="prepare":
        from prepare import prepare_pool
        print(json.dumps(prepare_pool(),indent=2)); return
    import msvcrt
    lock=(HOME/"supervisor.lock").open("a+b")
    lock.seek(0)
    if not lock.read(1): lock.write(b"0"); lock.flush()
    lock.seek(0)
    try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError: return
    freeze_policy()
    extension.freeze()
    server=ThreadingHTTPServer(("127.0.0.1",policy()["dashboard_port"]),Handler)
    atomic_json(HOME/"supervisor.json",{"pid":os.getpid(),"started_at":time.time(),"url":"http://127.0.0.1:8767"})
    threading.Thread(target=supervise,daemon=True).start()
    server.serve_forever()


if __name__=="__main__": main()
