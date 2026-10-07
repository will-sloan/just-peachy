"""Bounded runtime I/O; byte-submit draft in README_EVENT_WRITER_STREAMING.md."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import threading
import time


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('Duplicate JSON field')
            out[key] = value
        return out
    def bad(value):
        raise ValueError('Nonfinite JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def publish(path, value, *, replace=False, cap=1024*1024):
    path = Path(path)
    raw = encoded(value) + b'\n'
    if len(raw) > cap or path.is_symlink():
        raise ValueError('Receipt size/path bound')
    pending = path.with_name(path.name + '.pending')
    if pending.exists() or pending.is_symlink():
        raise FileExistsError('Preserve incomplete publication')
    with pending.open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short receipt write')
        stream.flush()
        os.fsync(stream.fileno())
    if replace:
        os.replace(pending, path)
    else:
        os.link(pending, path)
        pending.unlink()
    if os.name != 'nt':
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    if path.read_bytes() != raw:
        raise OSError('Receipt readback mismatch')


def current_owner():
    if os.name == 'nt':
        import psutil
        me = psutil.Process()
        return dict(pid=me.pid, create_time=me.create_time(), affinity=me.cpu_affinity())
    pid = os.getpid()
    return dict(pid=pid, start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def owner_status(owner, proc_root=Path('/proc')):
    """Prove an exact recorded owner closed; PID reuse is not that owner."""
    if not isinstance(owner, dict) or type(owner.get('pid')) is not int or owner['pid'] <= 0:
        return dict(closed=False, state='INVALID_OWNER')
    if 'create_time' in owner and 'start_ticks' not in owner:
        if type(owner['create_time']) not in (int, float):
            return dict(closed=False, state='INVALID_CREATE_TIME')
        import psutil
        try:
            actual = psutil.Process(owner['pid']).create_time()
            return dict(closed=actual != owner['create_time'], state='PID_REUSED' if actual != owner['create_time'] else 'ALIVE')
        except psutil.NoSuchProcess:
            return dict(closed=True, state='ABSENT')
        except psutil.AccessDenied:
            return dict(closed=False, state='UNVERIFIABLE')
    if type(owner.get('start_ticks')) is not int or not isinstance(owner.get('boot_id'), str) or not owner['boot_id']:
        return dict(closed=False, state='INVALID_LINUX_OWNER')
    try:
        boot = (proc_root/'sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        return dict(closed=False, state='UNVERIFIABLE_BOOT')
    if boot != owner['boot_id']:
        return dict(closed=True, state='HISTORICAL_DIFFERENT_BOOT')
    try:
        fields = (proc_root/str(owner['pid'])/'stat').read_text().rsplit(')', 1)[1].split()
        ticks = int(fields[19])
        if ticks != owner['start_ticks']:
            return dict(closed=True, state='PID_REUSED', actual_start_ticks=ticks)
        return dict(closed=False, state='ZOMBIE' if fields[0] == 'Z' else 'ALIVE')
    except (FileNotFoundError, ProcessLookupError):
        return dict(closed=True, state='ABSENT')
    except (OSError, ValueError, IndexError):
        return dict(closed=False, state='UNVERIFIABLE')


def verify_owned_unit(unit, ownership_path, *, runner=None):
    """Read-only verification of the exact invocation that contains this process."""
    import subprocess
    runner = runner or subprocess.run
    receipt = strict(Path(ownership_path).read_bytes())
    if receipt.get('unit') != unit or not unit.startswith('jp-v29-') or not unit.endswith('.service'):
        raise RuntimeError('Unique owned native unit required')
    expected = {name: receipt.get(key) for name, key in
                (('InvocationID', 'invocation_id'), ('ControlGroup', 'control_group'), ('MainPID', 'main_pid'))}
    if not all(expected.values()) or owner_status(receipt.get('owner')) != dict(closed=False, state='ALIVE'):
        raise RuntimeError('Native unit main owner is not exact and live')
    if receipt['owner']['pid'] != int(expected['MainPID']):
        raise RuntimeError('Native unit main PID differs from registered owner')
    observed = runner(['systemctl', '--user', 'show', unit,
                      '--property=InvocationID,ControlGroup,MainPID,ActiveState'],
                     capture_output=True, text=True, check=True, timeout=5).stdout
    properties = dict(line.split('=', 1) for line in observed.splitlines() if '=' in line)
    if any(str(properties.get(key)) != str(value) for key, value in expected.items()) or properties.get('ActiveState') not in ('active', 'activating', 'deactivating'):
        raise RuntimeError('Native unit invocation changed; signal refused')
    memberships = [line.split(':', 2)[-1] for line in Path('/proc/self/cgroup').read_text().splitlines()]
    if not any(path == expected['ControlGroup'] or path.startswith(expected['ControlGroup']+'/') for path in memberships):
        raise RuntimeError('Launcher is outside the claimed native unit')
    return receipt


def kill_owned_unit(unit, ownership_path, *, runner=None):
    """Request whole-unit kill only after validating exact invocation ownership."""
    import subprocess
    runner = runner or subprocess.run
    receipt = verify_owned_unit(unit, ownership_path, runner=runner)
    runner(['systemctl', '--user', 'kill', '--kill-whom=all', '--signal=KILL', unit],
           capture_output=True, text=True, check=True, timeout=5)
    return dict(requested=True, unit=unit, invocation_id=receipt['invocation_id'])


class Lease:
    """OS lease, released only by close/process exit; never steal a live lease."""
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink():
            raise ValueError('Symlink lease')
        self.file = self.path.open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0, 2)
                if self.file.tell() == 0:
                    self.file.write(b'0'); self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.file.close()
            raise

    def close(self):
        if self.file.closed:
            return
        if os.name == 'nt':
            import msvcrt
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.file, fcntl.LOCK_UN)
        self.file.close()


def verify_files(root, rows):
    root = Path(root).resolve()
    seen = set()
    for row in rows:
        rel = Path(row['path'])
        if rel.is_absolute() or '..' in rel.parts or rel.as_posix().casefold() in seen:
            raise ValueError('Manifest path/alias')
        seen.add(rel.as_posix().casefold())
        path = root / rel
        if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file():
            raise ValueError('Real pinned file required: ' + str(path))
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Source/asset pin changed: ' + str(path))


class DiskBudget:
    """Shared byte accounting; the estimate is not a cumulative disk quota.

    Actual free space, bounded individual writes and bounded RAM queues govern
    admission. A duration-derived estimate must not hide a Mode/caption failure
    or prevent Stop from completing after valid metadata has been delivered.
    """
    def __init__(self, maximum_bytes, reserve_bytes=5*1024**3, reserve_fraction=0):
        if type(maximum_bytes) is not int or maximum_bytes <= 0 or reserve_bytes < 0 or not 0 <= reserve_fraction < 1:
            raise ValueError('Invalid aggregate metadata allocation')
        self.maximum = maximum_bytes
        self.reserve = reserve_bytes
        self.reserve_fraction = reserve_fraction
        self.accepted = 0
        self.lock = threading.Lock()

    def claim(self, count):
        with self.lock:
            if type(count) is not int or count < 0:
                raise ValueError('Nonnegative integer metadata byte count required')
            self.accepted += count

    def unclaim(self, count):
        with self.lock:
            if type(count) is not int or not 0 <= count <= self.accepted:
                raise ValueError('Metadata rollback exceeds accepted byte accounting')
            self.accepted -= count

    def check_free(self, path, count):
        if type(count) is not int or count < 0:
            raise ValueError('Nonnegative integer write byte count required')
        usage = shutil.disk_usage(path)
        if usage.free < max(self.reserve, math.ceil(usage.total*self.reserve_fraction)) + count:
            raise OSError('Storage floor reached')


class SegmentedText:
    """Bounded async append, physical free-space guard, no cumulative quota."""
    def __init__(self, path, *, maximum_bytes, reserve_bytes=5*1024**3,
                 segment_bytes=8*1024**2, queue_bytes=4*1024**2, fail=None, budget=None):
        self.path = Path(path)
        if self.path.is_symlink() or any(parent.is_symlink() for parent in self.path.parents):
            raise ValueError('Real owned metadata directory required')
        if any(type(v) is not int or v <= 0 for v in (maximum_bytes, segment_bytes, queue_bytes)):
            raise ValueError('Positive finite metadata bounds required')
        self.maximum = int(maximum_bytes)
        self.reserve = int(reserve_bytes)
        self.segment_bytes = segment_bytes
        self.queue_bytes = queue_bytes
        self.queue = queue.Queue(512)
        self.lock = threading.RLock()
        self.pending = self.accepted = self.completed = 0
        self.closed = False
        self.error = None
        self.refusal = None
        self.io_failed = False
        self.fail = fail or (lambda exc: None)
        self.segment_count = 0
        self.budget = budget or DiskBudget(self.maximum, reserve_bytes)
        self.thread = threading.Thread(target=self._run, name='v29-segmented-writer', daemon=True)
        self.thread.start()

    def _fault(self, error):
        with self.lock:
            if self.error is None:
                self.error = str(error)
            reason = self.error
        try:
            self.fail(reason)
        except BaseException as exc:
            with self.lock:
                self.error = reason + '; failure callback: ' + repr(exc)

    def write(self, value):
        if not isinstance(value, str):
            raise TypeError('Text required')
        self.write_bytes(value.encode('utf-8'))
        return len(value)

    def write_bytes(self, raw):
        """Admit one immutable record through the existing bounded FIFO writer."""
        if type(raw) is not bytes:
            raise TypeError('Immutable bytes required')
        with self.lock:
            if self.closed or self.error:
                raise RuntimeError('Writer closed/failed: ' + str(self.error))
            boundary = ('logical_record' if len(raw) > min(1024**2, self.segment_bytes) else
                        'pending_queue_bytes' if self.pending+len(raw) > self.queue_bytes else None)
            if boundary:
                self.refusal = dict(boundary=boundary, incoming_bytes=len(raw),
                    accepted_bytes=self.accepted, pending_bytes=self.pending,
                    logical_record_maximum=min(1024**2,self.segment_bytes),
                    queue_maximum=self.queue_bytes, planned_writer_bytes=self.maximum,
                    planned_aggregate_bytes=self.budget.maximum, cumulative_quota_enforced=False)
                self._fault('Explicit event allocation refused: '+boundary)
                raise BufferError(self.error)
            self.budget.claim(len(raw))
            self.pending += len(raw); self.accepted += len(raw)
            try:
                self.queue.put_nowait(raw)
            except queue.Full:
                self.pending -= len(raw); self.accepted -= len(raw)
                self.budget.unclaim(len(raw))
                self._fault('Explicit event item queue exhausted')
                raise
        return len(raw)

    def _run(self):
        stream = None
        size = 0
        try:
            while True:
                raw = self.queue.get()
                try:
                    if raw is None:
                        break
                    if self.io_failed:
                        continue
                    if stream is None or size+len(raw) > self.segment_bytes:
                        if stream:
                            stream.flush(); os.fsync(stream.fileno()); stream.close()
                        path = self.path.with_name(self.path.name + '.%06d' % self.segment_count)
                        stream = path.open('xb'); self.segment_count += 1; size = 0
                    self.budget.check_free(self.path.parent, len(raw))
                    if stream.write(raw) != len(raw):
                        raise OSError('Short event write')
                    size += len(raw); self.completed += len(raw)
                except BaseException as exc:
                    self.io_failed = True
                    self._fault(repr(exc))
                finally:
                    if raw is not None:
                        with self.lock:
                            self.pending -= len(raw)
                    self.queue.task_done()
        finally:
            if stream:
                try:
                    stream.flush(); os.fsync(stream.fileno())
                except BaseException as exc:
                    self.io_failed = True
                    self._fault(repr(exc))
                finally:
                    stream.close()

    def close(self):
        with self.lock:
            if self.closed:
                if self.error: raise RuntimeError(self.error)
                return
            self.closed = True
        self.queue.put(None, timeout=10)
        self.thread.join(15)
        if self.thread.is_alive():
            raise TimeoutError('Event writer still owns output')
        publish(self.path.with_name(self.path.name+'.index.json'), dict(
            segment_count=self.segment_count, segment_pattern=self.path.name+'.%06d',
            accepted_bytes=self.accepted, completed_bytes=self.completed,
            error=self.error, refusal=self.refusal,
            planned_writer_bytes=self.maximum, cumulative_quota_enforced=False,
            complete=self.error is None and self.accepted == self.completed))
        if self.error:
            raise RuntimeError(self.error)

    def tell(self):
        return self.accepted

    def metrics(self):
        return dict(accepted=self.accepted, completed=self.completed, pending=self.pending,
                    closed=self.closed, error=self.error, refusal=self.refusal, segments=self.segment_count,
                    planned_writer_bytes=self.maximum, cumulative_quota_enforced=False)


_memory_details_lock = threading.Lock()
_memory_details = dict(sampled=-float('inf'), pid=None, values={})


def _extended_memory(now):
    with _memory_details_lock:
        if _memory_details['pid'] == os.getpid() and now-_memory_details['sampled'] < 1.0:
            age = now-_memory_details['sampled']
            return dict(_memory_details['values'], detailed_memory_age_seconds=age,
                        pss_sample_age_seconds=age if _memory_details['values']['pss_bytes'] is not None else None,
                        pss_sampled_monotonic_sec=_memory_details['sampled'] if _memory_details['values']['pss_bytes'] is not None else None)
        values = dict(virtual_bytes=None, vm_peak_bytes=None, vm_swap_bytes=None,
                      pss_bytes=None, pss_swap_bytes=None, detailed_memory_scope='current_process')
        try:
            fields = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
            for source, target in (('VmSize', 'virtual_bytes'), ('VmPeak', 'vm_peak_bytes'), ('VmSwap', 'vm_swap_bytes')):
                if source in fields:
                    values[target] = int(fields[source].split()[0])*1024
            rollup = dict(line.split(':', 1) for line in Path('/proc/self/smaps_rollup').read_text().splitlines() if ':' in line)
            for source, target in (('Pss', 'pss_bytes'), ('SwapPss', 'pss_swap_bytes')):
                if source in rollup:
                    values[target] = int(rollup[source].split()[0])*1024
        except (OSError, ValueError):
            # Missing rollup/permissions are unavailable metrics, not zero usage.
            pass
        values['peak_virtual_bytes'] = values['vm_peak_bytes']
        values['swap_bytes'] = values['vm_swap_bytes']
        _memory_details.update(sampled=now, pid=os.getpid(), values=values)
        return dict(values, detailed_memory_age_seconds=0.0,
                    pss_sample_age_seconds=0.0 if values['pss_bytes'] is not None else None,
                    pss_sampled_monotonic_sec=now if values['pss_bytes'] is not None else None)


def resource_snapshot():
    now = time.monotonic()
    result = dict(at_monotonic=now, pid=os.getpid(), scope='current_process',
                  whole_unit_aggregate=False)
    result.update(_extended_memory(now))
    try:
        import psutil
        process = psutil.Process()
        memory = process.memory_info()
        result.update(rss=memory.rss, cpu_seconds=sum(process.cpu_times()[:2]),
                      available_ram=psutil.virtual_memory().available, threads=process.num_threads())
        if result['virtual_bytes'] is None:
            result['virtual_bytes'] = memory.vms
    except ImportError:
        fields = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
        result.update(rss=int(fields['VmRSS'].split()[0])*1024,
                      available_ram=next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')),
                      cpu_seconds=time.process_time(), threads=int(fields['Threads']))
    for path, key in (('/sys/class/thermal/thermal_zone0/temp', 'temperature_millicelsius'),):
        if Path(path).is_file():
            result[key] = int(Path(path).read_text())
    # Temperature is not a substitute for firmware throttling flags.
    result['throttling_flags'] = None
    return result
