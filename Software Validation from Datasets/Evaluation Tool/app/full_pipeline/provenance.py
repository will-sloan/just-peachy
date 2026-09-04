"""Component identities derived only from the locked matrix and runtime config."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

from .matrix import PipelineSelection
from .models import ComponentRuntimeIdentity


def runtime_identities(
    selection: PipelineSelection,
    *,
    evaluation_root: Path,
    decision_policy_sha256: str | None = None,
) -> dict[str, ComponentRuntimeIdentity]:
    root = Path(evaluation_root).resolve()
    runtime_hash = selection.runtime_config_sha256
    asr = selection.asr
    diar = selection.diarization
    diar_embedding = selection.diarization_embedding
    identity = selection.identity
    asr_assets = asr.get("model_asset", {})
    asr_model_hashes = _hashes(asr_assets.get("result_affecting_files", {}))
    diar_model_hashes = tuple(
        value
        for value in (
            str(diar.get("segmentation_model_asset_sha256") or ""),
            str(diar_embedding.get("model_identity_sha256") or ""),
            str(diar_embedding.get("model_asset_sha256") or ""),
        )
        if len(value) == 64
    )
    identity_hashes = _identity_asset_hashes(identity)
    decision_hash = str(decision_policy_sha256 or "").lower()
    if not decision_hash and selection.frozen_hybrid_anchor:
        decision_hash = (
            "2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a"
        )
    if not decision_hash:
        decision_hash = str(selection.enrollment_policy["sha256"])
    if len(decision_hash) != 64:
        raise ValueError("decision policy identity must be a SHA-256 digest")
    environment_fingerprints = {
        "onnx": "d88638b4955ab0dada065ef0821ece33a8f02764c1c40946f99b753ce9219b16",
        "credential-diarization": "341562b3f910676d5b02b3c55ea09dab54ed05d67c71dfc898d562da3ddff960",
        "wespeaker": "cc861c6e0d49860f778e89decb4746ef48abd19ff5d67a75228d8b8def97b3cb",
        "redimnet2": "dabd04a37d7855751deef99ed05134c40a4c1c51be0ae5dfc039365c3623e932",
        "core-cpu": "2ca28ee808d80371de428dfec3154304778f9e7873085b4e71584f6534e85a6a",
    }

    def component(
        family: str,
        backend: str,
        config_id: str,
        config_sha: str,
        model_id: str | None,
        assets: tuple[str, ...],
        profile: str | None,
        implementation: str,
    ) -> ComponentRuntimeIdentity:
        return ComponentRuntimeIdentity(
            component_family=family,
            backend_id=backend,
            backend_config_id=config_id,
            backend_config_sha256=config_sha,
            pipeline_config_sha256=selection.pipeline_config_sha256,
            model_id=model_id,
            model_asset_sha256s=tuple(dict.fromkeys(value.lower() for value in assets)),
            environment_profile_id=profile,
            environment_fingerprint_sha256=environment_fingerprints.get(profile or ""),
            implementation_id=implementation,
            implementation_sha256=_implementation_hash(root, implementation),
        )

    return {
        "capture": component(
            "capture",
            "backend_neutral_audio_source",
            "full_pipeline_audio_normalization.v1",
            runtime_hash,
            None,
            (),
            "core-cpu",
            "app/full_pipeline/audio.py",
        ),
        "asr": component(
            "asr",
            str(asr["component_id"]),
            str(asr["registry_id"]),
            str(asr["config_sha256"]),
            str(asr_assets.get("asset_id") or asr["component_id"]),
            asr_model_hashes,
            str(asr["environment_profile"]),
            str(asr["implementation_path"]),
        ),
        "segmentation": component(
            "segmentation",
            "pyannote_segmentation_3_0",
            "full_pipeline_causal_pyannote_online_centroid.v1",
            runtime_hash,
            "pyannote/segmentation-3.0",
            (str(diar["segmentation_model_asset_sha256"]),),
            str(diar["segmentation_environment_profile"]),
            "app/full_pipeline/segmentation.py",
        ),
        "diarization": component(
            "diarization",
            str(diar["pipeline_id"]),
            str(diar["pipeline_id"]),
            str(diar["configuration_sha256"]),
            str(diar["resolved_identity_sha256"]),
            diar_model_hashes,
            str(diar["embedding_environment_profile"]),
            "app/full_pipeline/clustering.py",
        ),
        "clustering": component(
            "clustering",
            "online_normalized_centroid_cosine",
            "full_pipeline_online_centroid_cosine.v1",
            runtime_hash,
            None,
            (),
            "core-cpu",
            "app/full_pipeline/clustering.py",
        ),
        "speaker_embedding": component(
            "speaker_embedding",
            str(identity["backend_id"]),
            str(identity["registry_id"]),
            str(identity["config_sha256"]),
            str(identity["model_id"]),
            identity_hashes,
            str(identity["environment_profile"]),
            str(identity["implementation_path"]),
        ),
        "speaker_matching": component(
            "speaker_matching",
            f"open_set_{selection.hybrid_label.lower()}",
            "full_pipeline_open_set_decision.v1",
            decision_hash,
            str(identity["model_id"]),
            identity_hashes,
            "core-cpu",
            "app/full_pipeline/identity.py",
        ),
        "transcript": component(
            "transcript",
            "causal_transcript_speaker_aligner",
            "full_pipeline_transcript_alignment.v1",
            runtime_hash,
            None,
            (),
            "core-cpu",
            "app/full_pipeline/alignment.py",
        ),
        "telemetry": component(
            "telemetry",
            "resource_telemetry",
            "full_pipeline_resource_telemetry.v1",
            runtime_hash,
            None,
            (),
            "core-cpu",
            "app/full_pipeline/telemetry.py",
        ),
        "pipeline": component(
            "pipeline",
            "full_pipeline_coordinator",
            selection.pipeline_id,
            selection.pipeline_config_sha256,
            None,
            (),
            "core-cpu",
            "app/full_pipeline/coordinator.py",
        ),
    }


def _hashes(value: object) -> tuple[str, ...]:
    if not isinstance(value, Mapping):
        return ()
    return tuple(
        str(item).lower() for _, item in sorted(value.items()) if len(str(item)) == 64
    )


def _identity_asset_hashes(identity: Mapping[str, object]) -> tuple[str, ...]:
    values = list(_hashes(identity.get("result_affecting_files", {})))
    for key in ("model_asset_sha256", "model_identity_sha256"):
        value = str(identity.get(key) or "")
        if len(value) == 64:
            values.append(value.lower())
    return tuple(dict.fromkeys(values))


def _implementation_hash(root: Path, logical_path: str) -> str | None:
    path = (root / logical_path).resolve()
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    return None
