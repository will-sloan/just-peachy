from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

import scripts.audit_h2_enrollment_firewall as audit


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(_json_bytes(row) for row in rows))


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    tool_root = tmp_path / "tool"
    protocol_root = tool_root / "benchmarks/full_pipeline/full_speech_pipeline_v1"
    workspace = tool_root / "automated_runs/h2_complete_product_pipeline_v14"
    results_root = tool_root / "results/h2_complete_product_pipeline_v14"
    protocol_root.mkdir(parents=True)
    workspace.mkdir(parents=True)
    results_root.mkdir(parents=True)
    monkeypatch.setattr(audit, "TOOL_ROOT", tool_root)

    summary = {
        "schema_version": "full-speech-pipeline.v1",
        "protocol_id": "full_speech_pipeline_fixture",
        "development_evaluation_enrollment_gallery_speaker_disjoint": True,
        "primary_development_evaluation_speaker_disjoint": True,
        "evaluation_only": True,
        "training_eligible": False,
        "downloads_attempted": False,
        "audio_copied_or_modified": False,
        "development_identity": {"partition_id": "development_fixture"},
        "evaluation_identity": {"partition_id": "evaluation_fixture"},
    }
    summary_path = protocol_root / "protocol_summary.json"
    summary_path.write_bytes(_json_bytes(summary))

    def registry_row(split: str) -> dict[str, object]:
        return {
            "schema_version": "enrollment-registry.v1",
            "partition": split,
            "enrolled_id": f"{split}_enrolled",
            "global_speaker_id": f"{split}_speaker",
            "source_protocol_ids": ["controlled_v1"],
            "reserved_enrollment_clips": [
                {
                    "duration_sec": 2.0,
                    "logical_audio_path": f"audio/{split}_clip.wav",
                    "source_audio_sha256": (
                        "1" * 64 if split == "development" else "2" * 64
                    ),
                    "source_clip_id": f"{split}_clip",
                }
            ],
        }

    def case_row(split: str) -> dict[str, object]:
        prefix = "d" if split == "development" else "e"
        return {
            "schema_version": "full-speech-pipeline-case.v1",
            "partition": split,
            "protocol_case_id": f"{split}_case",
            "audio_sha256": prefix * 64,
            "pcm_sha256": ("a" if split == "development" else "b") * 64,
            "source_reference_id": f"{split}_reference",
            "source_case_id": f"{split}_source_case",
            "global_speaker_ids": [f"{split}_speaker"],
            "gallery_enrolled_ids": [f"{split}_enrolled"],
        }

    for split in ("development", "evaluation"):
        _write_jsonl(
            protocol_root / split / "enrollment/enrollment_registry.jsonl",
            [registry_row(split)],
        )
        _write_jsonl(
            protocol_root / split / "case_manifest.jsonl", [case_row(split)]
        )

    protocol_manifest = {
        "schema_version": "h2-product-protocol.v1",
        "protocol_id": "h2_fixture_protocol",
        "prepared_protocol_root": str(protocol_root.resolve()),
        "prepared_protocol_summary_sha256": _sha(summary_path.read_bytes()),
    }
    (workspace / "protocol_manifest.json").write_bytes(
        _json_bytes(protocol_manifest)
    )
    job_manifest = {
        "schema_version": "h2-job-manifest.v1",
        "jobs": [
            {
                "job_id": "evaluation_job",
                "split": "evaluation",
                "identity_sha256": "c" * 64,
            }
        ],
    }
    (workspace / "job_manifest.json").write_bytes(_json_bytes(job_manifest))
    (workspace / "runtime_implementation_identity.json").write_bytes(
        _json_bytes(
            {
                "schema_version": "h2-runtime-implementation-identity.v2",
                "identity_sha256": "f" * 64,
            }
        )
    )
    (workspace / "program_state.json").write_bytes(
        _json_bytes(
            {
                "schema_version": "h2-product-program-state.v1",
                "status": "RUNNING",
                "results_root": str(results_root.resolve()),
                "jobs": {
                    "evaluation_job": {
                        "state": "PENDING",
                        "attempt_count": 0,
                        "result_path": None,
                        "result_sha256": None,
                    }
                },
            }
        )
    )
    with sqlite3.connect(workspace / "campaign.sqlite3") as connection:
        connection.executescript(
            """
            CREATE TABLE jobs(
                job_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                attempt_count INTEGER NOT NULL
            );
            CREATE TABLE attempts(
                job_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL
            );
            INSERT INTO jobs VALUES ('evaluation_job', 'pending', 0);
            """
        )
    return workspace, protocol_root


def test_audit_proves_disjoint_enrollment_and_heldout_preopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _protocol_root = _fixture(tmp_path, monkeypatch)

    receipt = audit.build_receipt(workspace=workspace)
    validated = audit.validate_receipt(receipt)

    assert validated["status"] == "VALID"
    assert validated["partitions"]["development"]["registry_rows"] == 1
    assert validated["partitions"]["evaluation"]["registry_rows"] == 1
    assert all(
        value == 0
        for group in validated["cross_partition_overlap_counts"].values()
        for value in group.values()
    )
    assert validated["heldout_preopen"]["all_evaluation_jobs_pending"] is True
    assert validated["heldout_preopen"]["evaluation_attempt_count"] == 0
    assert len(validated["source_file_inventory"]) == 5


def test_run_audit_publishes_small_signed_metadata_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _protocol_root = _fixture(tmp_path, monkeypatch)
    output = workspace / "engineering_validation/firewall.json"

    receipt = audit.run_audit(workspace=workspace, output=output)

    assert output.is_file()
    assert output.stat().st_size < 32 * 1024
    assert audit.validate_receipt(json.loads(output.read_text())) == receipt
    assert receipt["evidence_boundaries"]["audio_opened_or_copied"] is False
    assert (
        receipt["evidence_boundaries"][
            "embeddings_or_biometric_templates_opened_or_copied"
        ]
        is False
    )


def test_audit_fails_closed_on_cross_split_speaker_overlap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, protocol_root = _fixture(tmp_path, monkeypatch)
    path = protocol_root / "evaluation/enrollment/enrollment_registry.jsonl"
    row = json.loads(path.read_text())
    row["global_speaker_id"] = "development_speaker"
    _write_jsonl(path, [row])

    with pytest.raises(
        audit.EnrollmentFirewallAuditError,
        match="identity or source overlap",
    ):
        audit.build_receipt(workspace=workspace)


def test_receipt_validation_detects_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, _protocol_root = _fixture(tmp_path, monkeypatch)
    receipt = audit.build_receipt(workspace=workspace)
    receipt["heldout_preopen"]["evaluation_attempt_count"] = 1

    with pytest.raises(ValueError, match="signature"):
        audit.validate_receipt(receipt)
