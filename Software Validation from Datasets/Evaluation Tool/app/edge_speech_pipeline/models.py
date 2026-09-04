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

    def segment(self, waveform: np.ndarray) -> dict[str, np.ndarray]:
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
        return {
            "speech": ordered[0, :, -1].astype(np.int8),
            "overlap": ordered[0, :, -2].astype(np.int8),
        }


class SherpaStream:
    """One native stateful Sherpa Giga stream with explicit endpoint resets."""

    def __init__(self, config: PipelineConfig) -> None:
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
            decoding_method="greedy_search",
            max_active_paths=4,
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
