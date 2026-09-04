"""User-facing preset metadata derived from the locked full-pipeline matrix.

Friendly labels in this module are presentation metadata only.  Every
result-affecting identity, policy, threshold, and qualification value comes
from :class:`app.full_pipeline.matrix.FullPipelineMatrix`.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import Mapping

import yaml

from app.full_pipeline.matrix import FullPipelineMatrix, PipelineSelection

from .h2_ux import (
    H2_DEFAULT_PRODUCT_MODE,
    H2_FALLBACK_PIPELINE_ID,
    H2_PIPELINE_IDS,
    H2_PRIMARY_PIPELINE_ID,
    H2_PRODUCT_MODES,
    h2_pipeline_role,
)


PRESET_SCHEMA = "full-pipeline-demo-preset.v1"
PRODUCTION_OVERLAY_ENV = "JP_FULL_PIPELINE_PRODUCTION_CATALOG"
PRODUCTION_OVERLAY_SHA_ENV = "JP_FULL_PIPELINE_PRODUCTION_CATALOG_SHA256"

ASR_FRIENDLY_NAMES: Mapping[str, str] = {
    "AO": "Sherpa-ONNX Original",
    "AG": "Sherpa-ONNX Libri-Giga Zipformer",
}
DIARIZATION_FRIENDLY_NAMES: Mapping[str, str] = {
    "DW": "Pyannote + WeSpeaker",
    "DR": "Pyannote + ReDimNet2-B2",
    "DE": "Pyannote + SpeechBrain ECAPA",
}
IDENTITY_FRIENDLY_NAMES: Mapping[str, str] = {
    "IW": "WeSpeaker identity",
    "IR": "ReDimNet2-B2 identity",
    "IE": "SpeechBrain ECAPA identity",
}


@dataclass(frozen=True)
class PipelinePreset:
    preset_id: str
    display_name: str
    protocol_version: str
    asr_alias: str
    asr_display_name: str
    diarization_alias: str
    diarization_display_name: str
    identity_alias: str
    identity_display_name: str
    hybrid_label: str
    hybrid_status: str
    frozen_anchor_derived: bool
    frozen_score_threshold: float | None
    highlight: str | None
    known_name_release_allowed: bool
    warning_codes: tuple[str, ...]
    pipeline_config_sha256: str
    runtime_config_sha256: str
    tier_a: str
    tier_b: str
    asr_identity: Mapping[str, object]
    diarization_identity: Mapping[str, object]
    identity_backend: Mapping[str, object]
    enrollment_policy: Mapping[str, object]
    hybrid_policy: Mapping[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": PRESET_SCHEMA,
            "preset_id": self.preset_id,
            "display_name": self.display_name,
            "protocol_version": self.protocol_version,
            "aliases": {
                "asr": self.asr_alias,
                "anonymous_diarization": self.diarization_alias,
                "identity": self.identity_alias,
                "hybrid": self.hybrid_label,
            },
            "friendly_names": {
                "asr": self.asr_display_name,
                "anonymous_diarization": self.diarization_display_name,
                "identity": self.identity_display_name,
            },
            "hybrid_status": self.hybrid_status,
            "frozen_anchor_derived": self.frozen_anchor_derived,
            "frozen_score_threshold": self.frozen_score_threshold,
            "highlight": self.highlight,
            "known_name_release_allowed": self.known_name_release_allowed,
            "warning_codes": list(self.warning_codes),
            "pipeline_config_sha256": self.pipeline_config_sha256,
            "runtime_config_sha256": self.runtime_config_sha256,
            "tier_a": self.tier_a,
            "tier_b": self.tier_b,
            "asr_identity": dict(self.asr_identity),
            "diarization_identity": dict(self.diarization_identity),
            "identity_backend": dict(self.identity_backend),
            "enrollment_policy": dict(self.enrollment_policy),
            "hybrid_policy": dict(self.hybrid_policy),
        }


class PresetCatalog:
    """Resolve all 18 presets from one authoritative matrix instance."""

    def __init__(
        self,
        matrix: FullPipelineMatrix,
        *,
        production_overlay_path: Path | None = None,
        production_overlay_sha256: str | None = None,
    ) -> None:
        self.matrix = matrix
        self._presets = tuple(
            _preset_from_selection(matrix.resolve(pipeline_id))
            for pipeline_id in matrix.pipeline_ids
        )
        if len(self._presets) != 18:
            raise ValueError("full-pipeline demo requires exactly 18 matrix presets")
        if len({row.preset_id for row in self._presets}) != 18:
            raise ValueError("full-pipeline preset IDs must be unique")
        overlay_path = production_overlay_path
        if overlay_path is None and os.environ.get(PRODUCTION_OVERLAY_ENV):
            overlay_path = Path(str(os.environ[PRODUCTION_OVERLAY_ENV]))
        expected_sha = production_overlay_sha256 or os.environ.get(
            PRODUCTION_OVERLAY_SHA_ENV
        )
        self._production_overlay = (
            _load_production_overlay(
                overlay_path,
                expected_sha256=expected_sha,
                known_pipeline_ids={row.preset_id for row in self._presets},
            )
            if overlay_path is not None
            else None
        )

    @property
    def presets(self) -> tuple[PipelinePreset, ...]:
        return self._presets

    @property
    def h2_presets(self) -> tuple[PipelinePreset, ...]:
        """Return the fixed H2 product pair in primary/fallback order."""

        by_id = {row.preset_id: row for row in self._presets}
        try:
            values = tuple(by_id[pipeline_id] for pipeline_id in H2_PIPELINE_IDS)
        except KeyError as exc:  # pragma: no cover - matrix validation catches this
            raise ValueError(f"H2 matrix preset is missing: {exc.args[0]}") from exc
        for row in values:
            if not (
                row.hybrid_label == "H2"
                and row.diarization_alias == "DR"
                and row.identity_alias == "IR"
            ):
                raise ValueError(f"H2 preset component identity differs: {row.preset_id}")
        return values

    def get(self, preset_id: str) -> PipelinePreset:
        for preset in self._presets:
            if preset.preset_id == preset_id:
                return preset
        raise KeyError(preset_id)

    @property
    def default_preset_id(self) -> str:
        if self._production_overlay is not None:
            return str(self._production_overlay["default_pipeline_id"])
        return "fullpipe_v1_ao_dr_ir"

    @property
    def default_h2_preset_id(self) -> str:
        """Return Sherpa Giga + H2 regardless of a legacy all-18 overlay."""

        self.get(H2_PRIMARY_PIPELINE_ID)
        return H2_PRIMARY_PIPELINE_ID

    @property
    def production_roles(self) -> Mapping[str, object]:
        if self._production_overlay is None:
            return {}
        return dict(self._production_overlay["roles"])

    def production_role(self, preset_id: str) -> str | None:
        return next(
            (
                str(role)
                for role, pipeline_id in self.production_roles.items()
                if pipeline_id == preset_id
            ),
            None,
        )

    def payload(self) -> dict[str, object]:
        highlighted = [row.preset_id for row in self._presets if row.highlight]
        return {
            "schema_version": "full-pipeline-demo-preset-catalog.v1",
            "matrix": self.matrix.status(),
            "preset_count": len(self._presets),
            "highlighted_frozen_anchor_count": len(highlighted),
            "highlighted_frozen_anchor_ids": highlighted,
            "production_overlay_loaded": self._production_overlay is not None,
            "production_roles": dict(self.production_roles),
            "default_preset_id": self.default_preset_id,
            "presets": [
                {
                    **row.to_dict(),
                    "production_role": self.production_role(row.preset_id),
                    "production_default": row.preset_id == self.default_preset_id,
                }
                for row in self._presets
            ],
        }

    def h2_payload(self) -> dict[str, object]:
        """Return the H2-only product catalog while retaining ``payload`` API."""

        values = self.h2_presets
        return {
            "schema_version": "h2-product-demo-preset-catalog.v1",
            "matrix": self.matrix.status(),
            "architecture": "H2",
            "preset_count": len(values),
            "default_preset_id": self.default_h2_preset_id,
            "primary_pipeline_id": H2_PRIMARY_PIPELINE_ID,
            "fallback_pipeline_id": H2_FALLBACK_PIPELINE_ID,
            "default_product_mode": H2_DEFAULT_PRODUCT_MODE,
            "product_modes": [
                {
                    "mode_id": row.mode_id,
                    "display_name": row.display_name,
                    "summary": row.summary,
                    "persistent_anonymous_labels": row.persistent_anonymous_labels,
                    "session_memory": row.session_memory,
                }
                for row in H2_PRODUCT_MODES
            ],
            "presets": [
                {
                    **row.to_dict(),
                    "h2_product_role": h2_pipeline_role(row.preset_id),
                    "product_default": row.preset_id == self.default_h2_preset_id,
                }
                for row in values
            ],
        }


def _load_production_overlay(
    path: Path,
    *,
    expected_sha256: str | None,
    known_pipeline_ids: set[str],
) -> dict[str, object]:
    source = Path(path).resolve(strict=True)
    expected = str(expected_sha256 or "").casefold()
    if len(expected) != 64 or any(
        character not in "0123456789abcdef" for character in expected
    ):
        raise ValueError("production overlay requires an expected SHA-256")
    observed = hashlib.sha256(source.read_bytes()).hexdigest()
    if observed != expected:
        raise ValueError("production overlay SHA-256 differs")
    value = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError("production overlay must be an object")
    expected_fields = {
        "schema_version": "full-pipeline-common-demo-production-overlay.v1",
        "scope_id": "full_pipeline_prompts_4_8_eight_day_c_only.v1",
        "scope_class": "BOUNDED_REDUCED",
        "original_full_scope_complete": False,
        "status": "PASS",
    }
    if any(value.get(key) != item for key, item in expected_fields.items()):
        raise ValueError("production overlay scope/schema/status differs")
    roles = value.get("roles")
    candidates = value.get("presets")
    if not isinstance(roles, Mapping) or not isinstance(candidates, list):
        raise ValueError("production overlay roles/presets are absent")
    selected = {
        str(role): str(pipeline_id)
        for role, pipeline_id in roles.items()
        if pipeline_id is not None
    }
    if "PRIMARY" not in selected or not 1 <= len(selected) <= 3:
        raise ValueError("production overlay must select a PRIMARY and at most 3 roles")
    if set(selected.values()) - known_pipeline_ids:
        raise ValueError("production overlay selects an unknown pipeline")
    if len(set(selected.values())) != len(selected):
        raise ValueError("production overlay assigns one pipeline to multiple roles")
    ready = {
        str(row.get("pipeline_id"))
        for row in candidates
        if isinstance(row, Mapping) and row.get("software_ready") is True
    }
    if set(selected.values()) != ready:
        raise ValueError("production overlay selected/ready pipeline inventory differs")
    if value.get("default_pipeline_id") != selected["PRIMARY"]:
        raise ValueError("production overlay default is not PRIMARY")
    return value


def _preset_from_selection(selection: PipelineSelection) -> PipelinePreset:
    row = dict(selection.matrix_row)
    frozen = bool(row.get("frozen_anchor_derived", False))
    threshold_value = row.get("frozen_anchor_score_threshold")
    threshold = float(threshold_value) if threshold_value is not None else None
    highlighted = frozen and selection.hybrid_label in {"H2", "H4", "H5"}
    warnings: list[str] = []
    if not highlighted or threshold is None:
        warnings.append("open_set_threshold_unresolved_known_name_release_disabled")
    heldout_warning = selection.diarization.get("heldout_warning")
    if heldout_warning:
        warnings.append(str(heldout_warning))
    asr_deployment = str(selection.asr.get("license_deployment_status", ""))
    if "REVIEW_REQUIRED" in asr_deployment:
        warnings.append(asr_deployment.lower())
    identity_deployment = str(selection.identity.get("license_deployment_status", ""))
    if "REVIEW_REQUIRED" in identity_deployment:
        warnings.append(identity_deployment.lower())
    provenance_warning = selection.identity.get("provenance_warning")
    if provenance_warning:
        warnings.append("identity_asset_provenance_review_required")
    asr_name = ASR_FRIENDLY_NAMES[selection.asr_alias]
    diarization_name = DIARIZATION_FRIENDLY_NAMES[selection.diarization_alias]
    identity_name = IDENTITY_FRIENDLY_NAMES[selection.identity_alias]
    return PipelinePreset(
        preset_id=selection.pipeline_id,
        display_name=(
            f"{selection.asr_alias} {asr_name} · "
            f"{selection.diarization_alias} {diarization_name} · "
            f"{selection.identity_alias} {identity_name} — {selection.hybrid_label}"
        ),
        protocol_version=selection.protocol_version,
        asr_alias=selection.asr_alias,
        asr_display_name=asr_name,
        diarization_alias=selection.diarization_alias,
        diarization_display_name=diarization_name,
        identity_alias=selection.identity_alias,
        identity_display_name=identity_name,
        hybrid_label=selection.hybrid_label,
        hybrid_status=str(selection.hybrid_policy.get("status", "unresolved")),
        frozen_anchor_derived=frozen,
        frozen_score_threshold=threshold,
        highlight="frozen_open_set_anchor" if highlighted else None,
        known_name_release_allowed=highlighted and threshold is not None,
        warning_codes=tuple(dict.fromkeys(warnings)),
        pipeline_config_sha256=selection.pipeline_config_sha256,
        runtime_config_sha256=selection.runtime_config_sha256,
        tier_a=str(row.get("tier_a", "")),
        tier_b=str(row.get("tier_b", "")),
        asr_identity=dict(selection.asr),
        diarization_identity=dict(selection.diarization),
        identity_backend=dict(selection.identity),
        enrollment_policy=dict(selection.enrollment_policy),
        hybrid_policy=dict(selection.hybrid_policy),
    )
