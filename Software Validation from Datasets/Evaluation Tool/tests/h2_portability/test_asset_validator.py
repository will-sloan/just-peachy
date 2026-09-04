from __future__ import annotations

import importlib.util
import json
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = TOOL_ROOT / "deployment/h2_arm64/validate_arm64_package.py"


def _module():
    spec = importlib.util.spec_from_file_location("h2_arm64_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_asset_validator_passes_exact_hash_and_blocks_mismatch(tmp_path: Path) -> None:
    module = _module()
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    asset = asset_root / "graph.onnx"
    asset.write_bytes(b"bounded-test-graph")
    digest = module.sha256_file(asset)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "assets": [
                    {"id": "test", "relative_path": "graph.onnx", "sha256": digest}
                ]
            }
        ),
        encoding="utf-8",
    )
    passed = module.validate(asset_root, manifest, False)
    assert passed["status"] == "PASS"
    asset.write_bytes(b"changed")
    blocked = module.validate(asset_root, manifest, False)
    assert blocked["status"] == "BLOCKED"
    assert blocked["hardware_ready_claimed"] is False
