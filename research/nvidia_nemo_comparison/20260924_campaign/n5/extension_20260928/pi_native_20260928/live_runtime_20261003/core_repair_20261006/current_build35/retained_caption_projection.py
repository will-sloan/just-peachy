"""Reuse the pinned original segment presentation loop. See README.md."""
import ast
from copy import deepcopy
import re
from types import SimpleNamespace
from runtime_support import digest, strict

_project = None


def load(binding):
    global _project
    if _project is not None:
        return _project
    from pathlib import Path
    root = Path(binding['installed_release'])
    manifest_path = root/'RELEASE_MANIFEST.json'
    if digest(manifest_path) != binding['installed_manifest_sha256']:
        raise ValueError('Original caption projection manifest changed')
    pins = {r['path']: r['sha256'] for r in strict(manifest_path.read_bytes())['files']}
    source = root/'app/controller.py'
    if digest(source) != pins['app/controller.py']:
        raise ValueError('Original caption projection source changed')
    tree = ast.parse(source.read_bytes())
    controller = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Controller')
    snapshot = next(n for n in controller.body if isinstance(n, ast.FunctionDef) and n.name == 'snapshot')
    loops = [n for n in snapshot.body if isinstance(n, ast.For) and
        isinstance(n.iter, ast.Name) and n.iter.id == 'raw' and
        n.body and isinstance(n.body[0], ast.Assign) and
        any(isinstance(t, ast.Name) and t.id == 'segments' for t in n.body[0].targets)]
    if len(loops) != 1:
        raise ValueError('Exact original supported-prefix segment loop required')
    function = ast.parse('def project(self, raw, people, assistance):\n'
        '    names = [p["name"] for p in people]\n'
        '    active_rules = {e["id"] for e in assistance["entries"] if e.get("active") and e.get("approved_auto")}\n'
        '    rows = []\n').body[0]
    function.body.extend([deepcopy(loops[0]), ast.Return(value=ast.Name(id='rows', ctx=ast.Load()))])
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    from app.casing import provisional_case
    from app.text_assistance import corrected_partition
    from app.mode_policy import NAMED_MODES
    namespace = dict(deepcopy=deepcopy, re=re, provisional_case=provisional_case,
        corrected_partition=corrected_partition, NAMED_MODES=NAMED_MODES)
    exec(compile(module, '<retained-caption-segment-loop>', 'exec'), namespace)
    original = namespace['project']
    def project(row, intent, people, assistance=None):
        state = SimpleNamespace(mode=intent['mode'], selected_ids=intent['selected_ids'],
            display_ids=intent['display_ids'], strict=intent['strict'])
        return original(state, [row], people, assistance or dict(enabled=False, entries=[]))
    _project = project
    return _project
