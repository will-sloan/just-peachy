"""Checksum validation and reproducible local Raspberry Pi bundle export."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Iterable

from .config import AssetSpec, PipelineConfig


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_assets(assets: Iterable[AssetSpec]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for asset in assets:
        path = asset.path.resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        observed = sha256_file(path)
        if observed != asset.sha256:
            raise ValueError(
                f"asset checksum mismatch for {asset.component_id}: {observed}"
            )
        rows.append(
            {
                "component_id": asset.component_id,
                "source_path": str(path),
                "deployment_relative_path": asset.deployment_relative_path,
                "bytes": path.stat().st_size,
                "sha256": observed,
                "status": "VALID",
            }
        )
    return rows


def _link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) == sha256_file(source):
            return "reused"
        raise FileExistsError(destination)
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def export_pi_bundle(config: PipelineConfig, output_dir: Path) -> dict[str, object]:
    """Stage exact graphs plus runtime source; never downloads or converts models."""

    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    validated = validate_assets(config.assets)
    asset_rows = []
    for asset, row in zip(config.assets, validated, strict=True):
        target = destination / asset.deployment_relative_path
        mode = _link_or_copy(asset.path, target)
        asset_rows.append({**row, "bundle_path": str(target), "transfer": mode})

    package_source = Path(__file__).resolve().parent
    package_target = destination / "edge_speech_pipeline"
    package_target.mkdir(parents=True, exist_ok=True)
    for pattern in ("*.py", "*.md"):
        for source in package_source.glob(pattern):
            shutil.copy2(source, package_target / source.name)

    requirements = """# Raspberry Pi OS 64-bit / Debian ARM64 runtime only.
numpy==2.2.6
scipy==1.15.3
soundfile==0.13.1
sounddevice==0.5.5
psutil==7.2.2
onnxruntime==1.29.0
sherpa-onnx==1.13.4
"""
    (destination / "requirements-linux-arm64.txt").write_text(
        requirements, encoding="utf-8", newline="\n"
    )
    launcher = """#!/usr/bin/env bash
set -euo pipefail
BUNDLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export EDGE_SPEECH_ASSET_ROOT="$BUNDLE_ROOT"
export EDGE_SPEECH_DATA_ROOT="${EDGE_SPEECH_DATA_ROOT:-${XDG_DATA_HOME:-$HOME/.local/share}/just_peachy_edge}"
export PYTHONPATH="$BUNDLE_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec python -m edge_speech_pipeline "${@:-gui}"
"""
    (destination / "run_pi.sh").write_text(launcher, encoding="utf-8", newline="\n")
    pi_readme = """# Raspberry Pi OS 64-bit run instructions

## Purpose

This bundle runs the same lossless-journal speech pipeline used on Windows:
Sherpa Giga streaming ASR, final-utterance INT8 ONNX punctuation, Pyannote
segmentation, ReDimNet speaker embeddings, enrollment, and the local GUI/CLI.
It does not download model weights and does not upload audio.

## Inputs and outputs

Inputs are a selected ALSA/PipeWire microphone, a WAV/FLAC file, or labelled
enrollment WAV files. Session audio, JSONL events, labelled transcripts, and
telemetry are stored locally under `EDGE_SPEECH_DATA_ROOT` (by default
`~/.local/share/just_peachy_edge`).

## One-time Raspberry Pi OS setup

```bash
sudo apt update
sudo apt install -y python3-venv python3-tk libportaudio2 portaudio19-dev libsndfile1
cd /absolute/path/to/edge_speech_pi_bundle_v1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-linux-arm64.txt
bash run_pi.sh validate
```

## Run

```bash
cd /absolute/path/to/edge_speech_pi_bundle_v1
source .venv/bin/activate
bash run_pi.sh devices
bash run_pi.sh gui
```

For headless live capture, replace `DEVICE_NUMBER` after listing devices:

```bash
bash run_pi.sh live --device DEVICE_NUMBER
```

For accelerated file simulation:

```bash
bash run_pi.sh file /absolute/path/to/sample.wav --accelerated
```

For labelled WAV enrollment:

```bash
bash run_pi.sh enroll-wav "Display Name" /absolute/path/to/sample1.wav /absolute/path/to/sample2.wav
```

## Qualification boundary

The assets and Python package are checksum-validated and the exported bundle
has been executed on Windows from its own paths. Actual Raspberry Pi/CM5
ARM64 wheel availability, audio capture, numerical parity, sustained real-time
performance, memory, and thermals still require testing on the target board.
Do not describe the bundle as Raspberry Pi qualified until those checks pass.
"""
    (destination / "README_RASPBERRY_PI.md").write_text(
        pi_readme, encoding="utf-8", newline="\n"
    )
    manifest = {
        "schema_version": "edge-speech-pi-bundle.v1",
        "status": "EXPORTED_UNQUALIFIED_ON_ARM64",
        "assets": asset_rows,
        "runtime": {
            "sample_rate": config.sample_rate,
            "audio_spool": "PCM16 mono; one lossless source-clock journal",
            "asr_lane": "independent native Sherpa streaming lane",
            "speaker_lane": "independent ONNX segmentation/embedding lane",
            "punctuation": "final utterances only; Sherpa CNN-BiLSTM INT8 ONNX",
            "xvf_contract_present": True,
        },
        "scientific_policy": {
            "score_threshold": config.identity_score_threshold,
            "margin_threshold": config.identity_margin_threshold,
            "minimum_evidence_sec": config.identity_minimum_evidence_sec,
            "clustering_threshold": config.clustering_threshold,
            "policy_source": "frozen H2 development policy; not retuned here",
        },
        "qualification": {
            "windows_x86_64_onnx_parity": "prior bounded pass",
            "linux_arm64_runtime": "not yet measured",
            "raspberry_pi_realtime": "not yet measured",
            "classification": "PORT_REQUIRES_WORK",
        },
        "licensing": {
            "punctuation_model": "Apache-2.0; commercial use and redistribution permitted subject to license conditions; see edge_speech_pipeline/EDGE_PUNCT_CASING_LICENSE.md and PUNCTUATION_LICENSE_AUDIT.md.",
            "distribution_warning": "Punctuation is permissively licensed. Review every other upstream model license before product redistribution; Pyannote source access/provenance remains gated.",
            "implicit_downloads_allowed": False,
        },
    }
    manifest_path = destination / "bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest
