"""Launch the activated immutable release from the logged-in graphical session."""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from release import read_json, validate_version, verify_release, check_data_schema

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--root', type=Path, required=True)
p.add_argument('--data-root', type=Path, required=True)
p.add_argument('app_args', nargs=argparse.REMAINDER)
a = p.parse_args()
if sys.platform != 'win32' and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
    p.error('Launch in the ordinary user graphical desktop session, not a headless root service.')
version = validate_version(read_json(a.root / 'current.json')['version'])
release = a.root / 'releases' / version
manifest=verify_release(release)
check_data_schema(a.data_root,manifest)
python = a.root / 'runtimes' / version / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if not python.is_file():
    p.error(f'Missing per-release runtime: {python}')
args = a.app_args[1:] if a.app_args[:1] == ['--'] else a.app_args
raise SystemExit(subprocess.call([str(python), str(release / 'main.py'), '--data-root', str(a.data_root), '--models', str(a.root / 'models'), *args], cwd=release))
