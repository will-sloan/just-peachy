"""Resumable CUDA LoRA/QAT training using Cactus's published Whistle architecture.

The optimizer loop, streaming loader and checkpoint lifecycle are local additions.
Upstream mathematical model, LoRA targets and export format remain authoritative.
"""
from __future__ import annotations
import argparse
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import os
import signal
import time
import traceback

from common import ASSETS, CONFIG, CONFIG_DIGEST, RUN, atomic_bytes, atomic_json, environment, read_json, replace_file, sha256, status
environment()
os.environ["JAX_PLATFORMS"] = "cuda"
import numpy as np
import pandas as pd
import jax
import jax.numpy as jnp
import optax
from flax import serialization
from flax.traverse_util import flatten_dict, unflatten_dict
from needle.model.finetune import init_lora, lora_target_paths
from needle.model.whistle import Whistle
from needle.model.whistle_finetune import WhistleTokenizer, build, load_base, tuned_params
from needle.model.checkpoints import write_adapter
from needle.model.quantize import configure_deploy, cq_ste, cq_ste_params
from data import BatchLoader, plan_batches

STOP = False


def stop_signal(*_):
    global STOP
    STOP = True


signal.signal(signal.SIGTERM, stop_signal)
signal.signal(signal.SIGINT, stop_signal)


class Training:
    def __init__(self):
        if jax.default_backend() != "gpu":
            raise RuntimeError(f"CUDA is required; available: {jax.devices()}")
        status("initializing", message="Loading Whistle on RTX 3080; preparing quantization")
        self.frame = pd.read_parquet(RUN / "train.parquet")
        self.plan = plan_batches(self.frame, 0)
        self.total_steps = len(self.plan) * CONFIG["epochs"]
        self.mean_batch_size = len(self.frame) / len(self.plan)
        self.loader = BatchLoader(self.frame, CONFIG["loader_workers"])
        self.prefetch = ThreadPoolExecutor(max_workers=1)
        self.params, original_cfg = load_base(str(ASSETS / "whistle.safetensors"))
        self.cfg = replace(original_cfg, dtype=CONFIG["dtype"], flash=True, remat=True)
        self.tokenizer = WhistleTokenizer(languages=self.cfg.languages)
        self.params = jax.device_put(jax.tree.map(lambda a: np.asarray(a, np.float32), self.params))
        configure_deploy(act_bits=8, kv_bits=8)
        self.model = Whistle(self.cfg)
        paths = lora_target_paths(self.params)
        self.scale = CONFIG["lora_alpha"] / CONFIG["lora_rank"]
        self.lora = init_lora(self.params, paths, CONFIG["lora_rank"], jax.random.PRNGKey(CONFIG["seed"]))
        self.original = {p: flatten_dict(self.params)[p] for p in paths}
        # Use the vendor's complete merge/quantization path. Moving its frozen
        # leaves to a separate graph changed codebook decisions near boundaries.
        self.qbase = self.params
        warmup = min(1000, max(1, self.total_steps // 20))
        schedule = optax.warmup_cosine_decay_schedule(0., CONFIG["learning_rate"], warmup, self.total_steps, end_value=CONFIG["learning_rate"] * 0.05)
        self.optimizer = optax.chain(optax.clip_by_global_norm(1.), optax.adamw(schedule, weight_decay=0.01))
        self.opt_state = self.optimizer.init(self.lora)
        self.schedule = schedule
        self.meta = {"epoch": 0, "next_batch": 0, "step": 0, "processed_records": 0, "processed_audio_seconds": 0., "active_seconds": 0., "dataset_records": {}, "best_validation_loss": None}
        audit = read_json(RUN / "data_audit.json")
        headers = read_json(RUN / "audio_header_audit.json")
        if headers.get("invalid_segments", -1) != 0 or headers.get("manifest_sha256") != {split: audit["splits"][split]["sha256"] for split in ("train", "dev")}:
            raise ValueError("Every selected segment must pass the audio-header audit before training")
        if sha256(RUN / "train.parquet") != audit["splits"]["train"]["sha256"]:
            raise ValueError("Training manifest changed after the audit")
        self.identity = hashlib.sha256(json.dumps({"config": CONFIG, "data": audit["splits"]["train"]["sha256"], "base": read_json(RUN / "assets.json")["files"]["whistle.safetensors"]["sha256"]}, sort_keys=True).encode()).hexdigest()
        self.meta["identity"] = self.identity
        self.step_fn = jax.jit(self._step)
        self.eval_fn = jax.jit(self._loss)
        self.last_save = time.monotonic()
        self.segment_start = time.monotonic()
        self.base_elapsed = 0.
        self.rate_samples = deque(maxlen=1000)
        print(f"CUDA: {jax.devices()}; {len(paths)} LoRA groups; {sum(x.size for x in jax.tree.leaves(self.lora)):,} trainable parameters; {self.total_steps:,} optimizer steps", flush=True)

    def merged_quantized(self, lora, qbase, original):
        return cq_ste_params(tuned_params(qbase, self.cfg, self.tokenizer, lora, self.scale, None), 4)

    def _loss(self, lora, qbase, original, wav, lengths, tokens, weights):
        params = self.merged_quantized(lora, qbase, original)
        logits = self.model.apply({"params": params}, wav, lengths, tokens[:, :-1], quant=True)
        targets = tokens[:, 1:]
        mask = targets != self.cfg.pad
        cross_entropy = optax.softmax_cross_entropy_with_integer_labels(logits, targets)
        per_clip = (cross_entropy * mask).sum(-1) / jnp.maximum(mask.sum(-1), 1)
        return (per_clip * weights).sum() / jnp.maximum((weights > 0).sum(), 1)

    def _step(self, lora, opt_state, qbase, original, *batch):
        def objective(adapters):
            per_clip_loss = self._loss(adapters, qbase, original, *batch)
            # Uniformly shuffled variable-size batches must not give a long
            # one-clip batch more total influence per row than a 16-clip batch.
            scale = (batch[-1] > 0).sum() / self.mean_batch_size
            return per_clip_loss * scale, per_clip_loss
        (_, loss), grads = jax.value_and_grad(objective, has_aux=True)(lora)
        updates, state = self.optimizer.update(grads, opt_state, lora)
        return optax.apply_updates(lora, updates), state, loss, optax.global_norm(grads)

    def save_adapter(self, name):
        path = RUN / name
        temporary = path.with_name(path.stem + ".tmp.safetensors")
        write_adapter(str(temporary), {"lora": {"/".join(p): {k: np.asarray(v) for k, v in value.items()} for p, value in self.lora.items()}, "rows": np.zeros((0, self.cfg.dim), np.float32), "scale": float(self.scale), "base": str(ASSETS / "whistle.safetensors"), "rank": CONFIG["lora_rank"], "seed": CONFIG["seed"], "pieces": [], "languages": list(self.cfg.languages)})
        replace_file(temporary, path)

    def save(self):
        self.meta["active_seconds"] = self.base_elapsed + time.monotonic() - self.segment_start
        payload = serialization.to_bytes({"lora": jax.device_get(self.lora), "optimizer": jax.device_get(self.opt_state), "metadata": json.dumps(self.meta)})
        checkpoint = RUN / "checkpoint.msgpack"
        if checkpoint.exists():
            # Keep one earlier complete checkpoint if the newest file is damaged.
            replace_file(checkpoint, RUN / "checkpoint.previous.msgpack")
        atomic_bytes(checkpoint, payload)
        self.save_adapter("adapter.latest.safetensors")
        atomic_json(RUN / "checkpoint.json", {**self.meta, "saved_at": time.time(), "bytes": len(payload), "sha256": sha256(checkpoint)})
        self.last_save = time.monotonic()
        print(f"Checkpoint saved: step {self.meta['step']}, epoch {self.meta['epoch']}, next batch {self.meta['next_batch']}", flush=True)

    def restore(self):
        paths = [RUN / "checkpoint.msgpack", RUN / "checkpoint.previous.msgpack"]
        for path in paths:
            if not path.exists():
                continue
            try:
                saved = serialization.from_bytes({"lora": self.lora, "optimizer": self.opt_state, "metadata": ""}, path.read_bytes())
                meta = json.loads(saved["metadata"])
            except Exception as error:
                print(f"Cannot load {path.name}: {error}", flush=True)
                continue
            if meta["identity"] != self.identity:
                raise ValueError("Configuration, training manifest or base identity changed; refusing incompatible resume")
            self.lora = jax.device_put(saved["lora"])
            self.opt_state = jax.device_put(saved["optimizer"])
            self.meta = meta
            self.base_elapsed = meta["active_seconds"]
            self.segment_start = time.monotonic()
            print(f"Resuming exact optimizer/scheduler state from step {meta['step']}", flush=True)
            return True
        if any(p.exists() for p in paths):
            raise RuntimeError("Both saved checkpoints are unreadable; refusing to start over")
        return False

    def benchmark(self):
        groups = {}
        load_examples = {}
        counts = Counter()
        for item in self.plan:
            key = tuple(item[1:])
            counts[key] += 1
            if len(load_examples.setdefault(key, [])) < 4:
                load_examples[key].append(item)
            if len(item[0]) == item[3] or key not in groups:
                groups[key] = item
        status("benchmarking", message="Checking vendor QAT and exact optimizer continuation")
        self.verify_numerics(next(iter(groups.values())))
        previous = read_json(RUN / "benchmark.json")
        results = previous.get("shapes", []) if previous.get("identity") == self.identity else []
        completed = {(r["audio_seconds"], r["tokens"], r["batch_size"]) for r in results}
        # Most frequent shapes first; also exercise every long-input shape.
        for number, key in enumerate(sorted(groups, key=lambda k: -counts[k]), 1):
            if STOP or read_json(RUN / "control.json").get("paused", False):
                status("paused", message="Benchmark paused; completed measurements retained")
                return False
            if key in completed:
                continue
            status("benchmarking", message=f"RTX 3080: testing bucket {number}/{len(groups)} ({key[0]} s, {key[2]} clips)", benchmark_done=number - 1, benchmark_total=len(groups))
            start = time.perf_counter()
            batch = self.loader.batch(groups[key])
            initial_load_seconds = time.perf_counter() - start
            timings = []
            for iteration in range(3):
                start = time.perf_counter()
                result = self.step_fn(self.lora, self.opt_state, self.qbase, self.original, *batch)
                jax.block_until_ready(result)
                loss, norm = float(result[2]), float(result[3])
                if not np.isfinite(loss + norm):
                    raise FloatingPointError(f"Nonfinite benchmark in {key}")
                if iteration:
                    timings.append(time.perf_counter() - start)
                else:
                    compile_seconds = time.perf_counter() - start
            loads = []
            for example in load_examples[key]:
                start = time.perf_counter()
                self.loader.batch(example)
                loads.append(time.perf_counter() - start)
            load_seconds = float(np.median(loads))
            row = {"audio_seconds": key[0], "tokens": key[1], "batch_size": key[2], "batches_per_epoch": counts[key], "compute_seconds": float(np.median(timings)), "load_seconds": load_seconds, "initial_load_seconds": initial_load_seconds, "first_call_seconds": compile_seconds, "loss": loss, "gradient_norm": norm}
            results.append(row)
            print(json.dumps(row), flush=True)
            seconds_per_epoch = sum(r["batches_per_epoch"] * max(r["compute_seconds"], r["load_seconds"]) for r in results)
            atomic_json(RUN / "benchmark.json", {"identity": self.identity, "config_digest": CONFIG_DIGEST, "complete": number == len(groups), "device": str(jax.devices()[0]), "shapes": results, "estimated_epoch_hours": seconds_per_epoch / 3600, "estimated_training_hours": seconds_per_epoch * CONFIG["epochs"] / 3600, "uncertainty_fraction": 0.35, "note": "Steady-state optimizer + median of independent source batches with loader prefetch; excludes initial compilation, pauses, final scoring; estimate is partial until all shapes pass"})
        return True

    def verify_numerics(self, first):
        # Actual checkpoint round trip and exact next-step equivalence.
        original_step = self.meta["step"]
        batch = self.loader.batch(first)
        one = self.step_fn(self.lora, self.opt_state, self.qbase, self.original, *batch)
        one = self.step_fn(one[0], one[1], self.qbase, self.original, *batch)
        # Verify the exact vendor merge/quantization path after nonzero updates.
        reference = jax.jit(lambda lora, params: cq_ste_params(tuned_params(params, self.cfg, self.tokenizer, lora, self.scale, None), 4))(one[0], self.params)
        optimized = jax.jit(self.merged_quantized)(one[0], self.qbase, self.original)
        left, right = flatten_dict(reference), flatten_dict(optimized)
        quant_differences = [{"parameter": "/".join(path), "max_difference": float(np.max(np.abs(np.asarray(value) - np.asarray(right[path]))))} for path, value in left.items()]
        quant_difference = max(row["max_difference"] for row in quant_differences)
        atomic_json(RUN / "quantization_verification.json", {"max_difference": quant_difference, "parameters": sorted(quant_differences, key=lambda r: -r["max_difference"]), "compilation": "both paths JIT-compiled; includes a nonzero adapter update"})
        if quant_difference > 1e-5:
            raise ValueError(f"QAT differs from upstream: {quant_difference}")
        payload = serialization.to_bytes({"lora": jax.device_get(one[0]), "optimizer": jax.device_get(one[1]), "metadata": "test"})
        restored = serialization.from_bytes({"lora": one[0], "optimizer": one[1], "metadata": ""}, payload)
        expected = self.step_fn(one[0], one[1], self.qbase, self.original, *batch)
        actual = self.step_fn(restored["lora"], restored["optimizer"], self.qbase, self.original, *batch)
        differences = [float(np.max(np.abs(np.asarray(a) - np.asarray(b)))) for a, b in zip(jax.tree.leaves(expected[0]), jax.tree.leaves(actual[0]))]
        if max(differences) > 1e-6:
            raise ValueError("Optimizer checkpoint continuation test failed")
        atomic_json(RUN / "resume_verification.json", {"passed": True, "identity": self.identity, "max_parameter_difference": max(differences), "qat_difference_from_upstream": quant_difference, "quantization_tolerance": 1e-5, "optimizer_and_schedule_restored": True, "benchmark_weights_discarded": True})
        assert self.meta["step"] == original_step

    def validate(self):
        frame = pd.read_parquet(RUN / "validation_monitor.parquet")
        loader = BatchLoader(frame, CONFIG["loader_workers"])
        summaries = {}
        for dataset, part in frame.groupby("dataset_id"):
            part = part.reset_index(drop=True)
            local_loader = BatchLoader(part, CONFIG["loader_workers"])
            summed = 0.
            for item in plan_batches(part, 0):
                value = float(self.eval_fn(self.lora, self.qbase, self.original, *local_loader.batch(item)))
                summed += value * len(item[0])
            local_loader.close()
            summaries[dataset] = summed / len(part)
        loader.close()
        mean = sum(summaries.values()) / len(summaries)
        if not np.isfinite(mean):
            raise FloatingPointError("Nonfinite validation loss")
        best = self.meta["best_validation_loss"]
        if best is None or mean < best:
            self.meta["best_validation_loss"] = mean
            self.save_adapter("adapter.best.safetensors")
        self.record(validation_loss=mean, validation_by_dataset=summaries)
        print(f"Validation: {summaries}, macro loss {mean:.4f}", flush=True)

    def record(self, **values):
        elapsed = self.base_elapsed + time.monotonic() - self.segment_start
        rows = self.meta["processed_records"]
        total = len(self.frame) * CONFIG["epochs"]
        benchmark = read_json(RUN / "benchmark.json")
        estimated = benchmark.get("estimated_training_hours", 0) * 3600
        remaining = max(0., estimated * (1 - rows / total)) if estimated else None
        eta_source = "GPU benchmark"
        if len(self.rate_samples) >= 200:
            first_time, first_rows = self.rate_samples[0]
            last_time, last_rows = self.rate_samples[-1]
            if last_time - first_time >= 120 and last_rows > first_rows:
                remaining = max(0., (total - rows) * (last_time - first_time) / (last_rows - first_rows))
                eta_source = "rolling measured training throughput"
        value = {"time": time.time(), "step": self.meta["step"], "total_steps": self.total_steps, "epoch": self.meta["epoch"], "epochs": CONFIG["epochs"], "processed_records": rows, "total_record_visits": total, "percent": 100 * rows / total, "elapsed_seconds": elapsed, "remaining_seconds": remaining, "eta_source": eta_source, "audio_hours_processed": self.meta["processed_audio_seconds"] / 3600, "dataset_records": self.meta["dataset_records"], "learning_rate": float(self.schedule(self.meta["step"])), **values}
        status("training", message="Training all selected AGE + ROBUST records", **value)
        with (RUN / "history.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, allow_nan=False) + "\n")

    def run(self):
        self.restore()
        for epoch in range(self.meta["epoch"], CONFIG["epochs"]):
            plan = plan_batches(self.frame, epoch)
            beginning = self.meta["next_batch"] if epoch == self.meta["epoch"] else 0
            self.meta["epoch"] = epoch
            future = self.prefetch.submit(self.loader.batch, plan[beginning]) if beginning < len(plan) else None
            for index in range(beginning, len(plan)):
                if STOP or read_json(RUN / "control.json").get("paused", False):
                    self.save()
                    status("paused", message="Paused safely; GPU released after checkpoint", percent=100 * self.meta["processed_records"] / (len(self.frame) * CONFIG["epochs"]))
                    return 75
                batch = future.result()
                future = self.prefetch.submit(self.loader.batch, plan[index + 1]) if index + 1 < len(plan) else None
                result = self.step_fn(self.lora, self.opt_state, self.qbase, self.original, *batch)
                loss, norm = float(result[2]), float(result[3])
                if not np.isfinite(loss + norm):
                    raise FloatingPointError(f"Nonfinite update at step {self.meta['step']}; previous checkpoint preserved")
                self.lora, self.opt_state = result[:2]
                chosen = self.frame.iloc[plan[index][0]]
                self.meta["step"] += 1
                self.meta["next_batch"] = index + 1
                self.meta["processed_records"] += len(chosen)
                self.rate_samples.append((time.monotonic(), self.meta["processed_records"]))
                self.meta["processed_audio_seconds"] += float((chosen.end_sec - chosen.start_sec).sum())
                for dataset, count in chosen.dataset_id.value_counts().items():
                    self.meta["dataset_records"][dataset] = self.meta["dataset_records"].get(dataset, 0) + int(count)
                if self.meta["step"] % 10 == 0 or self.meta["step"] == 1:
                    self.record(loss=loss, gradient_norm=norm)
                if time.monotonic() - self.last_save >= CONFIG["checkpoint_seconds"]:
                    self.save()
                if self.meta["step"] % CONFIG["validation_every_steps"] == 0:
                    self.save()
                    self.validate()
            self.meta["epoch"] = epoch + 1
            self.meta["next_batch"] = 0
            self.validate()
            self.save()
        self.save_adapter("adapter.final.safetensors")
        status("exporting", percent=100., message="All training epochs complete; exporting local model")
        merged = tuned_params(self.params, self.cfg, self.tokenizer, self.lora, self.scale, None)
        result = build(merged, self.cfg, self.tokenizer, str(RUN / "whistle.final.cact"))
        atomic_json(RUN / "export.json", result)
        # Also export the best monitored checkpoint, if distinct from the last one.
        from needle.model.checkpoints import read_adapter
        saved = read_adapter(str(RUN / "adapter.best.safetensors"))
        best = {tuple(k.split("/")): {n: jnp.asarray(v) for n, v in matrices.items()} for k, matrices in saved["lora"].items()}
        build(tuned_params(self.params, self.cfg, self.tokenizer, best, self.scale, None), self.cfg, self.tokenizer, str(RUN / "whistle.best.cact"))
        atomic_json(RUN / "model_manifest.json", {"config": CONFIG, "run_identity": self.identity, "training_manifest_sha256": read_json(RUN / "data_audit.json")["splits"]["train"]["sha256"], "base_revision": CONFIG["whistle_revision"], "completed_training": self.meta, "models": {name: {"sha256": sha256(RUN / name), "bytes": (RUN / name).stat().st_size} for name in ("whistle.final.cact", "whistle.best.cact")}, "license": "Apache-2.0 base weights and runtime; retain attribution and license texts in assets", "dataset_licenses": ["CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0"], "commercial_release_review_required": CONFIG["release_review_required"], "license_resolution": read_json(RUN / "release_review.json"), "no_training_data_uploaded": True, "telemetry_disabled": True})
        status("trained", percent=100., message="Fine-tuning complete; models exported; post-training comparison pending")
        return 0


def main():
    import fcntl
    RUN.mkdir(parents=True, exist_ok=True)
    lock = (RUN / "trainer.lock").open("a+b")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another Whistle trainer already owns this run", flush=True)
        return 73
    # Keep the descriptor alive throughout main, including all compilation.
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()
    training = Training()
    if args.benchmark:
        if not training.benchmark():
            return 75
        status("benchmarked", message="All GPU shapes and checkpoint continuation verified")
        return 0
    result = training.run()
    lock.close()
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        status("failed", message=str(error), traceback=traceback.format_exc())
        traceback.print_exc()
        raise
