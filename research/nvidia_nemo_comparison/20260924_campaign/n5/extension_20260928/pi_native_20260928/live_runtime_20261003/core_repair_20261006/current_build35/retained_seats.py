"""Pure exact projection of the recovered seat model, without inference imports."""
import ast
from copy import deepcopy
import math
from pathlib import Path
import threading
import time
import types
import uuid
from runtime_support import digest, strict

_cached = None


def load(binding):
    global _cached
    if _cached is not None:
        return _cached
    base = Path(binding['installed_release'])
    manifest_path = base/'RELEASE_MANIFEST.json'
    if digest(manifest_path) != binding['installed_manifest_sha256']:
        raise ValueError('Seat source manifest changed')
    manifest = strict(manifest_path.read_bytes())
    row = next(r for r in manifest['files'] if r['path'] == 'app/seats.py')
    path = base/row['path']
    if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
        raise ValueError('Recovered seat model source changed')
    names = {'validate_layout', 'collisions', 'StubMotionService', 'SeatSession'}
    nodes = []
    for node in ast.parse(path.read_bytes()).body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('DEFAULT_TOLERANCE', 'MAPPING') for t in node.targets):
            nodes.append(node)
    if {n.name for n in nodes if isinstance(n, (ast.ClassDef, ast.FunctionDef))} != names:
        raise ValueError('Recovered seat model shape differs')
    scope = dict(deepcopy=deepcopy, math=math, threading=threading, time=time, uuid=uuid)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<retained-seat-model>', 'exec'), scope)
    _cached = types.SimpleNamespace(**{name:scope[name] for name in names})
    return _cached
