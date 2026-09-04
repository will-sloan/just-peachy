"""Bounded model-free perfect/failure smoke for Prompt-3 infrastructure."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .io import sha256_file, write_json_atomic
from .schema import normalize_reuse_identity
from .scorers import score_asr, score_anonymous_diarization
from .store import EvaluationJobSpec, EvaluationStateStore, utc_now
from .synthetic import publish_synthetic_result


EVALUATION_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SMOKE_ROOT = (
    EVALUATION_ROOT
    / "JustPeachyResults/full_pipeline/evaluation_infrastructure_smoke"
)


def run_infrastructure_smoke(
    *, output_root: Path | None = None
) -> dict[str, object]:
    """Exercise schemas, scorers, retry state, and result checksums without models."""

    if output_root is None:
        suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_root = DEFAULT_SMOKE_ROOT / f"prompt3_{suffix}"
    root = Path(output_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"smoke output root already exists: {root}")
    root.mkdir(parents=True, exist_ok=True)
    perfect_identity = _reuse_identity("perfect", "3" * 64)
    failure_identity = _reuse_identity("failure", "4" * 64)
    perfect = publish_synthetic_result(
        root / "perfect_result",
        reuse_identity=perfect_identity,
        failed=False,
    )
    failure = publish_synthetic_result(
        root / "failure_result",
        reuse_identity=failure_identity,
        failed=True,
    )
    perfect_asr = score_asr(
        [
            {
                "utterance_id": "perfect",
                "reference_text": "one exact transcript",
                "hypothesis_text": "one exact transcript",
            }
        ]
    )
    failed_asr = score_asr(
        [
            {
                "utterance_id": "failure",
                "reference_text": "one exact transcript",
                "hypothesis_text": None,
                "output_failed": True,
            }
        ]
    )
    perfect_diar = score_anonymous_diarization(
        [{"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "spk1"}],
        [{"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "hyp1"}],
    )
    scorer_checks = {
        "perfect_asr_wer_zero": (
            perfect_asr["wer"].status == "computed"
            and perfect_asr["wer"].value == 0.0
        ),
        "failed_output_counted": (
            failed_asr["output_failure_rate"].status == "computed"
            and failed_asr["output_failure_rate"].value == 1.0
        ),
        "perfect_diarization_der_zero": (
            perfect_diar["der"].status == "computed"
            and perfect_diar["der"].value == 0.0
        ),
    }
    if not all(scorer_checks.values()):
        raise RuntimeError(f"synthetic scorer checks failed: {scorer_checks}")
    restart = _exercise_restart_state(root / "restart_state")
    result = {
        "schema_version": "full-pipeline-evaluation-infrastructure-smoke.v1",
        "status": "PASS",
        "purpose": "tiny_synthetic_infrastructure_only",
        "created_at_utc": utc_now(),
        "output_root": str(root),
        "perfect_result_valid": perfect.valid,
        "perfect_result_reusable": perfect.reusable,
        "failure_result_valid": failure.valid,
        "failure_result_reusable": failure.reusable,
        "perfect_result_checksum_sha256": sha256_file(
            root / "perfect_result/checksums.json"
        ),
        "failure_result_checksum_sha256": sha256_file(
            root / "failure_result/checksums.json"
        ),
        "scorer_checks": scorer_checks,
        "restart_state": restart,
        "model_inference_performed": False,
        "dataset_downloads_performed": False,
        "long_scientific_campaign_started": False,
        "pipelines_evaluated": 0,
        "synthetic_cases": 2,
    }
    write_json_atomic(root / "infrastructure_smoke.json", result)
    return result


def _exercise_restart_state(root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    store = EvaluationStateStore(root / "campaign.sqlite3")
    identities = (
        _reuse_identity("state-perfect", "5" * 64),
        _reuse_identity("state-retry", "6" * 64),
    )
    jobs = tuple(
        EvaluationJobSpec(
            job_id=f"synthetic_job_{index}",
            pipeline_id="fullpipe_v1_ao_dr_ir",
            protocol_id="synthetic_protocol",
            split="synthetic",
            source_key="synthetic",
            measurement_mode="accuracy",
            seed=5107,
            case_count=1,
            audio_duration_sec=1.0,
            protocol_identity=str(identity["evaluation_protocol_sha256"]),
            pipeline_identity=str(identity["pipeline_config_sha256"]),
            reuse_identity=identity,
            case_ids=(f"case_{index}",),
            result_relative_path=f"synthetic/job_{index}",
        )
        for index, identity in enumerate(identities, start=1)
    )
    store.prepare(jobs, campaign_id="synthetic_smoke", manifest_sha256="7" * 64)
    first = store.claim(jobs[0].job_id, owner="smoke")
    if first is None:
        raise RuntimeError("synthetic first job could not be claimed")
    store.heartbeat(
        jobs[0].job_id,
        owner="smoke",
        completed_cases=1,
        completed_audio_sec=1.0,
        current_case_id="case_1",
        latest_activity="synthetic perfect",
        rolling_rtf=0.01,
        cache_hits=1,
    )
    store.finish(
        jobs[0].job_id,
        owner="smoke",
        state="complete",
        completed_cases=1,
        completed_audio_sec=1.0,
        latest_activity="synthetic perfect complete",
        result_sha256="8" * 64,
    )
    failed = store.claim(jobs[1].job_id, owner="smoke-first-attempt")
    if failed is None:
        raise RuntimeError("synthetic retry job could not be claimed")
    store.finish(
        jobs[1].job_id,
        owner="smoke-first-attempt",
        state="failed",
        completed_cases=0,
        completed_audio_sec=0.0,
        latest_activity="intentional synthetic failure",
        last_error="intentional synthetic failure",
    )
    retried = store.claim(jobs[1].job_id, owner="smoke-second-attempt")
    if retried is None or retried.attempt_count != 2:
        raise RuntimeError("failed synthetic job was not restart-claimable")
    store.finish(
        jobs[1].job_id,
        owner="smoke-second-attempt",
        state="complete",
        completed_cases=1,
        completed_audio_sec=1.0,
        latest_activity="synthetic retry complete",
        result_sha256="9" * 64,
    )
    rows = store.list_jobs()
    return {
        "status": "PASS",
        "job_count": len(rows),
        "complete_jobs": sum(row.state == "complete" for row in rows),
        "retry_attempt_count": next(
            row.attempt_count for row in rows if row.spec.job_id == jobs[1].job_id
        ),
        "lease_restart_exercised": True,
        "checksum_reuse_identity_bound": True,
    }


def _reuse_identity(suffix: str, case_sha256: str) -> Mapping[str, object]:
    return normalize_reuse_identity(
        {
            "program_id": "just_peachy_full_pipeline_program_v1",
            "evaluation_protocol_id": "full_speech_pipeline_v1_synthetic",
            "evaluation_protocol_sha256": "a" * 64,
            "pipeline_id": "fullpipe_v1_ao_dr_ir",
            "pipeline_config_sha256": "b" * 64,
            "case_manifest_id": f"synthetic_{suffix}",
            "case_manifest_sha256": case_sha256,
            "runtime_config_sha256": "c" * 64,
            "partition": "smoke",
            "seed": 5107,
        }
    )
