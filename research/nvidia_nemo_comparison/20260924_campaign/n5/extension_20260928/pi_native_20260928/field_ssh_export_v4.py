"""Read-only Pi evidence exporter. See README_FIELD_SSH_MIRROR_V4.md."""
import os
os.sched_setaffinity(0, {2, 3})
import fcntl
import hashlib
import json
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone


def run(request, modules):
    # Modules are exact admitted source bytes injected by the small bootstrap.
    from field_host_budget_v1 import real
    from field_streamed_mirror_v1 import CHUNK, ancestors, identity, inventory, plan
    from field_ssh_mirror_v1 import receive_json, send_json
    root = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
    a = request['admission']
    assert datetime.now(timezone.utc) < datetime.fromisoformat(a['expires_utc']) <= datetime.fromisoformat('2026-10-01T17:42:44+00:00')
    assert set(os.sched_getaffinity(0)) == {2, 3}
    assert resource.getrlimit(resource.RLIMIT_AS)[0] == 128*1024**2
    assert resource.getrlimit(resource.RLIMIT_STACK)[0] == 1024**2
    assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
    assert os.uname().machine == 'aarch64'
    def ticks(pid):
        try: return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
        except FileNotFoundError: return None
    def sha(p):
        with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot == a['boot_id'] and ticks(1013) == 569 and ticks(1130) == 607
    assert sha(Path.home()/'JustPeachy/install/current.json') == a['install_sha256']
    assert sha(Path.home()/'JustPeachy/data/live_config.json') == a['live_config_sha256']
    assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip() == 'closed'
    assert {k:hashlib.sha256(v.encode()).hexdigest() for k,v in modules.items()} == a['module_sha256']
    source = root / a['source_relative']
    assert source.parent == root and source.name == 'd1-visible-entry-v2'
    deadline = time.monotonic() + 75
    signal.alarm(80)
    owner = dict(pid=os.getpid(), start_ticks=ticks(os.getpid()), boot_id=boot)
    unit = 'jp-field-ssh-mirror-v4.service'
    props = subprocess.check_output(['systemctl', '--user', 'show', unit,
        '-p', 'CPUQuotaPerSecUSec', '-p', 'TasksMax', '-p', 'LimitAS', '-p', 'LimitSTACK',
        '-p', 'RuntimeMaxUSec', '-p', 'TimeoutStopUSec', '-p', 'LimitFSIZE'], text=True)
    assert 'TasksMax=64\n' in props and 'LimitAS=134217728\n' in props and 'LimitSTACK=1048576\n' in props
    with (root/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX|fcntl.LOCK_NB)
        with (Path.home()/'JustPeachy/data/xvf-hardware.lock').open('r+b') as hw:
            fcntl.flock(hw, fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.flock(hw, fcntl.LOCK_UN)
        for row in a['closed_owners']:
            assert not (row['boot_id'] == boot and ticks(row['pid']) == row['start_ticks'])
        units = subprocess.check_output(['systemctl', '--user', 'list-units', '--state=active,activating,deactivating', '--plain', '--full', '--no-pager', '--no-legend', 'jp-*'], text=True)
        send_json(sys.stdout.buffer, dict(owner=owner, properties=props, source=str(source), active_units=units))
        assert receive_json(sys.stdin.buffer, deadline) == dict(ack=owner)
        names = [line.split()[0] for line in units.splitlines() if line.strip()]
        assert names == [unit], repr(names)
        def guard(initial=False):
            import shutil
            ram = next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
            assert ram >= (850 if initial else 192)*1024**2
            assert shutil.disk_usage(root).free >= 5*1024**3
        guard(True)
        value = plan(source, request['files'], deadline, a['mirror_maximum_bytes'])
        public = {k:v for k,v in value.items() if k != 'source_identities'}
        send_json(sys.stdout.buffer, public)
        for name, row in sorted(value['files'].items()):
            path = source/name
            ancestors(path.parent)
            assert identity(real(path)) == value['source_identities'][name]
            send_json(sys.stdout.buffer, dict(file=name, bytes=row['bytes']))
            h, left = hashlib.sha256(), row['bytes']
            with path.open('rb', buffering=0) as f:
                while left:
                    assert time.monotonic() < deadline
                    guard()
                    block = f.read(min(CHUNK, left))
                    if not block: raise EOFError('Source truncated')
                    sys.stdout.buffer.write(block); sys.stdout.buffer.flush()
                    h.update(block); left -= len(block)
                assert not f.read(1)
            assert identity(real(path)) == value['source_identities'][name]
            assert h.hexdigest() == row['sha256']
        after, dirs = inventory(source, deadline)
        assert after == value['source_identities'] and dirs == set(value['directories'])
        send_json(sys.stdout.buffer, dict(status='SOURCE_TREE_UNCHANGED', files=len(after), bytes=value['bytes']))
