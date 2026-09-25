"""A1/P0 ownership for the shared Controller; see README_N3_A1.md."""
from pathlib import Path

from .n3_a1_service import OnnxRecognizer, digest

MODEL_SHA256 = '6603a22a53b7c1a4bac4736cb24628fb568a7102ba931a28c799e2e72f109893'
BUNDLE_SHA256 = '29b70f460ed15c4b57f02bd7f6a08e143ceb6276b5acc18156f0cae756c1cbb6'


def validate_binding(document):
    expected = dict(schema='just-peachy.n3.a1-onnx.v1', variant='A1',
        model_sha256=MODEL_SHA256, bundle_sha256=BUNDLE_SHA256,
        precision='FP32', provider='CPUExecutionProvider', gpu=-1,
        decoder='greedy', right_context=1, language='en-US', chunk_samples=1280,
        frontend_policy='eval_no_dither', max_symbols_per_step=10)
    if any(document.get(k) != v for k, v in expected.items()):
        raise ValueError('A1 binding differs from the admitted portable service')
    bundle = Path(document['bundle_path']).resolve(strict=True)
    if digest(bundle / 'BUNDLE.json') != BUNDLE_SHA256:
        raise ValueError('A1 bundle manifest differs from the qualified export')
    return bundle


class PunctuationOwner:
    """Load the selected small P0 model without loading baseline Giga."""
    def __init__(self, config):
        from .assets import validate_assets
        from .models import SherpaStream
        import sherpa_onnx
        model = config.asset('sherpa_online_punctuation_int8')
        vocabulary = config.asset('sherpa_online_punctuation_bpe')
        validate_assets([model, vocabulary])
        settings = sherpa_onnx.OnlinePunctuationModelConfig(cnn_bilstm=str(model.path),
            bpe_vocab=str(vocabulary.path), num_threads=config.punctuation_threads,
            provider='cpu', debug=False)
        self.punctuation = sherpa_onnx.OnlinePunctuation(
            sherpa_onnx.OnlinePunctuationConfig(settings))
        self.punctuation_ms = 0.
        self._format = SherpaStream.punctuate

    def punctuate(self, text):
        return self._format(self, text)


class A1Stream:
    def __init__(self, owner, stream):
        self.owner, self.inner = owner, stream

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def punctuate(self, raw_text):
        return self.owner.punctuation.punctuate(raw_text)


class A1Recognizer:
    """One ONNX/P0 owner across scenes; independent state for each stream."""
    def __init__(self, document, config):
        bundle = validate_binding(document)
        self.recognizer = OnnxRecognizer(bundle)
        self.punctuation = PunctuationOwner(config)
        self.closed = False

    def stream(self):
        if self.closed:
            raise RuntimeError('A1 owner is closed')
        return A1Stream(self, self.recognizer.stream())

    def close(self):
        if self.closed:
            return
        self.recognizer.close()
        # Closed streams can remain referenced by archived engines. Break the
        # model/stream cycle and release native ORT sessions immediately.
        self.recognizer.active = None
        self.recognizer.service = None
        self.punctuation = None
        self.closed = True
