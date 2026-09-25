"""Lazy N3 ASR with reusable N2 identity owners; see README_N3.md."""
import hashlib
import json
from pathlib import Path

from .n2_models import N2ResidentModels, N2SpeakerModels
from edge_speech_pipeline.models import SpeakerModels
from edge_speech_pipeline.n3_asr_native import NativeRecognizer


def load_asr_runtime(data_root, component):
    path = Path(data_root) / 'n3_runtime.json'
    if not path.exists():
        raise ValueError('N3 model paths are not configured. See app/README_N3.md')
    document = json.loads(path.read_text(encoding='utf-8'))
    if document.get('schema') != 'just-peachy.n3.runtime.v1':
        raise ValueError('Unsupported N3 runtime catalog')
    binding = document['variants'][component['variant']]
    if binding['variant'] != component['variant'] or binding['model_sha256'] != component['model_sha256']:
        raise ValueError('Selected backend differs from local N3 model binding')
    if binding['right_context'] != component['right_context']:
        raise ValueError('Selected streaming profile differs from local binding')
    if component['variant'] == 'A1':
        from edge_speech_pipeline.n3_a1_adapter import validate_binding
        if binding.get('bundle_sha256') != component.get('bundle_sha256'):
            raise ValueError('Selected A1 export differs from local bundle')
        validate_binding(binding)
    return binding


class N3ResidentModels(N2ResidentModels):
    supports_read_progress = False
    def __init__(self, asr_document, *, identity=None, identity_document=None):
        identity = identity or dict(diarization='D0',embedding='E0')
        super().__init__(identity['diarization'],identity['embedding'],identity_document or {})
        self.asr_document = dict(asr_document)
        self.native_asr = None
        self.n2_identity = bool(identity_document)

    def acquire(self, config, caption_only=False):
        if self.native_asr is None:
            if self.asr_document['variant'] == 'A1':
                from edge_speech_pipeline.n3_a1_adapter import A1Recognizer
                self.native_asr = A1Recognizer(self.asr_document, config)
            else:
                self.native_asr = NativeRecognizer(self.asr_document)
            self.asr_loads += 1
        if not caption_only and self.speakers is None:
            self.speakers = (N2SpeakerModels(config,self.embedding,self.document,pyannote=self.diarization=='D0')
                             if self.n2_identity else SpeakerModels(config))
            self.speaker_loads += 1
        stream = self.native_asr.stream()
        self.streams += 1
        return (None if caption_only else self.speakers), stream

    def close(self):
        super().close()
        if self.native_asr is not None:
            self.native_asr.close()
            self.native_asr = None
        self.speakers = self.asr = self.enhancer = None
