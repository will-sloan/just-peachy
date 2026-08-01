from __future__ import annotations

from pathlib import Path

import pytest

from app.inference_pipeline.speaker_embedding import DeterministicFakeSpeakerEmbedding
from app.inference_pipeline.speaker_embedding.resemblyzer_adapter import (
    ResemblyzerSpeakerEmbeddingAdapter,
)
from app.inference_pipeline.speaker_embedding.sherpa_onnx_adapter import (
    SherpaOnnxSpeakerEmbeddingAdapter,
)
from app.inference_pipeline.speaker_embedding.speechbrain_adapter import (
    SpeechBrainECAPAAdapter,
)
from app.inference_pipeline.speaker_embedding.wespeaker_adapter import (
    WeSpeakerEmbeddingAdapter,
)
from scripts.enroll_speaker import REPO_ROOT, build_adapter, build_parser


@pytest.mark.parametrize(
    ("backend", "adapter_type"),
    [
        ("speechbrain", SpeechBrainECAPAAdapter),
        ("wespeaker", WeSpeakerEmbeddingAdapter),
        ("sherpa_onnx", SherpaOnnxSpeakerEmbeddingAdapter),
        ("resemblyzer", ResemblyzerSpeakerEmbeddingAdapter),
        ("fake", DeterministicFakeSpeakerEmbedding),
    ],
)
def test_enrollment_cli_builds_every_supported_embedding_backend(
    backend: str,
    adapter_type: type,
) -> None:
    args = build_parser().parse_args(
        [
            "--display-name",
            "Qualification Speaker",
            "--audio",
            "sample.wav",
            "--model-id",
            f"qualification_{backend}",
            "--backend",
            backend,
        ]
    )

    adapter = build_adapter(args)

    assert isinstance(adapter, adapter_type)
    assert adapter.model_name == f"qualification_{backend}"


def test_enrollment_backend_default_assets_are_repository_relative() -> None:
    parser = build_parser()
    common = [
        "--display-name",
        "Qualification Speaker",
        "--audio",
        "sample.wav",
        "--model-id",
        "qualification",
    ]

    speechbrain = build_adapter(parser.parse_args([*common, "--backend", "speechbrain"]))
    wespeaker = build_adapter(parser.parse_args([*common, "--backend", "wespeaker"]))
    sherpa = build_adapter(parser.parse_args([*common, "--backend", "sherpa_onnx"]))

    assert speechbrain.savedir == REPO_ROOT / "models/cache/speechbrain/spkrec-ecapa-voxceleb"
    assert Path(str(wespeaker.model_path)).is_absolute()
    assert Path(str(wespeaker.model_path)).is_relative_to(REPO_ROOT)
    assert Path(str(sherpa.model_path)).is_absolute()
    assert Path(str(sherpa.model_path)).is_relative_to(REPO_ROOT)


def test_enrollment_cli_preserves_explicit_absolute_model_path(tmp_path: Path) -> None:
    model_path = tmp_path / "custom.onnx"
    args = build_parser().parse_args(
        [
            "--display-name",
            "Qualification Speaker",
            "--audio",
            "sample.wav",
            "--model-id",
            "custom_sherpa",
            "--backend",
            "sherpa_onnx",
            "--model-path",
            str(model_path),
        ]
    )

    adapter = build_adapter(args)

    assert Path(str(adapter.model_path)) == model_path
