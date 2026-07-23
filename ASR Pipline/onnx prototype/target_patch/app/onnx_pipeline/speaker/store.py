from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np


@dataclass(slots=True)
class EnrollmentExample:
    speaker_name: str
    embedding: list[float]
    prompt_id: str | None = None
    note: str | None = None


@dataclass(slots=True)
class EnrollmentStore:
    path: Path
    examples: list[EnrollmentExample] = field(default_factory=list)

    def add_embedding(
        self,
        speaker_name: str,
        embedding: np.ndarray,
        prompt_id: str | None = None,
        note: str | None = None,
    ) -> None:
        self.examples.append(
            EnrollmentExample(
                speaker_name=speaker_name,
                embedding=np.asarray(embedding, dtype=np.float32).reshape(-1).tolist(),
                prompt_id=prompt_id,
                note=note,
            )
        )

    def gallery(self) -> dict[str, list[np.ndarray]]:
        out: dict[str, list[np.ndarray]] = {}
        for example in self.examples:
            out.setdefault(example.speaker_name, []).append(
                np.asarray(example.embedding, dtype=np.float32)
            )
        return out

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(example) for example in self.examples]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.examples = [EnrollmentExample(**item) for item in raw]
