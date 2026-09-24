"""Lazy candidate bundles with unchanged Sherpa/PnC. See README_N2.md."""
from dataclasses import asdict
from pathlib import Path
import json
import threading
from .pipeline import ResidentModels
from .n2_identity import binding
from edge_speech_pipeline.models import SpeakerModels, SherpaStream, _ort_session
from edge_speech_pipeline.assets import validate_assets


def redim_namespace(config):
    return dict(model_sha256=config.asset('redimnet2_b2_fp32').sha256,
        preprocessing='mono-float32-16k-redimnet2-native-l2-v1',dimension=192,normalization='L2',minimum_samples=8000)


class N2SpeakerModels:
    def __init__(self,config,embedding,binding_document,*,pyannote):
        self.config=config;self._lock=threading.Lock();self.last_embed_ms=self.last_segment_ms=0.
        self.encoder=None
        if embedding=='E0':
            asset=config.asset('redimnet2_b2_fp32');validate_assets([asset])
            self._redim=_ort_session(str(asset.path),config.speaker_threads)
            self.namespace=redim_namespace(config)
        elif embedding=='E1':
            from edge_speech_pipeline.titanet_embedding import TitanetEmbedding
            self.encoder=TitanetEmbedding(binding_document['titanet_manifest'],threads=config.speaker_threads)
            actual=self.encoder.namespace
            self.namespace=dict(model_sha256=actual['backend_sha256'],preprocessing=actual['preprocessing_version'],
                dimension=actual['dimension'],normalization='L2',minimum_samples=actual['minimum_samples'],
                onnx_sha256=actual['onnx_sha256'],frontend_sha256=actual['frontend_sha256'])
            if binding_document['embedding_namespace']!=self.namespace:
                raise ValueError('Configured E1 embedding namespace differs from actual loaded encoder')
        else:raise ValueError('Unknown embedding component')
        if pyannote:
            asset=config.asset('pyannote_segmentation_3_0_fp32');validate_assets([asset])
            self._segmentation=_ort_session(str(asset.path),config.speaker_threads)

    segment=SpeakerModels.segment

    def embed(self,waveform):
        if self.encoder is None:return SpeakerModels.embed(self,waveform)
        import time
        started=time.perf_counter();result=self.encoder.embed(waveform)
        self.last_embed_ms=(time.perf_counter()-started)*1000
        return result


class N2ResidentModels(ResidentModels):
    def __init__(self,diarization,embedding,document):
        super().__init__();self.diarization=diarization;self.embedding=embedding;self.document=document
        self.diarizer=None

    def acquire(self,config,caption_only=False):
        # The baseline resident implementation is unchanged and creates the
        # same native recognizer/decoder stream and punctuation object.
        _,asr=super().acquire(config,caption_only=True)
        if caption_only:return None,asr
        if self.speakers is None:
            self.speakers=N2SpeakerModels(config,self.embedding,self.document,pyannote=self.diarization=='D0')
            self.speaker_loads+=1
        return self.speakers,asr

    def enrollment_models(self,config):
        if self.speakers is None:
            self.speakers=N2SpeakerModels(config,self.embedding,self.document,pyannote=True)
            self.speaker_loads+=1
        if not hasattr(self.speakers,'_segmentation'):
            asset=config.asset('pyannote_segmentation_3_0_fp32');validate_assets([asset])
            self.speakers._segmentation=_ort_session(str(asset.path),config.speaker_threads)
        return self.speakers

    def acquire_diarizer(self,session_id):
        if self.diarization!='D1':raise ValueError('D1 model requested from D0 bundle')
        if self.diarizer is None:
            from edge_speech_pipeline.nemotron_diarization import NemotronDiarizer
            self.diarizer=NemotronDiarizer(self.document['nemotron_model'],self.document['nemotron_library'],
                expected_library_sha256=self.document['nemotron_library_sha256'],
                profile=self.document.get('streaming_profile','low_latency'),session_id=session_id,
                gpu=self.document.get('native_device',dict(kind='cpu',gpu_index=-1))['gpu_index'])
        else:self.diarizer.reset(session_id=session_id)
        return self.diarizer

    def close(self):
        if self.diarizer is not None:self.diarizer.close();self.diarizer=None


def load_runtime(data_root):
    path=Path(data_root)/'n2_runtime.json'
    if not path.exists():raise ValueError('N2 model paths are not configured. See app/README_N2.md')
    document=json.loads(path.read_text(encoding='utf-8'))
    if document.get('schema')!='just-peachy.n2.runtime.v1':raise ValueError('Unsupported N2 runtime binding')
    device=document.get('native_device',dict(kind='cpu',gpu_index=-1))
    if (not isinstance(device,dict) or type(device.get('gpu_index')) is not int or
            device not in (dict(kind='cpu',gpu_index=-1),dict(kind='cuda',gpu_index=0))):
        raise ValueError('Explicit supported native device binding required')
    import hashlib
    for row in document.get('native_runtime_files',[]):
        with Path(row['path']).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=row['sha256']:
                raise ValueError('Native runtime dependency hash changed: '+row['path'])
    if not document.get('native_runtime_files'):raise ValueError('Complete native runtime dependency binding required')
    manifest=Path(document['titanet_manifest'])
    with manifest.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=document['titanet_manifest_sha256']:
            raise ValueError('TitaNet export manifest binding changed')
    return document
