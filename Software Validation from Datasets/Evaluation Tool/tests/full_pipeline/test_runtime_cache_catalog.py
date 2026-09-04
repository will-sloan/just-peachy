from __future__ import annotations

from pathlib import Path

import pytest

from app.full_pipeline.cache import (
    RUNTIME_CACHE_CATALOG,
    CacheContractError,
    ContentAddressedCache,
    RuntimeCacheKey,
    audio_source_identity,
    cache_dependency,
    make_runtime_cache_key,
    result_affecting_identity,
    score_matrix_source_identity,
)


EXPECTED_CACHE_KINDS = {
    "decoded_resampled_audio",
    "pyannote_segmentation",
    "diarization_windows",
    "diarization_embeddings",
    "identity_embeddings",
    "enrollment_embeddings",
    "asr_finalized_results",
    "score_matrices",
}


def _identity(stage: str, revision: str = "v1"):
    return result_affecting_identity(
        stage,
        {
            "revision": revision,
            "result_affecting_sha256": "b" * 64,
        },
    )


def _audio_source():
    return audio_source_identity(
        audio_sha256="a" * 64,
        start_sample=0,
        end_sample=160_000,
        sample_rate_hz=16_000,
        parameters={"channel_policy": "mono"},
    )


def _make_key(
    cache_kind: str,
    *,
    source_mode: str,
    dependencies=(),
    source=None,
    revision: str = "v1",
    allow_live_microphone_audio: bool = False,
) -> RuntimeCacheKey:
    return make_runtime_cache_key(
        cache_kind=cache_kind,
        source_mode=source_mode,
        source_identity=source or _audio_source(),
        window_identity=_identity("window_policy", revision),
        preprocessing_identity=_identity("preprocessing_policy", revision),
        producer_identity=_identity("model_or_implementation", revision),
        configuration_identity=_identity("component_configuration", revision),
        upstream_dependencies=dependencies,
        allow_live_microphone_audio=allow_live_microphone_audio,
    )


def _catalog_keys() -> dict[str, RuntimeCacheKey]:
    decoded = _make_key("decoded_resampled_audio", source_mode="dataset")
    segmentation = _make_key(
        "pyannote_segmentation",
        source_mode="dataset",
        dependencies=(cache_dependency(decoded),),
    )
    windows = _make_key(
        "diarization_windows",
        source_mode="dataset",
        dependencies=(cache_dependency(segmentation),),
    )
    diarization = _make_key(
        "diarization_embeddings",
        source_mode="dataset",
        dependencies=(cache_dependency(windows),),
    )
    identity = _make_key(
        "identity_embeddings",
        source_mode="dataset",
        dependencies=(cache_dependency(windows),),
    )
    enrollment = _make_key(
        "enrollment_embeddings",
        source_mode="enrollment",
        dependencies=(cache_dependency(decoded),),
    )
    asr = _make_key(
        "asr_finalized_results",
        source_mode="dataset",
        dependencies=(cache_dependency(decoded),),
    )
    score_matrix = _make_key(
        "score_matrices",
        source_mode="aggregate",
        source=score_matrix_source_identity(
            probe_set_sha256="c" * 64,
            reference_set_sha256="d" * 64,
            parameters={"ordering_policy": "speaker_id_then_probe_id"},
        ),
        dependencies=(
            cache_dependency(identity),
            cache_dependency(enrollment),
        ),
    )
    return {
        "decoded_resampled_audio": decoded,
        "pyannote_segmentation": segmentation,
        "diarization_windows": windows,
        "diarization_embeddings": diarization,
        "identity_embeddings": identity,
        "enrollment_embeddings": enrollment,
        "asr_finalized_results": asr,
        "score_matrices": score_matrix,
    }


def test_catalog_explicitly_supports_all_eight_role_separated_products() -> None:
    assert set(RUNTIME_CACHE_CATALOG) == EXPECTED_CACHE_KINDS
    assert len({spec.role for spec in RUNTIME_CACHE_CATALOG.values()}) == 8

    asr = RUNTIME_CACHE_CATALOG["asr_finalized_results"]
    assert asr.payload_scope == "finalized_result_only_no_partial_timing_replay"
    assert asr.replays_partial_event_timing is False

    decoded = RUNTIME_CACHE_CATALOG["decoded_resampled_audio"]
    assert decoded.stores_decoded_audio is True
    assert decoded.caches_live_microphone_audio_by_default is False


def test_every_catalog_key_round_trips_through_content_cache(tmp_path: Path) -> None:
    cache = ContentAddressedCache(tmp_path / "cache")
    keys = _catalog_keys()
    assert set(keys) == EXPECTED_CACHE_KINDS

    for cache_kind, key in keys.items():
        payload = {"cache_kind": cache_kind, "status": "complete"}
        cache.publish(key, payload)
        assert cache.load(key) == payload
        assert key.to_jsonable()["role"] == RUNTIME_CACHE_CATALOG[cache_kind].role


def test_embedding_roles_and_result_affecting_identities_cannot_alias() -> None:
    keys = _catalog_keys()
    digests = {
        keys["diarization_embeddings"].digest,
        keys["identity_embeddings"].digest,
        keys["enrollment_embeddings"].digest,
    }
    assert len(digests) == 3

    decoded = keys["decoded_resampled_audio"]
    changed = _make_key(
        "pyannote_segmentation",
        source_mode="dataset",
        dependencies=(cache_dependency(decoded),),
        revision="v2",
    )
    assert changed.digest != keys["pyannote_segmentation"].digest

    with pytest.raises(CacheContractError, match="requires an upstream"):
        _make_key("identity_embeddings", source_mode="dataset")
    with pytest.raises(CacheContractError, match="unsupported upstream"):
        _make_key(
            "identity_embeddings",
            source_mode="dataset",
            dependencies=(cache_dependency(keys["enrollment_embeddings"]),),
        )


def test_live_microphone_decoded_audio_requires_explicit_opt_in() -> None:
    with pytest.raises(CacheContractError, match="explicit opt-in"):
        _make_key("decoded_resampled_audio", source_mode="live_microphone")

    opted_in = _make_key(
        "decoded_resampled_audio",
        source_mode="live_microphone",
        allow_live_microphone_audio=True,
    )
    assert opted_in.live_microphone_audio_opt_in is True
    assert opted_in.to_jsonable()["live_microphone_audio_opt_in"] is True
