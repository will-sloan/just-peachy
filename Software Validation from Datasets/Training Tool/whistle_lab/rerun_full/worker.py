"""Three complete passes of full-parameter QAT with exact optimizer continuation."""
from __future__ import annotations
import argparse
from collections import deque
import json
import time
import traceback
from runtime import *


def main():
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--target", type=int)
    args = parser.parse_args()
    if paused():
        return 75
    config = verify()
    locks = []
    for path in (BASE/"trainer.lock", FOLLOWUP/"gpu.lock", RUN/"worker.lock"):
        handle = path.open("a+b")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 73
        locks.append(handle)
    import audioio
    import train as original
    from data import plan_batches
    import numpy as np
    import jax
    import optax
    from flax import serialization
    from needle.model.quantize import cq_ste_params
    from needle.model.whistle_finetune import build

    class FullTraining(original.Training):
        def __init__(self):
            super().__init__()
            # Train every pretrained parameter; no LoRA adapter is initialized
            # into the values being updated, and no initial tuned weights merge.
            self.lora = self.params
            self.schedule = optax.warmup_cosine_decay_schedule(
                0., config["learning_rate"], config["warmup_steps"],
                config["total_steps"], end_value=config["end_learning_rate"])
            self.optimizer = optax.chain(optax.clip_by_global_norm(1.),
                                         optax.adamw(self.schedule, weight_decay=.01))
            self.opt_state = self.optimizer.init(self.lora)
            self.step_fn = jax.jit(self._step)
            self.parameter_count = sum(x.size for x in jax.tree.leaves(self.lora))
            if self.total_steps != config["total_steps"]:
                raise ValueError("Full-pass optimizer horizon changed")
            restored = self.restore()
            if not restored and (RUN/"initialization_verification.json").exists():
                raise RuntimeError("Saved run lost its optimizer; refusing a fresh restart")
            self.meta.setdefault("training_wall_seconds", 0.)
            self.meta.setdefault("distinct_sources", {})
            epoch = int(self.meta["epoch"])
            self.plan = plan_batches(self.frame, min(epoch, config["epochs"]-1))
            n = config["batches_per_epoch"]
            if len(self.plan) != n or self.meta["step"] != epoch*n+self.meta["next_batch"]:
                raise ValueError("Saved epoch/batch/step positions disagree")
            self.visited = {ds: set() for ds in self.frame.dataset_id.unique()}
            if epoch:
                for ds, p in self.frame.groupby("dataset_id"):
                    self.visited[ds].update(p.source_group_id)
            elif self.meta["next_batch"]:
                indices = np.concatenate([item[0] for item in self.plan[:self.meta["next_batch"]]])
                for ds, p in self.frame.iloc[indices].groupby("dataset_id"):
                    self.visited[ds].update(p.source_group_id)
            self.rates = deque(maxlen=1000)
            print(f"FULL parameters: {self.parameter_count:,}; {self.total_steps:,} updates; "
                  f"{config['epochs']} full passes; fresh pretrained base", flush=True)

        def merged_quantized(self, values, qbase, original_values):
            return cq_ste_params(values, 4)

        def save(self):
            payload = serialization.to_bytes({"lora": jax.device_get(self.lora),
                "optimizer": jax.device_get(self.opt_state), "metadata": json.dumps(self.meta)})
            checkpoint = RUN/"checkpoint.msgpack"
            if checkpoint.exists():
                replace_file(checkpoint, RUN/"checkpoint.previous.msgpack")
            atomic_bytes(checkpoint, payload)
            atomic_json(RUN/"checkpoint.json", {**self.meta, "saved_at": time.time(),
                "method": "full", "trainable_parameters": self.parameter_count,
                "bytes": len(payload), "sha256": sha256(checkpoint)})
            self.last_save = time.monotonic()
            print(f"Checkpoint: step {self.meta['step']}, epoch {self.meta['epoch']}, "
                  f"next batch {self.meta['next_batch']}", flush=True)

        def export(self):
            step = self.meta["step"]
            if step not in config["validation_steps"]:
                raise ValueError("Only the six frozen boundaries may export candidate models")
            weights, model = export_paths(step)
            status("exporting", step=step, message="Exporting exact full-parameter checkpoint")
            atomic_bytes(weights, serialization.to_bytes(jax.device_get(self.lora)))
            pending = model.with_suffix(".pending.cact")
            build(self.lora, self.cfg, self.tokenizer, str(pending))
            digest = sha256(pending)
            prior = read_json(RUN/"exports"/f"step_{step:07d}.json")
            if prior and prior["model_sha256"] != digest:
                raise ValueError("Repeated exact checkpoint export differs")
            replace_file(pending, model)
            atomic_json(RUN/"exports"/f"step_{step:07d}.json", {
                **self.meta, "complete": True, "method": "full",
                "weights": weights.name, "weights_sha256": sha256(weights),
                "model": model.name, "model_sha256": digest})

        def numerical_check(self):
            prior = read_json(RUN/"resume_verification.json")
            if prior.get("passed") and prior.get("identity") == self.identity:
                return
            status("preflight", step=self.meta["step"], message="Checking full optimizer/schedule serialization")
            batch = self.loader.batch(self.plan[0])
            one = self.step_fn(self.lora, self.opt_state, self.qbase, self.original, *batch)
            jax.block_until_ready(one)
            if not np.isfinite(float(one[2])+float(one[3])) or float(one[3]) <= 0:
                raise ValueError("Invalid diagnostic loss/gradient")
            payload = serialization.to_bytes({"lora": jax.device_get(one[0]), "optimizer": jax.device_get(one[1])})
            restored = serialization.from_bytes({"lora": one[0], "optimizer": one[1]}, payload)
            expected = self.step_fn(one[0], one[1], self.qbase, self.original, *batch)
            actual = self.step_fn(restored["lora"], restored["optimizer"], self.qbase, self.original, *batch)
            jax.block_until_ready((expected, actual))
            error = max(float(np.max(np.abs(np.asarray(a)-np.asarray(b))))
                        for a, b in zip(jax.tree.leaves(expected[:2]), jax.tree.leaves(actual[:2])))
            if error > 1e-6:
                raise ValueError("Full optimizer next-update equivalence failed")
            atomic_json(RUN/"resume_verification.json", {"passed": True, "identity": self.identity,
                "max_next_update_difference": error, "optimizer_and_schedule_restored": True,
                "diagnostic_updates_discarded": True, "trainable_parameters": self.parameter_count})

        def preflight(self):
            prior = read_json(RUN/"preflight.json")
            rows = prior.get("shapes", []) if prior.get("identity") == self.identity else []
            done = {tuple(r["shape"]) for r in rows}
            groups = {}
            for item in self.plan:
                key = tuple(item[1:])
                if key not in groups or len(item[0]) == item[3]:
                    groups[key] = item
            for key, item in sorted(groups.items()):
                if paused() or original.STOP:
                    return False
                status("preflight", step=self.meta["step"], completed_shapes=len(rows),
                       total_shapes=len(groups), message=f"Verifying/warming full-training GPU shape {key}")
                start = time.perf_counter()
                result = self.step_fn(self.lora, self.opt_state, self.qbase, self.original, *self.loader.batch(item))
                jax.block_until_ready(result)
                if not np.isfinite(float(result[2])+float(result[3])):
                    raise ValueError("Nonfinite preflight")
                if key not in done:
                    rows.append({"shape": list(key), "seconds": time.perf_counter()-start})
                del result
                atomic_json(RUN/"preflight.json", {"identity": self.identity, "complete": False,
                    "shapes": rows, "method": "full", "diagnostic_updates_discarded": True})
            atomic_json(RUN/"preflight.json", {"identity": self.identity, "complete": True,
                "shapes": rows, "method": "full", "diagnostic_updates_discarded": True})
            return True

        def run_block(self):
            initialization = read_json(RUN/"initialization_verification.json")
            if not initialization.get("passed"):
                if self.meta["step"] != 0:
                    raise ValueError("Missing initialization evidence after updates")
                error = max(float(np.max(np.abs(np.asarray(a)-np.asarray(b))))
                            for a, b in zip(jax.tree.leaves(self.lora), jax.tree.leaves(self.params)))
                if error != 0:
                    raise ValueError("Full run must start from the exact pretrained values")
                status("exporting", step=0, message="Exporting distinct fresh-base zero-update model")
                model = RUN/"whistle.base_zero.cact"
                pending = model.with_suffix(".pending.cact")
                build(self.lora, self.cfg, self.tokenizer, str(pending))
                replace_file(pending, model)
                self.save()
                atomic_json(RUN/"initialization_verification.json", {
                    "passed": True, "identity": self.identity, "method": "full",
                    "trainable_parameters": self.parameter_count, "all_parameters_trainable": True,
                    "exact_pretrained_values_max_difference": error,
                    "base_sha256": sha256(BASE/"assets/whistle.safetensors"),
                    "zero_update_native_sha256": sha256(model), "zero_update_native_model": model.name,
                    "fresh_optimizer": True, "step": 0, "initial_comparator_unchanged": True})
            self.numerical_check()
            if not self.preflight():
                status("paused", message="Preflight paused; verified shapes retained")
                return 75
            if args.initialize:
                status("initialized", step=self.meta["step"], message="Full-parameter initialization and exact resume verified")
                return 0
            target = args.target
            if target not in config["validation_steps"] or target < self.meta["step"]:
                raise ValueError("Target must be a frozen future boundary")
            n = config["batches_per_epoch"]
            while self.meta["step"] < target:
                epoch, begin = self.meta["epoch"], self.meta["next_batch"]
                if epoch >= config["epochs"]:
                    raise ValueError("Training would exceed three passes")
                self.plan = plan_batches(self.frame, epoch)
                if len(self.plan) != n:
                    raise ValueError("Epoch batch count changed")
                future = self.prefetch.submit(self.loader.batch, self.plan[begin])
                for index in range(begin, n):
                    if original.STOP or paused():
                        self.save()
                        status("paused", step=self.meta["step"], message="Paused at exact full-training optimizer state")
                        return 75
                    wall_start = time.perf_counter()
                    batch = future.result()
                    future = (self.prefetch.submit(self.loader.batch, self.plan[index+1])
                              if index+1 < n and self.meta["step"]+1 < target else None)
                    start = time.perf_counter()
                    result = self.step_fn(self.lora, self.opt_state, self.qbase, self.original, *batch)
                    jax.block_until_ready(result)
                    active = time.perf_counter()-start
                    loss, norm = float(result[2]), float(result[3])
                    if not np.isfinite(loss+norm):
                        raise FloatingPointError("Nonfinite update; saved checkpoint retained")
                    self.lora, self.opt_state = result[:2]
                    chosen = self.frame.iloc[self.plan[index][0]]
                    self.meta["step"] += 1
                    self.meta["next_batch"] = index+1
                    self.meta["active_seconds"] += active
                    self.meta["processed_records"] += len(chosen)
                    self.meta["processed_audio_seconds"] += float((chosen.end_sec-chosen.start_sec).sum())
                    for ds, p in chosen.groupby("dataset_id"):
                        self.visited[ds].update(p.source_group_id)
                        self.meta["dataset_records"][ds] = self.meta["dataset_records"].get(ds, 0)+len(p)
                    self.meta["distinct_sources"] = {ds: len(v) for ds, v in self.visited.items()}
                    if index+1 == n:
                        self.meta["epoch"], self.meta["next_batch"] = epoch+1, 0
                    wall = time.perf_counter()-wall_start
                    self.meta["training_wall_seconds"] += wall
                    self.rates.append(wall)
                    if self.meta["step"] == 1 or self.meta["step"] % 50 == 0:
                        remaining_steps = self.total_steps-self.meta["step"]
                        row = {**self.meta, "loss": loss, "gradient_norm": norm,
                            "method": "full", "trainable_parameters": self.parameter_count,
                            "learning_rate": float(self.schedule(self.meta["step"])),
                            "optimizer_remaining_seconds": self.meta["active_seconds"]/self.meta["step"]*remaining_steps,
                            "training_remaining_seconds": sum(self.rates)/len(self.rates)*remaining_steps,
                            "eta_excludes": "Future native scoring, exports, compilation, checkpoint writes and pauses",
                            "total_steps": self.total_steps, "planned_passes": 3}
                        status("training", training_launched=True, message="Full fine-tuning on all qualified training views", **row)
                        with (RUN/"history.jsonl").open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps(row, allow_nan=False)+"\n")
                    if time.monotonic()-self.last_save >= config["checkpoint_seconds"]:
                        self.save()
                    if self.meta["step"] >= target:
                        break
            self.meta["training_cap_reached"] = self.meta["step"] == self.total_steps
            if self.meta["training_cap_reached"]:
                expected = {ds: len(p)*3 for ds, p in self.frame.groupby("dataset_id")}
                if self.meta["dataset_records"] != expected:
                    raise ValueError("Completed exposure does not equal all rows times three")
            self.save()
            self.export()
            status("block_complete", step=self.meta["step"], message="Full-training checkpoint saved; native validation follows")
            return 0

    training = None
    try:
        training = FullTraining()
        return training.run_block()
    finally:
        if training is not None:
            training.loader.close()
            training.prefetch.shutdown(wait=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        status("failed", message=str(error), traceback=traceback.format_exc())
        raise
