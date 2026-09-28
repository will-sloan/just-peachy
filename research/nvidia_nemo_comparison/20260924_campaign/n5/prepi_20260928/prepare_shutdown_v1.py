"""Prepare a fresh bounded-shutdown derivative. See README.md."""
import argparse
import difflib
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent/'n4'))
from common import bind, freeze, load, verify
from metric_process import pin


def patch(raw):
    text = raw.decode('utf-8').replace('\r\n', '\n')
    old = """        if any(t.is_alive() for t in owned_threads if t is not threading.current_thread()):
            raise RuntimeError('Previous session still has live workers; its owner cannot be released')
"""
    new = """        # Finalization failure can precede the native lane's return. Give
        # teardown its own bounded join; never change the failed inference gate.
        from .session_shutdown_v1 import join_owned_workers
        cleanup = join_owned_workers(owned_threads)
        self.metrics['last_worker_cleanup'] = cleanup
        if failures:
            self.metrics['last_terminal_failures'] = list(failures)
        if not cleanup['owned_threads_joined']:
            raise RuntimeError('Previous session still has live workers; its owner cannot be released: '
                               + ', '.join(cleanup['live_after']))
"""
    if text.count(old) != 1:
        raise ValueError('Expected exactly one original ownership check')
    text = text.replace(old, new)
    compile(text, 'app/controller.py', 'exec')
    return text.replace('\n', '\r\n' if b'\r\n' in raw else '\n').encode('utf-8')


def prepare(parent_receipt, output):
    pin()
    parent_binding = bind(parent_receipt)
    parent = load(parent_receipt)
    root = Path(parent.get('prototype') or parent_receipt.parent/'prototype').resolve()
    if output.exists():
        raise FileExistsError('Fresh immutable output required')
    payloads = {}
    for relative, row in parent['files'].items():
        path = (root/relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Source escapes parent')
        verify(dict(path=str(path), **row))
        payloads[relative] = path.read_bytes()
    original = payloads['app/controller.py']
    payloads['app/controller.py'] = patch(original)
    payloads['app/session_shutdown_v1.py'] = (HERE/'session_shutdown_v1.py').read_bytes()
    payloads['tests/test_late_shutdown_v1.py'] = (HERE/'test_late_shutdown_v1.py').read_bytes()
    payloads['README_PREPI_SHUTDOWN_V1.md'] = (HERE/'README.md').read_bytes()
    output.mkdir()
    files = {}
    for relative, raw in payloads.items():
        path = output/'prototype'/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)
        files[relative] = {k:v for k,v in bind(path).items() if k != 'path'}
    diff = ''.join(difflib.unified_diff(original.decode().splitlines(True),
        payloads['app/controller.py'].decode().splitlines(True),
        fromfile='parent/app/controller.py', tofile='derivative/app/controller.py'))
    (output/'CHANGES.patch').write_text(diff, encoding='utf-8')
    freeze(output/'DERIVATIVE.json', dict(schema='prepi-shutdown-derivative-v1',
        status='PREPARED_NOT_RELEASE_ACCEPTED', parent_source_receipt=parent_binding,
        prototype=str(output/'prototype'), files=files, builder=bind(__file__),
        window=bind(HERE/'WINDOW.json'), changed_code=['app/controller.py','app/session_shutdown_v1.py'],
        scope='Bounded owned-thread cleanup only; no model, audio, 60-second drain or inference acceptance change'))
    print(dict(status='PREPARED_NOT_RELEASE_ACCEPTED', output=str(output), files=len(files)))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-receipt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    prepare(args.parent_receipt, args.output)
