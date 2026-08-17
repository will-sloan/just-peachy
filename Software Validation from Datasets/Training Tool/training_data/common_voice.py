"""Pin and acquire the Phase-3 Common Voice archive through Mozilla's SDK.

This module intentionally stops at a verified source archive. Extraction,
metadata normalization, older-speaker selection, and Phase-3 freezing happen
only after the authenticated acquisition has completed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SOURCE_ROOT = Path(__file__).resolve().parents[1]
TOOL_ROOT = SOURCE_ROOT.parent / "Evaluation Tool"
RELEASE_PATH = Path(__file__).with_name("common_voice_release.v1.json")
sys.path.insert(0, str(TOOL_ROOT))

from app.utils.paths import training_root  # noqa: E402


class AcquisitionBlocked(RuntimeError):
    """Raised when a safe, user-authorized acquisition cannot continue."""


def load_release(path: Path = RELEASE_PATH) -> dict[str, Any]:
    release = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "dataset_name",
        "dataset_id",
        "locale_code",
        "corpus_version",
        "release_id",
        "release_date",
        "official_dataset_source",
        "archive_filename",
        "archive_size_bytes",
        "archive_sha256",
        "dataset_license_identifier",
    }
    missing = sorted(required - set(release))
    if missing:
        raise ValueError(f"Common Voice release record is missing: {', '.join(missing)}")
    if release["schema_version"] != "common-voice-release.v1":
        raise ValueError("Unsupported Common Voice release schema")
    if release["locale_code"] != "en" or release["dataset_license_identifier"] != "CC0-1.0":
        raise ValueError("Pinned release is not the reviewed English CC0-1.0 dataset")
    digest = str(release["archive_sha256"]).upper()
    if len(digest) != 64 or any(character not in "0123456789ABCDEF" for character in digest):
        raise ValueError("Pinned archive SHA-256 is invalid")
    if int(release["archive_size_bytes"]) <= 0:
        raise ValueError("Pinned archive byte size is invalid")
    return release


def release_root(root: Path, release: dict[str, Any]) -> Path:
    return root / "datasets" / "common_voice" / "english" / str(release["release_id"])


def archive_path(root: Path, release: dict[str, Any]) -> Path:
    return release_root(root, release) / "source" / str(release["archive_filename"])


def sha256_file(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest().upper()


def verify_archive(path: Path, release: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed_bytes = path.stat().st_size
    expected_bytes = int(release["archive_size_bytes"])
    if observed_bytes != expected_bytes:
        raise ValueError(
            f"Archive byte-size mismatch at {path}: expected {expected_bytes}, observed {observed_bytes}. "
            "The file was preserved and will not be overwritten."
        )
    observed_sha256 = sha256_file(path)
    expected_sha256 = str(release["archive_sha256"]).upper()
    if observed_sha256 != expected_sha256:
        raise ValueError(
            f"Archive SHA-256 mismatch at {path}: expected {expected_sha256}, observed {observed_sha256}. "
            "The file was preserved and will not be overwritten."
        )
    return {"archive_bytes": observed_bytes, "archive_sha256": observed_sha256}


def status(root: Path, release: dict[str, Any]) -> dict[str, Any]:
    target = archive_path(root, release)
    complete = target.is_file() and target.stat().st_size == int(release["archive_size_bytes"])
    return {
        "release_frozen": True,
        "dataset_id": release["dataset_id"],
        "release_id": release["release_id"],
        "license_id": release["dataset_license_identifier"],
        "archive_logical_path": (
            f"datasets/common_voice/english/{release['release_id']}/source/{release['archive_filename']}"
        ),
        "archive_present": target.is_file(),
        "archive_size_complete": complete,
        "authentication_required": True,
        "mdc_api_key_present": bool(os.environ.get("MDC_API_KEY", "").strip()),
        "datacollective_sdk_installed": importlib.util.find_spec("datacollective") is not None,
    }


def _sdk_downloader(dataset_id: str, download_directory: str) -> Path:
    try:
        module = importlib.import_module("datacollective")
    except ModuleNotFoundError as error:
        raise AcquisitionBlocked(
            "The official Mozilla Data Collective SDK is not installed. Run "
            "'python -m pip install datacollective', then repeat the acquisition command."
        ) from error
    return Path(
        module.download_dataset(
            dataset_id,
            download_directory=download_directory,
            show_progress=True,
            overwrite_existing=False,
            enable_logging=False,
        )
    )


def acquire(
    root: Path,
    release: dict[str, Any],
    *,
    downloader: Callable[[str, str], Path] = _sdk_downloader,
) -> dict[str, Any]:
    target = archive_path(root, release)
    if target.exists():
        identity = verify_archive(target, release)
        return {"download_complete": True, "reused": True, **identity}

    if not os.environ.get("MDC_API_KEY", "").strip():
        raise AcquisitionBlocked(
            "Mozilla Data Collective authentication is required. Sign in, accept the dataset conditions, "
            "create an API key under Account -> Credentials, and set MDC_API_KEY only in the current shell."
        )

    source_dir = target.parent
    source_dir.mkdir(parents=True, exist_ok=True)
    downloaded = downloader(str(release["dataset_id"]), str(source_dir)).resolve()
    if downloaded != target.resolve():
        raise ValueError(
            f"The official SDK returned unexpected archive {downloaded}; expected {target.resolve()}. "
            "No file was moved or overwritten."
        )
    identity = verify_archive(target, release)
    manifest = {
        "schema_version": "common-voice-acquisition.v1",
        "dataset_id": release["dataset_id"],
        "release_id": release["release_id"],
        "archive_filename": release["archive_filename"],
        "archive_bytes": identity["archive_bytes"],
        "archive_sha256": identity["archive_sha256"],
        "acquisition_mechanism": release["official_acquisition_mechanism"],
        "official_dataset_source": release["official_dataset_source"],
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    metadata_dir = release_root(root, release) / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = metadata_dir / "acquisition_manifest.json"
    temporary_path = manifest_path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary_path.replace(manifest_path)
    return {"download_complete": True, "reused": False, **identity}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "acquire", "verify-archive"))
    parser.add_argument("--training-root", type=Path, default=None)
    args = parser.parse_args()
    release = load_release()
    root = (args.training_root or training_root().path).resolve()
    try:
        if args.command == "status":
            result = status(root, release)
        elif args.command == "verify-archive":
            result = verify_archive(archive_path(root, release), release)
        else:
            result = acquire(root, release)
    except (AcquisitionBlocked, FileNotFoundError, ValueError) as error:
        print(json.dumps({"complete": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
