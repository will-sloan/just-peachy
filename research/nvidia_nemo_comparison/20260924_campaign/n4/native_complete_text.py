"""Complete bounded native journal sink. See README_NATIVE_JOURNAL_RETENTION.md."""
from pathlib import Path
import threading


class CompleteText:
    """AsyncText worker sink: preserve the entire prefix or fail, never rotate.

    The single owner opens a fresh file. Queueing, asynchronous failure reporting
    and drain semantics remain the application's existing AsyncText behavior.
    """
    MAX_BYTES = 256*1024**2
    MAX_RECORD_BYTES = 1024**2

    def __init__(self, path, max_bytes=MAX_BYTES):
        if type(max_bytes) is not int or not 0 < max_bytes <= self.MAX_BYTES:
            raise ValueError('Invalid complete journal byte budget')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.closed = False
        self.rotations = 0
        self._bytes = 0
        self._lock = threading.Lock()
        self._handle = self.path.open('x', encoding='utf-8', newline='\n', buffering=1)

    def write(self, value):
        if not isinstance(value, str):
            raise TypeError('Complete journal accepts UTF-8 text only')
        encoded = len(value.encode('utf-8'))
        with self._lock:
            if self.closed:
                raise ValueError('Journal is closed')
            if encoded > self.MAX_RECORD_BYTES or self._bytes+encoded > self.max_bytes:
                raise RuntimeError('Complete journal byte budget exhausted; preserve evidence and stop')
            result = self._handle.write(value)
            if result != len(value):
                raise OSError('Incomplete native journal write')
            self._bytes += encoded
            return result

    def flush(self):
        with self._lock:
            if not self.closed:
                self._handle.flush()

    def close(self):
        with self._lock:
            if not self.closed:
                self._handle.close()
                self.closed = True
