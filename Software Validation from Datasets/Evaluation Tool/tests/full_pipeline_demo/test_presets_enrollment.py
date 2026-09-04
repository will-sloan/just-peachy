from __future__ import annotations

import json
from pathlib import Path
import wave

import numpy as np

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline.models import EmbeddingResult, RawAudioFrame
from app.full_pipeline_demo.enrollment import (
    DEFAULT_ENROLLMENT_PROMPTS,
    EnrollmentService,
    LabelledWav,
)
from app.full_pipeline_demo.presets import PresetCatalog


EVALUATION_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
RUNTIME_PATH = EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml"


def _matrix() -> FullPipelineMatrix:
    return FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)


def _wav(path: Path, *, seconds: float = 4.0, amplitude: float = 0.1) -> Path:
    rate = 16000
    timebase = np.arange(round(rate * seconds), dtype=np.float32) / rate
    samples = amplitude * np.sin(2 * np.pi * 220 * timebase)
    pcm = np.round(np.clip(samples, -1, 1) * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())
    return path


class _FakeEmbedder:
    def __init__(self, binding: object, vectors: list[list[float]]) -> None:
        self.binding = binding
        self.backend_id = str(getattr(binding, "backend_id"))
        self.vectors = list(vectors)
        self.index = 0
        self.started = False
        self.closed = False

    def start(self, _session_id: str) -> None:
        self.started = True

    def embed(self, window: object) -> EmbeddingResult:
        assert self.started
        vector = self.vectors[self.index]
        self.index += 1
        return EmbeddingResult(
            window_id=str(getattr(window, "window_id")),
            backend_id=self.backend_id,
            model_id=str(getattr(self.binding, "model_id")),
            model_sha256=str(getattr(self.binding, "model_sha256")),
            vector=np.asarray(vector, dtype=np.float32),
            duration_sec=float(getattr(window, "end_sec")),
            role="enrollment_embedding",
        )

    def close(self) -> None:
        self.closed = True


class _FakeEmbedderFactory:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.calls = 0
        self.instances: list[_FakeEmbedder] = []

    def __call__(self, binding: object, _work_root: Path) -> _FakeEmbedder:
        self.calls += 1
        value = _FakeEmbedder(binding, self.vectors)
        self.instances.append(value)
        return value


def _labelled_wavs(root: Path, *, amplitudes: tuple[float, float, float] = (0.1, 0.1, 0.1)) -> tuple[LabelledWav, ...]:
    return tuple(
        LabelledWav(
            prompt_id=f"prompt_{index}",
            prompt_text=f"Prompt {index}",
            path=_wav(root / f"take_{index}.wav", amplitude=amplitude),
        )
        for index, amplitude in enumerate(amplitudes, start=1)
    )


def test_presets_are_exact_matrix_rows_and_only_six_frozen_anchors_highlighted() -> None:
    catalog = PresetCatalog(_matrix())
    assert len(catalog.presets) == 18
    assert {row.preset_id for row in catalog.presets} == {
        f"fullpipe_v1_{asr}_{diar}_{identity}"
        for asr in ("ao", "ag")
        for diar in ("dw", "dr", "de")
        for identity in ("iw", "ir", "ie")
    }
    highlighted = [row for row in catalog.presets if row.highlight]
    assert len(highlighted) == 6
    assert {(row.asr_alias, row.hybrid_label) for row in highlighted} == {
        (asr, hybrid)
        for asr in ("AO", "AG")
        for hybrid in ("H2", "H4", "H5")
    }
    expected_thresholds = {
        "H2": 0.5265351286789879,
        "H4": 0.5331755752703802,
        "H5": 0.4572960706169966,
    }
    assert all(
        row.frozen_score_threshold == expected_thresholds[row.hybrid_label]
        and row.known_name_release_allowed
        for row in highlighted
    )
    unresolved = [row for row in catalog.presets if not row.highlight]
    assert len(unresolved) == 12
    assert all(
        "open_set_threshold_unresolved_known_name_release_disabled"
        in row.warning_codes
        and not row.known_name_release_allowed
        for row in unresolved
    )
    assert all(row.hybrid_label in row.display_name for row in catalog.presets)
    h2 = catalog.h2_payload()
    assert h2["default_preset_id"] == "fullpipe_v1_ag_dr_ir"
    assert h2["default_product_mode"] == "H2_SESSION_MEMORY_ENHANCED"
    assert [row["mode_id"] for row in h2["product_modes"]] == [
        "H2_KNOWN_ONLY",
        "H2_SESSION_ANONYMOUS",
        "H2_SESSION_MEMORY_ENHANCED",
    ]


def test_repeat_required_technical_qc_never_constructs_embedder_or_profile(
    tmp_path: Path,
) -> None:
    factory = _FakeEmbedderFactory([[1, 0], [1, 0], [1, 0]])
    service = EnrollmentService(
        matrix=_matrix(), enrollment_root=tmp_path / "enrollment", embedder_factory=factory
    )
    attempt = service.import_wavs(
        pipeline_id="fullpipe_v1_ao_dr_ir",
        display_label="Local Speaker",
        labelled_wavs=_labelled_wavs(tmp_path / "inputs", amplitudes=(0.1, 0.0, 0.1)),
    )
    assert attempt.state == "repeat_required"
    assert attempt.profile is None
    assert attempt.repeat_prompt_ids == ("prompt_2",)
    assert factory.calls == 0
    assert service.store.list_profiles() == ()
    operation = json.loads(
        (tmp_path / "enrollment" / "operations" / f"{attempt.operation_id}.json").read_text("utf-8")
    )
    assert operation["biometric_vectors_inline"] is False
    assert "\"vector\":" not in json.dumps(operation).lower()


def test_analyze_then_create_binds_backend_and_round_trips_take_quality(
    tmp_path: Path,
) -> None:
    factory = _FakeEmbedderFactory([[1, 0], [0.999, 0.01], [0.998, -0.01]])
    service = EnrollmentService(
        matrix=_matrix(), enrollment_root=tmp_path / "enrollment", embedder_factory=factory
    )
    draft = service.analyze(
        pipeline_id="fullpipe_v1_ao_dr_ir",
        labelled_wavs=_labelled_wavs(tmp_path / "inputs"),
        speaker_id="speaker_local_1",
    )
    assert factory.calls == 0
    assert all(row.status == "accepted" for row in draft.takes)
    attempt = service.create(draft=draft, display_label="Ada Local")
    assert attempt.state == "profile_created"
    assert attempt.profile is not None
    assert attempt.profile.backend_id == "redimnet2_b2_speaker_embedding"
    assert attempt.profile.aggregation_method == "multi_template_max"
    assert attempt.profile.profile_version == 1
    assert factory.calls == 1 and factory.instances[0].closed
    loaded = service.store.get_profile(attempt.profile.profile_id)
    assert [row.quality["policy_id"] for row in loaded.templates] == [
        "full_pipeline_demo_enrollment_technical_qc.v1"
    ] * 3
    assert all(row.quality["status"] == "accepted" for row in loaded.templates)


def test_embedding_consistency_reports_outlier_and_blocks_profile(
    tmp_path: Path,
) -> None:
    factory = _FakeEmbedderFactory([[1, 0], [1, 0], [0, 1]])
    service = EnrollmentService(
        matrix=_matrix(), enrollment_root=tmp_path / "enrollment", embedder_factory=factory
    )
    attempt = service.import_wavs(
        pipeline_id="fullpipe_v1_ao_dr_ir",
        display_label="Outlier",
        labelled_wavs=_labelled_wavs(tmp_path / "inputs"),
    )
    assert attempt.state == "repeat_required"
    assert attempt.profile is None
    assert attempt.repeat_prompt_ids == ("prompt_3",)
    assert attempt.outlier_take_id == attempt.takes[2].take_id
    assert attempt.within_enrollment_consistency == 0.0
    assert service.store.list_profiles() == ()


def test_remove_is_recoverable_and_rebuild_archives_immutable_prior_metadata(
    tmp_path: Path,
) -> None:
    factory = _FakeEmbedderFactory([[1, 0], [1, 0], [1, 0]])
    service = EnrollmentService(
        matrix=_matrix(), enrollment_root=tmp_path / "enrollment", embedder_factory=factory
    )
    first = service.import_wavs(
        pipeline_id="fullpipe_v1_ao_dr_ir",
        display_label="Versioned Speaker",
        labelled_wavs=_labelled_wavs(tmp_path / "inputs_one"),
        speaker_id="speaker_versioned",
    )
    assert first.profile is not None
    profile_path = service.store.profile_root / f"{first.profile.profile_id}.json"
    original_bytes = profile_path.read_bytes()
    archived = service.remove(first.profile.profile_id)
    assert not profile_path.exists()
    assert archived.archived_profile_path.read_bytes() == original_bytes
    assert [row.state for row in service.list()] == ["archived"]
    restored = service.restore_profile(first.profile.profile_id)
    assert restored.profile_sha256 == first.profile.profile_sha256
    assert profile_path.read_bytes() == original_bytes
    rebuilt = service.rebuild(
        profile_id=first.profile.profile_id,
        pipeline_id="fullpipe_v1_ao_dr_ir",
        labelled_wavs=_labelled_wavs(tmp_path / "inputs_two"),
    )
    assert rebuilt.profile is not None
    assert rebuilt.profile.profile_version == 2
    assert rebuilt.profile.supersedes_profile_id == first.profile.profile_id
    assert rebuilt.archived_profile_id == first.profile.profile_id
    assert service.store.get_profile(rebuilt.profile.profile_id).state == "active"
    assert service.store.list_archives(profile_id=first.profile.profile_id)[-1].archived_profile_path.read_bytes() == original_bytes


class _FakeMicrophoneSource:
    def __init__(self, **_kwargs: object) -> None:
        rate = 16000
        timebase = np.arange(rate * 4, dtype=np.float32) / rate
        self.samples = (0.1 * np.sin(2 * np.pi * 220 * timebase))[:, None]
        self.sent = False

    def start(self) -> None:
        self.sent = False

    def read(self, timeout_sec: float | None = None) -> RawAudioFrame | None:
        del timeout_sec
        if self.sent:
            return None
        self.sent = True
        return RawAudioFrame(
            frame_id="mic_frame",
            sequence=1,
            samples=self.samples,
            sample_rate_hz=16000,
            channel_count=1,
            source_sample_start=0,
            source_sample_end=len(self.samples),
            audio_start_sec=0.0,
            audio_end_sec=4.0,
            capture_start_monotonic_ns=1,
            capture_end_monotonic_ns=2,
            capture_start_utc=None,
            capture_end_utc=None,
            source_clock_id="fake_mic",
            source_clock_type="audio_sample",
        )

    def stop(self) -> None:
        pass

    def reset(self) -> None:
        self.sent = False

    def status(self) -> dict[str, object]:
        return {"source_mode": "fake_microphone"}


def test_record_uses_injected_microphone_source_and_local_wavs(tmp_path: Path) -> None:
    factory = _FakeEmbedderFactory([[1, 0], [1, 0], [1, 0]])
    service = EnrollmentService(
        matrix=_matrix(),
        enrollment_root=tmp_path / "enrollment",
        embedder_factory=factory,
        microphone_source_factory=lambda **kwargs: _FakeMicrophoneSource(**kwargs),
    )
    attempt = service.record(
        pipeline_id="fullpipe_v1_ao_dr_ir",
        display_label="Recorded Locally",
        prompts=DEFAULT_ENROLLMENT_PROMPTS,
    )
    assert attempt.state == "profile_created"
    assert all(row.source_mode == "microphone" for row in attempt.takes)
    assert all(row.local_audio_path.is_file() for row in attempt.takes)
    assert all(str(row.local_audio_path).startswith(str(tmp_path)) for row in attempt.takes)
