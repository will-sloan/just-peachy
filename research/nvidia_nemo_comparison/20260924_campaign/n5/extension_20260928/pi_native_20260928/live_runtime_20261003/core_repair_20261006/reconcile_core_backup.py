"""Host POSIX-path correction; see README_CORE_BACKUP.md."""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys


def main():
    import psutil
    me = psutil.Process()
    me.cpu_affinity([14])
    here = Path(__file__).resolve()
    private = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    early = private / 'audit-preparation' / ('core-backup-posix-' + str(me.pid))
    early.mkdir()
    def write(name, raw):
        with (early / name).open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Short receipt write')
            stream.flush(); os.fsync(stream.fileno())
        if (early / name).read_bytes() != raw:
            raise OSError('Receipt readback differs')
    write('REGISTERED_OWNER.json', json.dumps(dict(pid=me.pid, create_time=me.create_time(), affinity=[14])).encode())
    parent = here.parent.parent / 'reconcile_production_backup.py'
    raw = parent.read_bytes()
    if hashlib.sha256(raw).hexdigest() != 'b3cacd3948be2a4ffa367863e1ec80bf074e9f26069fb6d9d4d3ebdcca58ca08':
        raise ValueError('Pinned reconciler differs')
    for source in (here, here.with_name('README_CORE_BACKUP.md'), parent):
        value = source.read_bytes()
        write(source.name + '.backup', value)
        write(source.name + '.restore', value)
    text = raw.decode('utf-8')
    old = "common.validate_spec(self.census['scope'])"
    if text.count(old) != 1:
        raise ValueError('Expected one host native-scope validation')
    helper = '''
def validate_native_spec(common, spec):
    import inspect
    from pathlib import PurePosixPath
    tree = ast.parse(inspect.getsource(common.validate_spec))
    changed = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == 'Path':
            node.id = 'PurePosixPath'; changed += 1
    if changed != 2 or len(tree.body) != 1 or tree.body[0].name != 'validate_spec':
        raise ValueError('Exact native-path validator shape required')
    namespace = dict(common.__dict__, PurePosixPath=PurePosixPath)
    exec(compile(ast.fix_missing_locations(tree), '<native-posix-spec-validator>', 'exec'), namespace)
    return namespace['validate_spec'](spec)
'''
    text = text.replace(old, "validate_native_spec(common,self.census['scope'])")
    text = text.replace('def main():', helper + '\ndef main():', 1)
    write('DERIVATION.json', json.dumps(dict(parent_sha256=hashlib.sha256(raw).hexdigest(), correction='Two Path constructors in host-only pure scope validator become PurePosixPath; native bytes unchanged', native_deadline_extended=False)).encode())
    sys.path.insert(0, str(parent.parent))
    namespace = dict(__file__=str(parent), __name__='core_backup_runner', ast=ast)
    exec(compile(text, str(here), 'exec'), namespace)
    namespace['main']()


if __name__ == '__main__':
    main()
