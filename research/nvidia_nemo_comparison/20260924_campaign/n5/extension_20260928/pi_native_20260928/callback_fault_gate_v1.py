"""Serialize admitted preview dispatch. See README_CALLBACK_FAULT_V1.md."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    os.sched_setaffinity(0, {3})
    run = Path(__file__).resolve().parent
    campaign = run.parent
    with (campaign/'B05_PREVIEW_DISPATCH.lock').open('a') as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('A preview dispatch already holds the research lease.', flush=True)
            return 73
        if '--contend' in sys.argv:
            return 74  # The probe must be rejected before acquiring this lease.
        admission = json.loads((run/'ADMISSION.json').read_text())
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        assert boot == admission['boot_id'] and os.getuid() != 0
        assert datetime.now(timezone.utc) < datetime.fromisoformat(admission['expires_utc'])
        for row in admission['files']:
            assert sha(Path(row['path'])) == row['sha256'], row['path']
        assert sha(Path.home()/'JustPeachy/install/current.json') == 'fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
        def ticks(pid):
            try:
                return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
            except FileNotFoundError:
                return None
        for path in campaign.rglob('*OWNER*.json'):
            owner = json.loads(path.read_text())
            assert not(owner['boot_id'] == boot and ticks(owner['pid']) == owner['start_ticks']), str(path)
        assert not subprocess.check_output(['systemctl', '--user', 'list-units', '--state=active,activating,deactivating', '--no-legend', 'jp-*'], text=True).strip()
        assert ticks(1013) == 569 and ticks(1130) == 607
        available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        assert available >= 850*1024**2 and shutil.disk_usage(campaign).free >= 5*1024**3
        owner = dict(pid=os.getpid(), start_ticks=ticks(os.getpid()), boot_id=boot,
                     admission_sha256=sha(run/'ADMISSION.json'), role='B01_restart_gui_dispatch_lease')
        with (run/'DISPATCH_OWNER.json').open('x') as stream:
            json.dump(owner, stream)
        # Keep the exact dispatch owner visible to the existing owner scanners
        # until systemd-run --wait closes; never use a PID alone as a lease.
        result = dict(status='DISPATCH_PENDING', owner=owner, lock_held_through_service=True)
        python = str(Path.home()/'JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python')
        cmd = ['systemd-run', '--user', '--unit=jp-'+run.name, '--wait', '--pipe',
               '--setenv=DISPLAY=:0', '--setenv=XAUTHORITY=/home/peachyprototype/.Xauthority',
               '--setenv=ORT_DISABLE_TELEMETRY=1', '--setenv=MALLOC_ARENA_MAX=1',
               '--setenv=MALLOC_MMAP_THRESHOLD_=131072', '--setenv=MALLOC_TRIM_THRESHOLD_=131072']
        for prop in ['LimitSTACK=1048576', 'TasksMax=64', 'CPUQuota=200%', 'RuntimeMaxSec=180',
                     'TimeoutStopSec=10', 'LimitCORE=0', 'Nice=10']:
            cmd += ['-p', prop]
        cmd += ['taskset', '-c', '2,3', python, '-B']
        assert admission['ui_mode']=='callback_fault' and admission['mode']=='model_free' and not admission['capture']
        cmd += [str(run/'check_callback_fault_v1.py')]
        try:
            completed = subprocess.run(cmd, timeout=205)
            result['exit_code'] = completed.returncode
            result['status'] = 'SERVICE_CLOSED_REQUIRES_REVIEW'
            return completed.returncode
        finally:
            result['ended_utc'] = datetime.now(timezone.utc).isoformat()
            with (run/'DISPATCH_RESULT.json').open('x') as stream:
                json.dump(result, stream, indent=2)


if __name__ == '__main__':
    raise SystemExit(main())
