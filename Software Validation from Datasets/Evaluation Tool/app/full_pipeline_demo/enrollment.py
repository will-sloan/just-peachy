"""Local-only prompted enrollment for the full-pipeline demonstration layer.

The service owns capture/import/QC/lifecycle orchestration.  Speaker embedding
inference remains behind the existing isolated ``WorkerEmbeddingAdapter`` and
is constructed lazily only after all technical take checks pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Callable, Mapping, Protocol, Sequence
import uuid
import wave

import numpy as np

from app.full_pipeline.audio import (
    AudioReadTimeout,
    DurationLimitedAudioSource,
    FileAudioSource,
    MicrophoneAudioSource,
    StreamingAudioNormalizer,
)
from app.full_pipeline.enrollment import (
    ArchivedEnrollmentProfile,
    EnrollmentTemplate,
    ProtectedEnrollmentStore,
    RuntimeEnrollmentProfile,
)
from app.full_pipeline.matrix import FullPipelineMatrix, PipelineSelection
from app.full_pipeline.models import EmbeddingResult, EmbeddingWindow


TECHNICAL_QC_POLICY_ID = "full_pipeline_demo_enrollment_technical_qc.v1"
ENROLLMENT_OPERATION_SCHEMA = "full-pipeline-demo-enrollment-operation.v1"


@dataclass(frozen=True)
class EnrollmentPrompt:
    prompt_id: str
    text: str
    capture_duration_sec: float = 4.0

    def __post_init__(self) -> None:
        if not self.prompt_id.strip() or not self.text.strip():
            raise ValueError("enrollment prompt ID and text must be non-empty")
        if self.capture_duration_sec <= 0:
            raise ValueError("capture duration must be positive")


DEFAULT_ENROLLMENT_PROMPTS: tuple[EnrollmentPrompt, ...] = (
    EnrollmentPrompt(
        "prompt_1",
        "My voice helps this device recognize me while keeping my profile local.",
    ),
    EnrollmentPrompt(
        "prompt_2",
        "Today I am recording a clear sample at a comfortable speaking level.",
    ),
    EnrollmentPrompt(
        "prompt_3",
        "Please use these words only for the speaker profile I requested.",
    ),
)


@dataclass(frozen=True)
class LabelledWav:
    prompt_id: str
    path: Path
    prompt_text: str = "Imported labelled enrollment take"

    def __post_init__(self) -> None:
        if not self.prompt_id.strip():
            raise ValueError("imported WAV prompt_id must be non-empty")
        object.__setattr__(self, "path", Path(self.path).resolve())


@dataclass(frozen=True)
class TechnicalEnrollmentQualityPolicy:
    """Additive engineering QC; it does not replace a frozen model policy."""

    policy_id: str = TECHNICAL_QC_POLICY_ID
    minimum_take_duration_sec: float = 0.75
    minimum_rms_dbfs: float = -50.0
    minimum_peak_dbfs: float = -40.0
    clipping_amplitude: float = 0.999
    maximum_clipped_fraction: float = 0.001
    minimum_embedding_consistency: float = 0.35

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("technical enrollment QC policy_id must be non-empty")
        if self.minimum_take_duration_sec <= 0:
            raise ValueError("minimum take duration must be positive")
        if not 0 < self.clipping_amplitude <= 1:
            raise ValueError("clipping amplitude must be in (0, 1]")
        if not 0 <= self.maximum_clipped_fraction <= 1:
            raise ValueError("maximum clipped fraction must be in [0, 1]")
        if not -1 <= self.minimum_embedding_consistency <= 1:
            raise ValueError("minimum embedding consistency must be in [-1, 1]")


@dataclass(frozen=True)
class TakeQualityReport:
    take_id: str
    prompt_id: str
    prompt_text: str
    source_mode: str
    local_audio_path: Path
    audio_sha256: str
    source_sample_rate_hz: int
    source_channel_count: int
    normalized_sample_rate_hz: int
    duration_sec: float
    rms_dbfs: float
    peak_dbfs: float
    clipped_sample_count: int
    clipped_fraction: float
    status: str
    reason_codes: tuple[str, ...]
    policy_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "take_id": self.take_id,
            "prompt_id": self.prompt_id,
            "prompt_text": self.prompt_text,
            "source_mode": self.source_mode,
            "local_audio_path": str(self.local_audio_path),
            "audio_sha256": self.audio_sha256,
            "source_sample_rate_hz": self.source_sample_rate_hz,
            "source_channel_count": self.source_channel_count,
            "normalized_sample_rate_hz": self.normalized_sample_rate_hz,
            "duration_sec": self.duration_sec,
            "rms_dbfs": self.rms_dbfs,
            "peak_dbfs": self.peak_dbfs,
            "clipped_sample_count": self.clipped_sample_count,
            "clipped_fraction": self.clipped_fraction,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "policy_id": self.policy_id,
        }


@dataclass(frozen=True)
class BackendEnrollmentBinding:
    identity_alias: str
    backend_id: str
    backend_config_sha256: str
    model_id: str
    model_sha256: str
    minimum_backend_duration_sec: float
    enrollment_policy_id: str
    enrollment_policy_sha256: str
    utterance_count: int
    target_total_duration_sec: float
    aggregation_method: str


@dataclass(frozen=True)
class EnrollmentAttempt:
    operation_id: str
    state: str
    speaker_id: str
    display_label: str
    pipeline_id: str
    backend: BackendEnrollmentBinding
    takes: tuple[TakeQualityReport, ...]
    repeat_prompt_ids: tuple[str, ...]
    recommendation_codes: tuple[str, ...]
    within_enrollment_consistency: float | None = None
    outlier_take_id: str | None = None
    profile: RuntimeEnrollmentProfile | None = field(default=None, repr=False)
    archived_profile_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": ENROLLMENT_OPERATION_SCHEMA,
            "operation_id": self.operation_id,
            "state": self.state,
            "speaker_id": self.speaker_id,
            "display_label": self.display_label,
            "pipeline_id": self.pipeline_id,
            "backend": {
                "identity_alias": self.backend.identity_alias,
                "backend_id": self.backend.backend_id,
                "backend_config_sha256": self.backend.backend_config_sha256,
                "model_id": self.backend.model_id,
                "model_sha256": self.backend.model_sha256,
                "minimum_backend_duration_sec": (
                    self.backend.minimum_backend_duration_sec
                ),
                "enrollment_policy_id": self.backend.enrollment_policy_id,
                "enrollment_policy_sha256": self.backend.enrollment_policy_sha256,
                "utterance_count": self.backend.utterance_count,
                "target_total_duration_sec": (
                    self.backend.target_total_duration_sec
                ),
                "aggregation_method": self.backend.aggregation_method,
            },
            "takes": [row.to_dict() for row in self.takes],
            "repeat_prompt_ids": list(self.repeat_prompt_ids),
            "recommendation_codes": list(self.recommendation_codes),
            "within_enrollment_consistency": self.within_enrollment_consistency,
            "outlier_take_id": self.outlier_take_id,
            "profile_id": self.profile.profile_id if self.profile else None,
            "profile_sha256": self.profile.profile_sha256 if self.profile else None,
            "archived_profile_id": self.archived_profile_id,
            "biometric_vectors_inline": False,
            "network_transfer_performed": False,
        }


@dataclass(frozen=True)
class EnrollmentProfileSummary:
    profile_id: str
    profile_sha256: str
    speaker_id: str | None
    display_label: str | None
    backend_id: str
    state: str
    profile_version: int | None
    backend_config_sha256: str | None = None
    model_id: str | None = None
    model_sha256: str | None = None
    replacement_profile_id: str | None = None
    archive_id: str | None = None


class EnrollmentEmbedder(Protocol):
    backend_id: str

    def start(self, session_id: str) -> None: ...
    def embed(self, window: EmbeddingWindow) -> EmbeddingResult: ...
    def close(self) -> None: ...


EmbedderFactory = Callable[[BackendEnrollmentBinding, Path], EnrollmentEmbedder]
MicrophoneSourceFactory = Callable[..., object]


@dataclass(frozen=True)
class _PreparedTake:
    report: TakeQualityReport
    samples: np.ndarray = field(repr=False, compare=False)


@dataclass(frozen=True)
class EnrollmentDraft:
    """In-memory QC result; serialized views never contain normalized audio."""

    operation_id: str
    pipeline_id: str
    speaker_id: str
    backend: BackendEnrollmentBinding
    takes: tuple[TakeQualityReport, ...]
    _prepared: tuple[_PreparedTake, ...] = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": "full-pipeline-demo-enrollment-draft.v1",
            "operation_id": self.operation_id,
            "pipeline_id": self.pipeline_id,
            "speaker_id": self.speaker_id,
            "backend_id": self.backend.backend_id,
            "takes": [row.to_dict() for row in self.takes],
            "biometric_vectors_inline": False,
            "normalized_audio_inline": False,
        }


class EnrollmentService:
    """Record/import and manage backend-bound profiles on the local machine."""

    def __init__(
        self,
        *,
        matrix: FullPipelineMatrix,
        enrollment_root: Path,
        store: ProtectedEnrollmentStore | None = None,
        quality_policy: TechnicalEnrollmentQualityPolicy | None = None,
        embedder_factory: EmbedderFactory | None = None,
        microphone_source_factory: MicrophoneSourceFactory | None = None,
        normalizer_factory: Callable[[], StreamingAudioNormalizer] | None = None,
    ) -> None:
        self.matrix = matrix
        self.root = Path(enrollment_root).resolve()
        self.store = store or ProtectedEnrollmentStore(self.root)
        self.quality_policy = quality_policy or TechnicalEnrollmentQualityPolicy()
        self._embedder_factory = embedder_factory or _default_embedder_factory
        self._microphone_source_factory = (
            microphone_source_factory or _default_microphone_source_factory
        )
        self._normalizer_factory = normalizer_factory or StreamingAudioNormalizer

    def import_wavs(
        self,
        *,
        pipeline_id: str,
        display_label: str,
        labelled_wavs: Sequence[LabelledWav],
        speaker_id: str | None = None,
    ) -> EnrollmentAttempt:
        return self.create(
            draft=self.analyze(
                pipeline_id=pipeline_id,
                labelled_wavs=labelled_wavs,
                speaker_id=speaker_id,
            ),
            display_label=display_label,
        )

    def analyze(
        self,
        *,
        pipeline_id: str,
        labelled_wavs: Sequence[LabelledWav],
        speaker_id: str | None = None,
    ) -> EnrollmentDraft:
        """Import labelled WAVs locally and run technical QC without inference."""

        selection = self.matrix.resolve(pipeline_id)
        binding = _backend_binding(selection)
        speaker = speaker_id or f"speaker_{uuid.uuid4().hex}"
        operation_id = f"enroll_{uuid.uuid4().hex}"
        prepared = tuple(
            self._prepare_import(
                operation_id=operation_id,
                speaker_id=speaker,
                index=index,
                labelled=row,
                binding=binding,
            )
            for index, row in enumerate(labelled_wavs, start=1)
        )
        return EnrollmentDraft(
            operation_id=operation_id,
            pipeline_id=pipeline_id,
            speaker_id=speaker,
            backend=binding,
            takes=tuple(row.report for row in prepared),
            _prepared=prepared,
        )

    def create(
        self, *, draft: EnrollmentDraft, display_label: str
    ) -> EnrollmentAttempt:
        """Create a backend-bound profile from an analyzed in-memory draft."""

        selection = self.matrix.resolve(draft.pipeline_id)
        binding = _backend_binding(selection)
        if binding != draft.backend:
            raise ValueError("enrollment draft backend binding no longer matches matrix")
        return self._enroll(
            operation_id=draft.operation_id,
            selection=selection,
            binding=binding,
            speaker_id=draft.speaker_id,
            display_label=_display_label(display_label),
            prepared=draft._prepared,
            profile_version=1,
            supersedes_profile_id=None,
        )

    def record(
        self,
        *,
        pipeline_id: str,
        display_label: str,
        prompts: Sequence[EnrollmentPrompt] = DEFAULT_ENROLLMENT_PROMPTS,
        speaker_id: str | None = None,
        device: int | str | None = None,
        source_sample_rate_hz: int | None = None,
        source_channels: int | None = None,
    ) -> EnrollmentAttempt:
        """UI-oriented alias for :meth:`record_profile`."""

        return self.record_profile(
            pipeline_id=pipeline_id,
            display_label=display_label,
            prompts=prompts,
            speaker_id=speaker_id,
            device=device,
            source_sample_rate_hz=source_sample_rate_hz,
            source_channels=source_channels,
        )

    def record_profile(
        self,
        *,
        pipeline_id: str,
        display_label: str,
        prompts: Sequence[EnrollmentPrompt] = DEFAULT_ENROLLMENT_PROMPTS,
        speaker_id: str | None = None,
        device: int | str | None = None,
        source_sample_rate_hz: int | None = None,
        source_channels: int | None = None,
    ) -> EnrollmentAttempt:
        selection = self.matrix.resolve(pipeline_id)
        binding = _backend_binding(selection)
        display = _display_label(display_label)
        speaker = speaker_id or f"speaker_{uuid.uuid4().hex}"
        operation_id = f"enroll_{uuid.uuid4().hex}"
        prepared: list[_PreparedTake] = []
        for index, prompt in enumerate(prompts, start=1):
            take_id = _take_id(operation_id, index, prompt.prompt_id)
            path = self._audio_path(speaker, take_id)
            source = DurationLimitedAudioSource(
                self._microphone_source_factory(
                    device=device,
                    source_sample_rate_hz=source_sample_rate_hz,
                    source_channels=source_channels,
                    frame_duration_ms=100,
                ),
                prompt.capture_duration_sec,
            )
            self._capture_wav(source, path)
            prepared.append(
                self._prepare_local_wav(
                    take_id=take_id,
                    prompt_id=prompt.prompt_id,
                    prompt_text=prompt.text,
                    source_mode="microphone",
                    local_path=path,
                    speaker_id=speaker,
                    binding=binding,
                )
            )
        return self._enroll(
            operation_id=operation_id,
            selection=selection,
            binding=binding,
            speaker_id=speaker,
            display_label=display,
            prepared=tuple(prepared),
            profile_version=1,
            supersedes_profile_id=None,
        )

    def rebuild_profile(
        self,
        *,
        profile_id: str,
        pipeline_id: str,
        labelled_wavs: Sequence[LabelledWav],
    ) -> EnrollmentAttempt:
        prior = self.store.get_profile(profile_id)
        selection = self.matrix.resolve(pipeline_id)
        binding = _backend_binding(selection)
        if binding.backend_id != prior.backend_id:
            raise ValueError("rebuild pipeline identity backend does not match profile")
        if binding.backend_config_sha256 != prior.backend_config_sha256:
            raise ValueError("rebuild backend configuration does not match profile")
        if binding.model_sha256 != prior.model_sha256:
            raise ValueError("rebuild model identity does not match profile")
        operation_id = f"rebuild_{uuid.uuid4().hex}"
        prepared = tuple(
            self._prepare_import(
                operation_id=operation_id,
                speaker_id=prior.speaker_id,
                index=index,
                labelled=row,
                binding=binding,
            )
            for index, row in enumerate(labelled_wavs, start=1)
        )
        attempt = self._enroll(
            operation_id=operation_id,
            selection=selection,
            binding=binding,
            speaker_id=prior.speaker_id,
            display_label=prior.display_label,
            prepared=prepared,
            profile_version=prior.profile_version + 1,
            supersedes_profile_id=prior.profile_id,
        )
        if attempt.profile is None:
            return attempt
        self.store.archive_profile(
            prior.profile_id,
            reason="profile_rebuilt",
            replacement_profile_id=attempt.profile.profile_id,
        )
        completed = EnrollmentAttempt(
            **{
                **attempt.__dict__,
                "archived_profile_id": prior.profile_id,
            }
        )
        self._write_operation(completed)
        return completed

    def remove_profile(
        self, profile_id: str, *, reason: str = "operator_removed"
    ) -> ArchivedEnrollmentProfile:
        return self.store.archive_profile(profile_id, reason=reason)

    def remove(
        self, profile_id: str, *, reason: str = "operator_removed"
    ) -> ArchivedEnrollmentProfile:
        return self.remove_profile(profile_id, reason=reason)

    def restore_profile(
        self, profile_id: str, *, archive_id: str | None = None
    ) -> RuntimeEnrollmentProfile:
        return self.store.restore_profile(profile_id, archive_id=archive_id)

    def list_profiles(self) -> tuple[EnrollmentProfileSummary, ...]:
        rows = [
            EnrollmentProfileSummary(
                profile_id=row.profile_id,
                profile_sha256=row.profile_sha256,
                speaker_id=row.speaker_id,
                display_label=row.display_label,
                backend_id=row.backend_id,
                state=row.state,
                profile_version=row.profile_version,
                backend_config_sha256=row.backend_config_sha256,
                model_id=row.model_id,
                model_sha256=row.model_sha256,
            )
            for row in self.store.list_profiles()
        ]
        rows.extend(
            EnrollmentProfileSummary(
                profile_id=row.profile_id,
                profile_sha256=row.profile_sha256,
                speaker_id=None,
                display_label=None,
                backend_id=row.backend_id,
                state="archived",
                profile_version=None,
                backend_config_sha256=None,
                model_id=None,
                model_sha256=None,
                replacement_profile_id=row.replacement_profile_id,
                archive_id=row.archive_id,
            )
            for row in self.store.list_archives()
        )
        return tuple(rows)

    def list(self) -> tuple[EnrollmentProfileSummary, ...]:
        return self.list_profiles()

    def rebuild(
        self,
        *,
        profile_id: str,
        pipeline_id: str,
        labelled_wavs: Sequence[LabelledWav],
    ) -> EnrollmentAttempt:
        return self.rebuild_profile(
            profile_id=profile_id,
            pipeline_id=pipeline_id,
            labelled_wavs=labelled_wavs,
        )

    def _prepare_import(
        self,
        *,
        operation_id: str,
        speaker_id: str,
        index: int,
        labelled: LabelledWav,
        binding: BackendEnrollmentBinding,
    ) -> _PreparedTake:
        if labelled.path.suffix.lower() != ".wav" or not labelled.path.is_file():
            raise ValueError(f"labelled enrollment input must be a WAV: {labelled.path}")
        take_id = _take_id(operation_id, index, labelled.prompt_id)
        local_path = self._audio_path(speaker_id, take_id)
        _atomic_bytes(local_path, labelled.path.read_bytes())
        return self._prepare_local_wav(
            take_id=take_id,
            prompt_id=labelled.prompt_id,
            prompt_text=labelled.prompt_text,
            source_mode="imported_wav",
            local_path=local_path,
            speaker_id=speaker_id,
            binding=binding,
        )

    def _prepare_local_wav(
        self,
        *,
        take_id: str,
        prompt_id: str,
        prompt_text: str,
        source_mode: str,
        local_path: Path,
        speaker_id: str,
        binding: BackendEnrollmentBinding,
    ) -> _PreparedTake:
        samples, source_rate, source_channels = self._normalized_wav(local_path)
        report = _quality_report(
            take_id=take_id,
            prompt_id=prompt_id,
            prompt_text=prompt_text,
            source_mode=source_mode,
            local_path=local_path,
            source_rate=source_rate,
            source_channels=source_channels,
            samples=samples,
            policy=self.quality_policy,
            backend_minimum_duration_sec=binding.minimum_backend_duration_sec,
        )
        quality_path = (
            self.root / "quality" / _safe_component(speaker_id) / f"{take_id}.json"
        )
        _atomic_json(quality_path, report.to_dict())
        return _PreparedTake(report=report, samples=samples)

    def _normalized_wav(self, path: Path) -> tuple[np.ndarray, int, int]:
        source = FileAudioSource(path, frame_duration_ms=100, pace=0)
        normalizer = self._normalizer_factory()
        chunks: list[np.ndarray] = []
        source_rate = 0
        source_channels = 0
        source.start()
        try:
            while True:
                frame = source.read()
                if frame is None:
                    break
                source_rate = frame.sample_rate_hz
                source_channels = frame.channel_count
                chunks.append(normalizer.normalize(frame).samples)
        finally:
            source.stop()
        if not chunks:
            raise ValueError(f"enrollment WAV contains no audio: {path}")
        return (
            np.ascontiguousarray(np.concatenate(chunks), dtype=np.float32),
            source_rate,
            source_channels,
        )

    def _capture_wav(self, source: object, path: Path) -> None:
        chunks: list[np.ndarray] = []
        sample_rate = 0
        channels = 0
        source.start()  # type: ignore[attr-defined]
        try:
            while True:
                try:
                    frame = source.read(timeout_sec=1.0)  # type: ignore[attr-defined]
                except AudioReadTimeout:
                    continue
                if frame is None:
                    break
                if sample_rate and (
                    frame.sample_rate_hz != sample_rate
                    or frame.channel_count != channels
                ):
                    raise RuntimeError("microphone format changed during enrollment take")
                sample_rate = frame.sample_rate_hz
                channels = frame.channel_count
                value = np.asarray(frame.samples, dtype=np.float32)
                if value.ndim == 1:
                    value = value[:, None]
                chunks.append(value)
        finally:
            source.stop()  # type: ignore[attr-defined]
        if not chunks or sample_rate <= 0 or channels <= 0:
            raise RuntimeError("microphone enrollment take captured no audio")
        _atomic_pcm16_wav(path, np.concatenate(chunks, axis=0), sample_rate)

    def _enroll(
        self,
        *,
        operation_id: str,
        selection: PipelineSelection,
        binding: BackendEnrollmentBinding,
        speaker_id: str,
        display_label: str,
        prepared: Sequence[_PreparedTake],
        profile_version: int,
        supersedes_profile_id: str | None,
    ) -> EnrollmentAttempt:
        prompt_ids = [row.report.prompt_id for row in prepared]
        duplicate_prompts = sorted(
            {prompt for prompt in prompt_ids if prompt_ids.count(prompt) > 1}
        )
        repeat = [
            row.report.prompt_id
            for row in prepared
            if row.report.status == "repeat_required"
        ]
        recommendations: list[str] = []
        if len(prepared) != binding.utterance_count:
            recommendations.append(
                f"record_exactly_{binding.utterance_count}_labelled_takes"
            )
            repeat.extend(
                f"missing_take_{index}"
                for index in range(len(prepared) + 1, binding.utterance_count + 1)
            )
        if duplicate_prompts:
            recommendations.append("use_unique_prompt_ids")
            repeat.extend(duplicate_prompts)
        total_duration = sum(row.report.duration_sec for row in prepared)
        if total_duration < binding.target_total_duration_sec:
            recommendations.append(
                f"target_total_duration_{binding.target_total_duration_sec:g}_sec_not_met"
            )
        if repeat:
            attempt = EnrollmentAttempt(
                operation_id=operation_id,
                state="repeat_required",
                speaker_id=speaker_id,
                display_label=display_label,
                pipeline_id=selection.pipeline_id,
                backend=binding,
                takes=tuple(row.report for row in prepared),
                repeat_prompt_ids=tuple(dict.fromkeys(repeat)),
                recommendation_codes=tuple(dict.fromkeys(recommendations)),
            )
            self._write_operation(attempt)
            return attempt

        embedder = self._embedder_factory(
            binding, self.root / "work" / operation_id
        )
        templates: list[EnrollmentTemplate] = []
        embedder.start(operation_id)
        try:
            for row in prepared:
                duration = row.samples.size / 16000
                result = embedder.embed(
                    EmbeddingWindow(
                        window_id=row.report.take_id,
                        start_sec=0.0,
                        end_sec=duration,
                        assignment_start_sec=0.0,
                        assignment_end_sec=duration,
                        samples=row.samples,
                        role="enrollment_embedding",
                    )
                )
                _validate_embedding_identity(result, binding)
                templates.append(
                    EnrollmentTemplate(
                        sample_id=row.report.take_id,
                        vector=result.vector,
                        duration_sec=duration,
                        audio_sha256=row.report.audio_sha256,
                        quality=row.report.to_dict(),
                    )
                )
        finally:
            embedder.close()
        consistency, outlier_index = _embedding_consistency(templates)
        if consistency < self.quality_policy.minimum_embedding_consistency:
            outlier = prepared[outlier_index]
            attempt = EnrollmentAttempt(
                operation_id=operation_id,
                state="repeat_required",
                speaker_id=speaker_id,
                display_label=display_label,
                pipeline_id=selection.pipeline_id,
                backend=binding,
                takes=tuple(row.report for row in prepared),
                repeat_prompt_ids=(outlier.report.prompt_id,),
                recommendation_codes=tuple(
                    dict.fromkeys(
                        [*recommendations, "repeat_embedding_consistency_outlier"]
                    )
                ),
                within_enrollment_consistency=consistency,
                outlier_take_id=outlier.report.take_id,
            )
            self._write_operation(attempt)
            return attempt
        identity_material = {
            "speaker_id": speaker_id,
            "backend_id": binding.backend_id,
            "profile_version": profile_version,
            "audio_sha256s": [row.audio_sha256 for row in templates],
        }
        suffix = hashlib.sha256(
            json.dumps(identity_material, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        profile_id = (
            f"profile_{_safe_component(speaker_id)}_"
            f"{_safe_component(binding.identity_alias.lower())}_v{profile_version}_{suffix}"
        )
        profile = self.store.create_profile(
            profile_id=profile_id,
            profile_version=profile_version,
            supersedes_profile_id=supersedes_profile_id,
            speaker_id=speaker_id,
            display_label=display_label,
            backend_id=binding.backend_id,
            backend_config_sha256=binding.backend_config_sha256,
            model_id=binding.model_id,
            model_sha256=binding.model_sha256,
            aggregation_method=binding.aggregation_method,
            templates=templates,
            minimum_consistency=self.quality_policy.minimum_embedding_consistency,
        )
        attempt = EnrollmentAttempt(
            operation_id=operation_id,
            state="profile_created",
            speaker_id=speaker_id,
            display_label=display_label,
            pipeline_id=selection.pipeline_id,
            backend=binding,
            takes=tuple(row.report for row in prepared),
            repeat_prompt_ids=(),
            recommendation_codes=tuple(dict.fromkeys(recommendations)),
            within_enrollment_consistency=consistency,
            profile=profile,
        )
        self._write_operation(attempt)
        return attempt

    def _audio_path(self, speaker_id: str, take_id: str) -> Path:
        return self.root / "audio" / _safe_component(speaker_id) / f"{take_id}.wav"

    def _write_operation(self, attempt: EnrollmentAttempt) -> None:
        payload = {
            **attempt.to_dict(),
            "updated_at_utc": _utc_now(),
            "privacy": {
                "local_only": True,
                "biometric_sensitive": True,
                "vectors_inline": False,
                "upload_performed": False,
            },
        }
        _atomic_json(
            self.root / "operations" / f"{attempt.operation_id}.json", payload
        )


def _backend_binding(selection: PipelineSelection) -> BackendEnrollmentBinding:
    identity = selection.identity
    policy = selection.enrollment_policy
    return BackendEnrollmentBinding(
        identity_alias=selection.identity_alias,
        backend_id=str(identity["backend_id"]),
        backend_config_sha256=str(identity["config_sha256"]),
        model_id=str(identity["model_id"]),
        model_sha256=str(identity["model_identity_sha256"]),
        minimum_backend_duration_sec=float(identity["minimum_duration_sec"]),
        enrollment_policy_id=str(policy["policy_id"]),
        enrollment_policy_sha256=str(policy["sha256"]),
        utterance_count=int(policy["utterance_count"]),
        target_total_duration_sec=float(policy["target_total_duration_sec"]),
        aggregation_method=str(policy["aggregation"]),
    )


def _quality_report(
    *,
    take_id: str,
    prompt_id: str,
    prompt_text: str,
    source_mode: str,
    local_path: Path,
    source_rate: int,
    source_channels: int,
    samples: np.ndarray,
    policy: TechnicalEnrollmentQualityPolicy,
    backend_minimum_duration_sec: float,
) -> TakeQualityReport:
    value = np.asarray(samples, dtype=np.float32).reshape(-1)
    reasons: list[str] = []
    finite = np.isfinite(value)
    if not bool(np.all(finite)):
        reasons.append("non_finite_audio_samples")
    safe = np.where(finite, value, 0.0)
    duration = safe.size / 16000
    rms = float(np.sqrt(np.mean(np.square(safe, dtype=np.float64)))) if safe.size else 0
    peak = float(np.max(np.abs(safe))) if safe.size else 0
    rms_dbfs = _dbfs(rms)
    peak_dbfs = _dbfs(peak)
    clipped = int(np.count_nonzero(np.abs(safe) >= policy.clipping_amplitude))
    clipped_fraction = clipped / safe.size if safe.size else 0.0
    minimum_duration = max(
        policy.minimum_take_duration_sec, backend_minimum_duration_sec
    )
    if duration < minimum_duration:
        reasons.append("duration_below_technical_minimum")
    if rms_dbfs < policy.minimum_rms_dbfs:
        reasons.append("rms_level_too_low")
    if peak_dbfs < policy.minimum_peak_dbfs:
        reasons.append("peak_level_too_low")
    if clipped_fraction > policy.maximum_clipped_fraction:
        reasons.append("clipping_fraction_too_high")
    return TakeQualityReport(
        take_id=take_id,
        prompt_id=prompt_id,
        prompt_text=prompt_text,
        source_mode=source_mode,
        local_audio_path=local_path,
        audio_sha256=hashlib.sha256(local_path.read_bytes()).hexdigest(),
        source_sample_rate_hz=source_rate,
        source_channel_count=source_channels,
        normalized_sample_rate_hz=16000,
        duration_sec=duration,
        rms_dbfs=rms_dbfs,
        peak_dbfs=peak_dbfs,
        clipped_sample_count=clipped,
        clipped_fraction=clipped_fraction,
        status="accepted" if not reasons else "repeat_required",
        reason_codes=tuple(reasons),
        policy_id=policy.policy_id,
    )


def _embedding_consistency(
    templates: Sequence[EnrollmentTemplate],
) -> tuple[float, int]:
    matrix = np.stack([row.vector for row in templates]).astype(np.float32)
    if len(matrix) < 2:
        return 1.0, 0
    # Enrollment sets are tiny.  This is the same pairwise dot product as
    # ``matrix @ matrix.T`` but avoids a Windows MKL dispatcher abort observed
    # during repeated demo/profile quality checks.  The explicit reduction is
    # deterministic and remains portable to ARM64 NumPy builds.
    scores = np.einsum("ij,kj->ik", matrix, matrix, optimize=False)
    pairwise = scores[np.triu_indices(len(matrix), k=1)]
    consistency = float(np.min(pairwise)) if pairwise.size else 1.0
    mean_other = (np.sum(scores, axis=1) - 1.0) / (len(matrix) - 1)
    outlier_index = int(np.argmin(mean_other))
    return max(-1.0, min(1.0, consistency)), outlier_index


def _validate_embedding_identity(
    result: EmbeddingResult, binding: BackendEnrollmentBinding
) -> None:
    if result.backend_id != binding.backend_id:
        raise RuntimeError("enrollment embedding backend identity mismatch")
    if result.model_id != binding.model_id:
        raise RuntimeError("enrollment embedding model identity mismatch")
    if result.model_sha256 != binding.model_sha256:
        raise RuntimeError("enrollment embedding model checksum mismatch")


def _default_embedder_factory(
    binding: BackendEnrollmentBinding, work_root: Path
) -> EnrollmentEmbedder:
    """Construct the existing isolated adapter only when accepted audio needs it."""

    from app.full_pipeline.cache import ContentAddressedCache
    from app.full_pipeline.runtime_components import WorkerEmbeddingAdapter
    from app.full_pipeline.workers import (
        PersistentWorker,
        embedding_worker_spec,
    )

    worker = PersistentWorker(
        embedding_worker_spec(
            binding.backend_id,
            worker_id=f"enrollment-{binding.backend_id}-{uuid.uuid4().hex[:10]}",
        )
    )
    return WorkerEmbeddingAdapter(
        worker=worker,
        work_root=work_root,
        backend_config_sha256=binding.backend_config_sha256,
        model_id=binding.model_id,
        model_sha256=binding.model_sha256,
        cache=ContentAddressedCache(work_root / "protected_embedding_cache"),
    )


def _default_microphone_source_factory(**kwargs: object) -> MicrophoneAudioSource:
    return MicrophoneAudioSource(**kwargs)


def _display_label(value: str) -> str:
    label = str(value).strip()
    if not label:
        raise ValueError("enrollment display label must be non-empty")
    return label


def _safe_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("._")
    if not normalized:
        raise ValueError("local enrollment identifier has no safe characters")
    return normalized[:120]


def _take_id(operation_id: str, index: int, prompt_id: str) -> str:
    return f"take_{operation_id.split('_')[-1][:12]}_{index:02d}_{_safe_component(prompt_id)}"


def _dbfs(amplitude: float) -> float:
    if amplitude <= 0 or not math.isfinite(amplitude):
        return -120.0
    return max(-120.0, min(20.0, 20.0 * math.log10(amplitude)))


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(value)
    temporary.replace(path)


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    payload = json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    _atomic_bytes(path, payload)


def _atomic_pcm16_wav(path: Path, samples: np.ndarray, sample_rate_hz: int) -> None:
    value = np.asarray(samples, dtype=np.float32)
    if value.ndim == 1:
        value = value[:, None]
    channels = int(value.shape[1])
    pcm = np.round(np.clip(value, -1.0, 1.0) * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp.wav")
    with wave.open(str(temporary), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate_hz)
        handle.writeframes(pcm.tobytes())
    temporary.replace(path)


# Descriptive compatibility alias for early integration callers.
LocalEnrollmentService = EnrollmentService
