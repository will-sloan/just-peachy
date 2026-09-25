"""Fail-closed live admission for a supervised application cell. README_PACED_SLOT.md."""
from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
import math
import os
from pathlib import Path
import shutil
import sys
import time

import psutil
from common import bind, fingerprint, load, verify
from metric_process import exact_process, identity
from scoring_bank import writer_lock

GIB = 1024**3
MAX_CELL_BYTES = 512*1024**2
DEADLINE = datetime(2026, 9, 28, 14, 48, 19, tzinfo=timezone.utc)


def require(condition, message):
    if not condition: raise ValueError(message)


def key(owner):
    require(type(owner.get('pid')) is int and owner['pid'] > 0 and type(owner.get('create_time')) in (int, float)
            and math.isfinite(owner['create_time']) and owner['create_time'] > 0, 'Invalid exact process identity')
    return owner['pid'], owner['create_time']


def validate_supervision(record, coordinator, observations, now):
    """Pure identity/heartbeat contract; PID reuse and uncertainty cannot pass."""
    key(coordinator)
    require(record.get('status') == 'RUNNING' and record.get('child_launch_pending') is False
            and record.get('child_pid') == coordinator['pid'] and record.get('child_create_time') == coordinator['create_time'],
            'This is not the exact active supervised coordinator')
    require(type(record.get('heartbeat_unix')) in (int, float) and math.isfinite(record['heartbeat_unix'])
            and 0 <= now-record['heartbeat_unix'] <= 60, 'Supervisor heartbeat stale or invalid')
    supervisor = dict(pid=record['pid'], create_time=record['create_time']); key(supervisor)
    for who in (supervisor, coordinator):
        observed = observations.get(who['pid'])
        require(observed is not None and observed['create_time'] == who['create_time']
                and observed['affinity'] == [14], 'Supervised owner absent, reused, uncertain or on wrong CPU')
    require(observations[coordinator['pid']]['parent_pid'] == supervisor['pid'], 'Coordinator is not the direct supervised child')
    require(isinstance(record.get('run_id'), str) and bool(record['run_id']), 'Missing supervised run identity')
    return supervisor


def observe_owner(who):
    process = exact_process(who)
    require(process is not None, 'Required exact process has exited or PID was reused')
    return dict(**identity(process), parent_pid=process.ppid(), affinity=process.cpu_affinity(), executable=process.exe())


def process_census(campaign_root):
    """Observe possible competitors, without probing devices or stopping anything.

    All Python, WSL/QEMU and known native speech processes are included. Shell
    commands that mention this campaign and a Python script are helpers too.
    Access denial for these processes is an error, not evidence of absence.
    """
    rows = []; errors = []; scanned = 0; root = str(Path(campaign_root).resolve()).lower()
    for process in psutil.process_iter(['pid', 'name']):
        scanned += 1
        require(scanned <= 4096, 'Host process census exceeds declared bound')
        name = (process.info['name'] or '').lower()
        known = name.startswith(('python', 'qemu', 'nemotron', 'nemo-speech')) or name in ('wsl.exe', 'wslhost.exe')
        shell = name in ('powershell.exe', 'pwsh.exe', 'cmd.exe')
        if not known and not shell: continue
        try:
            argv = process.cmdline()
            command = ' '.join(argv).lower()
            if not known and not (root in command and '.py' in command): continue
            rows.append(dict(**identity(process), parent_pid=process.ppid(), affinity=process.cpu_affinity(),
                executable=process.exe(), name=name, argv_sha256=fingerprint(argv), kind='interpreter_or_native' if known else 'campaign_shell'))
        except psutil.NoSuchProcess: continue
        except (psutil.AccessDenied, psutil.ZombieProcess, OSError) as exc:
            errors.append(dict(pid=process.pid, kind=type(exc).__name__, name=name))
    return dict(rows=rows, errors=errors, scanned=scanned, observed_unix=time.time(),
        limitations='Conservative known-runtime census, not a proof that unrelated host workloads are idle')


def competitors(census, allowed):
    require(not census['errors'], 'Process ownership could not be established')
    identities = {key(who) for who in allowed}
    require(len(identities) == len(allowed), 'Duplicate allowed owner')
    return [row for row in census['rows'] if key(row) not in identities]


def validate_policy(policy, free_bytes, now, output_bytes=0, reservation_bytes=MAX_CELL_BYTES):
    require(now.tzinfo is not None, 'UTC-aware time required')
    original_cutoff = DEADLINE-timedelta(hours=12)
    configured_cutoff = datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12)
    require(now < min(original_cutoff, configured_cutoff), 'Original packaging reserve reached')
    resources = policy['resource_policy']
    require(resources['gpu_owner'] is None and 0 < resources['max_cpu_cores'] <= 2
            and 0 < resources['max_parallel_workers'] <= 2, 'Resource policy is not admitted CPU-only scope')
    require(type(reservation_bytes) is int and 0 < reservation_bytes <= MAX_CELL_BYTES
            and type(output_bytes) is int and 0 <= output_bytes <= reservation_bytes, 'Application cell output bound exceeded')
    for drive, base_floor in (('C:', 50), ('G:', 75)):
        floor = max(base_floor, resources['minimum_free_gib'][drive])*GIB
        require(free_bytes[drive] >= floor+reservation_bytes, 'Application drive floor unavailable')
    require(0 < resources['new_payload_allowance_gib'] <= 50, 'Shared payload policy changed')


def bounded_output_bytes(root):
    total = count = 0; pending = [Path(root)] if Path(root).exists() else []
    while pending:
        directory = pending.pop()
        for entry in os.scandir(directory):
            count += 1; require(count <= 10000, 'Application output file census exceeded')
            info = entry.stat(follow_symlinks=False)
            require(not entry.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 1024, 'Application output contains a reparse point')
            if entry.is_dir(follow_symlinks=False): pending.append(Path(entry.path))
            else:
                total += info.st_size
                require(total <= MAX_CELL_BYTES, 'Application cell hard output bound exceeded')
    return total


class ExclusiveApplicationSlot:
    """Ownership/resource gate, not a launcher or source-execution permission.

    Caller must first verify the production plan and fixed worker code. The
    future launcher owns child cleanup. release() refuses a live registered
    application; the guard never signals or terminates any process.
    """
    def __init__(self, state, output, *, reservation_bytes=MAX_CELL_BYTES):
        self.state = Path(state).resolve(strict=True); self.local = self.state.parent
        require(self.state.name == 'supervision' and (self.state/'campaign.json').is_file(), 'Exact campaign supervision required')
        self.output = Path(output).resolve()
        require(self.output.is_relative_to((self.local/'n4').resolve()) and not self.output.exists(), 'Fresh private application cell output required')
        require(type(reservation_bytes) is int and 0 < reservation_bytes <= MAX_CELL_BYTES, 'Invalid cell reservation')
        self.reservation = reservation_bytes; self.coordinator = identity(psutil.Process()); self.application = None
        self.locks = None; self.run_id = None; self.last_output_scan = 0.; self.output_size = 0

    def _ownership(self):
        record = load(self.state/'worker.json')
        supervisor = dict(pid=record['pid'], create_time=record['create_time'])
        observations = {who['pid']: observe_owner(who) for who in (supervisor, self.coordinator)}
        validate_supervision(record, self.coordinator, observations, time.time())
        if self.run_id is not None: require(record['run_id'] == self.run_id, 'Supervised run changed during application cell')
        allowed = [supervisor, self.coordinator]
        if self.application is not None:
            app = observe_owner(self.application)
            require(app['parent_pid'] == self.coordinator['pid'] and app['affinity'] == [4], 'Application ownership or CPU placement changed')
            allowed.append(self.application)
        census = process_census(self.local.parent)
        unexpected = competitors(census, allowed)
        require(not unexpected, 'Another model/helper or unadmitted runtime is active: '+','.join(str(r['pid']) for r in unexpected))
        return record, census

    def acquire(self):
        require(self.locks is None, 'Application slot already acquired')
        require(psutil.Process().cpu_affinity() == [14], 'Coordinator must already be pinned to CPU14')
        stack = ExitStack()
        try:
            stack.enter_context(writer_lock(self.local/'n4/paced-application.owner.lock'))
            stack.enter_context(writer_lock(self.local/'n4/metric-scoring.owner.lock'))
            record, census = self._ownership()
            self._resources(force_scan=True)
            from asr_full_bank import payload_inventory
            inventory = payload_inventory(self.local); policy = load(self.state/'campaign.json')
            require(not inventory['errors'] and inventory['total_logical_bytes']+6*GIB+self.reservation <=
                    min(50, policy['resource_policy']['new_payload_allowance_gib'])*GIB, 'Shared allowance cannot admit application cell')
            self.run_id = record['run_id']; self.locks = stack
            return dict(coordinator=self.coordinator, supervised_run=self.run_id, census=census, inventory=inventory,
                reservation_bytes=self.reservation, cpu_affinity=[4], gpu=False, source_execution_authorized=False,
                remaining_gate='Reviewed fixed private-desktop launcher and child admission required')
        except BaseException:
            stack.close(); raise

    def _resources(self, force_scan=False):
        if force_scan or time.monotonic()-self.last_output_scan >= 5:
            self.output_size = bounded_output_bytes(self.output); self.last_output_scan = time.monotonic()
        free = {drive: shutil.disk_usage(drive+'/').free for drive in ('C:', 'G:')}
        validate_policy(load(self.state/'campaign.json'), free, datetime.now(timezone.utc), self.output_size, self.reservation)

    def register_application(self, owner, *, executable_binding, argv_sha256):
        require(self.locks is not None and self.application is None, 'Fresh acquired slot required')
        key(owner); verify(executable_binding); process = exact_process(owner)
        require(process is not None and process.ppid() == self.coordinator['pid'] and process.cpu_affinity() == [4], 'Child must be the exact direct CPU4 application')
        require(bind(process.exe()) == executable_binding and fingerprint(process.cmdline()) == argv_sha256, 'Child executable or command differs')
        self.application = dict(owner)
        self.check()

    def check(self):
        require(self.locks is not None, 'No acquired application slot')
        record, census = self._ownership(); self._resources()
        return dict(supervised_run=record['run_id'], checked_unix=census['observed_unix'], possible_competitors=len(census['rows']),
                    output_bytes_last_scan=self.output_size)

    def release(self):
        require(self.locks is not None, 'No application slot to release')
        if self.application is not None:
            require(exact_process(self.application) is None, 'Application still alive; caller must close its exact child first')
        self.locks.close(); self.locks = None
        return dict(status='APPLICATION_SLOT_RELEASED', coordinator=self.coordinator, application=self.application,
                    child_cleanup_performed_by_guard=False, source_execution_authorized=False)
