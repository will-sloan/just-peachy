"""One exact-resumable warm-start block. Native scoring runs in a later process."""
from __future__ import annotations
import argparse
import json
import time
import traceback
from runtime import *


def main():
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--target", type=int, default=2000)
    args = parser.parse_args()
    if paused():
        return 75
    config = verify()
    locks = []
    for path in (BASE / "trainer.lock", FOLLOWUP / "gpu.lock", RUN / "worker.lock"):
        handle = path.open("a+b")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 73
        locks.append(handle)
    import audioio
    import train as original
    import numpy as np
    import jax
    import jax.numpy as jnp
    import optax
    from flax import serialization
    from needle.model.checkpoints import read_adapter
    from needle.model.whistle_finetune import build, tuned_params

    class Adaptation(original.Training):
        def __init__(self):
            super().__init__()
            saved = read_adapter(str(BASE / "adapter.final.safetensors"))
            values = {tuple(k.split("/")): {name: jnp.asarray(v) for name, v in matrices.items()}
                      for k, matrices in saved["lora"].items()}
            if saved["rank"] != config["lora_rank"] or saved["scale"] != self.scale or saved["pieces"]:
                raise ValueError("Parent adapter rank/scale/vocabulary mismatch")
            if list(saved["languages"]) != list(self.cfg.languages) or set(values) != set(self.lora):
                raise ValueError("Parent adapter languages or target paths differ")
            for key in values:
                if set(values[key]) != set(self.lora[key]):
                    raise ValueError("Parent adapter matrix keys differ")
                for matrix in values[key]:
                    if values[key][matrix].shape != self.lora[key][matrix].shape:
                        raise ValueError("Parent adapter matrix shape differs")
            self.lora = jax.device_put(values)
            self.total_steps = min(config["max_steps"], len(self.plan))
            self.schedule = optax.warmup_cosine_decay_schedule(
                0., config["learning_rate"], config["warmup_steps"], config["max_steps"],
                end_value=config["end_learning_rate"])
            self.optimizer = optax.chain(optax.clip_by_global_norm(1.),
                                         optax.adamw(self.schedule, weight_decay=.01))
            self.opt_state = self.optimizer.init(self.lora)
            self.step_fn = jax.jit(self._step)
            restored = self.restore()
            self.visited = {ds: set() for ds in self.frame.dataset_id.unique()}
            # Reconstruct exposure from the deterministic saved position, keeping
            # large ID sets out of the small checkpoint/status files.
            indices = [int(i) for item in self.plan[:self.meta["next_batch"]] for i in item[0]]
            if indices:
                for ds, p in self.frame.iloc[indices].groupby("dataset_id"):
                    self.visited[ds].update(p.source_group_id)
            self.meta.setdefault("distinct_sources", {})
            if not restored and (RUN / "initialization_verification.json").exists() and (RUN / "checkpoint.json").exists():
                raise RuntimeError("Saved experiment lost its optimizer; refusing a fresh restart")

        def save(self):
            payload = serialization.to_bytes({"lora": jax.device_get(self.lora),
                "optimizer": jax.device_get(self.opt_state), "metadata": json.dumps(self.meta)})
            checkpoint = RUN / "checkpoint.msgpack"
            if checkpoint.exists():
                replace_file(checkpoint, RUN / "checkpoint.previous.msgpack")
            atomic_bytes(checkpoint, payload)
            self.save_adapter("adapter.latest.safetensors")
            atomic_json(RUN / "checkpoint.json", {**self.meta, "saved_at": time.time(),
                                                 "bytes": len(payload), "sha256": sha256(checkpoint)})
            self.last_save = time.monotonic()
            print(f"Checkpoint: step {self.meta['step']}, active {self.meta['active_seconds']:.1f}s", flush=True)

        def export(self):
            adapter, model = export_paths(self.meta["step"])
            self.save_adapter(adapter.name)
            temporary = model.with_name(model.stem + ".pending.cact")
            status("exporting", step=self.meta["step"], message="Exporting the exact checkpoint for native validation")
            build(tuned_params(self.params, self.cfg, self.tokenizer, self.lora, self.scale, None),
                  self.cfg, self.tokenizer, str(temporary))
            replace_file(temporary, model)
            receipt = {**self.meta, "adapter_sha256": sha256(adapter), "model_sha256": sha256(model),
                       "adapter": adapter.name, "model": model.name, "complete": True}
            atomic_json(RUN / "exports" / f"step_{self.meta['step']:05d}.json", receipt)
            return receipt

        def numerical_check(self):
            prior = read_json(RUN / "resume_verification.json")
            if prior.get("passed") and prior.get("identity") == self.identity:
                return
            item = self.plan[0]
            batch = self.loader.batch(item)
            one = self.step_fn(self.lora, self.opt_state, self.qbase, self.original, *batch)
            jax.block_until_ready(one)
            if not np.isfinite(float(one[2]) + float(one[3])) or float(one[3]) <= 0:
                raise ValueError("Invalid diagnostic loss/gradient")
            payload = serialization.to_bytes({"lora": jax.device_get(one[0]), "optimizer": jax.device_get(one[1])})
            restored = serialization.from_bytes({"lora": one[0], "optimizer": one[1]}, payload)
            expected = self.step_fn(one[0], one[1], self.qbase, self.original, *batch)
            actual = self.step_fn(restored["lora"], restored["optimizer"], self.qbase, self.original, *batch)
            jax.block_until_ready((expected, actual))
            error = max(float(np.max(np.abs(np.asarray(a) - np.asarray(b))))
                        for a, b in zip(jax.tree.leaves(expected[:2]), jax.tree.leaves(actual[:2])))
            if error > 1e-6:
                raise ValueError("Optimizer/schedule next-step equivalence failed")
            atomic_json(RUN / "resume_verification.json", {"passed": True, "identity": self.identity,
                "max_next_update_difference": error, "optimizer_and_schedule_restored": True,
                "diagnostic_updates_discarded": True})

        def preflight(self):
            prior = read_json(RUN / "preflight.json")
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
                status("preflight", step=self.meta["step"], completed_shapes=len(rows), total_shapes=len(groups),
                       message=f"{'Warming verified' if key in done else 'Verifying'} GPU shape {key}")
                start = time.perf_counter()
                result = self.step_fn(self.lora, self.opt_state, self.qbase, self.original, *self.loader.batch(item))
                jax.block_until_ready(result)
                if not np.isfinite(float(result[2]) + float(result[3])):
                    raise ValueError("Nonfinite preflight result")
                if key not in done:
                    rows.append({"shape": list(key), "seconds": time.perf_counter() - start})
                del result
                atomic_json(RUN / "preflight.json", {"identity": self.identity, "complete": False,
                                                     "shapes": rows, "diagnostic_updates_discarded": True})
            atomic_json(RUN / "preflight.json", {"identity": self.identity, "complete": True,
                                                 "shapes": rows, "diagnostic_updates_discarded": True})
            return True

        def run_block(self):
            initialization = read_json(RUN / "initialization_verification.json")
            if not initialization.get("passed"):
                if self.meta["step"] != 0:
                    raise ValueError("Missing step-zero equivalence evidence")
                receipt = self.export()
                expected = read_json(RUN / "proposal_snapshot.json")["proposal"]["initialization"]["reference_export_sha256"]
                if receipt["model_sha256"] != expected:
                    raise ValueError("Zero-update export is not byte-identical to the preserved initial model")
                atomic_json(RUN / "initialization_verification.json", {
                    "passed": True, "identity": self.identity, "zero_update_export_sha256": expected,
                    "native_export_byte_identical": True, "fresh_optimizer": True,
                    "parent_adapter_sha256": config["initial_adapter_sha256"], "step": 0})
                self.save()
            self.numerical_check()
            if not self.preflight():
                status("paused", message="Preflight paused; verified shapes retained")
                return 75
            if args.initialize:
                status("initialized", step=self.meta["step"], message="Warm start, zero-update export and exact resume verified")
                return 0
            target = min(args.target, self.total_steps)
            if target <= 0 or target > 10000:
                raise ValueError("Invalid target")
            begin = self.meta["next_batch"]
            future = self.prefetch.submit(self.loader.batch, self.plan[begin]) if begin < len(self.plan) and self.meta["step"] < target else None
            for index in range(begin, len(self.plan)):
                if self.meta["step"] >= target or self.meta["active_seconds"] >= config["max_active_seconds"]:
                    break
                if original.STOP or paused():
                    self.save()
                    status("paused", step=self.meta["step"], message="Paused at exact saved optimizer state")
                    return 75
                batch = future.result()
                future = self.prefetch.submit(self.loader.batch, self.plan[index+1]) if index+1 < len(self.plan) and self.meta["step"]+1 < target else None
                start = time.perf_counter()
                result = self.step_fn(self.lora, self.opt_state, self.qbase, self.original, *batch)
                loss, norm = float(result[2]), float(result[3])
                active = time.perf_counter() - start
                if not np.isfinite(loss + norm):
                    raise FloatingPointError("Nonfinite update; saved checkpoint retained")
                self.lora, self.opt_state = result[:2]
                chosen = self.frame.iloc[self.plan[index][0]]
                self.meta["step"] += 1
                self.meta["next_batch"] = index + 1
                self.meta["active_seconds"] += active
                self.meta["processed_records"] += len(chosen)
                self.meta["processed_audio_seconds"] += float((chosen.end_sec-chosen.start_sec).sum())
                for ds, p in chosen.groupby("dataset_id"):
                    self.visited[ds].update(p.source_group_id)
                    self.meta["dataset_records"][ds] = self.meta["dataset_records"].get(ds, 0) + len(p)
                self.meta["distinct_sources"] = {ds: len(v) for ds, v in self.visited.items()}
                if self.meta["step"] == 1 or self.meta["step"] % 10 == 0:
                    remaining = min(max(0., 3600-self.meta["active_seconds"]),
                                    self.meta["active_seconds"]/self.meta["step"]*(self.total_steps-self.meta["step"]))
                    row = {**self.meta, "loss": loss, "gradient_norm": norm,
                           "learning_rate": float(self.schedule(self.meta["step"])), "remaining_seconds": remaining}
                    status("training", training_launched=True, message="Initial model adaptation with mixed-domain clean replay", **row)
                    with (RUN / "history.jsonl").open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(row, allow_nan=False) + "\n")
                if time.monotonic() - self.last_save >= config["checkpoint_seconds"]:
                    self.save()
            self.meta["training_cap_reached"] = self.meta["step"] >= self.total_steps or self.meta["active_seconds"] >= 3600 or self.meta["next_batch"] >= len(self.plan)
            self.save()
            self.export()
            status("block_complete", step=self.meta["step"], message="Checkpoint saved; native validation follows")
            return 0

    training = None
    try:
        training = Adaptation()
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
