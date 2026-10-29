"""Local paths and atomic state for the Whistle experiment; see README.md."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
RUN = REPO / "training" / CONFIG["run_name"]
ASSETS = RUN / "assets"
CONFIG_DIGEST = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode()).hexdigest()


def replace_file(source, destination, retry_seconds=5.):
    """Allow short Windows sharing locks without weakening atomic replacement."""
    deadline = time.monotonic() + retry_seconds
    delay = .01
    while True:
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise
            time.sleep(min(delay, remaining))
            delay = min(delay * 2, .25)


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        replace_file(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except PermissionError:
            # A scanner may still hold our private temporary file. Preserve the
            # original exception; never remove or rewrite the destination here.
            pass


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2, allow_nan=False, default=str) + "\n").encode())


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {} if default is None else default


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def status(phase, **values):
    previous = read_json(RUN / "status.json")
    if phase != "failed":
        previous.pop("traceback", None)
    previous.update(phase=phase, updated_at=time.time(), **values)
    try:
        atomic_json(RUN / "status.json", previous)
    except PermissionError as error:
        # The next status update can retry. A progress-display sharing lock must
        # not kill GPU work; checkpoint writes still propagate persistent errors.
        print(f"Progress update deferred after file sharing lock: {error}", flush=True)


def environment(offline=True):
    os.environ["NEEDLE_TELEMETRY"] = "0"
    os.environ["DO_NOT_TRACK"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    if offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
    os.environ.setdefault("JAX_COMPILATION_CACHE_DIR", str(Path.home() / ".cache/whistle-jax"))
    os.environ.setdefault("JAX_PERSISTENT_CACHE_MIN_COMPILE_TIME_SECS", "1")
    os.environ["JAX_DEFAULT_MATMUL_PRECISION"] = CONFIG["matmul_precision"]
    if (ASSETS / "libneedle.so").exists():
        os.environ["NEEDLE3_LIB_PATH"] = str(ASSETS / "libneedle.so")


def audio_path(root_id, relative):
    roots = {"JP_TRAINING_ROOT": REPO / "training", "JP_DATA_ROOT": REPO / "Software Validation from Datasets"}
    path = roots[root_id] / relative
    # The existing Windows junction is not traversable from every WSL version.
    if root_id == "JP_TRAINING_ROOT" and relative.startswith("datasets/common_voice/"):
        suffix = relative.split("/prepared/", 1)[-1]
        candidate = roots["JP_DATA_ROOT"] / "Raw Datasets (Not formatted)/Common Voice/cv-corpus-26.0-2026-06-12/prepared" / suffix
        if candidate.is_file():
            return candidate
    return path
