"""Isolated resumable LoRA/encoder/full QAT worker. Never runs alongside the baseline."""
from __future__ import annotations
import argparse
import json
import os
import time
import traceback
from shared import BASE, HOME, configure, initial_complete, paused, atomic_json, read_json, sha256


def main():
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    args = parser.parse_args()
    if not initial_complete():
        raise RuntimeError("The original training and matched comparison must complete first")
    if paused():
        return 75
    locks = []
    for path in (BASE / "trainer.lock", HOME / "gpu.lock"):
        handle = path.open("a+b")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 73
        locks.append(handle)
    config, folder = configure(args.run)
    import audio  # installs explicit channel selection before the trainer is imported
    import train as original
    import numpy as np
    import pandas as pd
    import jax
    import jax.numpy as jnp
    import optax
    from flax import serialization
    from flax.traverse_util import flatten_dict, unflatten_dict
    from common import ASSETS, atomic_bytes, status
    from data import plan_batches
    from needle.model.quantize import cq_ste_params
    from needle.model.whistle_finetune import build, tuned_params

    class CampaignTraining(original.Training):
        def __init__(self):
            super().__init__()
            self.mode = config["method"]
            self.total_steps = min(self.total_steps, config.get("max_steps") or self.total_steps)
            if self.mode == "full":
                self.lora = self.params
            elif self.mode == "partial":
                self.lora = {k:v for k,v in self.params.items() if k in {"stem", "encoder"}}
                if set(self.lora) != {"stem", "encoder"}:
                    raise ValueError("Audio encoder/stem parameter names changed")
            elif self.mode != "lora":
                raise ValueError("Unsupported training method")
            self.schedule = optax.warmup_cosine_decay_schedule(0., config["learning_rate"], min(1000,max(1,self.total_steps//20)), self.total_steps, end_value=config["learning_rate"]*.05)
            self.optimizer = optax.chain(optax.clip_by_global_norm(1.), optax.adamw(self.schedule,weight_decay=.01))
            self.opt_state = self.optimizer.init(self.lora)
            self.step_fn = jax.jit(self._step)
            self.eval_fn = jax.jit(self._loss)
            print(f"Method {self.mode}; trainable values {sum(x.size for x in jax.tree.leaves(self.lora)):,}; budget {self.total_steps:,} updates", flush=True)

        def merged(self, values, base):
            if self.mode == "full":
                return values
            if self.mode == "partial":
                return {**base, **values}
            return tuned_params(base,self.cfg,self.tokenizer,values,self.scale,None)

        def merged_quantized(self, values, base, unused):
            return cq_ste_params(self.merged(values,base),4)

        def save_adapter(self, name):
            if self.mode == "lora":
                return super().save_adapter(name)
            if name == "adapter.latest.safetensors":
                return  # Full optimizer checkpoints already contain these weights.
            target = name.replace("adapter.","weights.").replace(".safetensors",".msgpack")
            atomic_bytes(folder / target, serialization.to_bytes(jax.device_get(self.lora)))

        def verify_numerics(self, first):
            batch = self.loader.batch(first)
            one = self.step_fn(self.lora,self.opt_state,self.qbase,self.original,*batch)
            jax.block_until_ready(one)
            if not np.isfinite(float(one[2])+float(one[3])) or float(one[3]) == 0:
                raise ValueError("First update has invalid or zero gradients")
            payload = serialization.to_bytes({"values":jax.device_get(one[0]),"optimizer":jax.device_get(one[1])})
            restored = serialization.from_bytes({"values":one[0],"optimizer":one[1]},payload)
            expected = self.step_fn(one[0],one[1],self.qbase,self.original,*batch)
            actual = self.step_fn(restored["values"],restored["optimizer"],self.qbase,self.original,*batch)
            jax.block_until_ready((expected,actual))
            diff=max(float(np.max(np.abs(np.asarray(a)-np.asarray(b)))) for a,b in zip(jax.tree.leaves(expected[:2]),jax.tree.leaves(actual[:2])))
            if diff > 1e-6:
                raise ValueError("Checkpoint next-update equivalence failed")
            if self.mode == "partial":
                merged=self.merged(one[0],self.params)
                if any(merged[k] is not self.params[k] for k in self.params if k not in self.lora):
                    raise ValueError("Partial tuning changed a frozen component")
            atomic_json(folder/"resume_verification.json",{"passed":True,"method":self.mode,"max_next_update_difference":diff,"optimizer_and_schedule_restored":True,"diagnostic_updates_discarded":True})

        def preflight(self):
            previous=read_json(folder/"preflight.json")
            if previous.get("identity")==self.identity and previous.get("complete"):
                return True
            groups={}
            for item in self.plan:
                key=tuple(item[1:])
                if key not in groups or len(item[0])==item[3]: groups[key]=item
            results=previous.get("shapes",[]) if previous.get("identity")==self.identity else []
            done={tuple(r["shape"]) for r in results}
            for key,item in sorted(groups.items()):
                if paused() or original.STOP:
                    status("paused",message="GPU shape preflight paused; verified shapes retained")
                    return False
                if key in done: continue
                status("benchmarking",message=f"Checking {self.mode} memory/gradients for {key}",completed_shapes=len(results),total_shapes=len(groups))
                batch=self.loader.batch(item)
                start=time.perf_counter()
                update=self.step_fn(self.lora,self.opt_state,self.qbase,self.original,*batch)
                jax.block_until_ready(update)
                if not np.isfinite(float(update[2])+float(update[3])):
                    raise ValueError(f"Nonfinite preflight shape {key}")
                results.append({"shape":list(key),"compile_and_step_seconds":time.perf_counter()-start})
                del update,batch
                atomic_json(folder/"preflight.json",{"identity":self.identity,"complete":False,"shapes":results})
            atomic_json(folder/"preflight.json",{"identity":self.identity,"complete":True,"shapes":results,"diagnostic_updates_discarded":True})
            return True

        def validate(self):
            if not config.get("production"):
                super().validate()

        def record(self, **values):
            elapsed=self.base_elapsed+time.monotonic()-self.segment_start
            steps=self.meta["step"]
            remaining=(elapsed/steps)*(self.total_steps-steps) if steps else None
            if config.get("max_active_seconds"):
                time_left=max(0.,config["max_active_seconds"]-elapsed)
                remaining=time_left if remaining is None else min(time_left,remaining)
            value={"time":time.time(),"step":steps,"total_steps":self.total_steps,"epoch":self.meta["epoch"],"epochs":config["epochs"],"processed_records":self.meta["processed_records"],"training_rows":len(self.frame),"percent":100*steps/self.total_steps,"elapsed_seconds":elapsed,"remaining_seconds":remaining,"learning_rate":float(self.schedule(steps)),"dataset_records":self.meta["dataset_records"],"audio_hours_processed":self.meta["processed_audio_seconds"]/3600,"method":self.mode,**values}
            status("training",message=f"{args.run}: {self.mode} training",**value)
            with (folder/"history.jsonl").open("a",encoding="utf-8") as handle:
                handle.write(json.dumps(value,allow_nan=False)+"\n")

        def export(self):
            self.save_adapter("adapter.final.safetensors")
            status("exporting",percent=100.,message="Exporting W4A8 deployment models")
            build(self.merged(self.lora,self.params),self.cfg,self.tokenizer,str(folder/"whistle.final.cact"))
            best_path=folder/("adapter.best.safetensors" if self.mode=="lora" else "weights.best.msgpack")
            if not best_path.exists():
                self.save_adapter("adapter.best.safetensors")
            if self.mode == "lora":
                from needle.model.checkpoints import read_adapter
                saved=read_adapter(str(best_path))
                best={tuple(k.split("/")):{n:jnp.asarray(v) for n,v in mats.items()} for k,mats in saved["lora"].items()}
            else:
                best=serialization.from_bytes(self.lora,best_path.read_bytes())
            build(self.merged(best,self.params),self.cfg,self.tokenizer,str(folder/"whistle.best.cact"))
            atomic_json(folder/"model_manifest.json",{"run_identity":self.identity,"config":config,"completed_training":self.meta,"model_sha256":{n:sha256(folder/n) for n in ("whistle.best.cact","whistle.final.cact")},"base_assets":str(ASSETS),"license_resolution":read_json(BASE/"release_review.json"),"training_includes_development":bool(config.get("production")),"development_selection_disabled":bool(config.get("production")),"frozen_test_preserved":True,"real_product_validation_available":False})
            status("trained",percent=100.,message="Export complete; decoding comparison pending")

        def run(self):
            restored=self.restore()
            if not read_json(folder/"resume_verification.json").get("passed"):
                self.verify_numerics(self.plan[0])
            if not self.preflight():
                return 75
            self.segment_start=time.monotonic()
            if not restored:
                self.save()
            for epoch in range(self.meta["epoch"],config["epochs"]):
                plan=plan_batches(self.frame,epoch)
                beginning=self.meta["next_batch"]
                self.meta["epoch"]=epoch
                future=self.prefetch.submit(self.loader.batch,plan[beginning]) if beginning<len(plan) and self.meta["step"]<self.total_steps else None
                for index in range(beginning,len(plan)):
                    if self.meta["step"]>=self.total_steps:
                        break
                    elapsed=self.base_elapsed+time.monotonic()-self.segment_start
                    if config.get("max_active_seconds") and elapsed>=config["max_active_seconds"]:
                        self.meta["budget_stop"]="pilot active-time cap"
                        break
                    if original.STOP or paused():
                        self.save()
                        status("paused",message="Campaign paused at a saved optimizer state")
                        return 75
                    batch=future.result()
                    future=self.prefetch.submit(self.loader.batch,plan[index+1]) if index+1<len(plan) and self.meta["step"]+1<self.total_steps else None
                    result=self.step_fn(self.lora,self.opt_state,self.qbase,self.original,*batch)
                    loss,norm=float(result[2]),float(result[3])
                    if not np.isfinite(loss+norm):
                        raise FloatingPointError("Nonfinite update; checkpoint preserved")
                    self.lora,self.opt_state=result[:2]
                    chosen=self.frame.iloc[plan[index][0]]
                    self.meta["step"]+=1
                    self.meta["next_batch"]=index+1
                    self.meta["processed_records"]+=len(chosen)
                    self.meta["processed_audio_seconds"]+=float((chosen.end_sec-chosen.start_sec).sum())
                    for ds,count in chosen.dataset_id.value_counts().items():
                        self.meta["dataset_records"][ds]=self.meta["dataset_records"].get(ds,0)+int(count)
                    if self.meta["step"]%10==0 or self.meta["step"]==1:
                        self.record(loss=loss,gradient_norm=norm)
                    if time.monotonic()-self.last_save>=config["checkpoint_seconds"]:
                        self.save()
                    if self.meta["step"]%config["validation_every_steps"]==0:
                        self.save(); self.validate()
                if self.meta["next_batch"]==len(plan):
                    self.meta["epoch"]=epoch+1
                    self.meta["next_batch"]=0
                self.validate(); self.save()
                if self.meta["step"]>=self.total_steps or self.meta.get("budget_stop"):
                    break
            self.export()
            self.loader.close(); self.prefetch.shutdown(wait=True)
            return 0

    try:
        if (folder/"model_manifest.json").exists():
            manifest=read_json(folder/"model_manifest.json")
            if all((folder/n).exists() and sha256(folder/n)==digest for n,digest in manifest["model_sha256"].items()):
                return 0
        training=CampaignTraining()
        return training.run()
    except Exception as error:
        status("failed",message=str(error),traceback=traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
