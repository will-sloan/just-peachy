"""Pure original recipe projection; no model imports. See README.md."""
import ast
from copy import deepcopy
from pathlib import Path
from runtime_support import digest, strict


def recipes(binding, selection):
    root = Path(binding['installed_release'])
    manifest = root/'RELEASE_MANIFEST.json'
    if digest(manifest) != binding['installed_manifest_sha256']:
        raise ValueError('Original recipe manifest changed')
    pins = {row['path']: row['sha256'] for row in strict(manifest.read_bytes())['files']}
    source = root/'app/pipeline.py'
    if digest(source) != pins['app/pipeline.py']:
        raise ValueError('Original recipe source changed')
    tree = ast.parse(source.read_bytes())
    assignment = [node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'RECIPES' for t in node.targets)]
    loops = [node for node in tree.body if isinstance(node, ast.For)
        and isinstance(node.iter, ast.Name) and node.iter.id == 'RECIPES']
    if len(assignment) != 1 or len(loops) != 1:
        raise ValueError('Exact original recipe definition required')
    from application_contract import MODES
    namespace = dict(MODES=MODES)
    module = ast.fix_missing_locations(ast.Module(body=deepcopy(assignment+loops), type_ignores=[]))
    exec(compile(module, '<retained-original-recipes>', 'exec'), namespace)
    result = deepcopy(namespace['RECIPES'])
    for row in result:
        row['taps'] = ['O0']
        if row['id'] == 'classic' and selection.diarizer != 'pyannote':
            row.update(available=False, reason='The original B36 recipe requires its Pyannote continuity tracker.')
    return result
