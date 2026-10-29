"""Export the latest saved adapter on CPU and smoke-test the local native runtime.

This does not change training, optimizer state, or final/best output models.
See README.md for the WSL command and output descriptions.
"""
import os
import time
from common import ASSETS, RUN, atomic_json, environment, sha256

environment()
os.environ["JAX_PLATFORMS"] = "cpu"


def main():
    import jax.numpy as jnp
    import numpy as np
    import pandas as pd
    import needle
    from needle.model.checkpoints import read_adapter
    from needle.model.quantize import configure_deploy
    from needle.model.whistle_finetune import WhistleTokenizer, load_base, tuned_params, build
    from data import load_audio

    adapter_path = RUN / "adapter.latest.safetensors"
    adapter = read_adapter(str(adapter_path))
    base, cfg = load_base(str(ASSETS / "whistle.safetensors"))
    tokenizer = WhistleTokenizer(languages=adapter["languages"])
    lora = {tuple(k.split("/")): {name: jnp.asarray(matrix) for name, matrix in matrices.items()} for k, matrices in adapter["lora"].items()}
    configure_deploy(act_bits=8, kv_bits=8)
    output = RUN / "whistle.export_smoke.cact"
    built = build(tuned_params(base, cfg, tokenizer, lora, adapter["scale"], adapter.get("rows")), cfg, tokenizer, str(output))
    frame = pd.read_parquet(RUN / "evaluation.parquet")
    row = frame[frame.dataset_id.eq("ami")].iloc[0].to_dict()
    audio = load_audio(row)
    start = time.perf_counter()
    model = needle.Whistle(weights=str(output))
    prediction = model.transcribe(audio, language="en")
    if not isinstance(prediction.get("text"), str):
        raise ValueError("Exported model did not return a text prediction")
    embedding = np.asarray(model.embed(audio), np.float32)
    if not embedding.size or not np.isfinite(embedding).all():
        raise ValueError("Exported model produced invalid acoustic embeddings")
    result = {"passed": True, "adapter_sha256": sha256(adapter_path), "export_sha256": sha256(output), "export_bytes": output.stat().st_size, "build": built, "text": prediction["text"], "wall_seconds_including_load": time.perf_counter() - start, "audio_seconds": len(audio) / 16000, "embedding_values": int(embedding.size), "quality_evaluation": False, "training_checkpoint_unchanged": True}
    atomic_json(RUN / "export_verification.json", result)
    print(result, flush=True)


if __name__ == "__main__":
    main()
