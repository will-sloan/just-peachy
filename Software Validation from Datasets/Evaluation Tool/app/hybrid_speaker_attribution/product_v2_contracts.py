"""Contracts and immutable registry for the Hybrid Speaker Attribution Product V2 study."""

from __future__ import annotations

from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Iterable, Mapping, Sequence

import yaml

from app.hybrid_speaker_attribution.contracts import TOOL_ROOT, canonical_sha256, file_sha256


SEED = 3800
SCHEMA = "hybrid-speaker-attribution-product-v2"
PROTOCOL_VERSION = "hybrid_speaker_attribution_product_v2"
V1_PROTOCOL_ID = "hybrid_speaker_attribution_v1_6c43a2bbe1ca"
V1_BENCHMARK_ID = "controlled_diarization_v1_acd5e6e431d8"
V2_BENCHMARK_ID = "diarization_product_v2_6b6c50a5de31"
V1_OVERLAY_COUNTS = {"smoke": 24, "development": 180, "evaluation": 360}
DIARIZATION_PIPELINES = {
    "modular_pyannote_wespeaker": "3e924c369ac77c8c9b916958f938807479f0df2fc05182ac3624590add412226",
    "modular_pyannote_redimnet2": "d5ac7afb401addd440dde48707ba1fca669c233173a3f4ddee7e084db02b0e90",
}
BACKEND_MINIMUM_SEC = {
    "wespeaker": 0.75,
    "redimnet2_b2_speaker_embedding": 0.50,
    "speechbrain_ecapa": 0.75,
}
COMBINATIONS = (
    {"combination_id": "H1", "diarization_pipeline_id": "modular_pyannote_wespeaker", "identity_backend_id": "wespeaker", "same_model": True},
    {"combination_id": "H2", "diarization_pipeline_id": "modular_pyannote_redimnet2", "identity_backend_id": "redimnet2_b2_speaker_embedding", "same_model": True},
    {"combination_id": "H3", "diarization_pipeline_id": "modular_pyannote_redimnet2", "identity_backend_id": "wespeaker", "same_model": False},
    {"combination_id": "H4", "diarization_pipeline_id": "modular_pyannote_wespeaker", "identity_backend_id": "redimnet2_b2_speaker_embedding", "same_model": False},
    {"combination_id": "H5", "diarization_pipeline_id": "modular_pyannote_redimnet2", "identity_backend_id": "speechbrain_ecapa", "same_model": False},
    {"combination_id": "H6", "diarization_pipeline_id": "modular_pyannote_wespeaker", "identity_backend_id": "speechbrain_ecapa", "same_model": False},
)
OVERLAYS = ("ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN")
GALLERY_SIZES = (1, 2, 5, 10, 20, 50, "full")
PRIMARY_GALLERY_SIZES = (5, 10, 20)
EVIDENCE_CHECKPOINTS_SEC = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0)
OPERATING_MODES = {
    "STRICT": {"target_fpir": 0.005, "default_margin": 0.04},
    "BALANCED": {"target_fpir": 0.01, "default_margin": 0.03},
    "RESPONSIVE": {"target_fpir": 0.02, "default_margin": 0.01},
    "DIAGNOSTIC_5PCT": {"target_fpir": 0.05, "default_margin": 0.0},
}
LABEL_POLICIES = {
    "CONSERVATIVE": {"minimum_evidence_sec": 3.0, "confirmations": 2, "hysteresis": 0.03, "tentative_visible": False},
    "ADAPTIVE": {"minimum_evidence_sec": 2.0, "confirmations": 2, "hysteresis": 0.02, "tentative_visible": True},
    "AGGRESSIVE_DIAGNOSTIC": {"minimum_evidence_sec": 1.0, "confirmations": 1, "hysteresis": 0.0, "tentative_visible": True},
}

V1_BENCHMARK_ROOT = TOOL_ROOT / "benchmarks" / "stage11" / "controlled_diarization_v1"
V2_BENCHMARK_ROOT = TOOL_ROOT / "benchmarks" / "stage11" / "diarization_product_v2"
V1_PROTOCOL_ROOT = TOOL_ROOT / "benchmarks" / "hybrid_speaker_attribution" / "hybrid_speaker_attribution_v1"
PRODUCT_PROTOCOL_ROOT = TOOL_ROOT / "benchmarks" / "hybrid_speaker_attribution" / "hybrid_speaker_attribution_product_v2"
UPSTREAM_DIARIZATION_ROOT = TOOL_ROOT / "JustPeachyResults" / "diarization_product_v2_development"
FROZEN_DIARIZATION_SELECTION = UPSTREAM_DIARIZATION_ROOT / "frozen_diarization_development_selection.yaml"
RESULT_ROOT = TOOL_ROOT / "JustPeachyResults" / "hybrid_speaker_attribution_product_v2_development"
SUMMARY_ROOT = TOOL_ROOT / "JustPeachyResearchSummaries"
POLICY_ROOT = TOOL_ROOT / "configs" / "automated_evaluation" / "hybrid_product_v2"


class ProductV2Error(RuntimeError):
    """Raised when a Product V2 scientific invariant is violated."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    _replace_with_retry(temporary, path)


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    _replace_with_retry(temporary, path)


def _replace_with_retry(source: Path, destination: Path) -> None:
    """Publish through short Windows sharing violations from read-only monitors."""

    last_error: PermissionError | None = None
    for attempt in range(40):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(min(0.5, 0.01 * (attempt + 1)))
    if last_error is not None:
        raise last_error


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    atomic_text(path, "".join(json.dumps(dict(row), sort_keys=True) + "\n" for row in rows))


def write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(fieldnames or sorted({key for row in rows for key in row}))
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _csv_value(row.get(name)) for name in names})
    _replace_with_retry(temporary, path)


def _csv_value(value: object) -> object:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def yaml_bytes(value: object) -> bytes:
    return yaml.safe_dump(value, sort_keys=False, allow_unicode=True).encode("utf-8")


def write_yaml(path: Path, value: object) -> str:
    data = yaml_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    _replace_with_retry(temporary, path)
    return hashlib.sha256(data).hexdigest()


def checksum_tree(root: Path, *, exclude_names: set[str] | None = None) -> list[dict[str, object]]:
    excluded = exclude_names or set()
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.name not in excluded):
        rows.append({"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": file_sha256(path).lower()})
    return rows


def protocol_id(payload: Mapping[str, object]) -> str:
    return f"{PROTOCOL_VERSION}_{canonical_sha256(payload).lower()[:12]}"


def stable_order(values: Iterable[str], salt: object) -> list[str]:
    return sorted(set(values), key=lambda value: canonical_sha256({"seed": SEED, "salt": salt, "value": value}))


def speaker_band(count: int) -> str:
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    if count <= 5:
        return "3-5"
    if count <= 8:
        return "6-8"
    return "9-12"
