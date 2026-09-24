"""Shared app/update ownership, including Linux crash recovery. See README_STARTUP.md."""
import json
import os
from pathlib import Path
import sys
import uuid


def boot_id():
    if sys.platform == 'linux':
        return Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    return None


def proven_stale(record):
    # Never infer death from age: offline devices may have an incorrect clock.
    if sys.platform != 'linux':
        return False
    pid = record.get('pid')
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    previous_boot = record.get('boot_id')
    if previous_boot and previous_boot != boot_id():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        pass
    return False


class RuntimeLock:
    def __init__(self, data_root, purpose):
        self.path = Path(data_root) / 'runtime.lock'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.token = uuid.uuid4().hex
        self.guard = None
        self.owned = False
        # Stable inode, never unlinked: simultaneous recovery attempts serialize.
        guard = (self.path.parent / '.runtime.guard').open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                if guard.seek(0, 2) == 0:
                    guard.write(b'0'); guard.flush()
                guard.seek(0)
                msvcrt.locking(guard.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            guard.close()
            raise FileExistsError('Application or updater is running') from None
        self.guard = guard
        try:
            if self.path.exists():
                try:
                    record = json.loads(self.path.read_text())
                    stale = isinstance(record, dict) and proven_stale(record)
                except (ValueError, OSError):
                    stale = False
                if not stale:
                    raise FileExistsError('Application/update owns runtime.lock; inspect uncertain ownership')
                self.path.unlink()
            record = dict(pid=os.getpid(), token=self.token, purpose=purpose, boot_id=boot_id())
            tmp = self.path.with_name('.runtime.' + self.token + '.tmp')
            try:
                with tmp.open('x', encoding='utf-8') as stream:
                    json.dump(record, stream)
                    stream.flush(); os.fsync(stream.fileno())
                # Publish a complete record exclusively; an older updater also
                # using O_EXCL cannot be overwritten between inspection/create.
                os.link(tmp, self.path)
                self.owned = True
            finally:
                tmp.unlink(missing_ok=True)
        except BaseException:
            self.close()
            raise

    def close(self):
        try:
            if self.owned and self.path.exists():
                if json.loads(self.path.read_text()).get('token') == self.token:
                    self.path.unlink()
        finally:
            self.owned = False
            if self.guard is not None:
                self.guard.close()  # OS also releases ownership after a crash.
                self.guard = None
