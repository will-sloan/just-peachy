"""Strict local bindings for N4; see README.md. No model or hardware access."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def bind(path):
    path = Path(path).resolve(strict=True)
    return dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size)


def verify(binding):
    if bind(binding['path']) != binding:
        raise ValueError('Binding changed: ' + binding['path'])


def freeze(path, value):
    path = Path(path)
    if path.exists():
        if load(path) != value:
            raise ValueError('Preserve existing evidence; use a fresh output: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


AUDIO_FIELDS = {'job_id', 'audio_path', 'audio_sha256', 'frames', 'sample_rate_hz',
                'gain', 'reset_between_scenes', 'tap'}


def audio_only(job):
    if set(job) != AUDIO_FIELDS or job['gain'] != 1 or job['sample_rate_hz'] != 16000:
        raise ValueError('Audio-only firewall or prepared gain failed')
    if job['reset_between_scenes'] is not True or job['tap'] not in ('O0', 'O1'):
        raise ValueError('Independent scene reset and explicit tap required')
    if type(job['frames']) is not int or job['frames'] <= 0:
        raise ValueError('Invalid source length')
    if not job['job_id'] or any(not (c.isalnum() or c in '_-') for c in job['job_id']):
        raise ValueError('Invalid job ID')
    return job


def cache_key(kind, *, audio, model, preprocessing, streaming, runtime,
              history, scheduler, window=None, parents=None):
    """No cache aliasing across model, query span, history, availability policy."""
    audio_only(audio)
    if kind not in ('asr', 'diarization', 'embedding', 'integrated'):
        raise ValueError('Unknown cache kind')
    if not all((model, preprocessing, streaming, runtime, history, scheduler)):
        raise ValueError('Every causal contract must be explicit')
    if kind == 'embedding':
        if not window or set(window) != {'start_sample', 'end_sample', 'waveform_sha256'}:
            raise ValueError('Embedding needs exact waveform and sample span')
        if not 0 <= window['start_sample'] < window['end_sample'] <= audio['frames']:
            raise ValueError('Embedding window is outside audio')
    if kind == 'integrated' and not parents:
        raise ValueError('Integrated result requires exact component evidence keys')
    return fingerprint(dict(kind=kind, audio={k: audio[k] for k in sorted(AUDIO_FIELDS)
        if k not in ('audio_path', 'job_id')}, model=model, preprocessing=preprocessing,
        streaming=streaming, runtime=runtime, history=history, scheduler=scheduler,
        window=window, parents=parents))
