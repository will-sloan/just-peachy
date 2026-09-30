"""Persistent close outcome; README_FIELD_TRANSPORT_CLOSE_LATCH_V1.md."""
import json
import threading


def source_class(base, fault_type):
    """Bind to the exact reviewed transport class before constructing a source."""
    class LatchedSource(base):
        def _initialize_close_outcome(self):
            self._close_lock = threading.Lock()
            self._close_state = 'new'
            self._close_failure = None
            self._close_result = None

        def __init__(self, *args, **kwargs):
            self._initialize_close_outcome()
            super().__init__(*args, **kwargs)

        def _raise_close_failure(self):
            code, raw = self._close_failure
            # Callers cannot mutate the saved outcome through exception.detail.
            raise fault_type(code, json.loads(raw)) from None

        def close(self, timeout=4):
            # One physical attempt, including when two callers arrive together.
            with self._close_lock:
                if self._close_state == 'failed':
                    self._raise_close_failure()
                if self._close_state == 'complete':
                    return self._close_result
                try:
                    if self.closed:
                        raise fault_type('CLOSE_OUTCOME_UNAVAILABLE')
                    result = super().close(timeout)
                except BaseException as exc:
                    code = 'CLOSE_FINALIZATION_EXCEPTION'
                    detail = {'type': type(exc).__name__, 'message': str(exc)}
                    if isinstance(exc, fault_type):
                        code, detail = exc.code, exc.detail
                    try:
                        raw = json.dumps(detail, ensure_ascii=False, allow_nan=False)
                    except (TypeError, ValueError):
                        code = 'CLOSE_FAILURE_DETAIL_UNSERIALIZABLE'
                        raw = json.dumps({'type': type(exc).__name__, 'message': str(exc)})
                    self._close_failure = (code, raw)
                    self._close_state = 'failed'
                    if not isinstance(exc, Exception):
                        raise
                    self._raise_close_failure()
                else:
                    self._close_result = result
                    self._close_state = 'complete'
                    return result
    return LatchedSource
