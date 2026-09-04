from __future__ import annotations

import hashlib

from app.full_pipeline_core_evaluation.selection import rank_digest, source_bucket


def test_rank_digest_is_exact_predeclared_utf8_contract() -> None:
    row = {"protocol_case_id": "fspcase_example"}
    expected = hashlib.sha256(
        b"prompt5_reduced_core_v1|5107|fspcase_example"
    ).hexdigest()

    assert rank_digest(row) == expected


def test_standard_asr_source_buckets_are_explicit() -> None:
    assert (
        source_bucket({"source_key": "standard_asr", "source_dataset": "cmu_arctic"})
        == "cmu_arctic"
    )
    assert (
        source_bucket({"source_key": "standard_asr", "source_dataset": "hifitts_eval"})
        == "hifitts"
    )
    assert (
        source_bucket(
            {"source_key": "standard_asr", "source_dataset": "librispeech_test"}
        )
        == "librispeech"
    )
    assert (
        source_bucket({"source_key": "standard_asr", "source_dataset": "voices_asr"})
        == "voices"
    )
