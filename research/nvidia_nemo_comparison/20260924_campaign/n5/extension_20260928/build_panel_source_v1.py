"""Reapply the qualified complete-journal sink to the current source; README_PANEL_RETRY_V1.md."""
from pathlib import Path
import ast
import shutil
import sys
import unittest

HERE = Path(__file__).resolve().parent
N4 = HERE.parent.parent / 'n4'
sys.path.insert(0, str(N4))
from common import bind, freeze, load, verify
from metric_process import pin, exact_process
from window_guard import window


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Changed source anchor: ' + old)
    return text.replace(old, new, 1)


def main():
    pin(); window()
    local = HERE.parent.parents[4] / 'local'
    census = bind(local / 'n5/research-extension-20260928/census-20260928T2301.json')
    c = load(census['path'])
    if c['status'] != 'CENSUS_ONLY_NO_WORKER_DISPATCHED':
        raise ValueError('Missing census')
    w = load(local / 'supervision/worker.json')
    owners = [dict(pid=w['pid'], create_time=w['create_time'])]
    if w.get('child_pid'):
        owners.append(dict(pid=w['child_pid'], create_time=w['child_create_time']))
    if any(exact_process(o) is not None for o in owners):
        raise RuntimeError('Prior owner remains')
    parent = bind(local / 'n5/research-extension-20260928/derivatives/component-costs-v1/DERIVATIVE.json')
    if parent['sha256'] != '98c63f2d56d2c91e84b42dc72a4ed08bb04790fdb1a483272e0c12bbc07f9f02':
        raise ValueError('Unreviewed parent')
    d = load(parent['path']); source = Path(d['prototype'])
    target = local / 'n5/research-extension-20260928/derivatives/panel-journal-v1'
    if target.exists():
        raise FileExistsError(target)
    if sum(r['bytes'] for r in d['files'].values()) > 16*1024**2:
        raise ValueError('Source copy exceeds reservation')
    prototype = target / 'prototype'
    for name, row in d['files'].items():
        verify(dict(path=str(source/name), **row))
        out = prototype/name; out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/name, out)
    path = prototype/'app/buffers.py'; text = path.read_bytes().decode('utf-8')
    text = once(text, 'def __init__(self, path, capacity=4096, delay_once=0):',
                'def __init__(self, path, capacity=4096, delay_once=0, sink_factory=None):')
    text = once(text, 'self.sink = RotatingText(path)', 'self.sink = (sink_factory or RotatingText)(path)')
    ast.parse(text); path.write_bytes(text.encode('utf-8'))
    path = prototype/'app/pipeline.py'; text = path.read_bytes().decode('utf-8')
    newline = '\r\n' if '\r\n' in text else '\n'
    text = once(text, 'from .buffers import MemoryJournal, AsyncText',
                'from .buffers import MemoryJournal, AsyncText'+newline+'from .native_complete_text import CompleteText')
    text = once(text, "writer=AsyncText(path,delay_once=self.writer_delay if Path(path).name=='events.jsonl' else 0)",
                "writer=AsyncText(path,delay_once=self.writer_delay if Path(path).name=='events.jsonl' else 0,sink_factory=CompleteText if Path(path).name=='events.jsonl' else None)")
    ast.parse(text); path.write_bytes(text.encode('utf-8'))
    shutil.copyfile(N4/'native_complete_text.py', prototype/'app/native_complete_text.py')
    shutil.copyfile(HERE/'README_PANEL_RETRY_V1.md', prototype/'README_PANEL_RETRY_V1.md')
    files = {}
    for path in sorted(prototype.rglob('*')):
        if path.is_file():
            b = bind(path); files[path.relative_to(prototype).as_posix()] = {k:b[k] for k in ('sha256','bytes')}
    changed = sorted(k for k,v in d['files'].items() if files[k] != v)
    if changed != ['app/buffers.py','app/pipeline.py']:
        raise ValueError('Unexpected source mutation')
    import test_native_journal_retention as tests
    tests.SOURCE = prototype; tests.OUTPUT = target/'retention-tests'; tests.OUTPUT.mkdir()
    with (target/'retention-tests.txt').open('x', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    if not result.wasSuccessful() or result.testsRun != 8:
        raise RuntimeError('Complete-journal qualification failed')
    freeze(target/'DERIVATIVE.json', dict(schema='extended-panel-journal-v1', status='PREPARED_NOT_APPLICATION_ACCEPTED',
        prototype=str(prototype), parent_source_receipt=parent, files=files, changed_code=changed,
        added=['app/native_complete_text.py','README_PANEL_RETRY_V1.md'],
        retained_inference_and_drain_gates=True, retention_tests_passed=result.testsRun,
        retention_test_log=bind(target/'retention-tests.txt'), census=census, closed_prior_owners=owners,
        code=[bind(p) for p in (Path(__file__), HERE/'README_PANEL_RETRY_V1.md', N4/'native_complete_text.py', N4/'test_native_journal_retention.py')]))
    print(dict(status='BUILT_RETENTION_TESTED_NOT_APPLICATION_ACCEPTED', files=len(files), tests=result.testsRun))


if __name__ == '__main__':
    main()
