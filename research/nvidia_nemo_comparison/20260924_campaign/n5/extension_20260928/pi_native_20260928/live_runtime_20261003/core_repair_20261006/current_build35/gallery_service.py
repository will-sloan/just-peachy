"""Owned lazy helper for original enrollment/people workflows. See README.md."""
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

from runtime_support import current_owner, digest, publish, strict, owner_status


class GalleryService:
    def __init__(self, manager, selection, settings):
        if manager.process is not None or manager.export_task is not None:
            raise RuntimeError('Stop/drain speech and exports before enrollment or gallery editing')
        self.manager = manager
        self.directory = manager.data_root/'gallery_operations'/uuid.uuid4().hex
        self.directory.mkdir(parents=True)
        request = dict(binding=str(manager.binding_path), binding_sha256=digest(manager.binding_path),
            selection=selection.validate(), data_root=str(manager.data_root),
            settings=settings, parent=current_owner())
        publish(self.directory/'REQUEST.json', request)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
            OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1',
            MALLOC_ARENA_MAX='1', MALLOC_MMAP_THRESHOLD_='131072', MALLOC_TRIM_THRESHOLD_='131072')
        self.process = subprocess.Popen([manager.binding['python'], str(Path(__file__).with_name('gallery_worker.py')),
            '--directory', str(self.directory)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, env=env)
        # The child waits for this exact identity acknowledgement before imports.
        self.launch_owner = dict(pid=self.process.pid,
            start_ticks=int(Path('/proc/%d/stat' % self.process.pid).read_text().rsplit(')',1)[1].split()[19]),
            boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        publish(self.directory/'LAUNCH_OWNER.json', self.launch_owner)
        publish(self.directory/'START_ACK.json', self.launch_owner)
        self.state = dict(state='LOADING', can_save=False)
        self.error = None
        self.started = time.monotonic()
        self.input_lock = threading.Lock()
        self.close_requested = False
        self.closed = False
        self.reader = threading.Thread(target=self._read, name='gallery-state-reader', daemon=True)
        self.reader.start()

    def _read(self):
        total = 0
        try:
            with (self.directory/'OUTPUT.log').open('xb') as log:
                while True:
                    raw = self.process.stdout.readline(32769)
                    if not raw:
                        break
                    if len(raw) > 32768 or not raw.endswith(b'\n'):
                        raise RuntimeError('Gallery helper output record exceeds 32 KiB')
                    if raw.startswith(b'JP_GALLERY '):
                        self.state = strict(raw[len(b'JP_GALLERY '):])
                    else:
                        if total+len(raw) > 65536:
                            raise RuntimeError('Gallery helper diagnostic output exceeds 64 KiB')
                        log.write(raw); total += len(raw)
                log.flush(); os.fsync(log.fileno())
        except BaseException as exc:
            self.error = repr(exc)
        finally:
            self.process.stdout.close()

    def command(self, name, *args, **kwargs):
        if self.closed or self.process.poll() is not None:
            raise RuntimeError('Gallery helper has closed')
        row = json.dumps(dict(command=name, args=args, kwargs=kwargs), allow_nan=False).encode()+b'\n'
        if len(row)>65536:
            raise ValueError('Gallery command exceeds 64 KiB')
        with self.input_lock:
            self.process.stdin.write(row); self.process.stdin.flush()

    def poll(self):
        if self.closed:
            return self.state
        result = self.process.poll()
        if result is not None:
            self.process.wait()
            self.reader.join(5)
            if self.reader.is_alive():
                raise RuntimeError('Gallery output reader remains owned')
            self.process.stdin.close()
            path = self.directory/'REGISTERED_OWNER.json'
            owner = strict(path.read_bytes()) if path.exists() else None
            if owner != self.launch_owner or not owner_status(owner)['closed']:
                raise RuntimeError('Gallery helper exact identity closure remains unverified')
            publish(self.directory/'HOST_CLOSURE.json', dict(owner=owner, returncode=result,
                direct_child_reaped=True, reader_joined=True, output_error=self.error))
            self.closed = True
            if result or self.error:
                self.state = dict(state='ERROR', can_save=False, error=self.error or 'Gallery operation failed; evidence retained')
        return self.state

    def close(self):
        if not self.closed and not self.close_requested:
            self.command('close')
            self.close_requested = True
        return self.poll()
