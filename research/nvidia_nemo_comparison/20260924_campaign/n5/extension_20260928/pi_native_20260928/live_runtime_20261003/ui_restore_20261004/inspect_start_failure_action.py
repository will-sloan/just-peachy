"""Read the installed shortcut and recent failed launch receipts. See README_DIAGNOSTIC.md."""
from pathlib import Path
import hashlib
import json
import os

home = Path('/home/peachyprototype')
desktop = home/'Desktop/JustPeachy.desktop'
shortcuts = []
for path in sorted((home/'Desktop').glob('*.desktop')):
    if 'peachy' in path.name.lower():
        raw = path.read_bytes()
        if len(raw) > 65536 or path.is_symlink():
            raise ValueError('Bounded real shortcut required')
        shortcuts.append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), text=raw.decode()))
data = home/'JustPeachy/research/nemotron-20260928/field-runtime-v29-data'
# The actual desktop command is authoritative; do not infer a data store.
import shlex
for row in shortcuts:
    for line in row['text'].splitlines():
        if line.startswith('Exec='):
            words = shlex.split(line[5:])
            if '--data-root' in words:
                data = Path(words[words.index('--data-root')+1])
if data.is_symlink() or data.parent != home/'JustPeachy/research/nemotron-20260928':
    raise ValueError('Canonical current runtime data root required')
records = []
launches = data/'launches'
if launches.exists():
    recent = sorted((p for p in launches.iterdir() if p.is_dir()), key=lambda p:p.stat().st_mtime_ns)[-12:]
    for folder in recent:
        for relative in ('REQUEST.json','START_FAILURE.json','CHILD_LAUNCH.json','HOST_CLOSURE.json',
                         'worker/REGISTERED_OWNER.json','worker/RESULT.json','worker/SESSION.json','WORKER.log'):
            path = folder/relative
            if not path.exists():
                continue
            if path.is_symlink() or path.stat().st_size > 1024*1024:
                raise ValueError('Bounded real launch diagnostic required')
            raw = path.read_bytes()
            records.append(dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                text=raw[-32768:].decode('utf-8',errors='replace')))
RESULT = dict(shortcuts=shortcuts, data_root=str(data), diagnostics=records,
              native_mutation=False, capture_started=False)
