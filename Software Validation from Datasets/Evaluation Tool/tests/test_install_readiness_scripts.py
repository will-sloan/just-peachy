from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str):
    path = PROJECT_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bootstrap():
    return _load_script("bootstrap_models")


@pytest.fixture(scope="module")
def verifier():
    return _load_script("verify_install")


def test_whisper_policy_allows_only_approved_small_models(bootstrap, verifier) -> None:
    approved = ["tiny", "tiny.en", "base", "base.en", "small", "small.en"]
    bootstrap.validate_whisper_models(approved)
    assert verifier.parse_whisper_models(",".join(approved)) == approved

    for prohibited in ("medium", "large-v1", "large-v2", "large-v3", "turbo"):
        with pytest.raises(ValueError, match="prohibited"):
            bootstrap.validate_whisper_models([prohibited])
        with pytest.raises(ValueError, match="prohibited"):
            verifier.parse_whisper_models(prohibited)


def test_prohibited_whisper_request_creates_no_cache(bootstrap, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    result = bootstrap.main(["--cache-root", str(cache), "--whisper", "medium"])
    assert result == 2
    assert not cache.exists()


def test_download_file_checks_cached_sha_without_network(
    bootstrap,
    tmp_path: Path,
) -> None:
    asset = tmp_path / "asset.bin"
    asset.write_bytes(b"verified")
    expected = bootstrap.file_sha256(asset)
    assert (
        bootstrap.download_file(
            "https://invalid.example/unused",
            asset,
            expected_sha256=expected,
        )
        == asset
    )
    with pytest.raises(RuntimeError, match="SHA-256"):
        bootstrap.download_file(
            "https://invalid.example/unused",
            asset,
            expected_sha256="0" * 64,
        )


def test_model_archive_extracts_required_markers(bootstrap, tmp_path: Path) -> None:
    archive = tmp_path / "model.tar.gz"
    payload = b"model-data"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("model/model.bin")
        info.size = len(payload)
        handle.addfile(info, io.BytesIO(payload))

    destination = tmp_path / "cache" / "model"
    result = bootstrap.install_model_archive(
        archive,
        destination=destination,
        archive_directory="model",
        markers=("model.bin",),
    )
    assert result == destination
    assert (destination / "model.bin").read_bytes() == payload


def test_tar_extraction_rejects_path_traversal(bootstrap, tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar.gz"
    payload = b"unsafe"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("../escape.bin")
        info.size = len(payload)
        handle.addfile(info, io.BytesIO(payload))

    with pytest.raises(RuntimeError, match="unsafe archive member"):
        bootstrap.extract_tar_safely(archive, tmp_path / "destination")
    assert not (tmp_path / "escape.bin").exists()


def test_bootstrap_paths_match_asr_component_configs(bootstrap) -> None:
    config_root = (
        PROJECT_ROOT
        / "Software Validation from Datasets"
        / "Evaluation Tool"
        / "configs"
        / "inference"
        / "components"
        / "asr"
    )
    sherpa = (config_root / "sherpa_onnx.yaml").read_text(encoding="utf-8")
    vosk = (config_root / "vosk.yaml").read_text(encoding="utf-8")
    wenet = (config_root / "wenet.yaml").read_text(encoding="utf-8")
    faster = (config_root / "faster_whisper.yaml").read_text(encoding="utf-8")

    assert bootstrap.SHERPA_ASR_DIRECTORY in sherpa
    assert bootstrap.VOSK_ASR_DIRECTORY in vosk
    assert bootstrap.WENET_ASR_DIRECTORY in wenet
    assert "models/cache/faster_whisper/tiny" in faster


def test_full_requirements_include_pinned_speaker_backends() -> None:
    full = (PROJECT_ROOT / "requirements" / "full.txt").read_text(encoding="utf-8")
    speakers = (PROJECT_ROOT / "requirements" / "speaker_backends.txt").read_text(
        encoding="utf-8"
    )
    optional = (PROJECT_ROOT / "requirements" / "optional.txt").read_text(
        encoding="utf-8"
    )

    assert "-r speaker_backends.txt" in full
    assert "resemblyzer==0.1.4" in speakers
    assert "wespeaker.git@1d4164bdb1dcfee4624093190fd5ecbb19447686" in speakers
    assert "wenet.git@v3.1.0" in optional
    assert "wenet.git\n" not in optional


def test_asset_presence_is_not_reported_as_qualification(
    verifier,
    tmp_path: Path,
) -> None:
    asset = tmp_path / "model.bin"
    asset.write_bytes(b"model")
    present = verifier.model_asset_check("model", asset, required=True)
    qualification = verifier.qualification_check("model", "inference not run")

    assert present.status == "PRESENT"
    assert present.category == "ASSET"
    assert qualification.status == "NOT_RUN"
    assert qualification.category == "QUALIFICATION"
