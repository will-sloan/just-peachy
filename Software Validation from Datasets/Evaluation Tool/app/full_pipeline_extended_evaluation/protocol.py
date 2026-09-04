"""Outcome-independent bounded Prompt-6 panel and job construction."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
import hashlib
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from app.benchmark_contracts.rir_registry import RIRRegistry, load_condition_sets
from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from app.full_pipeline_evaluation.planning import (
    MATRIX_PATH,
    RUNTIME_CONFIG_PATH,
    build_campaign_manifest,
)
from app.full_pipeline_evaluation.schema import normalize_reuse_identity
from app.full_pipeline_evaluation.store import EvaluationJobSpec

from . import (
    RELIABILITY_FAULTS,
    NOMINAL_STAGE_TARGET_HOURS,
    SCOPE_CLASS,
    SCOPE_ID,
    SELECTION_SEED,
    scope_fields,
)
from .io import ExtendedEvaluationError, ensure_c_drive


PANEL_CAPS = {
    "true_streaming_asr": 24,
    "online_speaker": 24,
    "integrated": 8,
    "native_ami": 4,
    "native_chime6": 4,
    "native_voices": 24,
    "noise_rir": 12,
    "speaker_gallery_overlap_stress": 12,
}


def build_bounded_plan(
    cases: Sequence[Mapping[str, object]],
    *,
    protocol_summary: Mapping[str, object],
    extended_pipeline_ids: Sequence[str],
    workspace_root: Path,
    decision_policy_registry_sha256: str,
    enrollment_rows: Sequence[Mapping[str, object]],
    frozen_execution_contract: Mapping[str, object],
    deployment_context: Mapping[str, object],
) -> dict[str, object]:
    """Create fixed metadata/reference-only selection and execution identities."""

    workspace = ensure_c_drive(workspace_root, label="Prompt-6 workspace")
    rows = tuple(sorted((dict(row) for row in cases), key=_case_id))
    if not rows or any(_split(row) != "evaluation" for row in rows):
        raise ExtendedEvaluationError(
            "Prompt-6 selector requires the untouched evaluation metadata only"
        )
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    pipelines = tuple(str(item) for item in extended_pipeline_ids)
    if not pipelines or len(set(pipelines)) != len(pipelines):
        raise ExtendedEvaluationError("extended pipeline inventory is empty/duplicated")
    if set(pipelines) - set(matrix.pipeline_ids):
        raise ExtendedEvaluationError(
            "extended pipeline inventory contains unknown IDs"
        )
    execution_binding = _execution_contract_binding(frozen_execution_contract)
    deployment_binding = _deployment_context_binding(deployment_context, pipelines)
    representatives = _representatives(matrix, pipelines)
    selections = _select_panels(rows)
    _validate_panel_caps(selections)
    noise_rows = _noise_rir_rows(
        selections["noise_rir"], workspace / "materialized/noise_rir"
    )
    panel_rows = {**selections, "noise_rir": noise_rows}
    protocol_id = str(protocol_summary.get("protocol_id") or "")
    development_identity = _identity_sha(protocol_summary, "development")
    evaluation_identity = _identity_sha(protocol_summary, "evaluation")
    panel_pipelines: dict[str, tuple[str, ...]] = {
        "true_streaming_asr": tuple(representatives["asr"]),
        "online_speaker": tuple(representatives["hybrid"]),
        "integrated": pipelines,
        "native_ami": tuple(representatives["diarization"]),
        "native_chime6": tuple(representatives["diarization"]),
        "native_voices": tuple(representatives["asr"]),
        "noise_rir": pipelines,
        "speaker_gallery_overlap_stress": pipelines,
    }
    realtime_panels = {"true_streaming_asr", "online_speaker", "integrated"}
    job_records: list[dict[str, object]] = []
    panel_manifests: dict[str, object] = {}
    for panel_id in PANEL_CAPS:
        selected = panel_rows[panel_id]
        manifest, raw_jobs = build_campaign_manifest(
            selected,
            protocol_id=protocol_id,
            development_identity=development_identity,
            evaluation_identity=evaluation_identity,
            seed=SELECTION_SEED,
            pipeline_ids=panel_pipelines[panel_id],
            measurement_modes=("accuracy",),
            campaign_stage=f"prompt6_reduced_8day_{panel_id}",
            decision_policy_registry_sha256=decision_policy_registry_sha256,
        )
        panel_manifests[panel_id] = {
            "campaign_id": manifest["campaign_id"],
            "campaign_identity_sha256": manifest["campaign_identity_sha256"],
            "selected_case_ids": [_case_id(row) for row in selected],
            "selected_case_sha256": _line_hash(_case_id(row) for row in selected),
            "case_count": len(selected),
            "pipeline_ids": list(panel_pipelines[panel_id]),
            "logical_pipeline_case_count": len(selected)
            * len(panel_pipelines[panel_id]),
            "native_realtime_pacing": panel_id in realtime_panels,
            "metric_support_contract": _metric_support(panel_id),
        }
        case_index = {_case_id(row): row for row in selected}
        for raw_spec in raw_jobs:
            spec = replace(raw_spec, result_relative_path=raw_spec.job_id)
            job_records.append(
                {
                    "job_id": spec.job_id,
                    "engine": "scored_runtime",
                    "panel_id": panel_id,
                    "measurement_class": "accuracy",
                    "runtime_pace": 1.0 if panel_id in realtime_panels else 0.0,
                    "spec": spec.to_jsonable(),
                    "cases": [case_index[case_id] for case_id in spec.case_ids],
                    "metric_support_contract": _metric_support(panel_id),
                }
            )

    long_sources = _select_distinct_long_sources(selections["integrated"])
    hardening_inputs = _hardening_input_plan(
        selections["integrated"],
        enrollment_rows,
        workspace,
        long_sources=long_sources,
    )
    for pipeline_id in pipelines:
        for index, source in enumerate(long_sources, start=1):
            provenance = _audio_provenance(source)
            job_records.append(
                _custom_job(
                    matrix=matrix,
                    protocol_id=protocol_id,
                    evaluation_identity=evaluation_identity,
                    pipeline_id=pipeline_id,
                    panel_id="long_session",
                    discriminator=f"stream_{index}",
                    source_case_id=_case_id(source),
                    duration_sec=1800.0,
                    engine="long_stream_runtime",
                    extra={
                        "stream_index": index,
                        "source_case": source,
                        "source_provenance": provenance,
                        "long_stream_input_id": f"prompt6_long_stream_{index}",
                        "target_duration_sec": 1800.0,
                        # These are deliberately wall-clock, stateful streams.
                        # Accelerated replay would not exercise the long-lived
                        # native queues/state required by Prompt 6.
                        "runtime_pace": 1.0,
                    },
                )
            )
        for fault in RELIABILITY_FAULTS:
            duration = 60.0 if fault == "continuous_session" else 30.0
            job_records.append(
                _custom_job(
                    matrix=matrix,
                    protocol_id=protocol_id,
                    evaluation_identity=evaluation_identity,
                    pipeline_id=pipeline_id,
                    panel_id="reliability",
                    discriminator=fault,
                    source_case_id=_case_id(selections["integrated"][0]),
                    duration_sec=duration,
                    engine="reliability_runtime",
                    extra={
                        "fault_id": fault,
                        "source_case": selections["integrated"][0],
                        "target_duration_sec": duration,
                    },
                )
            )
        job_records.append(
            _custom_job(
                matrix=matrix,
                protocol_id=protocol_id,
                evaluation_identity=evaluation_identity,
                pipeline_id=pipeline_id,
                panel_id="serial_resources",
                discriminator="cold_warm_measured",
                source_case_id=_case_id(selections["integrated"][0]),
                duration_sec=360.0,
                engine="serial_resource_runtime",
                measurement_mode="resources",
                extra={
                    "source_case": selections["integrated"][0],
                    "cold_start_required": True,
                    "warmup_duration_sec": 60.0,
                    "measured_duration_sec": 300.0,
                    "runtime_pace": 1.0,
                },
            )
        )

    job_records.sort(key=lambda row: str(row["job_id"]))
    if len({str(row["job_id"]) for row in job_records}) != len(job_records):
        raise ExtendedEvaluationError("Prompt-6 job IDs are not unique")
    selection_inventory = _selection_inventory(rows, selections)
    core = {
        "schema_version": "full-pipeline-extended-bounded-plan.v1",
        **scope_fields(),
        "status": "FROZEN_NOT_STARTED",
        "selection_seed": SELECTION_SEED,
        "selection_inputs": ["metadata", "references"],
        "outcome_dependent_selection": False,
        "prompt5_scientific_outcome_tables_opened_for_selection": False,
        "prompt5_deployment_evidence_opened_for_reporting": True,
        "deployment_evidence_used_as_filter": False,
        "pipeline_membership_changed_after_heldout": False,
        "pipeline_ids": list(pipelines),
        "pipeline_count": len(pipelines),
        "representatives": representatives,
        "panel_caps": dict(PANEL_CAPS),
        "panels": panel_manifests,
        "selection_inventory": selection_inventory,
        "jobs": job_records,
        "job_count": len(job_records),
        "accuracy_job_count": sum(
            row["measurement_class"] == "accuracy" for row in job_records
        ),
        "resource_job_count": sum(
            row["measurement_class"] == "resources" for row in job_records
        ),
        "accuracy_maximum_concurrency": 2,
        "resource_concurrency": 1,
        "nominal_stage_planning_target_hours": NOMINAL_STAGE_TARGET_HOURS,
        "elapsed_time_kill_switch_enabled": False,
        "reliability_fault_ids": list(RELIABILITY_FAULTS),
        "reliability_fault_duration_policy_sec": {"minimum": 30, "maximum": 60},
        "long_streams_per_pipeline": 2,
        "long_stream_duration_sec": 1800,
        "serial_resource_method": {
            "cold_start": True,
            "warmup_sec": 60,
            "measured_sec": 300,
            "energy_claim_supported": False,
            "beaker_power_claim_supported": False,
        },
        "hardening_input_plan": hardening_inputs,
        "decision_policy_registry_sha256": decision_policy_registry_sha256,
        "frozen_execution_contract": execution_binding,
        "deployment_context": deployment_binding,
        "matrix_sha256": sha256_file(MATRIX_PATH),
        "runtime_config_sha256": sha256_file(RUNTIME_CONFIG_PATH),
    }
    return {**core, "plan_identity_sha256": sha256_bytes(canonical_json_bytes(core))}


def validate_plan(value: Mapping[str, object]) -> None:
    if value.get("schema_version") != "full-pipeline-extended-bounded-plan.v1":
        raise ExtendedEvaluationError("Prompt-6 plan schema differs")
    if value.get("scope_id") != SCOPE_ID or value.get("scope_class") != SCOPE_CLASS:
        raise ExtendedEvaluationError("Prompt-6 plan scope differs")
    if value.get("original_full_scope_complete") is not False:
        raise ExtendedEvaluationError("Prompt-6 plan overclaims original scope")
    if value.get("selection_seed") != SELECTION_SEED:
        raise ExtendedEvaluationError("Prompt-6 selection seed differs")
    if value.get("panel_caps") != PANEL_CAPS:
        raise ExtendedEvaluationError("Prompt-6 panel caps differ")
    if value.get("outcome_dependent_selection") is not False:
        raise ExtendedEvaluationError("Prompt-6 plan is outcome-dependent")
    if (
        value.get("deployment_evidence_used_as_filter") is not False
        or value.get("pipeline_membership_changed_after_heldout") is not False
    ):
        raise ExtendedEvaluationError("deployment evidence altered Prompt-6 membership")
    if value.get("matrix_sha256") != sha256_file(MATRIX_PATH):
        raise ExtendedEvaluationError("live full-pipeline matrix changed after freeze")
    if value.get("runtime_config_sha256") != sha256_file(RUNTIME_CONFIG_PATH):
        raise ExtendedEvaluationError("live full-pipeline runtime changed after freeze")
    _execution_contract_binding(
        value.get("frozen_execution_contract")
        if isinstance(value.get("frozen_execution_contract"), Mapping)
        else {}
    )
    _deployment_context_binding(
        value.get("deployment_context")
        if isinstance(value.get("deployment_context"), Mapping)
        else {},
        tuple(str(item) for item in value.get("pipeline_ids", [])),
    )
    _validate_long_stream_jobs(value)
    unsigned = dict(value)
    claimed = unsigned.pop("plan_identity_sha256", None)
    if claimed != sha256_bytes(canonical_json_bytes(unsigned)):
        raise ExtendedEvaluationError("Prompt-6 plan identity differs")


def plan_specs(value: Mapping[str, object]) -> tuple[EvaluationJobSpec, ...]:
    validate_plan(value)
    raw_jobs = value.get("jobs")
    if not isinstance(raw_jobs, list):
        raise ExtendedEvaluationError("Prompt-6 plan jobs are absent")
    return tuple(
        EvaluationJobSpec.from_jsonable(row["spec"])
        for row in raw_jobs
        if isinstance(row, Mapping) and isinstance(row.get("spec"), Mapping)
    )


def _select_panels(
    rows: Sequence[dict[str, object]],
) -> dict[str, tuple[dict[str, object], ...]]:
    asr_groups = {
        "commonvoice": lambda row: row.get("source_key") == "commonvoice_60plus_asr",
        "librispeech": lambda row: row.get("source_dataset") == "librispeech",
        "cmu_arctic": lambda row: row.get("source_dataset") == "cmu_arctic",
        "hifitts": lambda row: row.get("source_dataset") == "hifitts",
        "controlled": lambda row: row.get("source_key") == "controlled_v1",
        "product": lambda row: row.get("source_key") == "product_v2",
    }
    asr: list[dict[str, object]] = []
    for name, predicate in asr_groups.items():
        candidates = [row for row in rows if predicate(row) and _supports(row, "asr")]
        asr.extend(_hash_take(candidates, 4, f"asr:{name}"))

    online: list[dict[str, object]] = []
    for source in ("controlled_v1", "product_v2"):
        for overlay in ("ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"):
            candidates = [
                row
                for row in rows
                if row.get("source_key") == source and row.get("overlay_id") == overlay
            ]
            online.extend(_hash_take(candidates, 4, f"online:{source}:{overlay}"))
    online = list(_unique(online))
    integrated = _balanced_take(
        online,
        8,
        key=lambda row: (
            str(row.get("source_key")),
            str(row.get("overlay_id")),
            str(row.get("scenario_id")),
        ),
        salt="integrated",
    )

    ami = _unique_recording_take(
        [
            row
            for row in rows
            if row.get("source_dataset") == "ami"
            and row.get("der_jer_eligible") is True
            and row.get("cpwer_eligible") is True
            and _supports(row, "asr")
            and _supports(row, "diarization")
            and _supports(row, "speaker_attributed_transcript")
        ],
        4,
        "native:ami",
    )
    chime = _unique_recording_take(
        [
            row
            for row in rows
            if row.get("source_dataset") == "chime6"
            and row.get("der_jer_eligible") is True
            and _supports(row, "diarization")
        ],
        4,
        "native:chime6",
    )
    voices = _hash_take(
        [
            row
            for row in rows
            if row.get("source_dataset") == "voices"
            and _supports(row, "asr")
            and isinstance(row.get("reference_text"), str)
            and bool(str(row.get("reference_text") or "").strip())
        ],
        24,
        "native:voices",
    )
    product = [row for row in rows if row.get("source_key") == "product_v2"]
    noise_bases = _balanced_take(
        product,
        12,
        key=lambda row: (
            str(row.get("scenario_id")),
            str(row.get("overlay_id")),
        ),
        salt="noise-rir",
    )
    stress = _balanced_take(
        product,
        12,
        key=lambda row: (
            str(row.get("overlap")),
            str(row.get("gallery_requested_size")),
            str(row.get("scenario_id")),
        ),
        salt="speaker-stress",
    )
    return {
        "true_streaming_asr": tuple(sorted(asr, key=_case_id)),
        "online_speaker": tuple(sorted(online, key=_case_id)),
        "integrated": tuple(sorted(integrated, key=_case_id)),
        "native_ami": tuple(sorted(ami, key=_case_id)),
        "native_chime6": tuple(sorted(chime, key=_case_id)),
        "native_voices": tuple(sorted(voices, key=_case_id)),
        "noise_rir": tuple(sorted(noise_bases, key=_case_id)),
        "speaker_gallery_overlap_stress": tuple(sorted(stress, key=_case_id)),
    }


def _noise_rir_rows(
    bases: Sequence[Mapping[str, object]], destination: Path
) -> tuple[dict[str, object], ...]:
    conditions = load_condition_sets(RIRRegistry.load())["core_controlled"]
    nonclean = [row for row in conditions if row.get("augmentation") != "none"]
    if len(nonclean) < 4:
        raise ExtendedEvaluationError("core controlled augmentation set is too small")
    selected_conditions = nonclean[:4]
    result: list[dict[str, object]] = []
    for index, base in enumerate(bases):
        condition = dict(selected_conditions[index % len(selected_conditions)])
        case_id = f"{_case_id(base)}__p6_{condition['id']}"
        current = dict(base)
        current.update(
            {
                "protocol_case_id": case_id,
                "source_key": "prompt6_noise_rir",
                "source_protocol_id": "prompt6_noise_rir_seed3800.v1",
                "scoring_stratum": "prompt6_noise_rir",
                "audio_path": str((destination / f"{case_id}.wav").resolve()),
                "audio_sha256": None,
                "augmentation_condition": condition,
                "augmentation_seed": SELECTION_SEED,
                "augmentation_outcome_independent": True,
                "source_audio_logical_path": base.get("audio_logical_path"),
                "source_audio_sha256": base.get("audio_sha256"),
            }
        )
        current.pop("audio_logical_path", None)
        result.append(current)
    return tuple(sorted(result, key=_case_id))


def _representatives(
    matrix: FullPipelineMatrix, pipelines: Sequence[str]
) -> dict[str, list[str]]:
    selections = [matrix.resolve(pipeline_id) for pipeline_id in pipelines]

    def choose(groups: Mapping[str, list[object]]) -> list[str]:
        result: list[str] = []
        for key in sorted(groups):
            candidates = groups[key]
            selected = min(
                candidates,
                key=lambda item: (
                    getattr(item, "asr_alias") != "AO",
                    getattr(item, "hybrid_label") != "H2",
                    getattr(item, "pipeline_id"),
                ),
            )
            result.append(str(getattr(selected, "pipeline_id")))
        return result

    asr: dict[str, list[object]] = defaultdict(list)
    hybrid: dict[str, list[object]] = defaultdict(list)
    diarization: dict[str, list[object]] = defaultdict(list)
    for selection in selections:
        asr[selection.asr_alias].append(selection)
        hybrid[
            f"{selection.diarization['embedding_backend_id']}+"
            f"{selection.identity['backend_id']}"
        ].append(selection)
        diarization[str(selection.diarization["embedding_backend_id"])].append(
            selection
        )
    if set(asr) != {"AO", "AG"}:
        raise ExtendedEvaluationError("extended set does not cover both ASR backends")
    return {
        "asr": choose(asr),
        "hybrid": choose(hybrid),
        "diarization": choose(diarization),
    }


def _custom_job(
    *,
    matrix: FullPipelineMatrix,
    protocol_id: str,
    evaluation_identity: str,
    pipeline_id: str,
    panel_id: str,
    discriminator: str,
    source_case_id: str,
    duration_sec: float,
    engine: str,
    extra: Mapping[str, object],
    measurement_mode: str = "accuracy",
) -> dict[str, object]:
    selection = matrix.resolve(pipeline_id)
    case_contract = {
        "panel_id": panel_id,
        "discriminator": discriminator,
        "source_case_id": source_case_id,
        "duration_sec": duration_sec,
        "engine": engine,
        "extra": dict(extra),
    }
    case_sha = sha256_bytes(canonical_json_bytes(case_contract))
    reuse = normalize_reuse_identity(
        {
            "program_id": "just_peachy_full_pipeline_program_v1",
            "evaluation_protocol_id": protocol_id,
            "evaluation_protocol_sha256": evaluation_identity,
            "pipeline_id": pipeline_id,
            "pipeline_config_sha256": selection.pipeline_config_sha256,
            "case_manifest_id": f"prompt6:{panel_id}:{discriminator}",
            "case_manifest_sha256": case_sha,
            "runtime_config_sha256": selection.runtime_config_sha256,
            "partition": "evaluation",
            "seed": SELECTION_SEED,
        }
    )
    job_id = (
        f"p6_{panel_id}_{pipeline_id.removeprefix('fullpipe_v1_')}_"
        f"{_portable(discriminator)}_{str(reuse['identity_sha256'])[:12]}"
    )
    spec = EvaluationJobSpec(
        job_id=job_id,
        pipeline_id=pipeline_id,
        protocol_id=protocol_id,
        split="evaluation",
        source_key=panel_id,
        measurement_mode=measurement_mode,
        seed=SELECTION_SEED,
        case_count=1,
        audio_duration_sec=duration_sec,
        protocol_identity=evaluation_identity,
        pipeline_identity=selection.pipeline_config_sha256,
        reuse_identity=reuse,
        case_ids=(source_case_id,),
        result_relative_path=job_id,
    )
    return {
        "job_id": job_id,
        "engine": engine,
        "panel_id": panel_id,
        "measurement_class": measurement_mode,
        "spec": spec.to_jsonable(),
        **dict(extra),
    }


def _hardening_input_plan(
    integrated: Sequence[Mapping[str, object]],
    enrollment_rows: Sequence[Mapping[str, object]],
    workspace: Path,
    *,
    long_sources: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not integrated:
        raise ExtendedEvaluationError("hardening input plan has no source session")
    source = min(integrated, key=lambda row: _rank(row, "hardening-long"))
    enrolled = sorted(
        (dict(row) for row in enrollment_rows),
        key=lambda row: _rank(row, "hardening-enrollment"),
    )[:3]
    if len(enrolled) != 3:
        raise ExtendedEvaluationError("hardening input plan needs three enrollments")
    samples: list[dict[str, object]] = []
    for index, row in enumerate(enrolled, start=1):
        clips = row.get("reserved_enrollment_clips")
        if not isinstance(clips, list) or not clips:
            raise ExtendedEvaluationError("hardening enrollment has no reserved clips")
        clip = min(
            (dict(item) for item in clips if isinstance(item, Mapping)),
            key=lambda item: _rank(item, f"hardening-clip:{index}"),
        )
        samples.append(
            {
                "input_id": f"enrollment_sample_{index}",
                "destination_path": str(
                    (
                        workspace
                        / f"materialized/hardening/enrollment_sample_{index}.wav"
                    ).resolve()
                ),
                "roles": ["enrollment_sample"],
                "enrolled_id": row.get("enrolled_id"),
                "source_logical_path": clip.get("logical_audio_path"),
                "source_sha256": clip.get("source_audio_sha256"),
                "source_duration_sec": clip.get("duration_sec"),
                "capture_method": "frozen_reserved_enrollment_clip_transcode",
            }
        )
    long_stream_inputs: list[dict[str, object]] = []
    for index, stream_source in enumerate(long_sources, start=1):
        provenance = _audio_provenance(stream_source)
        long_stream_inputs.append(
            {
                "input_id": f"prompt6_long_stream_{index}",
                "destination_path": str(
                    (
                        workspace
                        / f"materialized/long_streams/stream_{index}_1800s.wav"
                    ).resolve()
                ),
                "roles": ["prompt6_long_stream"],
                "target_duration_sec": 1800.0,
                "source_case_id": _case_id(stream_source),
                "source_logical_path": provenance["audio_logical_path"],
                "source_sha256": provenance["audio_sha256"],
                "source_provenance": provenance,
                "capture_method": "deterministic_repeated_distinct_frozen_panel_audio",
            }
        )
    return {
        "schema_version": "full-pipeline-hardening-input-plan.v1",
        "outcome_independent": True,
        "long_input": {
            "input_id": "hardening_loopback_3600s",
            "destination_path": str(
                (
                    workspace / "materialized/hardening/hardening_loopback_3600s.wav"
                ).resolve()
            ),
            "roles": [
                "deterministic_replay",
                "controlled_loopback",
                "repeated_session",
                "soak",
            ],
            "target_duration_sec": 3600.0,
            "source_case_id": _case_id(source),
            "source_logical_path": source.get("audio_logical_path"),
            "source_sha256": source.get("audio_sha256"),
            "capture_method": "deterministic_repeated_frozen_panel_audio",
        },
        "long_stream_inputs": long_stream_inputs,
        "enrollment_samples": samples,
    }


def _execution_contract_binding(value: Mapping[str, object]) -> dict[str, object]:
    if value.get("execution_contract_validation") != "EXACT_LIVE_MATCH":
        raise ExtendedEvaluationError(
            "Prompt-6 requires an exact frozen/live execution proof"
        )
    code_sha = str(value.get("live_result_affecting_code_sha256") or "").casefold()
    checksums_sha = str(value.get("checksums_sha256") or "").casefold()
    identities = value.get("pipeline_freeze_identity_sha256s")
    if (
        len(code_sha) != 64
        or len(checksums_sha) != 64
        or not isinstance(identities, Mapping)
        or len(identities) != 18
    ):
        raise ExtendedEvaluationError("Prompt-6 execution proof is incomplete")
    normalized = {str(key): str(item).casefold() for key, item in identities.items()}
    if any(len(item) != 64 for item in normalized.values()):
        raise ExtendedEvaluationError("Prompt-6 frozen pipeline identity is invalid")
    core = {
        "execution_contract_validation": "EXACT_LIVE_MATCH",
        "checksums_sha256": checksums_sha,
        "live_result_affecting_code_sha256": code_sha,
        "pipeline_freeze_identity_sha256s": dict(sorted(normalized.items())),
    }
    binding_sha = sha256_bytes(canonical_json_bytes(core))
    claimed = value.get("binding_identity_sha256")
    if claimed is not None and str(claimed).casefold() != binding_sha:
        raise ExtendedEvaluationError("Prompt-6 execution-proof binding differs")
    return {
        **core,
        "binding_identity_sha256": binding_sha,
    }


def _deployment_context_binding(
    value: Mapping[str, object], pipeline_ids: Sequence[str]
) -> dict[str, object]:
    steering = value.get("raspberry_pi_deployment_steering")
    prompt5 = value.get("prompt5_deployment_evidence")
    extended = value.get("prompt4_extended_set")
    if not all(isinstance(item, Mapping) for item in (steering, prompt5, extended)):
        raise ExtendedEvaluationError("Prompt-6 deployment context is incomplete")
    assert isinstance(steering, Mapping)
    assert isinstance(prompt5, Mapping)
    assert isinstance(extended, Mapping)
    selected = [str(item) for item in pipeline_ids]
    mandatory = [str(item) for item in extended.get("mandatory_pipeline_ids", [])]
    challengers = [
        str(item) for item in extended.get("additional_challenger_pipeline_ids", [])
    ]
    frozen_ids = [str(item) for item in extended.get("extended_pipeline_ids", [])]
    if (
        selected != frozen_ids
        or mandatory + challengers != frozen_ids
        or len(mandatory) != 6
        or len(challengers) > 2
    ):
        raise ExtendedEvaluationError(
            "deployment context differs from the Prompt-4 predeclared extended set"
        )
    for raw, label in ((steering, "steering"), (prompt5, "Prompt-5 deployment")):
        path = ensure_c_drive(str(raw.get("path") or ""), label=label, must_exist=True)
        if sha256_file(path) != str(raw.get("sha256") or "").casefold():
            raise ExtendedEvaluationError(f"{label} deployment binding changed")
    extended_path = ensure_c_drive(
        str(extended.get("path") or ""), label="Prompt-4 extended set", must_exist=True
    )
    if sha256_file(extended_path) != str(extended.get("sha256") or "").casefold():
        raise ExtendedEvaluationError(
            "Prompt-4 extended-set deployment binding changed"
        )
    if (
        value.get("predeclared_membership_unchanged_after_heldout") is not True
        or value.get("deployment_evidence_used_as_filter") is not False
    ):
        raise ExtendedEvaluationError("Prompt-6 deployment firewall differs")
    return {
        "raspberry_pi_deployment_steering": dict(steering),
        "prompt5_deployment_evidence": dict(prompt5),
        "prompt4_extended_set": {
            "path": str(extended_path),
            "sha256": sha256_file(extended_path),
            "mandatory_pipeline_ids": mandatory,
            "additional_challenger_pipeline_ids": challengers,
            "extended_pipeline_ids": frozen_ids,
            "pipeline_count": len(frozen_ids),
        },
        "predeclared_membership_unchanged_after_heldout": True,
        "deployment_evidence_used_as_filter": False,
    }


def _audio_provenance(row: Mapping[str, object]) -> dict[str, object]:
    logical_path = str(
        row.get("audio_logical_path")
        or row.get("source_audio_logical_path")
        or row.get("audio_path")
        or ""
    )
    audio_sha = str(
        row.get("audio_sha256") or row.get("source_audio_sha256") or ""
    ).casefold()
    core = {
        "source_case_id": _case_id(row),
        "audio_logical_path": logical_path,
        "audio_sha256": audio_sha or None,
        "source_recording_id": row.get("source_recording_id"),
        "source_start_sec": row.get("source_start_sec"),
        "source_end_sec": row.get("source_end_sec"),
    }
    stable_source = {
        key: core[key]
        for key in (
            "audio_logical_path",
            "audio_sha256",
            "source_recording_id",
            "source_start_sec",
            "source_end_sec",
        )
    }
    if not logical_path and not audio_sha and not core["source_recording_id"]:
        raise ExtendedEvaluationError(
            f"long-stream source {_case_id(row)} has no audio provenance"
        )
    return {
        **core,
        "provenance_identity_sha256": sha256_bytes(canonical_json_bytes(stable_source)),
    }


def _select_distinct_long_sources(
    rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    selected: list[dict[str, object]] = []
    identities: set[str] = set()
    for raw in sorted(rows, key=lambda row: _rank(row, "long-stream-distinct")):
        row = dict(raw)
        identity = str(_audio_provenance(row)["provenance_identity_sha256"])
        if identity in identities:
            continue
        selected.append(row)
        identities.add(identity)
        if len(selected) == 2:
            return selected[0], selected[1]
    raise ExtendedEvaluationError(
        "Prompt-6 needs two provenance-distinct long-stream sources"
    )


def _validate_long_stream_jobs(plan: Mapping[str, object]) -> None:
    jobs = plan.get("jobs")
    pipelines = tuple(str(item) for item in plan.get("pipeline_ids", []))
    if not isinstance(jobs, list) or not pipelines:
        raise ExtendedEvaluationError("Prompt-6 long-stream inventory is absent")
    for pipeline_id in pipelines:
        selected = [
            row
            for row in jobs
            if isinstance(row, Mapping)
            and row.get("panel_id") == "long_session"
            and isinstance(row.get("spec"), Mapping)
            and row["spec"].get("pipeline_id") == pipeline_id
        ]
        identities = {
            str(
                dict(row.get("source_provenance") or {}).get(
                    "provenance_identity_sha256"
                )
            )
            for row in selected
        }
        if (
            len(selected) != 2
            or len(identities) != 2
            or any(float(row.get("runtime_pace") or 0.0) != 1.0 for row in selected)
            or any(
                float(row.get("target_duration_sec") or 0.0) != 1800.0
                for row in selected
            )
        ):
            raise ExtendedEvaluationError(
                f"Prompt-6 long-stream provenance contract differs for {pipeline_id}"
            )


def _selection_inventory(
    all_rows: Sequence[Mapping[str, object]],
    panels: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    all_ids = {_case_id(row) for row in all_rows}
    result: dict[str, object] = {}
    for panel_id, selected in panels.items():
        selected_ids = sorted({_case_id(row) for row in selected})
        excluded_ids = sorted(all_ids - set(selected_ids))
        result[panel_id] = {
            "selected_count": len(selected_ids),
            "selected_case_ids": selected_ids,
            "selected_case_ids_sha256": _line_hash(selected_ids),
            "excluded_count": len(excluded_ids),
            "excluded_case_ids_sha256": _line_hash(excluded_ids),
            "selection_rule": _selection_rule(panel_id),
        }
    return result


def selection_exclusions(
    all_rows: Sequence[Mapping[str, object]], plan: Mapping[str, object]
) -> Iterable[dict[str, object]]:
    inventory = plan.get("selection_inventory")
    if not isinstance(inventory, Mapping):
        raise ExtendedEvaluationError("plan selection inventory is missing")
    all_ids = sorted({_case_id(row) for row in all_rows})
    for panel_id, raw in sorted(inventory.items()):
        if not isinstance(raw, Mapping):
            continue
        selected = set(str(item) for item in raw.get("selected_case_ids", []))
        for case_id in all_ids:
            if case_id not in selected:
                yield {
                    "panel_id": str(panel_id),
                    "protocol_case_id": case_id,
                    "reason": "outside_fixed_hash_ranked_bounded_panel",
                    "selection_seed": SELECTION_SEED,
                }


def _validate_panel_caps(panels: Mapping[str, Sequence[object]]) -> None:
    observed = {key: len(panels.get(key, ())) for key in PANEL_CAPS}
    if observed != PANEL_CAPS:
        raise ExtendedEvaluationError(
            f"Prompt-6 bounded panel counts differ: {observed}"
        )


def _metric_support(panel_id: str) -> dict[str, object]:
    if panel_id == "native_chime6":
        return {
            "asr": "unsupported_no_complete_transcript_reference",
            "diarization": "supported_der_jer",
            "identity": "unsupported_no_leakage_safe_enrollment",
            "energy": "unsupported_no_energy_instrumentation",
        }
    if panel_id == "native_ami":
        return {
            "asr": "supported_only_where_complete_reference_declared",
            "diarization": "supported_der_jer",
            "identity": "unsupported_no_leakage_safe_enrollment",
            "cpwer": "supported_only_cpwer_eligible_cases",
            "energy": "unsupported_no_energy_instrumentation",
        }
    if panel_id == "native_voices":
        return {
            "asr": "supported_acoustic_diagnostic",
            "diarization": "unsupported_single_speaker_acoustic_panel",
            "identity": "unsupported_no_gallery",
            "energy": "unsupported_no_energy_instrumentation",
        }
    return {"declared_case_supported_views_enforced": True, "energy": "unsupported"}


def _selection_rule(panel_id: str) -> str:
    return {
        "true_streaming_asr": "4 hash-ranked cases from each of six fixed ASR strata",
        "online_speaker": "4 per source x known/mixed/unknown stratum",
        "integrated": "8 balanced source/overlay/scenario cases from online panel",
        "native_ami": "4 unique complete-reference cpWER+DER/JER recordings, seed 3800",
        "native_chime6": "4 unique DER/JER-eligible recordings, seed 3800",
        "native_voices": "24 complete-reference VOiCES ASR/acoustic cases",
        "noise_rir": "12 balanced Product-V2 bases with fixed core augmentation recipes",
        "speaker_gallery_overlap_stress": "12 balanced overlap/gallery/scenario cases",
    }[panel_id]


def _balanced_take(
    rows: Sequence[dict[str, object]],
    count: int,
    *,
    key: object,
    salt: str,
) -> list[dict[str, object]]:
    key_fn = key  # keep annotation concise for Python 3.10 compatibility
    grouped: dict[object, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[key_fn(row)].append(row)  # type: ignore[operator]
    for group_key in grouped:
        grouped[group_key].sort(key=lambda row: _rank(row, f"{salt}:{group_key}"))
    result: list[dict[str, object]] = []
    while len(result) < count and grouped:
        progressed = False
        for group_key in sorted(grouped, key=str):
            if grouped[group_key]:
                result.append(grouped[group_key].pop(0))
                progressed = True
                if len(result) == count:
                    break
        if not progressed:
            break
    if len(result) != count:
        raise ExtendedEvaluationError(
            f"balanced selector {salt} found {len(result)}/{count}"
        )
    return list(_unique(result))


def _hash_take(
    rows: Sequence[dict[str, object]], count: int, salt: str
) -> list[dict[str, object]]:
    if len(rows) < count:
        raise ExtendedEvaluationError(f"selector {salt} found {len(rows)}/{count}")
    return sorted(rows, key=lambda row: _rank(row, salt))[:count]


def _unique_recording_take(
    rows: Sequence[dict[str, object]],
    count: int,
    salt: str,
    *,
    prefer: object | None = None,
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = str(row.get("source_recording_id") or row.get("source_case_id"))
        grouped[key].append(row)
    selected: list[dict[str, object]] = []
    for recording_id, values in grouped.items():
        values.sort(
            key=lambda row: (
                0 if prefer is not None and prefer(row) else 1,  # type: ignore[operator]
                _rank(row, f"{salt}:{recording_id}"),
            )
        )
        selected.append(values[0])
    return _hash_take(selected, count, salt)


def _unique(rows: Iterable[dict[str, object]]) -> tuple[dict[str, object], ...]:
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        result.setdefault(_case_id(row), row)
    return tuple(result[key] for key in sorted(result))


def _supports(row: Mapping[str, object], view: str) -> bool:
    return view in {str(item) for item in row.get("supported_views", [])}


def _rank(row: Mapping[str, object], salt: str) -> str:
    identity = str(
        row.get("protocol_case_id")
        or row.get("enrolled_id")
        or row.get("source_clip_id")
        or canonical_json_bytes(dict(row)).hex()
    )
    return hashlib.sha256(f"{SELECTION_SEED}:{salt}:{identity}".encode()).hexdigest()


def _line_hash(values: Iterable[str]) -> str:
    return hashlib.sha256(("\n".join(sorted(values)) + "\n").encode()).hexdigest()


def _identity_sha(summary: Mapping[str, object], split: str) -> str:
    raw = summary.get(f"{split}_identity")
    if not isinstance(raw, Mapping):
        raise ExtendedEvaluationError(f"protocol summary lacks {split} identity")
    value = str(raw.get("identity_sha256") or "").casefold()
    if len(value) != 64:
        raise ExtendedEvaluationError(f"protocol {split} identity is invalid")
    return value


def _case_id(row: Mapping[str, object]) -> str:
    value = str(row.get("protocol_case_id") or row.get("case_id") or "")
    if not value:
        raise ExtendedEvaluationError("case ID is absent")
    return value


def _split(row: Mapping[str, object]) -> str:
    return str(row.get("split") or row.get("partition") or "")


def _portable(value: str) -> str:
    return "".join(char if char.isalnum() or char == "_" else "_" for char in value)


__all__ = [
    "PANEL_CAPS",
    "build_bounded_plan",
    "plan_specs",
    "selection_exclusions",
    "validate_plan",
]
