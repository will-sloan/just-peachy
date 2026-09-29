"""Read-only CM5 inventory; send through SSH stdin. See README.md."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
from datetime import datetime, timezone


def command(argv):
    try:
        value = subprocess.run(argv, capture_output=True, text=True, timeout=5)
        return dict(exit_code=value.returncode, stdout=value.stdout.strip(), stderr=value.stderr.strip())
    except Exception as exc:
        return dict(error=str(exc))


def main():
    model = Path('/proc/device-tree/model').read_text().rstrip('\0')
    if not model.startswith('Raspberry Pi Compute Module 5') or os.getuid() == 0:
        raise RuntimeError('Expected confirmed CM5 ordinary account')
    root = Path.home() / 'JustPeachy/install'
    memory = {k: int(v.split()[0])*1024 for k, v in
              (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
              if k in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree')}
    processes = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            cmd = (path/'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if 'JustPeachy' not in cmd and 'nemo-speech' not in cmd:
                continue
            stat = (path/'stat').read_text().rsplit(')', 1)[1].split()
            processes.append(dict(pid=int(path.name), start_ticks=int(stat[19]),
                                  command=cmd, state=stat[0],
                                  resource_lines=[x for x in (path/'status').read_text().splitlines()
                                                  if x.startswith(('VmRSS:', 'Threads:', 'Cpus_allowed_list:'))]))
        except (OSError, ValueError):
            pass
    packages = {}
    for name in ('numpy', 'onnxruntime', 'sherpa-onnx', 'soundfile', 'psutil'):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    result = dict(schema='cm5-read-only-inventory.v1', utc=datetime.now(timezone.utc).isoformat(),
                  model=model, hostname=socket.gethostname(), uid=os.getuid(),
                  boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  architecture=platform.machine(), kernel=platform.release(),
                  os_release=Path('/etc/os-release').read_text(), python=platform.python_version(),
                  python_executable=os.sys.executable, glibc=platform.libc_ver(),
                  cpu_count=os.cpu_count(), affinity=sorted(os.sched_getaffinity(0)),
                  cpu_features=sorted(set(line.split(':', 1)[1].strip() for line in
                      Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('Features'))),
                  memory_bytes=memory, disk_bytes=shutil.disk_usage(Path.home())._asdict(),
                  temperature_millic=int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()),
                  throttling=command(['vcgencmd', 'get_throttled']),
                  arm_clock=command(['vcgencmd', 'measure_clock', 'arm']),
                  current_install=json.loads((root/'current.json').read_text()),
                  packages=packages, relevant_processes=processes,
                  user_cgroup=command(['systemctl', '--user', 'show', '-p', 'ControlGroup']),
                  commands_available={x: shutil.which(x) for x in ('systemd-run', 'taskset', 'cmake', 'g++', 'readelf')},
                  scope='Metadata only; no capture, device enumeration, model load, GUI operation or performance qualification')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
