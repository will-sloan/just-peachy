"""NVIDIA NeMo clustering or MSDD diarization adapter."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import soundfile as sf

from app.inference_pipeline.asr.audio_utils import resolve_model_path
from app.inference_pipeline.diarization.adapter_utils import materialized_audio_path
from app.inference_pipeline.diarization.base import (
    DiarizationBase,
    DiarizationParameters,
    DiarizationUnavailableError,
    SpeakerTurnRegion,
    mark_overlapping_turns,
)
from app.inference_pipeline.errors import ContractValidationError


class NemoDiarizationUnavailableError(DiarizationUnavailableError):
    """Raised when NeMo or an MSDD configuration cannot run locally."""


@dataclass
class NemoDiarizer(DiarizationBase):
    """NeMo clustering/MSDD wrapper driven by a local Hydra/OmegaConf YAML."""

    params: DiarizationParameters | Mapping[str, object] | None = None
    diarizer_factory: Any | None = None

    name = "nemo_diarization"

    def __post_init__(self) -> None:
        raw = dict(self.params or {}) if isinstance(self.params, Mapping) else {}
        DiarizationBase.__init__(self, self.params)
        self.config_path = raw.get("config_path")
        self.device = str(raw.get("device") or "cpu")
        self.batch_size = int(raw.get("batch_size", 1))
        if not self.device.strip():
            raise ContractValidationError("NeMo diarization device must be non-empty")
        if self.batch_size < 1:
            raise ContractValidationError("NeMo diarization batch_size must be >= 1")
        if (
            self.params.min_speakers is not None
            and self.params.min_speakers != self.params.max_speakers
        ):
            raise ContractValidationError(
                "NeMo adapter supports min_speakers only when it equals max_speakers"
            )
        self.last_runtime_sec: float | None = None
        self.last_turns: tuple[SpeakerTurnRegion, ...] = ()

    def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
        config_path = self._config_path()
        started_at = time.perf_counter()
        try:
            with materialized_audio_path(
                audio,
                prefix="nemo-diarization-audio-",
            ) as path:
                with tempfile.TemporaryDirectory(prefix="nemo-diarization-") as directory:
                    workdir = Path(directory)
                    manifest = workdir / "manifest.jsonl"
                    duration = float(sf.info(path).duration)
                    manifest.write_text(
                        json.dumps(
                            {
                                "audio_filepath": str(path.resolve()),
                                "offset": 0.0,
                                "duration": duration,
                                "label": "infer",
                                "text": "-",
                                "num_speakers": _known_speaker_count(self.params),
                                "rttm_filepath": None,
                                "uem_filepath": None,
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    diarizer = self._build_diarizer(config_path, manifest, workdir)
                    diarizer.diarize()
                    rttm = _find_rttm(workdir, path.stem)
                    turns = _read_rttm(rttm, min_turn_sec=self.params.min_turn_sec)
        except NemoDiarizationUnavailableError:
            raise
        except Exception as exc:
            raise NemoDiarizationUnavailableError(
                f"NeMo diarization failed: {exc}"
            ) from exc
        turns = mark_overlapping_turns(turns)
        self.last_runtime_sec = time.perf_counter() - started_at
        self.last_turns = tuple(turns)
        return turns

    def _config_path(self) -> Path:
        try:
            return resolve_model_path(self.config_path)
        except Exception as exc:
            raise NemoDiarizationUnavailableError(
                f"NeMo diarization config is unavailable: {exc}"
            ) from exc

    def _build_diarizer(self, config_path: Path, manifest: Path, out_dir: Path) -> Any:
        if self.diarizer_factory is not None:
            return self.diarizer_factory(config_path, manifest, out_dir)
        if not sys.platform.startswith("linux"):
            raise NemoDiarizationUnavailableError(
                "NeMo speaker diarization is supported by this project only on Linux; "
                "use WSL2/a Linux host or select another diarizer."
            )
        try:
            nemo_spec = importlib.util.find_spec("nemo.collections.asr")
        except (ImportError, ModuleNotFoundError):
            nemo_spec = None
        if nemo_spec is None:
            raise NemoDiarizationUnavailableError(
                "nemo_toolkit[asr] is not installed in the active environment."
            )
        try:
            from omegaconf import OmegaConf
            from nemo.collections.asr.models import ClusteringDiarizer, NeuralDiarizer

            config = OmegaConf.load(config_path)
            if bool(_config_get(config, "diarizer.oracle_vad")):
                raise NemoDiarizationUnavailableError(
                    "NeMo oracle_vad requires a reference RTTM, which is not available in "
                    "the inference record contract; disable oracle_vad for prediction."
                )
            config.diarizer.manifest_filepath = str(manifest)
            config.diarizer.out_dir = str(out_dir)
            config.device = self.device
            config.diarizer.collar = self.params.collar_sec
            if self.params.max_speakers is not None:
                clustering = getattr(config.diarizer, "clustering", None)
                if clustering is not None and hasattr(clustering, "parameters"):
                    clustering.parameters.max_num_speakers = self.params.max_speakers
            if hasattr(config.diarizer, "speaker_embeddings"):
                config.diarizer.speaker_embeddings.parameters.batch_size = self.batch_size
            _resolve_configured_model_assets(
                config,
                allow_model_downloads=self.params.allow_model_downloads,
                omega_conf=OmegaConf,
            )
            diarizer_class = (
                NeuralDiarizer
                if _is_msdd_config(config)
                else ClusteringDiarizer
            )
            return diarizer_class(cfg=config)
        except Exception as exc:  # pragma: no cover - dependency boundary
            if isinstance(exc, NemoDiarizationUnavailableError):
                raise
            raise NemoDiarizationUnavailableError(
                f"NeMo diarizer load failed: {exc}"
            ) from exc


def _find_rttm(out_dir: Path, stem: str) -> Path:
    candidates = list(out_dir.rglob(f"{stem}.rttm")) or list(out_dir.rglob("*.rttm"))
    if not candidates:
        raise NemoDiarizationUnavailableError("NeMo did not produce an RTTM file.")
    return candidates[0]


def _read_rttm(path: Path, *, min_turn_sec: float) -> list[SpeakerTurnRegion]:
    turns: list[SpeakerTurnRegion] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[0] != "SPEAKER":
            continue
        try:
            start = float(fields[3])
            duration = float(fields[4])
        except ValueError:
            continue
        if start < 0 or duration <= 0:
            continue
        if duration < min_turn_sec:
            continue
        turns.append(
            SpeakerTurnRegion(
                start_sec=start,
                end_sec=start + duration,
                speaker_turn_label=str(fields[7]),
                source="nemo_diarization",
            )
        )
    return turns


def _known_speaker_count(params: DiarizationParameters) -> int | None:
    if (
        params.min_speakers is not None
        and params.max_speakers is not None
        and params.min_speakers == params.max_speakers
    ):
        return params.min_speakers
    return None


def _is_msdd_config(config: object) -> bool:
    name = str(_config_get(config, "name") or "").casefold()
    if "neuraldiarizer" in name or "msdd" in name:
        return True
    return _config_get(config, "diarizer.msdd_model") is not None


def _resolve_configured_model_assets(
    config: object,
    *,
    allow_model_downloads: bool,
    omega_conf: Any,
) -> None:
    """Resolve active NeMo model references or reject implicit downloads."""

    active_keys = ["diarizer.speaker_embeddings.model_path"]
    if not bool(_config_get(config, "diarizer.oracle_vad")) and not _config_get(
        config,
        "diarizer.vad.external_vad_manifest",
    ):
        active_keys.append("diarizer.vad.model_path")
    if _is_msdd_config(config):
        active_keys.append("diarizer.msdd_model.model_path")
    if bool(_config_get(config, "diarizer.asr.parameters.asr_based_vad")):
        active_keys.append("diarizer.asr.model_path")

    missing: list[str] = []
    unresolved: list[str] = []
    for key in active_keys:
        value = _config_get(config, key)
        if value is None or not str(value).strip():
            missing.append(f"{key}=<missing>")
            continue
        try:
            path = resolve_model_path(value)
        except (FileNotFoundError, ValueError):
            if not allow_model_downloads:
                unresolved.append(f"{key}={value!r}")
            continue
        omega_conf.update(config, key, str(path), merge=False)

    if missing:
        joined = ", ".join(missing)
        raise NemoDiarizationUnavailableError(
            f"NeMo config is missing active model entries: {joined}."
        )
    if unresolved and not allow_model_downloads:
        joined = ", ".join(unresolved)
        raise NemoDiarizationUnavailableError(
            "NeMo model downloads are disabled but active config entries are not local "
            f"assets: {joined}. Bootstrap .nemo files or explicitly enable downloads."
        )


def _config_get(config: object, dotted_key: str) -> object | None:
    current = config
    for key in dotted_key.split("."):
        if isinstance(current, Mapping):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
        if current is None:
            return None
    return current
