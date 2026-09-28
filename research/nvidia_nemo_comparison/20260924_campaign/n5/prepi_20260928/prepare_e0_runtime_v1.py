"""Remove the retired E1 dependency from E0 selections. See README_E0_RUNTIME.md."""
import argparse
import difflib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'n4'))
from common import bind, freeze, load, verify
from metric_process import pin


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Expected one source anchor: ' + before[:80])
    return text.replace(before, after, 1)


def prepare(parent_receipt, output):
    pin()
    parent_binding = bind(parent_receipt)
    parent = load(parent_receipt)
    if parent['schema'] != 'prepi-shutdown-derivative-v1':
        raise ValueError('Expected reviewed shutdown parent')
    root = Path(parent['prototype']).resolve(strict=True)
    if output.exists():
        raise FileExistsError('Fresh derivative required')
    payloads = {}
    for relative, row in parent['files'].items():
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError('Source escaped parent')
        verify(dict(path=str(path), **row))
        payloads[relative] = path.read_bytes()
    originals = {name: payloads[name] for name in ('app/controller.py', 'app/n2_models.py')}
    controller = originals['app/controller.py'].decode('utf-8').replace('\r\n', '\n')
    controller = replace_once(controller, 'document=load_runtime(self.data_root)',
                              "document=load_runtime(self.data_root,embedding=components['embedding'])")
    models = originals['app/n2_models.py'].decode('utf-8').replace('\r\n', '\n')
    models = replace_once(models, 'def load_runtime(data_root):', """def load_runtime(data_root,*,embedding='E1'):
    # Legacy callers remain strict; explicitly selected E0 never requires E1 assets.
    if embedding not in ('E0','E1'):raise ValueError('Unknown embedding component')""")
    before = """    manifest=Path(document['titanet_manifest'])
    with manifest.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=document['titanet_manifest_sha256']:
            raise ValueError('TitaNet export manifest binding changed')
"""
    models = replace_once(models, before, "    if embedding=='E1':\n" + ''.join('    ' + line for line in before.splitlines(True)))
    for name, text in [('app/controller.py', controller), ('app/n2_models.py', models)]:
        compile(text, name, 'exec')
        payloads[name] = text.replace('\n', '\r\n' if b'\r\n' in originals[name] else '\n').encode('utf-8')
    payloads['tests/test_e0_runtime_v1.py'] = (HERE / 'test_e0_runtime_v1.py').read_bytes()
    payloads['README_E0_RUNTIME_V1.md'] = (HERE / 'README_E0_RUNTIME.md').read_bytes()
    output.mkdir(parents=True)
    files = {}
    for relative, raw in payloads.items():
        path = output / 'prototype' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
        files[relative] = {k: v for k, v in bind(path).items() if k != 'path'}
    differences = []
    for name, raw in originals.items():
        differences.extend(difflib.unified_diff(raw.decode('utf-8').splitlines(True),
            payloads[name].decode('utf-8').splitlines(True), fromfile='parent/'+name, tofile='derivative/'+name))
    (output / 'CHANGES.patch').write_text(''.join(differences), encoding='utf-8')
    freeze(output / 'DERIVATIVE.json', dict(schema='prepi-e0-runtime-derivative-v1',
        status='PREPARED_NOT_RELEASE_ACCEPTED', parent_source_receipt=parent_binding,
        prototype=str(output / 'prototype'), files=files, builder=bind(__file__),
        window=bind(HERE / 'WINDOW.json'), changed_code=list(originals),
        scope='E0 selects only its own dependencies; legacy E1 checks and native runtime integrity remain strict'))
    print(dict(status='PREPARED_NOT_RELEASE_ACCEPTED', files=len(files), output=str(output)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-receipt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    prepare(a.parent_receipt, a.output)
