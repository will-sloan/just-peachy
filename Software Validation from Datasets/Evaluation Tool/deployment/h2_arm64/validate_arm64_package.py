"""Validate staged H2 ARM64 assets and local platform without downloads."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(asset_root: Path, manifest_path: Path, require_linux_arm64: bool) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    for asset in manifest["assets"]:
        path = asset_root / asset["relative_path"]
        observed = sha256_file(path) if path.is_file() else None
        rows.append(
            {
                "id": asset["id"],
                "path": str(path.resolve(strict=False)),
                "expected_sha256": asset["sha256"],
                "observed_sha256": observed,
                "status": "MATCH" if observed == asset["sha256"] else "MISSING_OR_MISMATCH",
            }
        )
    target = platform.system() == "Linux" and platform.machine().casefold() in {
        "aarch64",
        "arm64",
    }
    assets_pass = all(row["status"] == "MATCH" for row in rows)
    platform_pass = target or not require_linux_arm64
    return {
        "schema_version": "h2-linux-arm64-package-validation.v1",
        "status": "PASS" if assets_pass and platform_pass else "BLOCKED",
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "is_linux_arm64": target,
            "required": require_linux_arm64,
        },
        "asset_root": str(asset_root.resolve(strict=False)),
        "manifest_path": str(manifest_path.resolve()),
        "assets": rows,
        "implicit_downloads_performed": False,
        "hardware_ready_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-root", required=True, type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("asset_manifest.json"),
    )
    parser.add_argument("--require-linux-arm64", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = validate(args.asset_root, args.manifest, args.require_linux_arm64)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(value, indent=2))
    return 0 if value["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
