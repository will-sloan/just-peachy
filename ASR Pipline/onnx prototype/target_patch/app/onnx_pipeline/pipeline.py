from __future__ import annotations

from dataclasses import dataclass

from .audio import concatenate_segments, load_audio_mono
from .contracts import InferenceRecord, UtterancePredictionData
from .interfaces import AsrEngine, Punctuator, SpeakerEmbedder, VadEngine
from .matching import choose_speaker
from .speaker.store import EnrollmentStore


@dataclass(slots=True)
class OnnxSpeechPipeline:
    asr: AsrEngine | None
    vad: VadEngine | None = None
    speaker_embedder: SpeakerEmbedder | None = None
    punctuator: Punctuator | None = None
    enrollment_store: EnrollmentStore | None = None
    accept_threshold: float = 0.72
    margin_threshold: float = 0.05
    unknown_label: str = "Unknown"
    asr_sample_rate: int = 16000
    vad_trim_only: bool = True

    def predict_record(self, record: InferenceRecord) -> UtterancePredictionData:
        audio, sample_rate = load_audio_mono(
            record.inference_audio_path,
            target_sample_rate=self.asr_sample_rate,
            start_sec=record.start_sec,
            end_sec=record.end_sec,
        )

        if self.vad is not None:
            segments = self.vad.segment(audio, sample_rate)
            if segments:
                spans = [(seg.start_sec, seg.end_sec) for seg in segments]
                audio = concatenate_segments(audio, sample_rate, spans)

        if self.asr is None:
            text = "TODO_ASR"
        else:
            text = self.asr.transcribe(audio, sample_rate).strip()

        if self.punctuator is not None and text:
            text = self.punctuator.punctuate(text)

        speaker_label = None
        if self.speaker_embedder is not None and self.enrollment_store is not None and audio.size:
            embedding = self.speaker_embedder.embed(audio, sample_rate)
            match = choose_speaker(
                query=embedding,
                gallery=self.enrollment_store.gallery(),
                accept_threshold=self.accept_threshold,
                margin_threshold=self.margin_threshold,
            )
            speaker_label = match.label if match.accepted else self.unknown_label

        return UtterancePredictionData(
            recording_id=record.recording_id,
            utt_id=record.utt_id,
            start_sec=record.start_sec,
            end_sec=record.end_sec,
            speaker_label=speaker_label,
            text=text,
        )
