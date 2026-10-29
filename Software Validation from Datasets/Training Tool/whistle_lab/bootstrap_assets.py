"""Download public pinned assets once. No datasets are uploaded."""
import json
from pathlib import Path
import shutil
import zipfile
from common import ASSETS, CONFIG, REPO, RUN, atomic_json, environment, sha256, status

ENGINE_REVISION = "d6c7d6a2e9655505e0f8e23339356dd1705900eb"
ENGINE_WHEEL = "python/cactus_needle-3.3.3-py3-none-manylinux2014_x86_64.whl"


def main():
    environment(offline=False)
    from huggingface_hub import hf_hub_download
    import needle
    from needle.model.tokenizer import TOKENIZER_DIR
    ASSETS.mkdir(parents=True, exist_ok=True)
    status("downloading", message="Downloading public model, tokenizer and local inference runtime")
    versions = {"package": needle.__version__, "whistle_revision": CONFIG["whistle_revision"]}
    for name in ("checkpoints/whistle.safetensors", "whistle.cact", "LICENSE", "README.md", "config.json"):
        source = hf_hub_download("Cactus-Compute/whistle", name, revision=CONFIG["whistle_revision"])
        target = ASSETS / Path(name).name
        shutil.copyfile(source, target)
    needle_revision = ENGINE_REVISION
    versions["needle3_revision"] = needle_revision
    for name in ("tokenizer.model", "tokenizer.vocab"):
        source = hf_hub_download("Cactus-Compute/needle3", "tokenizer/" + name, revision=needle_revision)
        shutil.copyfile(source, ASSETS / name)
        shutil.copyfile(source, Path(TOKENIZER_DIR) / name)
    source = hf_hub_download("Cactus-Compute/needle3", "LICENSE", revision=needle_revision)
    shutil.copyfile(source, ASSETS / "needle-engine-LICENSE")
    shutil.copyfile(REPO / "training/toolchains/needle-whistle/LICENSE", ASSETS / "needle-python-LICENSE")
    wheel = hf_hub_download("Cactus-Compute/needle3", ENGINE_WHEEL, revision=needle_revision)
    with zipfile.ZipFile(wheel) as archive:
        (ASSETS / "libneedle.so").write_bytes(archive.read("needle/libneedle3.so"))
    versions["runtime"] = str(ASSETS / "libneedle.so")
    versions["runtime_wheel"] = ENGINE_WHEEL
    versions["needle_python_source_commit"] = "b4fc11b04f1852888d375c8c6dfbaca44572d014"
    versions["files"] = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in ASSETS.iterdir() if p.is_file()}
    atomic_json(RUN / "assets.json", versions)
    print(json.dumps(versions, indent=2))


if __name__ == "__main__":
    main()
