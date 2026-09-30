"""Failure-aware post-run diagnostics. README_FIELD_POSTRUN_V1.md."""
from pathlib import Path


def model_counters(models):
    result = {}
    for name in ('asr_loads', 'speaker_loads', 'punctuation_loads'):
        value = getattr(models, name, None)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('Invalid optional model counter: ' + name)
        result[name] = {'available': value is not None, 'value': value}
    return result


def completed_session(epoch, expected_parent, expected_samples):
    """Resolve only a durable, completed epoch; never stringify an early None."""
    raw = epoch.get('native_session_path')
    if not isinstance(raw, str) or not raw or raw == 'None':
        raise ValueError('Durable native session path unavailable')
    path = Path(raw)
    if not path.is_absolute() or not path.is_dir() or path.resolve().parent != Path(expected_parent).resolve():
        raise ValueError('Durable native session parent mismatch')
    if epoch.get('pipeline_terminal_state') != 'COMPLETED' or epoch.get('closed') is not True:
        raise ValueError('Durable epoch not complete')
    if epoch.get('source_samples') != expected_samples or epoch.get('recorded_samples') != expected_samples:
        raise ValueError('Durable source sample mismatch')
    return str(path.resolve())
