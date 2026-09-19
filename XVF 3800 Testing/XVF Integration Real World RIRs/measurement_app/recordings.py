"""Recycle exactly the latest completed recording, never an arbitrary path."""
import hashlib
import json
import subprocess
from pathlib import Path


def latest_recording(root):
    root = Path(root).resolve()
    candidates = []
    for path in root.iterdir():
        if not path.name.startswith(('JPXVF_', 'TAKE_')) or not path.is_dir():
            continue
        if path.is_symlink() or path.is_junction() or path.resolve().parent != root:
            continue
        request = path / 'request.json'
        if request.is_file() and ((path / 'result.json').is_file() or (path / 'server_failure.txt').is_file()):
            candidates.append(path)
    if not candidates:
        return None
    path = max(candidates, key=lambda p: (p.stat().st_birthtime_ns, p.name))
    payload = (path / 'request.json').read_bytes()
    setup = json.loads(payload).get('setup', {})
    manifest = path / 'SHA256SUMS.txt'
    token = hashlib.sha256(str(path.stat().st_birthtime_ns).encode() + payload +
                           (manifest.read_bytes() if manifest.exists() else b'')).hexdigest()
    return {'id': path.name, 'token': token, 'room_name': setup.get('room_name'),
            'position_name': setup.get('position_name'),
            'distance_m': setup.get('source', {}).get('distance_to_array_m'),
            'angle_deg': setup.get('source', {}).get('azimuth_lab_deg'),
            'pose': setup.get('device', {}).get('orientation')}


def recycle_directory(path, root):
    script = Path(__file__).with_name('Recycle-Recording.ps1')
    process = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(script),
        '-RunPath', str(path), '-ExperimentRoot', str(root)], capture_output=True, timeout=60,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if process.returncode:
        raise RuntimeError(process.stderr.decode('utf-8', errors='replace').strip() or 'Recycle Bin operation failed')


def recycle_latest(root, expected_id, expected_token, recycler=recycle_directory):
    """Caller holds the recording lease through discovery, recycling and verification."""
    root = Path(root).resolve()
    latest = latest_recording(root)
    if not latest or latest['id'] != expected_id or latest['token'] != expected_token:
        raise RuntimeError('The latest recording changed. Refresh and check the displayed run before deleting.')
    path = root / latest['id']
    if path.resolve().parent != root or path.is_symlink() or path.is_junction():
        raise RuntimeError('Recording is outside the experiment directory')
    recycler(path, root)
    if path.exists():
        raise RuntimeError('The recording still exists; no deletion was confirmed')
    return {**latest, 'deleted': True, 'disposition': 'Windows Recycle Bin',
            'message': 'Moved ' + latest['id'] + ' to the Recycle Bin. Restore it there if needed.'}
