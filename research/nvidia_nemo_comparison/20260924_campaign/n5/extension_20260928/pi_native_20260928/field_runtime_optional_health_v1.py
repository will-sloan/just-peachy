"""Actual source/audio-selection closure checks; README_RUNTIME_OPTIONAL_HEALTH_V1.md."""
import hashlib

INPUT_SHA='2724499e8ad9dc5275b50f7994c74d1fbd1478c52028650092c603d3f6ec62eb'


def derive(raw):
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest()!=INPUT_SHA:
        raise ValueError('Exact existing manager health source required')
    s=raw.decode()
    def change(old,new):
        nonlocal s
        if s.count(old)!=1:raise ValueError('Exact health closure boundary changed')
        s=s.replace(old,new)
    change("if actual.get('actual_capture_started'):",
           "if actual.get('actual_source_started') or actual.get('actual_capture_started'):")
    change("if not (recording/'source/CHILD_OWNER.json').exists():raise ValueError('Captured source identity absent')",
        """if actual.get('actual_capture_started'):
                    if not (recording/'source/CHILD_OWNER.json').exists():raise ValueError('Captured source identity absent')
                elif actual.get('source_kind')!='file' or not policy['profile'].endswith('-saved'):
                    raise ValueError('Explicit saved source route required')""")
    change("if model['samples']!=samples or stop['archive']['recorded_samples']!=samples or not stop['archive']['closed'] or stop['archive']['archive_error'] is not None:",
        """archive=stop['archive'];audio=archive['audio_enabled']
                if type(audio) is not bool:raise ValueError('Actual recording selection required')
                if type(archive['recorded_samples']) is not int or archive['recorded_samples']!=(samples if audio else 0) or archive['source_samples']!=samples:
                    raise ValueError('Exact selected audio and source clock coverage')
                if not stop['source_thread_joined'] or not stop['archive_thread_joined'] or not stop['integrity']['ok']:
                    raise ValueError('Source/archive thread and integrity closure')
                if not actual.get('actual_capture_started'):
                    receipt=stop['stop_receipt']
                    if (receipt.get('schema')!='just-peachy.saved-source-closure.v1' or receipt.get('physical_microphone') is not False
                        or receipt.get('child_process_created') is not False or not receipt['file_context_closed'] or not receipt['thread_joined']):
                        raise ValueError('Actual file source closure')
                if model['samples']!=samples or not archive['closed'] or archive['archive_error'] is not None:""")
    compile(s,'field_operator_health_v1.py','exec')
    return s.encode()

