"""Tests for the pinned, authentication-safe Common Voice acquisition layer."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


TRAINING_TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_TOOL))

from training_data.common_voice import (  # noqa: E402
    AcquisitionBlocked,
    acquire,
    archive_path,
    load_release,
    status,
    verify_archive,
)


def _fixture_release(payload: bytes) -> dict:
    return {
        "dataset_id": "fixture",
        "release_id": "fixture-release",
        "archive_filename": "fixture.tar.gz",
        "archive_size_bytes": len(payload),
        "archive_sha256": hashlib.sha256(payload).hexdigest().upper(),
        "dataset_license_identifier": "CC0-1.0",
        "official_acquisition_mechanism": "fixture",
        "official_dataset_source": "https://example.invalid/fixture",
    }


def test_frozen_release_is_exact_current_english_release() -> None:
    release = load_release()
    assert release["dataset_id"] == "cmqim2hn800ssnr07gvmpcnwu"
    assert release["release_id"] == "cv-corpus-26.0-2026-06-12"
    assert release["dataset_license_identifier"] == "CC0-1.0"
    assert release["archive_size_bytes"] == 94_639_372_950
    assert release["archive_sha256"] == "6809228E6AB506D18F6A1EBC830056450F8266C8F513D6038BDB0FC88A49E6CB"


def test_archive_verification_accepts_only_exact_bytes(tmp_path: Path) -> None:
    payload = b"small deterministic archive fixture"
    release = _fixture_release(payload)
    target = archive_path(tmp_path, release)
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)
    assert verify_archive(target, release)["archive_sha256"] == release["archive_sha256"]
    target.write_bytes(payload + b"changed")
    with pytest.raises(ValueError, match="byte-size mismatch"):
        verify_archive(target, release)


def test_missing_key_blocks_before_downloader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MDC_API_KEY", raising=False)
    called = False

    def downloader(dataset_id: str, download_directory: str) -> Path:
        nonlocal called
        called = True
        raise AssertionError((dataset_id, download_directory))

    with pytest.raises(AcquisitionBlocked, match="authentication is required"):
        acquire(tmp_path, _fixture_release(b"fixture"), downloader=downloader)
    assert not called


def test_acquire_reuses_verified_archive_without_authentication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("MDC_API_KEY", raising=False)
    payload = b"already complete"
    release = _fixture_release(payload)
    target = archive_path(tmp_path, release)
    target.parent.mkdir(parents=True)
    target.write_bytes(payload)
    result = acquire(tmp_path, release)
    assert result["download_complete"] is True
    assert result["reused"] is True


def test_status_reports_key_presence_without_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "do-not-leak-this-api-key"
    monkeypatch.setenv("MDC_API_KEY", secret)
    result = status(tmp_path, _fixture_release(b"fixture"))
    assert result["mdc_api_key_present"] is True
    assert secret not in json.dumps(result)
