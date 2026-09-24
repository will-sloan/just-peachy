"""Bound native streaming ASR C ABI. See README_N3_ASR.md."""
from __future__ import annotations

import ctypes as C
import hashlib
import math
import os
from pathlib import Path
import time
import numpy as np

NATIVE_REVISION = '97a15afa5caa9bce5baaa86c1184103877af4101'
MODEL_PINS = {
    'A2': ('ebe59e5a817142986528bbbee5dba8db7b38ed50', 'd9a01898d2a611c8764e23a1c2f45e70bbd5a425dc4de93692ac951dd603812d'),
    'A3': ('ea30d66debe3740a08b573244286791d423d6b3e', '3fc991d3badad7277c11030a7519832cddaf2057aafed6d4b25147e953a070b1'),
}


class Sized(C.Structure):
    def __init__(self, **kwargs):
        super().__init__()
        self.size = C.sizeof(type(self))
        for key, value in kwargs.items():
            if key not in dict(self._fields_):
                raise ValueError('Unknown C ABI field: ' + key)
            setattr(self, key, value)


class Backend(Sized):
    _fields_ = [('size', C.c_size_t), ('gpu', C.c_int32)]


class Model(Sized):
    _fields_ = [('size', C.c_size_t), ('path', C.c_char_p), ('name', C.c_char_p)]


class Streaming(Sized):
    _fields_ = [('size', C.c_size_t), ('chunk_size', C.c_float),
                ('ctc_left_padding', C.c_float), ('ctc_right_padding', C.c_float),
                ('rnnt_right_context', C.c_int32)]

    def __init__(self, **kwargs):
        # Match StreamingConfig in pinned src/asr/runner.h. The recognizer
        # validates CTC geometry even when the selected model uses RNNT.
        values = dict(chunk_size=0.16, ctc_left_padding=1.92,
                      ctc_right_padding=1.92, rnnt_right_context=1)
        values.update(kwargs)
        super().__init__(**values)


class Endpointing(Sized):
    _fields_ = [('size', C.c_size_t), ('enable', C.c_bool), ('vad_based', C.c_bool),
                ('stop_history_eou_ms', C.c_int32)]


class Decoder(Sized):
    _fields_ = [('size', C.c_size_t), ('kind', C.c_int32), ('flashlight_lm', C.c_char_p),
                ('flashlight_lexicon', C.c_char_p), ('flashlight_tokenizer', C.c_char_p),
                ('beam_size', C.c_int32), ('beam_size_token', C.c_int32),
                ('beam_threshold', C.c_double), ('lm_weight', C.c_double),
                ('word_insertion_score', C.c_double), ('max_boost', C.c_double)]


class Config(Sized):
    _fields_ = [('size', C.c_size_t), ('backend', C.POINTER(Backend)),
                ('model', C.POINTER(Model)), ('streaming', C.POINTER(Streaming)),
                ('decoder', C.POINTER(Decoder)), ('vad', C.c_void_p),
                ('endpointing', C.POINTER(Endpointing)), ('postproc', C.c_void_p),
                ('diar', C.c_void_p), ('batching', C.c_void_p)]


class Options(Sized):
    _fields_ = [('size', C.c_size_t), ('request_id', C.c_char_p), ('language_code', C.c_char_p),
                ('interim_results', C.c_bool), ('enable_word_time_offsets', C.c_bool),
                ('enable_automatic_punctuation', C.c_bool), ('verbatim_transcripts', C.c_bool),
                ('profanity_filter', C.c_bool), ('stop_history_eou_ms', C.c_int32),
                ('speech_contexts', C.c_void_p), ('speech_context_count', C.c_size_t),
                ('max_alternatives', C.c_int32), ('enable_speaker_diarization', C.c_bool),
                ('max_speaker_count', C.c_int32)]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_binding(document):
    if document.get('schema') != 'just-peachy.n3.native-asr.v1':
        raise ValueError('Unsupported N3 ASR binding')
    variant = document.get('variant')
    if variant not in MODEL_PINS:
        raise ValueError('Native adapter supports exact A2/A3; A1 EOU is a separate architecture')
    revision, digest = MODEL_PINS[variant]
    if document.get('model_revision') != revision or document.get('model_sha256') != digest:
        raise ValueError('Model identity/revision binding differs from admitted N3 artifact')
    if document.get('runtime_revision') != NATIVE_REVISION or document.get('precision') != 'Q8_0':
        raise ValueError('Runtime or precision is not admitted')
    if document.get('gpu') not in (-1, 0) or type(document.get('gpu')) is not int:
        raise ValueError('Explicit CPU -1 or CUDA 0 required')
    if document.get('right_context') not in (0, 1, 6, 13) or type(document.get('right_context')) is not int:
        raise ValueError('Unsupported streaming right context')
    if document.get('language') != 'en-US':
        raise ValueError('This English-only comparison requires explicit en-US')
    if document.get('stop_history_eou_ms') != 800 or document.get('decoder') != 'greedy':
        raise ValueError('Frozen native endpoint/decoder settings required')
    if sha(document['model_path']) != digest:
        raise ValueError('ASR weight bytes changed')
    library = Path(document['library_path']).resolve()
    files = document.get('runtime_files', [])
    if not files or len({Path(row['path']).resolve() for row in files}) != len(files):
        raise ValueError('Complete unique runtime dependency bindings required')
    if library not in {Path(row['path']).resolve() for row in files}:
        raise ValueError('Main library is absent from dependency binding')
    for row in files:
        path = Path(row['path']).resolve()
        if path.parent != library.parent or sha(path) != row['sha256']:
            raise ValueError('Native runtime dependency path/hash mismatch')
    if os.name == 'nt':
        expected = {p.resolve() for p in library.parent.glob('*.dll')}
        if expected != {Path(row['path']).resolve() for row in files}:
            raise ValueError('Every colocated native DLL must be hash-bound')
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.GetModuleHandleW.argtypes = [C.c_wchar_p]
        kernel.GetModuleHandleW.restype = C.c_void_p
        kernel.GetModuleFileNameW.argtypes = [C.c_void_p, C.c_wchar_p, C.c_uint32]
        kernel.GetModuleFileNameW.restype = C.c_uint32
        for path in expected:
            handle = kernel.GetModuleHandleW(path.name)
            if handle:
                buffer = C.create_unicode_buffer(32768)
                if not kernel.GetModuleFileNameW(handle, buffer, len(buffer)):
                    raise OSError('Cannot verify loaded native DLL identity')
                if Path(buffer.value).resolve() != path:
                    raise RuntimeError('A different CPU/CUDA native runtime is already loaded; use a fresh process')
    return library


class NativeRecognizer:
    """Immutable native weights; one independent active stream per owner."""

    def __init__(self, document):
        library = validate_binding(document)
        self.document = dict(document)
        self._dll_dir = os.add_dll_directory(str(library.parent)) if os.name == 'nt' else None
        self.lib = C.CDLL(str(library))
        self.handle = C.c_void_p()
        self.active = None
        self._bind()
        backend = Backend(gpu=document['gpu'])
        model = Model(path=os.fsencode(document['model_path']), name=document['variant'].encode())
        streaming = Streaming(rnnt_right_context=document['right_context'])
        endpoint = Endpointing(enable=True, vad_based=False, stop_history_eou_ms=800)
        decoder = Decoder(kind=0)
        config = Config(backend=C.pointer(backend), model=C.pointer(model),
                        streaming=C.pointer(streaming), decoder=C.pointer(decoder),
                        endpointing=C.pointer(endpoint))
        self.check(self.lib.nemo_speech_asr_create(C.byref(config), C.byref(self.handle)))

    def _bind(self):
        pointer = C.c_void_p
        spec = {
            'create': ([C.POINTER(Config), C.POINTER(pointer)], C.c_int),
            'destroy': ([pointer], None),
            'streaming_recognize': ([pointer, C.POINTER(Options), C.POINTER(pointer)], C.c_int),
            'stream_push_f32': ([pointer, C.POINTER(C.c_float), C.c_size_t, C.c_int32], C.c_int),
            'stream_force_endpoint': ([pointer], C.c_int),
            'stream_finish': ([pointer], C.c_int),
            'stream_next': ([pointer, C.POINTER(pointer)], C.c_int),
            'stream_close': ([pointer], None),
            'result_is_final': ([pointer], C.c_bool),
            'result_audio_processed': ([pointer], C.c_float),
            'result_transcript': ([pointer, C.c_size_t], C.c_char_p),
            'result_word_count': ([pointer, C.c_size_t], C.c_size_t),
            'result_word_text': ([pointer, C.c_size_t, C.c_size_t], C.c_char_p),
            'result_word_start_time': ([pointer, C.c_size_t, C.c_size_t], C.c_int32),
            'result_word_end_time': ([pointer, C.c_size_t, C.c_size_t], C.c_int32),
            'result_destroy': ([pointer], None),
            'last_error': ([], C.c_char_p),
            'version': ([], C.c_char_p),
        }
        for name, (args, result) in spec.items():
            function = getattr(self.lib, 'nemo_speech_asr_' + name)
            function.argtypes, function.restype = args, result

    def check(self, status):
        if status:
            error = self.lib.nemo_speech_asr_last_error()
            raise RuntimeError(f'Native ASR status {status}: {(error or b"").decode("utf-8", errors="replace")}')

    def stream(self):
        if not self.handle:
            raise RuntimeError('Recognizer is closed')
        if self.active is not None and self.active.handle:
            raise RuntimeError('Close the previous stream before starting an independent scene')
        self.active = NativeStream(self)
        return self.active

    def close(self):
        if self.active is not None:
            self.active.close()
        if self.handle:
            self.lib.nemo_speech_asr_destroy(self.handle)
            self.handle = C.c_void_p()
        if self._dll_dir is not None:
            self._dll_dir.close()
            self._dll_dir = None


class NativeStream:
    """Causal pushes return every result, including multiple finals in one call."""

    sample_rate = 16000
    padding_seconds = 0.0  # Native finish owns its documented internal flush.

    def __init__(self, owner):
        self.owner = owner
        self.handle = C.c_void_p()
        self.finished = False
        self.input_samples = 0
        self.utterance_index = 0
        self.decode_ms = self.punctuation_ms = 0.0
        options = Options(request_id=b'just-peachy-n3', language_code=b'en-US', interim_results=True,
                          enable_word_time_offsets=True, enable_automatic_punctuation=True,
                          verbatim_transcripts=True, stop_history_eou_ms=800, max_alternatives=1)
        owner.check(owner.lib.nemo_speech_asr_streaming_recognize(owner.handle, C.byref(options), C.byref(self.handle)))

    def _read(self):
        rows = []
        lib = self.owner.lib
        for _ in range(100000):
            result = C.c_void_p()
            self.owner.check(lib.nemo_speech_asr_stream_next(self.handle, C.byref(result)))
            if not result:
                return rows
            try:
                text = (lib.nemo_speech_asr_result_transcript(result, 0) or b'').decode('utf-8')
                processed = float(lib.nemo_speech_asr_result_audio_processed(result))
                if not math.isfinite(processed):
                    raise RuntimeError('Nonfinite native audio-processed position')
                count = lib.nemo_speech_asr_result_word_count(result, 0)
                if count > 100000:
                    raise RuntimeError('Unbounded native word result')
                words = [dict(text=(lib.nemo_speech_asr_result_word_text(result, 0, i) or b'').decode('utf-8'),
                              start_ms=lib.nemo_speech_asr_result_word_start_time(result, 0, i),
                              end_ms=lib.nemo_speech_asr_result_word_end_time(result, 0, i)) for i in range(count)]
                final = bool(lib.nemo_speech_asr_result_is_final(result))
                rows.append(dict(raw_text=text, final=final, utterance=self.utterance_index,
                    native_audio_processed_sec=processed, words=words,
                    word_time_kind='native_model_offsets_unadjusted_not_ground_truth',
                    input_samples=self.input_samples, input_end_sec=self.input_samples / self.sample_rate,
                    available_at_monotonic=time.perf_counter(),
                    endpoint_reason='native_blank_history_or_requested_flush' if final else None))
                if final:
                    self.utterance_index += 1
            finally:
                lib.nemo_speech_asr_result_destroy(result)
        raise RuntimeError('Native stream did not reach an input boundary')

    def feed(self, samples):
        if self.finished or not self.handle:
            raise RuntimeError('Cannot feed a finished/closed stream')
        values = np.asarray(samples, dtype=np.float32)
        if values.ndim != 1 or not np.all(np.isfinite(values)):
            raise ValueError('Finite mono float32 audio required')
        values = np.ascontiguousarray(values)
        if not values.size:
            return []
        started = time.perf_counter()
        self.owner.check(self.owner.lib.nemo_speech_asr_stream_push_f32(
            self.handle, values.ctypes.data_as(C.POINTER(C.c_float)), values.size, self.sample_rate))
        self.input_samples += int(values.size)
        rows = self._read()
        self.decode_ms = (time.perf_counter() - started) * 1000
        return rows

    def force_endpoint(self):
        if self.finished or not self.handle:
            raise RuntimeError('Cannot force an endpoint after finish')
        self.owner.check(self.owner.lib.nemo_speech_asr_stream_force_endpoint(self.handle))
        return self._read()

    def finish_events(self):
        if self.finished:
            return []
        if not self.handle:
            raise RuntimeError('Stream is closed')
        started = time.perf_counter()
        self.owner.check(self.owner.lib.nemo_speech_asr_stream_finish(self.handle))
        self.finished = True
        rows = self._read()
        self.decode_ms = (time.perf_counter() - started) * 1000
        return rows

    def punctuate(self, raw_text):
        return dict(text=raw_text, status='native_punctuation_preserved', terminal_fallback=None,
                    compute_ms=0.0, model_id=self.owner.document['variant'] + '-native-P1',
                    model_sha256=self.owner.document['model_sha256'], error=None)

    def close(self):
        if self.handle:
            self.owner.lib.nemo_speech_asr_stream_close(self.handle)
            self.handle = C.c_void_p()
