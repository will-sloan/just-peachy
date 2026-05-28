"""PyTorch-native cosine speaker matcher with conservative Unknown fallback."""

from __future__ import annotations

import math
from typing import Mapping, Sequence

import torch
import torch.nn.functional as F

from app.inference_pipeline.enrollment.schema import (
    EnrollmentDatabase,
    EnrollmentExemplar,
    EnrollmentSpeaker,
)
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.speaker_matching.base import (
    DECISION_ACCEPTED,
    DECISION_AMBIGUOUS,
    DECISION_BELOW_THRESHOLD,
    DECISION_DIMENSION_MISMATCH,
    DECISION_INVALID_EMBEDDING,
    DECISION_MODEL_MISMATCH,
    DECISION_NO_ENROLLED_SPEAKERS,
    SCORING_MODE_CENTROID,
    SCORING_MODE_EXEMPLAR,
    SpeakerDecision,
    SpeakerMatcherBase,
    SpeakerScore,
    embedding_id_from_embedding,
    ensure_enrollment_database,
    model_id_from_embedding,
    vector_from_embedding,
)


class CosineThresholdSpeakerMatcher(SpeakerMatcherBase):
    """Assign enrolled names using cosine score, threshold, and score margin."""

    name = "cosine_threshold"

    def match(
        self,
        embedding: object,
        enrollment_db: EnrollmentDatabase | Mapping[str, object],
    ) -> SpeakerDecision:
        try:
            vector = vector_from_embedding(embedding)
            query = _normal_tensor(vector)
        except ContractValidationError as exc:
            return self.unknown_decision(
                DECISION_INVALID_EMBEDDING,
                embedding=embedding,
                notes=str(exc),
            )

        db = ensure_enrollment_database(enrollment_db)
        if not db.speakers:
            return self.unknown_decision(
                DECISION_NO_ENROLLED_SPEAKERS,
                embedding=embedding,
                notes="enrollment database has no speakers",
            )

        model_mismatch = self._model_mismatch(embedding, db)
        if model_mismatch is not None:
            return self.unknown_decision(
                DECISION_MODEL_MISMATCH,
                embedding=embedding,
                notes=model_mismatch,
            )

        scores = self._speaker_scores(query, db)
        if not scores:
            return self.unknown_decision(
                DECISION_DIMENSION_MISMATCH,
                embedding=embedding,
                notes="no enrolled speaker embedding had the same dimension as the query",
            )

        sorted_scores = tuple(sorted(scores, key=lambda item: item.score, reverse=True))
        best_score = sorted_scores[0]
        second_best = sorted_scores[1] if len(sorted_scores) > 1 else None
        margin = (
            None
            if second_best is None
            else best_score.score - second_best.score
        )

        if best_score.score < self.threshold:
            return self.unknown_decision(
                DECISION_BELOW_THRESHOLD,
                embedding=embedding,
                best_score=best_score,
                second_best_score=second_best,
                scores=sorted_scores,
                notes=(
                    f"best cosine {best_score.score:.4f} is below threshold "
                    f"{self.threshold:.4f}"
                ),
            )
        if margin is not None and margin < self.min_margin:
            return self.unknown_decision(
                DECISION_AMBIGUOUS,
                embedding=embedding,
                best_score=best_score,
                second_best_score=second_best,
                scores=sorted_scores,
                notes=(
                    f"best-second margin {margin:.4f} is below min_margin "
                    f"{self.min_margin:.4f}"
                ),
            )

        return SpeakerDecision(
            speaker_label=best_score.speaker_label,
            best_label=best_score.speaker_label,
            confidence=best_score.score,
            margin=margin,
            threshold=self.threshold,
            min_margin=self.min_margin,
            threshold_decision=DECISION_ACCEPTED,
            accepted=True,
            second_best_label=second_best.speaker_label if second_best is not None else None,
            second_best_score=second_best.score if second_best is not None else None,
            matched_reference_id=best_score.reference_id,
            method=self.name,
            embedding_id=embedding_id_from_embedding(embedding),
            model_id=model_id_from_embedding(embedding) or self.runtime_model_id,
            scores=sorted_scores,
        )

    def _speaker_scores(
        self,
        query: torch.Tensor,
        db: EnrollmentDatabase,
    ) -> tuple[SpeakerScore, ...]:
        if self.scoring_mode == SCORING_MODE_EXEMPLAR:
            return self._exemplar_scores(query, db.speakers)
        return self._centroid_scores(query, db.speakers)

    def _centroid_scores(
        self,
        query: torch.Tensor,
        speakers: Sequence[EnrollmentSpeaker],
    ) -> tuple[SpeakerScore, ...]:
        scores: list[SpeakerScore] = []
        for speaker in speakers:
            centroid = speaker.centroid_embedding
            if len(centroid) != int(query.numel()):
                continue
            score = _cosine_score(query, centroid)
            scores.append(
                SpeakerScore(
                    speaker_label=speaker.display_name,
                    score=score,
                    speaker_id=speaker.speaker_id,
                    reference_id=f"centroid:{speaker.speaker_id}",
                    model_id=",".join(speaker.model_ids) or None,
                    scoring_mode=SCORING_MODE_CENTROID,
                )
            )
        return tuple(scores)

    def _exemplar_scores(
        self,
        query: torch.Tensor,
        speakers: Sequence[EnrollmentSpeaker],
    ) -> tuple[SpeakerScore, ...]:
        speaker_scores: list[SpeakerScore] = []
        for speaker in speakers:
            best: SpeakerScore | None = None
            for exemplar in speaker.exemplars:
                exemplar_score = self._score_exemplar(query, speaker, exemplar)
                if exemplar_score is None:
                    continue
                if best is None or exemplar_score.score > best.score:
                    best = exemplar_score
            if best is not None:
                speaker_scores.append(best)
        return tuple(speaker_scores)

    def _score_exemplar(
        self,
        query: torch.Tensor,
        speaker: EnrollmentSpeaker,
        exemplar: EnrollmentExemplar,
    ) -> SpeakerScore | None:
        if len(exemplar.embedding) != int(query.numel()):
            return None
        return SpeakerScore(
            speaker_label=speaker.display_name,
            score=_cosine_score(query, exemplar.embedding),
            speaker_id=speaker.speaker_id,
            reference_id=exemplar.embedding_id or f"exemplar:{speaker.speaker_id}:{exemplar.prompt_id}",
            model_id=exemplar.model_id,
            scoring_mode=SCORING_MODE_EXEMPLAR,
        )

    def _model_mismatch(
        self,
        embedding: object,
        db: EnrollmentDatabase,
    ) -> str | None:
        if not self.enforce_model_id:
            return None
        target_model_id = self.runtime_model_id or model_id_from_embedding(embedding)
        if target_model_id is None:
            return None
        mismatches = sorted(
            {
                model_id
                for model_id in db.embedding_model_ids
                if model_id != target_model_id
            }
        )
        if not mismatches:
            return None
        return (
            "enrollment model_id mismatch: "
            f"expected {target_model_id!r}, found {', '.join(repr(item) for item in mismatches)}"
        )


def _normal_tensor(values: Sequence[float]) -> torch.Tensor:
    tensor = torch.as_tensor(values, dtype=torch.float32).flatten()
    if tensor.numel() == 0:
        raise ContractValidationError("speaker match embedding vector must be non-empty")
    if not bool(torch.isfinite(tensor).all()):
        raise ContractValidationError("speaker match embedding vector must be finite")
    norm = torch.linalg.vector_norm(tensor)
    if not math.isfinite(float(norm.item())) or float(norm.item()) <= 0.0:
        raise ContractValidationError("speaker match embedding vector must be non-zero")
    return F.normalize(tensor, dim=0)


def _cosine_score(query: torch.Tensor, reference: Sequence[float]) -> float:
    reference_tensor = _normal_tensor(reference)
    return float(torch.dot(query, reference_tensor).item())
