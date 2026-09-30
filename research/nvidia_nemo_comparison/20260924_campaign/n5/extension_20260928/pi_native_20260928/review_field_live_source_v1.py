"""Read/compile the fresh source derivation; README_FIELD_LIVE_SOURCE_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--installed-mirror', type=Path, required=True)
    args = parser.parse_args()
    p = Path(__file__).parent
    b = args.preparation
    admission = json.loads((b/'REVIEW_CONTINUATION_V1.json').read_bytes())
    assert admission['native_dispatch'] is False
    assert datetime.now(timezone.utc) < datetime.fromisoformat(admission['expires_utc'])
    destination = b/'SOURCE_REVIEW_V1.json'
    if destination.exists():
        raise FileExistsError('Closed source review must not be replayed')
    changes = json.loads((b/'DERIVATION_V1.json').read_bytes())['files']
    derived = []
    for row in changes:
        assert digest(p/row['old']) == row['old_sha256']
        assert digest(p/row['new']) == row['new_sha256']
        text = (p/row['old']).read_text()
        for change in row['replacements']:
            assert text.count(change['before']) == change['count']
            text = text.replace(change['before'], change['after'])
        assert text == (p/row['new']).read_text()
        derived.append(row['new'])
    correction = json.loads((b/'STOP_ORDER_DERIVATION_V1.json').read_bytes())
    for name in ('old','new'):
        assert digest(p/correction[name]) == correction[name+'_sha256']
    source = ast.parse((p/'isolated_pipeline_source_v5.py').read_text())
    cls = next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='IsolatedPipelineSource')
    methods = {n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    old_cls = next(n for n in ast.parse((p/'isolated_pipeline_source_v2.py').read_text()).body
                   if isinstance(n,ast.ClassDef) and n.name==cls.name)
    unchanged = []
    for method in old_cls.body:
        if isinstance(method,ast.FunctionDef) and method.name not in ('start','_accept','_run','_error'):
            assert ast.dump(method)==ast.dump(methods[method.name])
            unchanged.append(method.name)
    error = ast.unparse(methods['_error'])
    assert error.index('self.stop_event.set()') < error.index("self.callback('source_timing'")
    accept = ast.unparse(methods['_accept'])
    assert accept.index('2080000') < accept.index('self.timing.accept')
    assert accept.index('self.journal.append') < accept.index('self.sent +=') < accept.index('outputs.trace')
    assert accept.index('self.stop_event.set()') < accept.index("self.callback('source_limit'")
    run = ast.unparse(methods['_run'])
    assert 'accepted_before = self.sent' in run and 'if self.sent == accepted_before:' in run
    files = derived + ['field_live_layout_v3.py','field_live_source_outputs_v1.py',
                       'field_live_source_factory_v1.py','isolated_pipeline_source_v4.py',
                       'isolated_pipeline_source_v5.py']
    pins = []
    for name in files:
        raw = (p/name).read_bytes()
        compile(raw, name, 'exec')
        pins.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    installed = args.installed_mirror
    manifest = installed/'RELEASE_MANIFEST.json'
    assert digest(manifest)=='274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'
    entries = {row['path']:row for row in json.loads(manifest.read_bytes())['files']}
    live = installed/'app/live_audio.py'
    assert digest(live)==entries['app/live_audio.py']['sha256']
    live_cls = next(n for n in ast.parse(live.read_text()).body
                    if isinstance(n,ast.ClassDef) and n.name=='XVFLiveSource')
    start = next(n for n in live_cls.body if isinstance(n,ast.FunctionDef) and n.name=='start')
    assert 'consent' in [n.arg for n in start.args.kwonlyargs]
    receipt = dict(status='PREPARED_ACTUAL_SOURCE_DERIVATION_REVIEWED_NOT_EXECUTED',
        as_of_utc=datetime.now(timezone.utc).isoformat(),host_affinity=[14],
        exact_full_file_derivations=derived,unchanged_selected_source_methods=unchanged,
        changed_accounting_and_stop_order_reviewed=True,files=pins,
        actual_installed_live_source_sha256=digest(live),
        installed_modules_imported=False,native_execution=False,capture=False,
        limitations=['No source/transport constructors or callbacks executed',
            'No hardware route/Stop/terminal or failure-concurrency proof',
            'Full FieldController, config/archive writers and streamed host mirror remain open',
            'Prepared full layout remains unadmitted'])
    raw = json.dumps(receipt,indent=2,allow_nan=False).encode()
    assert len(raw)<=65536
    with destination.open('xb') as handle:
        handle.write(raw)
    print(json.dumps(dict(status=receipt['status'],derivations=len(derived),compiled_files=len(files),
                          unchanged_methods=unchanged,native_execution=False)))


if __name__=='__main__':
    main()
