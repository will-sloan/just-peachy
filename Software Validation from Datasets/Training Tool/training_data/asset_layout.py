"""Reconcile Common Voice prepared assets into the external shared-data root."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from training_data.portability import portable_roots, preferred_common_voice_root


EXPECTED_FILES = 101_428
EXPECTED_BYTES = 7_299_277_413
EXPECTED_SAMPLE_SHA256 = "FC54DEEC8CDA1D199026C8AEEF6A9E9387E1A13F6BDCCDD6544A65696203A57D"


class AssetLayoutError(RuntimeError):
    pass


def paths() -> tuple[Path, Path, Path]:
    roots = portable_roots(Path(__file__).resolve().parents[3])
    source = (
        roots.training
        / "datasets/common_voice/english/cv-corpus-26.0-2026-06-12/prepared/en"
    )
    target = preferred_common_voice_root(roots)
    registry = (
        roots.training
        / "successors/common_voice_26_english_phase3/registries/common_voice_older_registry.parquet"
    )
    if roots.training not in source.parents or roots.data not in target.parents:
        raise AssetLayoutError("Resolved relocation paths escaped their configured roots")
    return source, target, registry


def _files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file()] if root.is_dir() else []


def _counts(source: Path, target: Path) -> dict[str, Any]:
    same_location = source.exists() and target.exists() and source.resolve() == target.resolve()
    source_paths = [] if same_location else _files(source)
    target_paths = _files(target)
    source_files = {path.relative_to(source): path for path in source_paths}
    target_files = {path.relative_to(target): path for path in target_paths}
    overlap = sorted(source_files.keys() & target_files.keys())
    differing: list[str] = []
    for relative in overlap:
        source_path = source_files[relative]
        target_path = target_files[relative]
        if (
            source_path.stat().st_size != target_path.stat().st_size
            or hashlib.sha256(source_path.read_bytes()).digest()
            != hashlib.sha256(target_path.read_bytes()).digest()
        ):
            differing.append(relative.as_posix())
    unique_paths = {
        relative: target_files.get(relative, source_path)
        for relative, source_path in source_files.items()
    }
    unique_paths.update(target_files)
    return {
        "source_files": len(source_files),
        "source_bytes": sum(path.stat().st_size for path in source_files.values()),
        "target_files": len(target_files),
        "target_bytes": sum(path.stat().st_size for path in target_files.values()),
        "duplicate_files": len(overlap),
        "differing_duplicates": differing,
        "unique_files": len(unique_paths),
        "unique_bytes": sum(path.stat().st_size for path in unique_paths.values()),
    }


def verify() -> dict[str, Any]:
    source, target, registry = paths()
    counts = _counts(source, target)
    frame = (
        pd.read_parquet(registry, columns=["prepared_audio_relative_path", "audio_sha256"])
        .sort_values("prepared_audio_relative_path")
        .drop_duplicates("prepared_audio_relative_path")
        .reset_index(drop=True)
    )
    indexes = sorted(set(round(i * (len(frame) - 1) / 255) for i in range(256)))
    digest = hashlib.sha256()
    missing: list[str] = []
    mismatches: list[str] = []
    for index in indexes:
        row = frame.iloc[index]
        relative = Path(str(row["prepared_audio_relative_path"]))
        candidates = [target / relative, source / relative]
        path = next((item for item in candidates if item.is_file()), None)
        if path is None:
            missing.append(relative.as_posix())
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        if actual != str(row["audio_sha256"]):
            mismatches.append(relative.as_posix())
        digest.update(f"{relative.as_posix()}\0{actual}\n".encode())
    total_files = counts["unique_files"]
    total_bytes = counts["unique_bytes"]
    result = {
        "schema_version": "common-voice-external-layout-verification.v1",
        **counts,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "sample_files": len(indexes),
        "sample_sha256": digest.hexdigest().upper(),
        "sample_missing": missing,
        "sample_mismatches": mismatches,
        "expected_files": EXPECTED_FILES,
        "expected_bytes": EXPECTED_BYTES,
        "expected_sample_sha256": EXPECTED_SAMPLE_SHA256,
        "ready": bool(
            total_files == EXPECTED_FILES
            and total_bytes == EXPECTED_BYTES
            and not counts["differing_duplicates"]
            and not missing
            and not mismatches
            and digest.hexdigest().upper() == EXPECTED_SAMPLE_SHA256
        ),
        "fully_consolidated": counts["source_files"] == 0
        and counts["target_files"] == EXPECTED_FILES,
        "source": str(source),
        "target": str(target),
    }
    return result


def reconcile() -> dict[str, Any]:
    source, target, _ = paths()
    before = verify()
    if not before["ready"]:
        raise AssetLayoutError("Pre-move counts or deterministic hash sample failed")
    if source.exists() and target.exists() and source.resolve() == target.resolve():
        if not before["fully_consolidated"]:
            raise AssetLayoutError("Shared layout alias did not verify as consolidated")
        return before
    target.mkdir(parents=True, exist_ok=True)
    def move_one(source_path: Path) -> None:
        relative = source_path.relative_to(source)
        target_path = target / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if target_path.exists():
            if (
                source_path.stat().st_size != target_path.stat().st_size
                or hashlib.sha256(source_path.read_bytes()).digest()
                != hashlib.sha256(target_path.read_bytes()).digest()
            ):
                raise AssetLayoutError(f"Collision differs: {relative.as_posix()}")
            source_path.unlink()
        else:
            os.replace(source_path, target_path)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(move_one, _files(source)))
    for directory in sorted(
        (item for item in source.rglob("*") if item.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        directory.rmdir()
    result = verify()
    if not result["ready"] or not result["fully_consolidated"]:
        raise AssetLayoutError("Post-move layout verification failed")
    return result


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("verify", "reconcile"))
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        result = reconcile() if args.action == "reconcile" else verify()
    except (AssetLayoutError, FileNotFoundError, OSError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
