"""Minimal persistent Sherpa and ONNX model runtimes."""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any

import numpy as np

from .assets import validate_assets
from .config import PipelineConfig
from .text_format import finalize_punctuation_output, prepare_for_punctuation


POWERSET_TO_MULTILABEL = np.asarray(
    [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [1, 0, 1], [0, 1, 1]],
    dtype=np.float32,
)


def _ort_session(path: str, threads: int):
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(
        path, sess_options=options, providers=["CPUExecutionProvider"]
    )


class SpeakerModels:
    """Persistent, thread-safe ReDimNet2 and Pyannote ONNX sessions."""

    def __init__(self, config: PipelineConfig) -> None:
        validate_assets(
            [
                config.asset("redimnet2_b2_fp32"),
                config.asset("pyannote_segmentation_3_0_fp32"),
            ]
        )
        self._redim = _ort_session(
            str(config.asset("redimnet2_b2_fp32").path), config.speaker_threads
        )
        self._segmentation = _ort_session(
            str(config.asset("pyannote_segmentation_3_0_fp32").path),
            config.speaker_threads,
        )
        self._lock = threading.Lock()
        self.last_embed_ms = 0.0
        self.last_segment_ms = 0.0
        self.config = config

    def embed(self, waveform: np.ndarray) -> np.ndarray:
        samples = np.asarray(waveform, dtype=np.float32).reshape(-1)
        if samples.size < 8_000:
            raise ValueError("speaker embedding requires at least 0.5 seconds")
        started = time.perf_counter()
        with self._lock:
            raw = self._redim.run(None, {"waveform": samples[None, :]})[0]
        vector = np.asarray(raw[0], dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 0:
            raise RuntimeError("speaker embedding was zero or non-finite")
        self.last_embed_ms = (time.perf_counter() - started) * 1000.0
        return vector / norm

    def segment(self, waveform: np.ndarray, *, include_posteriors: bool = False) -> dict[str, np.ndarray]:
        samples = np.asarray(waveform, dtype=np.float32).reshape(-1)
        if samples.size != 160_000:
            raise ValueError("segmentation requires exactly 10 seconds at 16 kHz")
        started = time.perf_counter()
        with self._lock:
            raw = self._segmentation.run(
                None, {"waveform": samples[None, None, :]}
            )[0]
        classes = np.argmax(raw, axis=-1)
        ordered = np.sort(POWERSET_TO_MULTILABEL[classes], axis=-1)
        self.last_segment_ms = (time.perf_counter() - started) * 1000.0
        result = {
            "speech": ordered[0, :, -1].astype(np.int8),
            "overlap": ordered[0, :, -2].astype(np.int8),
        }
        if include_posteriors or self.config.segmentation_post_policy != "hard_argmax_fraction":
            result.update(powerset_posteriors(raw))
        return result


class SherpaStream:
    """One native stateful Sherpa Giga stream with explicit endpoint resets."""

    def __init__(self, config: PipelineConfig, *, resident: "SherpaStream | None" = None) -> None:
        if resident is not None:
            self.sample_rate = resident.sample_rate
            self.recognizer = resident.recognizer
            self.punctuation = resident.punctuation
            self.stream = self.recognizer.create_stream()
            self.utterance_index = 0
            self.last_text = ""
            self.decode_ms = self.punctuation_ms = 0.0
            return
        validate_assets(
            [
                config.asset("sherpa_giga_encoder_int8"),
                config.asset("sherpa_giga_decoder_fp32"),
                config.asset("sherpa_giga_joiner_int8"),
                config.asset("sherpa_giga_tokens"),
                config.asset("sherpa_online_punctuation_int8"),
                config.asset("sherpa_online_punctuation_bpe"),
            ]
        )
        import sherpa_onnx

        self.sample_rate = config.sample_rate
        self.recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(config.asset("sherpa_giga_tokens").path),
            encoder=str(config.asset("sherpa_giga_encoder_int8").path),
            decoder=str(config.asset("sherpa_giga_decoder_fp32").path),
            joiner=str(config.asset("sherpa_giga_joiner_int8").path),
            num_threads=config.asr_threads,
            provider="cpu",
            sample_rate=config.sample_rate,
            feature_dim=80,
            decoding_method=config.asr_decoding_method,
            max_active_paths=config.asr_max_active_paths,
            blank_penalty=config.asr_blank_penalty,
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=config.endpoint_rule1_silence_sec,
            rule2_min_trailing_silence=config.endpoint_rule2_silence_sec,
            rule3_min_utterance_length=config.endpoint_rule3_utterance_sec,
        )
        punctuation_model = sherpa_onnx.OnlinePunctuationModelConfig(
            cnn_bilstm=str(
                config.asset("sherpa_online_punctuation_int8").path
            ),
            bpe_vocab=str(config.asset("sherpa_online_punctuation_bpe").path),
            num_threads=config.punctuation_threads,
            provider="cpu",
            debug=False,
        )
        self.punctuation = sherpa_onnx.OnlinePunctuation(
            sherpa_onnx.OnlinePunctuationConfig(punctuation_model)
        )
        self.stream = self.recognizer.create_stream()
        self.utterance_index = 0
        self.last_text = ""
        self.decode_ms = 0.0
        self.punctuation_ms = 0.0



    def accept(self, samples: np.ndarray) -> tuple[str, bool]:
        started = time.perf_counter()
        self.stream.accept_waveform(self.sample_rate, np.asarray(samples, np.float32))
        while self.recognizer.is_ready(self.stream):
            self.recognizer.decode_stream(self.stream)
        text = _result_text(self.recognizer.get_result(self.stream))
        endpoint = bool(
            hasattr(self.recognizer, "is_endpoint")
            and self.recognizer.is_endpoint(self.stream)
        )
        self.decode_ms = (time.perf_counter() - started) * 1000.0
        self.last_text = text
        return text, endpoint

    def reset_endpoint(self) -> str:
        final = _result_text(self.recognizer.get_result(self.stream))
        if hasattr(self.recognizer, "reset"):
            self.recognizer.reset(self.stream)
        else:
            self.stream = self.recognizer.create_stream()
        self.utterance_index += 1
        self.last_text = ""
        return final

    def finish(self) -> str:
        padding = np.zeros(round(0.66 * self.sample_rate), dtype=np.float32)
        self.stream.accept_waveform(self.sample_rate, padding)
        self.stream.input_finished()
        guard = 0
        while self.recognizer.is_ready(self.stream):
            self.recognizer.decode_stream(self.stream)
            guard += 1
            if guard > 100_000:
                raise RuntimeError("Sherpa failed to drain the final stream")
        return _result_text(self.recognizer.get_result(self.stream))

    def punctuate(self, raw_text: str) -> dict[str, object]:
        """Apply learned punctuation to one final ASR utterance."""

        prepared = prepare_for_punctuation(raw_text)
        started = time.perf_counter()
        try:
            restored = self.punctuation.add_punctuation_with_case(prepared)
            status = "learned"
            error = None
        except Exception as exc:
            restored = ""
            status = "fallback"
            error = f"{type(exc).__name__}: {exc}"
        self.punctuation_ms = (time.perf_counter() - started) * 1000.0
        learned_terminal = bool(str(restored).strip()) and str(restored).strip()[
            -1
        ] in ".?!"
        final_text = finalize_punctuation_output(restored, raw_text)
        return {
            "text": final_text,
            "status": status,
            "terminal_fallback": (
                None
                if learned_terminal
                else "question_start"
                if final_text.endswith("?")
                else "period"
            ),
            "compute_ms": self.punctuation_ms,
            "model_id": "sherpa-onnx-online-punct-en-2024-08-06-int8",
            "model_sha256": "9d611f445fe4a46186080fe161be6059d87d72eb88d3a8cb00c1a06e83a6067e",
            "error": error,
        }


def _result_text(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        return str(result.get("text", "")).strip()
    return str(getattr(result, "text", "")).strip()


def powerset_posteriors(raw: np.ndarray) -> dict[str, np.ndarray]:
    """Decode the bound seven-class log-probability graph, not multilabel logits.

    Slots are local to the complete 10-second invocation; their identities must
    never be compared across calls without a separate permutation alignment.
    """
    scores = np.asarray(raw, dtype=np.float32)
    if scores.ndim != 3 or scores.shape[0] != 1 or scores.shape[-1] != 7:
        raise ValueError("expected [1, frames, 7] powerset log scores")
    if not np.all(np.isfinite(scores)):
        raise ValueError("non-finite powerset log scores")
    probability = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
    probability /= np.sum(probability, axis=-1, keepdims=True)
    return {
        "powerset_probability": probability[0],
        "local_speaker_probability": probability[0] @ POWERSET_TO_MULTILABEL,
        "speech_probability": 1.0 - probability[0, :, 0],
        "overlap_probability": np.sum(probability[0, :, 4:], axis=-1),
    }


class ResidentModelBundle:
    """One admitted immutable model configuration, one active session at a time.

    Weight bytes are validated by model constructors once at bundle admission.
    Each acquire creates a fresh Sherpa stream; no utterance or tracker state is
    retained. Callers must keep admitted files immutable for the bundle lifetime.
    """
    @staticmethod
    def signature(config):
        from dataclasses import asdict
        values = asdict(config)
        # Paths for journal/gallery do not affect neural weights or frontend.
        return {k: v for k, v in values.items() if k not in {"session_root", "profile_root"}}

    def __init__(self, config: PipelineConfig):
        self.config_signature = self.signature(config)
        self._lease = threading.Lock()
        started = time.perf_counter()
        self.speaker_models = SpeakerModels(config)
        self._resident_asr = SherpaStream(config)
        self.admission_elapsed_sec = time.perf_counter() - started
        self.sessions_created = 0

    def acquire(self, config):
        if self.signature(config) != self.config_signature:
            raise ValueError("resident bundle configuration differs; create a new recipe bundle")
        if not self._lease.acquire(blocking=False):
            raise RuntimeError("resident bundle already owns an active session")
        try:
            stream = SherpaStream(config, resident=self._resident_asr)
            self.sessions_created += 1
            return self.speaker_models, stream
        except Exception:
            self._lease.release()
            raise

    def release(self):
        self._lease.release()
