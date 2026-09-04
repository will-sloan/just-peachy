from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from scripts.verify_redimnet_stage10_execution_lock import (
    _canonical_json_sha256,
    _tree_identity,
    _yaml_selection,
)


def test_canonical_json_sha256_is_order_independent() -> None:
    assert _canonical_json_sha256({"b": 2, "a": 1}) == _canonical_json_sha256(
        {"a": 1, "b": 2}
    )


def test_yaml_selection_can_lock_one_list_entry(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "components": [
                    {"family": "speaker_embedding", "name": "other"},
                    {
                        "family": "speaker_embedding",
                        "name": "redimnet2_b2_speaker_embedding",
                        "dimension": 192,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    selected = _yaml_selection(
        path,
        {
            "selector": ["components"],
            "match": {
                "family": "speaker_embedding",
                "name": "redimnet2_b2_speaker_embedding",
            },
        },
    )
    assert selected["dimension"] == 192


def test_tree_identity_matches_registry_algorithm(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.py").write_bytes(b"alpha")
    (tmp_path / "nested" / "b.py").write_bytes(b"beta")
    digest = hashlib.sha256()
    for relative, payload in (("a.py", b"alpha"), ("nested/b.py", b"beta")):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(payload)).encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(payload).hexdigest().encode("ascii"))
        digest.update(b"\n")
    observed, total_bytes = _tree_identity(tmp_path)
    assert observed == digest.hexdigest().upper()
    assert total_bytes == 9
